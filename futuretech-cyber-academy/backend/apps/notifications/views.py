from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.contrib import messages
from .models import Notification, Announcement
from .services import NotificationService


class NotificationCenterView(LoginRequiredMixin, ListView):
    model = Notification
    template_name = 'notifications/notification_center.html'
    context_object_name = 'notifications'
    paginate_by = 25

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user).order_by('-created_at')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['unread_count'] = Notification.objects.filter(recipient=self.request.user, is_read=False).count()
        ctx['announcements'] = Announcement.objects.filter(is_published=True).order_by('-is_pinned', '-published_at')[:5]
        return ctx


class MarkNotificationReadView(LoginRequiredMixin, View):
    def post(self, request, pk):
        success = NotificationService.mark_as_read(pk, request.user)
        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'hx-request' in request.headers:
            return JsonResponse({'success': success})
        messages.success(request, "Notification marked as read.")
        return redirect('notifications:center')


class MarkAllNotificationsReadView(LoginRequiredMixin, View):
    def post(self, request):
        NotificationService.mark_all_as_read(request.user)
        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'hx-request' in request.headers:
            return JsonResponse({'success': True})
        messages.success(request, "All notifications marked as read.")
        return redirect('notifications:center')

