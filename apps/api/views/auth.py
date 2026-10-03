from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework.authtoken.models import Token

from apps.api.serializers.auth import (
    LoginRequestSerializer, RegisterRequestSerializer,
    TokenResponseSerializer, PushDeviceSerializer
)
from apps.api.throttling import AuthRateThrottle
from apps.users.models import PushDevice


class LoginAPIView(APIView):
    """
    POST /api/v1/auth/login/
    Universal login for Mobile (Android/iOS) and Web clients.
    Supports:
      - Permanent Account ID (MEL-00012345)
      - Verified Email address
      - Username
    """
    permission_classes = [permissions.AllowAny]
    throttle_classes = [AuthRateThrottle]

    def post(self, request):
        serializer = LoginRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']

        # Mobile push device registration if provided
        device_token = request.data.get('device_token')
        platform = serializer.validated_data.get('platform', PushDevice.Platform.ANDROID)
        device_name = serializer.validated_data.get('device_name', '')
        if device_token:
            PushDevice.objects.update_or_create(
                token=device_token,
                defaults={
                    'user': user,
                    'platform': platform,
                    'device_name': device_name,
                    'is_active': True,
                }
            )

        token, _ = Token.objects.get_or_create(user=user)
        payload = {
            'token': token.key,
            'account_id': user.account_id or '',
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'role': user.role,
            'roles': user.roles,
            'active_mode': user.active_mode,
            'is_associate': user.is_associate,
        }
        return Response({
            'message': 'Authentication successful.',
            'auth': TokenResponseSerializer(payload).data
        }, status=status.HTTP_200_OK)


class RegisterAPIView(APIView):
    """
    POST /api/v1/auth/register/
    Registers a new student account, assigning a permanent Myanmar E-Learning Account ID.
    """
    permission_classes = [permissions.AllowAny]
    throttle_classes = [AuthRateThrottle]

    def post(self, request):
        serializer = RegisterRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        token, _ = Token.objects.get_or_create(user=user)
        payload = {
            'token': token.key,
            'account_id': user.account_id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'role': user.role,
            'roles': user.roles,
            'active_mode': user.active_mode,
            'is_associate': user.is_associate,
        }
        return Response({
            'message': 'Account registered successfully.',
            'auth': TokenResponseSerializer(payload).data
        }, status=status.HTTP_201_CREATED)


class LogoutAPIView(APIView):
    """
    POST /api/v1/auth/logout/
    Revokes the current authentication token.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        return Response({'message': 'Successfully logged out.'}, status=status.HTTP_200_OK)


class PushDeviceRegisterAPIView(APIView):
    """
    POST /api/v1/auth/device/register/
    Registers or refreshes a native Android/iOS mobile push token.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = PushDeviceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        device, _ = PushDevice.objects.update_or_create(
            token=serializer.validated_data['token'],
            defaults={
                'user': request.user,
                'platform': serializer.validated_data['platform'],
                'device_name': serializer.validated_data.get('device_name', ''),
                'is_active': True,
            }
        )
        return Response({
            'message': 'Push device registered.',
            'device': PushDeviceSerializer(device).data
        }, status=status.HTTP_200_OK)
