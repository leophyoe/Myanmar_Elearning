from django.views.generic import TemplateView, View, FormView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.contrib import messages
from django.db.models import Avg, Count
from apps.core.permissions import StudentRequiredMixin, InstructorRequiredMixin, AdminRequiredMixin
from apps.courses.models import Course, CourseModule, Lesson, CourseResource, CourseStatus
from apps.enrollments.models import Enrollment, EnrollmentStatus
from apps.progress.models import LessonProgress
from apps.accounts.models import User
from .forms import CourseCreationForm, CourseModuleForm, LessonForm, CourseResourceForm

class StudentDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'dashboard/student_dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        enrollments = Enrollment.objects.filter(student=user).select_related('course')
        active_enrollments = enrollments.filter(status=EnrollmentStatus.ACTIVE)
        completed_enrollments = enrollments.filter(status=EnrollmentStatus.COMPLETED)

        # Calculate overall progress across all enrolled courses
        avg_progress = enrollments.aggregate(avg=Avg('progress_percentage'))['avg'] or 0
        overall_progress = int(avg_progress)

        completed_lessons = LessonProgress.objects.filter(
            student=user,
            completed=True
        ).select_related('lesson', 'lesson__module__course')[:5]

        completed_lessons_count = LessonProgress.objects.filter(student=user, completed=True).count()

        # Primary Continue Learning course
        continue_enrollment = active_enrollments.order_by('-updated_at').first()
        next_lesson = None
        continue_course_summary = None
        if continue_enrollment:
            # Find next incomplete lesson
            completed_ids = set(
                LessonProgress.objects.filter(
                    student=user,
                    lesson__module__course=continue_enrollment.course,
                    completed=True
                ).values_list('lesson_id', flat=True)
            )
            next_lesson = Lesson.objects.filter(
                module__course=continue_enrollment.course,
                is_published=True
            ).exclude(id__in=completed_ids).first()

            from apps.progress.services import ProgressCalculationService
            continue_course_summary = ProgressCalculationService.get_student_course_summary(
                user, continue_enrollment.course
            )

        # Phase 2 Advanced LMS data
        from apps.learning_paths.models import StudentLearningPath
        from apps.assessments.models import Assignment, AssignmentSubmission, QuizAttempt, Exam, ExamAttempt
        from apps.certificates.models import Certificate
        from apps.achievements.models import StudentAchievement
        from apps.notifications.models import Notification, Announcement

        enrolled_paths = StudentLearningPath.objects.filter(student=user).select_related('learning_path')
        for ep in enrolled_paths:
            ep.recalculate_progress()

        pending_assignments = Assignment.objects.filter(
            course__in=enrollments.values('course'),
            status='PUBLISHED'
        ).exclude(submissions__student=user)[:5]

        recent_quiz_attempts = QuizAttempt.objects.filter(
            student=user,
            is_completed=True
        ).select_related('quiz', 'quiz__course')[:5]

        certificates = Certificate.objects.filter(student=user, status='ISSUED').select_related('course')
        achievements = StudentAchievement.objects.filter(student=user).select_related('achievement')
        unread_notifications_count = Notification.objects.filter(recipient=user, is_read=False).count()
        announcements = Announcement.objects.filter(is_published=True).order_by('-is_pinned', '-published_at')[:4]

        context.update({
            'enrollments': enrollments,
            'active_enrollments': active_enrollments,
            'completed_enrollments': completed_enrollments,
            'courses_enrolled_count': enrollments.count(),
            'courses_completed_count': completed_enrollments.count(),
            'lessons_completed_count': completed_lessons_count,
            'overall_progress': overall_progress,
            'continue_enrollment': continue_enrollment,
            'continue_course_summary': continue_course_summary,
            'next_lesson': next_lesson,
            'recently_completed_lessons': completed_lessons,
            # Phase 2
            'enrolled_paths': enrolled_paths,
            'pending_assignments': pending_assignments,
            'recent_quiz_attempts': recent_quiz_attempts,
            'certificates': certificates,
            'achievements': achievements,
            'unread_notifications_count': unread_notifications_count,
            'announcements': announcements,
        })
        return context


