from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from apps.users.services import authenticate_universal
from apps.users.models import UserRole, ActiveMode, PushDevice

User = get_user_model()


class LoginRequestSerializer(serializers.Serializer):
    """
    Universal login serializer accepting:
    1. Permanent Myanmar E-Learning Account ID (e.g. MEL-00012345)
    2. Verified Email
    3. Username
    """
    identifier = serializers.CharField(
        required=True,
        help_text="Permanent MEL Account ID (MEL-XXXXXXXX), Email address, or Username."
    )
    password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'}
    )
    device_name = serializers.CharField(required=False, default='', allow_blank=True)
    platform = serializers.ChoiceField(
        choices=PushDevice.Platform.choices,
        required=False,
        default=PushDevice.Platform.ANDROID
    )

    def validate(self, attrs):
        identifier = attrs.get('identifier', '').strip()
        password = attrs.get('password', '')

        user = authenticate_universal(identifier=identifier, password=password)
        if not user:
            raise serializers.ValidationError("Invalid credentials. Please verify your Account ID, email or password.")
        if not user.is_active:
            raise serializers.ValidationError("This account has been deactivated. Please contact support.")

        attrs['user'] = user
        return attrs


class RegisterRequestSerializer(serializers.Serializer):
    """
    Registration serializer creating a standard Student account with
    an immutable Myanmar E-Learning Account ID (MEL-XXXXXXXX).
    """
    username = serializers.CharField(max_length=150, required=True)
    email = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})
    first_name = serializers.CharField(max_length=150, required=False, default='', allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, default='', allow_blank=True)
    phone_number = serializers.CharField(max_length=32, required=False, default='', allow_blank=True)

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("A user with that username already exists.")
        return value

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("An account with this email address already exists.")
        return value

    def validate_password(self, value):
        validate_password(value)
        return value

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User(
            username=validated_data['username'],
            email=validated_data['email'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            phone_number=validated_data.get('phone_number', ''),
            role=UserRole.STUDENT,
            active_mode=ActiveMode.STUDENT,
        )
        user.set_password(password)
        user.save()
        return user


class TokenResponseSerializer(serializers.Serializer):
    """
    Standard authentication payload for mobile and web clients.
    """
    token = serializers.CharField()
    account_id = serializers.CharField()
    username = serializers.CharField()
    email = serializers.EmailField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    role = serializers.CharField()
    roles = serializers.ListField(child=serializers.CharField())
    active_mode = serializers.CharField()
    is_associate = serializers.BooleanField()


class PushDeviceSerializer(serializers.ModelSerializer):
    """
    Mobile device registration serializer for push notifications.
    """
    class Meta:
        model = PushDevice
        fields = ['id', 'token', 'platform', 'device_name', 'is_active', 'created_at']
        read_only_fields = ['id', 'created_at']
