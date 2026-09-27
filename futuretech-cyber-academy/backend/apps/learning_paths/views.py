from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from apps.enrollments.models import Enrollment, EnrollmentStatus
from .models import LearningPath, StudentLearningPath


class LearningPathListView(ListView):
    model = LearningPath
    template_name = 'learning_paths/path_list.html'
    context_object_name = 'learning_paths'

    def get_queryset(self):
        return LearningPath.objects.filter(is_published=True).prefetch_related('path_courses__course')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if self.request.user.is_authenticated:
            user_paths = {
                slp.learning_path_id: slp
                for slp in StudentLearningPath.objects.filter(student=self.request.user)
            }
            # recalculate progress
            for slp in user_paths.values():
                slp.recalculate_progress()
            ctx['user_paths'] = user_paths
        return ctx


class LearningPathDetailView(DetailView):
    model = LearningPath
    template_name = 'learning_paths/path_detail.html'
    context_object_name = 'learning_path'
    slug_url_kwarg = 'slug'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        path = self.object
        ctx['path_courses'] = path.path_courses.select_related('course').order_by('order')

        if self.request.user.is_authenticated:
            student = self.request.user
            slp = StudentLearningPath.objects.filter(student=student, learning_path=path).first()
            if slp:
                slp.recalculate_progress()
            ctx['student_enrollment'] = slp

            # Get user's enrolled status in each course
            user_course_ids = set(
                Enrollment.objects.filter(student=student, is_active=True).values_list('course_id', flat=True)
            )
            ctx['enrolled_course_ids'] = user_course_ids
        return ctx


class EnrollLearningPathView(LoginRequiredMixin, View):
    def post(self, request, slug):
        learning_path = get_object_or_404(LearningPath, slug=slug, is_published=True)
        student = request.user

        slp, created = StudentLearningPath.objects.get_or_create(
            student=student,
            learning_path=learning_path
        )

        # Automatically enroll in the child courses if not already enrolled
        enrolled_count = 0
        for pc in learning_path.path_courses.all():
            course = pc.course
            enrollment, c_created = Enrollment.objects.get_or_create(
                student=student,
                course=course,
                defaults={'status': EnrollmentStatus.ACTIVE}
            )
            if c_created:
                enrolled_count += 1

        slp.recalculate_progress()

        from apps.notifications.services import NotificationService
        NotificationService.create_notification(
            recipient=student,
            title=f"Path Enrolled: {learning_path.title}",
            message=f"You have enrolled in the {learning_path.title} career roadmap.",
            notification_type="COURSE"
        )

        messages.success(request, f"Successfully enrolled in {learning_path.title}!")
        return redirect('learning_paths:path-detail', slug=slug)

