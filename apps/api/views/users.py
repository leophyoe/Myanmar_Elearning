from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions

from apps.api.serializers.users import (
    UserDetailSerializer, UserUpdateSerializer,
    ModeSwitchSerializer, PasswordChangeSerializer
)


class UserProfileAPIView(APIView):
    """
    GET /api/v1/users/me/
    PATCH /api/v1/users/me/
    Retrieves and updates authenticated user details, assigned roles, and student/teacher profile stats.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        serializer = UserDetailSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request):
        serializer = UserUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        user = serializer.update(request.user, serializer.validated_data)
        return Response({
            'message': 'Profile updated successfully.',
            'user': UserDetailSerializer(user).data
        }, status=status.HTTP_200_OK)


class ModeSwitchAPIView(APIView):
    """
    POST /api/v1/users/switch-mode/
    Switches active workspace context between Student Mode and Instructor Mode.
    Zero-trust validation ensures only users with instructor credentials can switch to Instructor Mode.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = ModeSwitchSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        new_mode = serializer.validated_data['mode']
        request.user.active_mode = new_mode
        request.user.save(update_fields=['active_mode'])

        return Response({
            'message': f'Switched to {request.user.get_active_mode_display()}.',
            'active_mode': request.user.active_mode,
            'roles': request.user.roles,
        }, status=status.HTTP_200_OK)


class PasswordChangeAPIView(APIView):
    """
    POST /api/v1/users/change-password/
    Updates user account password with secure verification of old password.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = PasswordChangeSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        new_password = serializer.validated_data['new_password']
        request.user.set_password(new_password)
        request.user.save()

        return Response({
            'message': 'Password changed successfully.'
        }, status=status.HTTP_200_OK)
