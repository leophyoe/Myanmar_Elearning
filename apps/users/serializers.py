from rest_framework import serializers
from .models import User, UserRole, StudentProfile, TeacherProfile
from .services import create_user_account, authenticate_universal


class UserPublicSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'id', 'account_id', 'username', 'email',
            'first_name', 'last_name', 'role', 'active_mode',
            'is_associate', 'created_at'
        ]
        read_only_fields = fields


class StudentProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentProfile
        fields = ['student_id', 'batch', 'points', 'rank', 'bio', 'github_url', 'linkedin_url']


class TeacherProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = TeacherProfile
        fields = ['department', 'title', 'qualifications', 'level', 'is_verified', 'total_live_hours']


class UserProfileSerializer(serializers.ModelSerializer):
    student_profile = StudentProfileSerializer(read_only=True)
    teacher_profile = TeacherProfileSerializer(read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'account_id', 'username', 'email',
            'first_name', 'last_name', 'role', 'active_mode',
            'is_associate', 'avatar', 'phone_number',
            'student_profile', 'teacher_profile', 'created_at'
        ]
        read_only_fields = ['id', 'account_id', 'created_at']


class UserRegistrationSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("A user with that username already exists.")
        return value

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("An account with this email address already exists.")
        return value

    def create(self, validated_data):
        return create_user_account(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            role=UserRole.STUDENT
        )


class UserLoginSerializer(serializers.Serializer):
    identifier = serializers.CharField(required=True, help_text="Account ID, Email, or Username")
    password = serializers.CharField(required=True, write_only=True)

    def validate(self, attrs):
        user = authenticate_universal(
            identifier=attrs.get('identifier'),
            password=attrs.get('password')
        )
        if not user:
            raise serializers.ValidationError("Invalid credentials provided.")
        attrs['user'] = user
        return attrs
