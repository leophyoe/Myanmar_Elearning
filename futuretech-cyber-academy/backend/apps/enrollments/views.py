from django.views.generic import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from .models import Enrollment, EnrollmentStatus
from apps.courses.models import Course

class EnrollCourseView(LoginRequiredMixin, View):
    def post(self, request, slug):
        course = get_object_or_404(Course, slug=slug, status='PUBLISHED')

        # Check existing enrollment
        enrollment, created = Enrollment.objects.get_or_create(
            student=request.user,
            course=course,
            defaults={'status': EnrollmentStatus.ACTIVE}
        )

        if not created and enrollment.status == EnrollmentStatus.ACTIVE:
            messages.info(request, f"You are already enrolled in '{course.title}'.")
        elif not created and enrollment.status != EnrollmentStatus.ACTIVE:
            enrollment.status = EnrollmentStatus.ACTIVE
            enrollment.save(update_fields=['status'])
            messages.success(request, f"Your enrollment in '{course.title}' has been reactivated.")
        else:
            messages.success(request, f"Successfully enrolled in '{course.title}'! Welcome to the class.")

        # Redirect to first lesson or course detail
        first_module = course.modules.filter(is_published=True).first()
        if first_module and first_module.lessons.filter(is_published=True).exists():
            first_lesson = first_module.lessons.filter(is_published=True).first()
            return redirect('lesson-learn', course_slug=course.slug, lesson_slug=first_lesson.slug)

        return redirect('course-detail', slug=course.slug)

