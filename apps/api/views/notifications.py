from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions

from apps.users.models import Notification
from apps.api.serializers.notifications import NotificationSerializer
from apps.api.pagination import StandardResultsSetPagination


class NotificationListAPIView(APIView):
    """
    GET /api/v1/notifications/
    Lists in-app academic and account notifications for the authenticated user.
    """
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get(self, request):
        qs = Notification.objects.filter(user=request.user).order_by('-created_at')
        is_read = request.query_params.get('is_read')
        if is_read in ('true', 'false'):
            qs = qs.filter(is_read=(is_read == 'true'))

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request)
        serializer = NotificationSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class NotificationUnreadCountAPIView(APIView):
    """
    GET /api/v1/notifications/unread-count/
    Returns integer count of unread notifications for mobile notification bell badge.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        count = Notification.objects.filter(user=request.user, is_read=False).count()
        return Response({'unread_count': count}, status=status.HTTP_200_OK)


class NotificationMarkReadAPIView(APIView):
    """
    POST /api/v1/notifications/<id>/mark-read/
    Marks a specific notification as read.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        notif = get_object_or_404(Notification, pk=pk, user=request.user)
        notif.mark_as_read()
        return Response({'message': 'Notification marked as read.'}, status=status.HTTP_200_OK)


class NotificationMarkAllReadAPIView(APIView):
    """
    POST /api/v1/notifications/mark-all-read/
    Marks all notifications for the current user as read.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        Notification.objects.filter(user=request.user, is_read=False).update(
            is_read=True,
            read_at=timezone.now()
        )
        return Response({'message': 'All notifications marked as read.'}, status=status.HTTP_200_OK)