class InstructorDashboardView(InstructorRequiredMixin, TemplateView):
    template_name = 'dashboard/instructor_dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        if user.is_superuser or user.is_academy_admin:
            courses = Course.objects.all().prefetch_related('modules', 'enrollments')
        else:
            courses = Course.objects.filter(created_by=user).prefetch_related('modules', 'enrollments')

        total_courses = courses.count()
        published_courses = courses.filter(status=CourseStatus.PUBLISHED).count()

        total_students_enrolled = Enrollment.objects.filter(course__in=courses).values('student').distinct().count()
        avg_completion = Enrollment.objects.filter(course__in=courses).aggregate(avg=Avg('progress_percentage'))['avg'] or 0

        # Phase 2: Grading Queue & Assessment Overview
        from apps.assessments.models import AssignmentSubmission, QuizAttempt, Exam
        pending_submissions = AssignmentSubmission.objects.filter(
            assignment__course__in=courses,
            status__in=['SUBMITTED', 'RESUBMITTED']
        ).select_related('assignment', 'student', 'assignment__course')

        recent_quiz_attempts = QuizAttempt.objects.filter(
            quiz__course__in=courses,
            is_completed=True
        ).select_related('student', 'quiz')[:8]

        total_exams = Exam.objects.filter(course__in=courses).count()

        context.update({
            'courses': courses,
            'total_courses': total_courses,
            'published_courses': published_courses,
            'total_students_enrolled': total_students_enrolled,
            'avg_completion': int(avg_completion),
            'pending_submissions_count': pending_submissions.count(),
            'pending_submissions': pending_submissions[:6],
            'recent_quiz_attempts': recent_quiz_attempts,
            'total_exams': total_exams,
        })
        return context



# ==============================================================================
# Instructor 6-Step Course Creation Workflow
# ==============================================================================

class CourseCreateStep1View(InstructorRequiredMixin, View):
    """Step 1: Course Basic Information."""
    template_name = 'dashboard/instructor/course_create_step1.html'

    def get(self, request):
        form = CourseCreationForm()
        return render(request, self.template_name, {'form': form, 'step': 1})

    def post(self, request):
        form = CourseCreationForm(request.POST, request.FILES)
        if form.is_valid():
            course = form.save(commit=False)
            course.created_by = request.user
            course.status = CourseStatus.DRAFT  # Remains DRAFT until Step 6
            course.save()
            form.save_m2m()
            messages.success(request, f"Step 1 Complete! Course '{course.title}' draft initiated.")
            return redirect('instructor-course-step2', slug=course.slug)
        return render(request, self.template_name, {'form': form, 'step': 1})


class CourseCreateStep2View(InstructorRequiredMixin, View):
    """Step 2: Add Curriculum Modules."""
    template_name = 'dashboard/instructor/course_create_step2.html'

    def get(self, request, slug):
        course = get_object_or_404(Course, slug=slug)
        self._check_owner(request.user, course)
        modules = course.modules.all()
        form = CourseModuleForm(initial={'order': modules.count() + 1})
        return render(request, self.template_name, {'course': course, 'modules': modules, 'form': form, 'step': 2})

    def post(self, request, slug):
        course = get_object_or_404(Course, slug=slug)
        self._check_owner(request.user, course)
        form = CourseModuleForm(request.POST)
        if form.is_valid():
            module = form.save(commit=False)
            module.course = course
            module.save()
            messages.success(request, f"Added module: {module.title}")
            return redirect('instructor-course-step2', slug=course.slug)
        modules = course.modules.all()
        return render(request, self.template_name, {'course': course, 'modules': modules, 'form': form, 'step': 2})

    def _check_owner(self, user, course):
        if not (user.is_superuser or user.is_academy_admin or course.created_by == user):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied("You are not authorized to edit this course.")


class CourseCreateStep3View(InstructorRequiredMixin, View):
    """Step 3: Add Lessons to Modules."""
    template_name = 'dashboard/instructor/course_create_step3.html'

    def get(self, request, slug):
        course = get_object_or_404(Course, slug=slug)
        modules = course.modules.all()
        form = LessonForm()
        selected_module_id = request.GET.get('module_id')
        selected_module = modules.filter(id=selected_module_id).first() if selected_module_id else modules.first()
        lessons = selected_module.lessons.all() if selected_module else []
        return render(request, self.template_name, {
            'course': course,
            'modules': modules,
            'selected_module': selected_module,
            'lessons': lessons,
            'form': form,
            'step': 3
        })

    def post(self, request, slug):
        course = get_object_or_404(Course, slug=slug)
        module_id = request.POST.get('module_id')
        module = get_object_or_404(CourseModule, id=module_id, course=course)
        form = LessonForm(request.POST)
        if form.is_valid():
            lesson = form.save(commit=False)
            lesson.module = module
            lesson.save()
            messages.success(request, f"Added lesson '{lesson.title}' to {module.title}.")
            return redirect(f"{reverse('instructor-course-step3', kwargs={'slug': course.slug})}?module_id={module.id}")
        modules = course.modules.all()
        return render(request, self.template_name, {
            'course': course,
            'modules': modules,
            'selected_module': module,
            'lessons': module.lessons.all(),
            'form': form,
            'step': 3
        })


