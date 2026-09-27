import logging
from decimal import Decimal
from django.utils import timezone
from apps.enrollments.models import Enrollment, EnrollmentStatus
from apps.progress.models import LessonProgress
from apps.courses.models import Lesson

logger = logging.getLogger(__name__)


class CourseCompletionService:
    """
    Evaluates professional course completion criteria:
    1. 100% lesson progress
    2. Passing score on all published course quizzes
    3. Passing/submission of all published course assignments
    4. Passing score on final/midterm examinations
    """

    @classmethod
    def check_and_complete_course(cls, student, course):
        """
        Evaluates completion requirements. Returns a dict:
        {'eligible': bool, 'completed': bool, 'details': dict}
        """
        # 1. Check lesson completion
        total_lessons = Lesson.objects.filter(module__course=course, is_published=True).count()
        completed_lessons = LessonProgress.objects.filter(
            student=student,
            lesson__module__course=course,
            completed=True
        ).count()

        lessons_done = (total_lessons == 0 or completed_lessons >= total_lessons)

        # 2. Check quiz completion
        from apps.assessments.models import Quiz, QuizAttempt
        course_quizzes = Quiz.objects.filter(course=course, is_published=True)
        quizzes_passed = True
        quiz_details = []
        for q in course_quizzes:
            passed = QuizAttempt.objects.filter(quiz=q, student=student, passed=True).exists()
            quiz_details.append({'quiz_id': str(q.id), 'title': q.title, 'passed': passed})
            if not passed:
                quizzes_passed = False

        # 3. Check assignment completion
        from apps.assessments.models import Assignment, AssignmentSubmission
        course_assignments = Assignment.objects.filter(course=course, status='PUBLISHED')
        assignments_done = True
        assignment_details = []
        for a in course_assignments:
            submitted = AssignmentSubmission.objects.filter(assignment=a, student=student).exists()
            assignment_details.append({'assignment_id': str(a.id), 'title': a.title, 'submitted': submitted})
            if not submitted:
                assignments_done = False

        # 4. Check final/midterm exam completion
        from apps.assessments.models import Exam, ExamAttempt
        course_exams = Exam.objects.filter(course=course, is_published=True)
        exams_passed = True
        exam_details = []
        for e in course_exams:
            passed = ExamAttempt.objects.filter(exam=e, student=student, passed=True).exists()
            exam_details.append({'exam_id': str(e.id), 'title': e.title, 'passed': passed})
            if not passed:
                exams_passed = False

        is_eligible = (lessons_done and quizzes_passed and assignments_done and exams_passed)
        # 5. Check final project if configured
        from apps.assessments.models import FinalProject, ProjectSubmission
        final_project = FinalProject.objects.filter(course=course, is_published=True, is_required=True).first()
        project_done = True
        project_details = None
        if final_project:
            proj_sub = ProjectSubmission.objects.filter(project=final_project, student=student).first()
            passed_project = proj_sub.passed if proj_sub else False
            project_details = {
                'project_id': str(final_project.id),
                'title': final_project.title,
                'submitted': proj_sub is not None,
                'passed': passed_project,
            }
            if not passed_project:
                project_done = False

        is_eligible = (lessons_done and quizzes_passed and assignments_done and exams_passed and project_done)

        details = {
            'total_lessons': total_lessons,
            'completed_lessons': completed_lessons,
            'lessons_done': lessons_done,
            'quizzes_passed': quizzes_passed,
            'quiz_details': quiz_details,
            'assignments_done': assignments_done,
            'assignment_details': assignment_details,
            'exams_passed': exams_passed,
            'exam_details': exam_details,
            'project_done': project_done,
            'project_details': project_details,
            'is_eligible': is_eligible,
        }

        if is_eligible:
            enrollment = Enrollment.objects.filter(student=student, course=course).first()
            if enrollment:
                enrollment.progress_percentage = Decimal('100.00')
                enrollment.status = EnrollmentStatus.COMPLETED
                if not enrollment.completed_at:
                    enrollment.completed_at = timezone.now()
                enrollment.save(update_fields=['progress_percentage', 'status', 'completed_at', 'updated_at'])

            # Log audit event
            from apps.core.audit import log_audit_event
            log_audit_event(
                user=student,
                action="COURSE_COMPLETED",
                object_type="Course",
                object_id=str(course.id),
                metadata={'course_title': course.title}
            )

            # Issue Certificate
            try:
                from apps.certificates.services import CertificateGenerationService
                CertificateGenerationService.issue_certificate(student=student, course=course)
            except Exception as ex:
                logger.error(f"Certificate generation error on course completion: {ex}")

            # Notify student
            try:
                from apps.notifications.services import NotificationService
                NotificationService.create_notification(
                    recipient=student,
                    title=f"🎓 Course Completed: {course.title}",
                    message=f"Congratulations! You have fulfilled all graduation requirements for {course.title}. Your certificate has been issued.",
                    notification_type="CERTIFICATE"
                )
            except Exception as ex:
                logger.error(f"Notification error on course completion: {ex}")

            # Evaluate achievements
            try:
                from apps.achievements.services import AchievementEvaluationService
                AchievementEvaluationService.evaluate_student(student, event="COURSE_COMPLETED", context={'course': course})
            except Exception as ex:
                logger.error(f"Achievement evaluation error on course completion: {ex}")

            return {'eligible': True, 'completed': True, 'details': details}

        return {'eligible': False, 'completed': False, 'details': details}

