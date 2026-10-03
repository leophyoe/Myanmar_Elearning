from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from apps.users.models import UserRole, ActiveMode, StudentProfile, TeacherProfile
from apps.billing.models import active_subscription_for

User = get_user_model()


class StudentProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentProfile
        fields = ['student_id', 'batch', 'points', 'rank', 'bio', 'github_url', 'linkedin_url']


class TeacherProfileSerializer(serializers.ModelSerializer):
    level_display = serializers.CharField(source='get_level_display', read_only=True)

    class Meta:
        model = TeacherProfile
        fields = [
            'department', 'title', 'qualifications', 'is_verified', 'level',
            'level_display', 'total_live_hours', 'total_recorded_hours',
            'bio', 'website', 'github_url', 'linkedin_url',
            'recorded_revenue_share_pct', 'live_revenue_share_pct'
        ]


class UserDetailSerializer(serializers.ModelSerializer):
    roles = serializers.SerializerMethodField()
    membership = serializers.SerializerMethodField()
    student_profile = serializers.SerializerMethodField()
    teacher_profile = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'account_id', 'username', 'email', 'first_name', 'last_name',
            'phone_number', 'avatar', 'role', 'roles', 'active_mode',
            'is_associate', 'associate_awarded_at', 'membership',
            'student_profile', 'teacher_profile', 'created_at',
        ]
        read_only_fields = ['id', 'account_id', 'role', 'roles', 'is_associate', 'associate_awarded_at', 'created_at']

    def get_roles(self, obj):
        return obj.roles

    def get_membership(self, obj):
        sub = active_subscription_for(obj)
        if sub and sub.is_current:
            return {
                'plan_type': sub.plan.plan_type,
                'plan_name': sub.plan.name,
                'billing_cycle': sub.billing_cycle,
                'end_date': sub.end_date,
                'is_current': sub.is_current,
            }
        return {
            'plan_type': 'starter',
            'plan_name': 'Starter',
            'billing_cycle': 'lifetime',
            'end_date': None,
            'is_current': True,
        }

    def get_student_profile(self, obj):
        if hasattr(obj, 'student_profile'):
            return StudentProfileSerializer(obj.student_profile).data
        return None

    def get_teacher_profile(self, obj):
        if hasattr(obj, 'teacher_profile'):
            return TeacherProfileSerializer(obj.teacher_profile).data
        return None


class UserUpdateSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    phone_number = serializers.CharField(max_length=32, required=False, allow_blank=True)
    bio = serializers.CharField(required=False, allow_blank=True)
    github_url = serializers.URLField(required=False, allow_blank=True)
    linkedin_url = serializers.URLField(required=False, allow_blank=True)

    def update(self, instance, validated_data):
        if 'first_name' in validated_data:
            instance.first_name = validated_data['first_name']
        if 'last_name' in validated_data:
            instance.last_name = validated_data['last_name']
        if 'phone_number' in validated_data:
            instance.phone_number = validated_data['phone_number']
        instance.save()

        # Update student or teacher profile bio / social links
        if hasattr(instance, 'student_profile'):
            sp = instance.student_profile
            if 'bio' in validated_data:
                sp.bio = validated_data['bio']
            if 'github_url' in validated_data:
                sp.github_url = validated_data['github_url']
            if 'linkedin_url' in validated_data:
                sp.linkedin_url = validated_data['linkedin_url']
            sp.save()

        if hasattr(instance, 'teacher_profile'):
            tp = instance.teacher_profile
            if 'bio' in validated_data and not getattr(instance, 'student_profile', None):
                tp.bio = validated_data['bio']
            if 'github_url' in validated_data:
                tp.github_url = validated_data['github_url']
            if 'linkedin_url' in validated_data:
                tp.linkedin_url = validated_data['linkedin_url']
            tp.save()

        return instance


class ModeSwitchSerializer(serializers.Serializer):
    """
    Validates dual-mode switching between Student Mode and Instructor Mode.
    Server-side checks ensure user possesses instructor credentials before allowing Instructor Mode.
    """
    mode = serializers.ChoiceField(choices=[
        (ActiveMode.STUDENT, 'Student Mode'),
        (ActiveMode.INSTRUCTOR, 'Instructor Mode'),
    ])

    def validate_mode(self, value):
        user = self.context['request'].user
        if value == ActiveMode.INSTRUCTOR and not user.is_teacher:
            raise serializers.ValidationError(
                "You do not possess approved instructor credentials to switch into Instructor Mode."
            )
        return value


class PasswordChangeSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(required=True, write_only=True)

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value

    def validate_new_password(self, value):
        validate_password(value)
        return value