class CourseCreateStep4View(InstructorRequiredMixin, View):
    """Step 4: Upload Course Resources."""
    template_name = 'dashboard/instructor/course_create_step4.html'

    def get(self, request, slug):
        course = get_object_or_404(Course, slug=slug)
        modules = course.modules.prefetch_related('lessons')
        form = CourseResourceForm()
        return render(request, self.template_name, {'course': course, 'modules': modules, 'form': form, 'step': 4})

    def post(self, request, slug):
        course = get_object_or_404(Course, slug=slug)
        lesson_id = request.POST.get('lesson_id')
        lesson = get_object_or_404(Lesson, id=lesson_id, module__course=course)
        form = CourseResourceForm(request.POST, request.FILES)
        if form.is_valid():
            res = form.save(commit=False)
            res.lesson = lesson
            res.save()
            messages.success(request, f"Uploaded resource: {res.title}")
            return redirect('instructor-course-step4', slug=course.slug)
        modules = course.modules.prefetch_related('lessons')
        return render(request, self.template_name, {'course': course, 'modules': modules, 'form': form, 'step': 4})


class CourseCreateStep5ReviewView(InstructorRequiredMixin, View):
    """Step 5: Review Course Curriculum."""
    template_name = 'dashboard/instructor/course_create_step5.html'

    def get(self, request, slug):
        course = get_object_or_404(Course, slug=slug)
        modules = course.modules.prefetch_related('lessons', 'lessons__resources')
        return render(request, self.template_name, {'course': course, 'modules': modules, 'step': 5})


class CoursePublishToggleView(InstructorRequiredMixin, View):
    """Step 6: Publish Course."""

    def post(self, request, slug):
        course = get_object_or_404(Course, slug=slug)
        # Check permissions
        if not (request.user.is_superuser or request.user.is_academy_admin or course.created_by == request.user):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied("Unauthorized to publish this course.")

        if course.status == CourseStatus.PUBLISHED:
            course.status = CourseStatus.DRAFT
            messages.info(request, f"Course '{course.title}' reverted to DRAFT status.")
        else:
            course.status = CourseStatus.PUBLISHED
            messages.success(request, f"Congratulations! Course '{course.title}' is now PUBLISHED and visible to students.")

        course.save(update_fields=['status', 'updated_at'])
        return redirect('instructor-dashboard')


class AcademyAdminDashboardView(AdminRequiredMixin, TemplateView):
    template_name = 'dashboard/admin_dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        total_students = User.objects.filter(role='STUDENT').count()
        total_instructors = User.objects.filter(role__in=['INSTRUCTOR', 'LAB_INSTRUCTOR', 'TEACHING_ASSISTANT']).count()
        total_courses = Course.objects.count()
        published_courses = Course.objects.filter(status=CourseStatus.PUBLISHED).count()
        total_enrollments = Enrollment.objects.count()

        avg_comp = Enrollment.objects.aggregate(avg=Avg('progress_percentage'))['avg'] or 0
        completion_rate = int(avg_comp)

        recent_users = User.objects.order_by('-date_joined')[:10]
        recent_enrollments = Enrollment.objects.order_by('-enrolled_at').select_related('student', 'course')[:10]

        # Phase 2 metrics
        from apps.assessments.models import QuizAttempt, ExamAttempt, AssignmentSubmission
        from apps.certificates.models import Certificate
        from apps.core.models import AuditLog

        total_quizzes_completed = QuizAttempt.objects.filter(is_completed=True).count()
        total_exams_completed = ExamAttempt.objects.filter(is_completed=True).count()
        total_submissions = AssignmentSubmission.objects.count()
        total_certificates = Certificate.objects.filter(status='ISSUED').count()
        recent_audits = AuditLog.objects.select_related('user').order_by('-created_at')[:8]

        context.update({
            'total_students': total_students,
            'total_instructors': total_instructors,
            'total_courses': total_courses,
            'published_courses': published_courses,
            'total_enrollments': total_enrollments,
            'completion_rate': completion_rate,
            'recent_users': recent_users,
            'recent_enrollments': recent_enrollments,
            # Phase 2
            'total_quizzes_completed': total_quizzes_completed,
            'total_exams_completed': total_exams_completed,
            'total_submissions': total_submissions,
            'total_certificates': total_certificates,
            'recent_audits': recent_audits,
        })
        return context


