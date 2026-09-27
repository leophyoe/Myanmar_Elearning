from django.utils import timezone
from decimal import Decimal
from apps.courses.models import Lesson
from apps.courses.models import Lesson, CourseModule, LessonType
from apps.enrollments.models import Enrollment, EnrollmentStatus
from .models import LessonProgress
from .models import LessonProgress, ModuleProgress


class ProgressCalculationService:
    """
    Recalculates module and overall course completion percentages.
    Updates the student's Enrollment record automatically.
    """

    @classmethod
    def update_module_progress(cls, student, module: CourseModule):
        """
        Calculates granular module progress according to institutional formula:
        Lessons: 30%, Quizzes: 15%, Assignments: 15%, Practical Activities: 25%, Module Exam: 15%.
        """
        # 1. Lessons progress
        published_lessons = Lesson.objects.filter(module=module, is_published=True)
        total_lessons = published_lessons.count()
        if total_lessons > 0:
            completed_lessons = LessonProgress.objects.filter(
                student=student,
                lesson__module=module,
                completed=True
            ).count()
            lesson_pct = Decimal((completed_lessons / total_lessons) * 100).quantize(Decimal('0.01'))
        else:
            lesson_pct = Decimal('100.00')

        # 2. Quizzes progress
        from apps.assessments.models import Quiz, QuizAttempt
        published_quizzes = Quiz.objects.filter(module=module, is_published=True)
        total_quizzes = published_quizzes.count()
        if total_quizzes > 0:
            passed_quizzes = 0
            for q in published_quizzes:
                if QuizAttempt.objects.filter(quiz=q, student=student, passed=True).exists():
                    passed_quizzes += 1
            quiz_pct = Decimal((passed_quizzes / total_quizzes) * 100).quantize(Decimal('0.01'))
        else:
            quiz_pct = Decimal('100.00')

        # 3. Assignments progress
        from apps.assessments.models import Assignment, AssignmentSubmission
        published_assignments = Assignment.objects.filter(module=module, status='PUBLISHED')
        total_assignments = published_assignments.count()
        if total_assignments > 0:
            done_assignments = 0
            for a in published_assignments:
                if AssignmentSubmission.objects.filter(assignment=a, student=student).exists():
                    done_assignments += 1
            assignment_pct = Decimal((done_assignments / total_assignments) * 100).quantize(Decimal('0.01'))
        else:
            assignment_pct = Decimal('100.00')

        # 4. Practical Activities progress (placeholder academic category for practical lessons)
        practical_lessons = published_lessons.filter(lesson_type=LessonType.PRACTICAL)
        total_practicals = practical_lessons.count()
        if total_practicals > 0:
            completed_practicals = LessonProgress.objects.filter(
                student=student,
                lesson__in=practical_lessons,
                completed=True
            ).count()
            practical_pct = Decimal((completed_practicals / total_practicals) * 100).quantize(Decimal('0.01'))
        else:
            practical_pct = Decimal('100.00')

        # 5. Module Exam progress
        from apps.assessments.models import Exam, ExamAttempt
        module_exams = Exam.objects.filter(module=module, is_published=True)
        total_exams = module_exams.count()
        if total_exams > 0:
            passed_exams = 0
            for e in module_exams:
                if ExamAttempt.objects.filter(exam=e, student=student, passed=True).exists():
                    passed_exams += 1
            exam_pct = Decimal((passed_exams / total_exams) * 100).quantize(Decimal('0.01'))
        else:
            exam_pct = Decimal('100.00')

        # Weighted composite overall module progress
        overall = (
            (lesson_pct * Decimal('0.30')) +
            (quiz_pct * Decimal('0.15')) +
            (assignment_pct * Decimal('0.15')) +
            (practical_pct * Decimal('0.25')) +
            (exam_pct * Decimal('0.15'))
        ).quantize(Decimal('0.01'))

        overall = min(Decimal('100.00'), max(Decimal('0.00'), overall))
        is_completed = (overall >= Decimal('100.00'))

        record, _ = ModuleProgress.objects.get_or_create(student=student, module=module)
        record.lesson_progress = lesson_pct
        record.quiz_progress = quiz_pct
        record.assignment_progress = assignment_pct
        record.practical_progress = practical_pct
        record.exam_progress = exam_pct
        record.overall_progress = overall
        record.is_completed = is_completed
        if is_completed and not record.completed_at:
            record.completed_at = timezone.now()
        record.save()

        return record

    @classmethod
    def update_course_progress(cls, student, course):
        # Update progress for all course modules
        for mod in course.modules.filter(is_published=True):
            cls.update_module_progress(student, mod)

        total_lessons = Lesson.objects.filter(module__course=course, is_published=True).count()
        if total_lessons == 0:
            return Decimal('0.00')

        completed_lessons = LessonProgress.objects.filter(
            student=student,
            lesson__module__course=course,
            completed=True
        ).count()

        percentage = Decimal((completed_lessons / total_lessons) * 100).quantize(Decimal('0.01'))

        # Update Enrollment record if present
        enrollment = Enrollment.objects.filter(student=student, course=course).first()
        if enrollment:
            enrollment.progress_percentage = min(percentage, Decimal('100.00'))
            if enrollment.progress_percentage >= Decimal('100.00'):
                enrollment.status = EnrollmentStatus.COMPLETED
                if not enrollment.completed_at:
                    enrollment.completed_at = timezone.now()
                # Trigger graduation check if all other requirements are fulfilled
                try:
                    from apps.courses.completion_service import CourseCompletionService
                    CourseCompletionService.check_and_complete_course(student, course)
                except Exception:
                    pass
            else:
                if enrollment.status == EnrollmentStatus.COMPLETED:
                    enrollment.status = EnrollmentStatus.ACTIVE
                    enrollment.completed_at = None
            enrollment.save(update_fields=['progress_percentage', 'status', 'completed_at', 'updated_at'])

        return percentage

    @classmethod
    def get_student_course_summary(cls, student, course):
        """
        Returns full institutional dashboard breakdown for the student.
        """
        modules = course.modules.filter(is_published=True).order_by('order')
        module_summaries = []
        completed_modules_count = 0
        current_module = None
        next_activity = None

        for mod in modules:
            mod_prog = ModuleProgress.objects.filter(student=student, module=mod).first()
            if not mod_prog:
                mod_prog = cls.update_module_progress(student, mod)

            if mod_prog.is_completed:
                completed_modules_count += 1
            elif not current_module:
                current_module = mod

            module_summaries.append({
                'module': mod,
                'progress': mod_prog,
                'is_completed': mod_prog.is_completed,
            })

        if not current_module and modules.exists():
            current_module = modules.last()

        # Find next uncompleted lesson
        if current_module:
            next_lesson = current_module.lessons.filter(
                is_published=True
            ).exclude(
                student_progress__student=student,
                student_progress__completed=True
            ).order_by('order').first()
            if next_lesson:
                next_activity = f"Complete \"{next_lesson.title}\""
            else:
                next_activity = f"Review coursework in {current_module.title}"

        enrollment = Enrollment.objects.filter(student=student, course=course).first()
        overall_pct = enrollment.progress_percentage if enrollment else Decimal('0.00')

        from apps.assessments.services import GradeCalculationService
        grades = GradeCalculationService.calculate_student_grade(student, course)

        from apps.certificates.services import CertificateEligibilityService
        eligibility = CertificateEligibilityService.evaluate_eligibility(student, course)

        return {
            'course': course,
            'enrollment': enrollment,
            'overall_percentage': overall_pct,
            'completed_modules_count': completed_modules_count,
            'total_modules_count': modules.count(),
            'current_module': current_module,
            'next_activity': next_activity,
            'module_summaries': module_summaries,
            'grades': grades,
            'eligibility': eligibility,
        }
