try:
    from rest_framework import serializers
    from apps.accounts.models import User, StudentProfile, InstructorProfile
    from apps.courses.models import Course, CourseModule, Lesson, CourseCategory, CourseResource
    from apps.enrollments.models import Enrollment
    from apps.progress.models import LessonProgress
    from apps.progress.models import LessonProgress, ModuleProgress

    class UserSerializer(serializers.ModelSerializer):
        class Meta:
            model = User
            fields = ('id', 'email', 'username', 'first_name', 'last_name', 'phone', 'role', 'is_active', 'date_joined')
            read_only_fields = ('id', 'role', 'date_joined')


    class CourseCategorySerializer(serializers.ModelSerializer):
        class Meta:
            model = CourseCategory
            fields = ('id', 'name', 'slug', 'description', 'icon')


    class CourseResourceSerializer(serializers.ModelSerializer):
        class Meta:
            model = CourseResource
            fields = ('id', 'title', 'file', 'resource_type', 'description', 'external_link')


    class LessonSerializer(serializers.ModelSerializer):
        resources = CourseResourceSerializer(many=True, read_only=True)

        class Meta:
            model = Lesson
            fields = ('id', 'module', 'title', 'slug', 'lesson_type', 'content', 'video_url', 'order', 'estimated_minutes', 'is_published', 'resources')


    class CourseModuleSerializer(serializers.ModelSerializer):
        lessons = LessonSerializer(many=True, read_only=True)

        class Meta:
            model = CourseModule
            fields = ('id', 'course', 'title', 'slug', 'description', 'order', 'learning_objectives', 'estimated_hours', 'is_published', 'lessons')


    class CourseSerializer(serializers.ModelSerializer):
        categories = CourseCategorySerializer(many=True, read_only=True)
        created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
        total_lessons = serializers.IntegerField(source='total_lessons_count', read_only=True)

        class Meta:
            model = Course
            fields = ('id', 'title', 'slug', 'short_description', 'description', 'thumbnail', 'level', 'duration', 'language', 'price', 'is_free', 'status', 'categories', 'created_by_name', 'total_lessons', 'created_at')


    class EnrollmentSerializer(serializers.ModelSerializer):
        course_title = serializers.CharField(source='course.title', read_only=True)
        student_email = serializers.CharField(source='student.email', read_only=True)

        class Meta:
            model = Enrollment
            fields = ('id', 'student', 'student_email', 'course', 'course_title', 'enrolled_at', 'completed_at', 'status', 'progress_percentage')
            read_only_fields = ('id', 'enrolled_at', 'completed_at', 'progress_percentage')


    class LessonProgressSerializer(serializers.ModelSerializer):
        lesson_title = serializers.CharField(source='lesson.title', read_only=True)

        class Meta:
            model = LessonProgress
            fields = ('id', 'student', 'lesson', 'lesson_title', 'started_at', 'completed_at', 'completed', 'time_spent_seconds')
            read_only_fields = ('id', 'started_at', 'completed_at')


    class ModuleProgressSerializer(serializers.ModelSerializer):
        module_title = serializers.CharField(source='module.title', read_only=True)

        class Meta:
            model = ModuleProgress
            fields = (
                'id', 'student', 'module', 'module_title',
                'lesson_progress', 'quiz_progress', 'assignment_progress',
                'practical_progress', 'exam_progress', 'overall_progress',
                'is_completed', 'completed_at', 'created_at', 'updated_at'
            )


    # ==========================================================================
    # Phase 2 Serializers
    # ==========================================================================
    from apps.assessments.models import (
        Quiz, Question, QuestionOption, QuizAttempt,
        Assignment, AssignmentSubmission, AssignmentFeedback,
        Exam, ExamAttempt
    )
    from apps.learning_paths.models import LearningPath, StudentLearningPath
    from apps.certificates.models import Certificate
    from apps.achievements.models import Achievement, StudentAchievement
    from apps.notifications.models import Notification, Announcement
    from apps.courses.models import CourseReview

    class QuestionOptionSerializer(serializers.ModelSerializer):
        class Meta:
            model = QuestionOption
            fields = ('id', 'option_text', 'order')

    class QuestionSerializer(serializers.ModelSerializer):
        options = QuestionOptionSerializer(many=True, read_only=True)

        class Meta:
            model = Question
            fields = ('id', 'question_text', 'question_type', 'points', 'order', 'options')

    class QuizSerializer(serializers.ModelSerializer):
        questions = QuestionSerializer(many=True, read_only=True)
        course_title = serializers.CharField(source='course.title', read_only=True)

        class Meta:
            model = Quiz
            fields = ('id', 'course', 'course_title', 'title', 'description', 'time_limit_minutes', 'passing_score', 'max_attempts', 'questions')

    class QuizAttemptSerializer(serializers.ModelSerializer):
        quiz_title = serializers.CharField(source='quiz.title', read_only=True)

        class Meta:
            model = QuizAttempt
            fields = ('id', 'student', 'quiz', 'quiz_title', 'attempt_number', 'score', 'percentage', 'passed', 'is_completed', 'started_at', 'submitted_at')
            read_only_fields = ('id', 'attempt_number', 'score', 'percentage', 'passed', 'is_completed', 'started_at', 'submitted_at')

    class AssignmentSerializer(serializers.ModelSerializer):
        course_title = serializers.CharField(source='course.title', read_only=True)

        class Meta:
            model = Assignment
            fields = ('id', 'course', 'course_title', 'title', 'description', 'instructions', 'due_date', 'max_score', 'status')

    class AssignmentFeedbackSerializer(serializers.ModelSerializer):
        instructor_name = serializers.CharField(source='instructor.get_full_name', read_only=True)

        class Meta:
            model = AssignmentFeedback
            fields = ('id', 'instructor_name', 'score', 'feedback', 'graded_at')

    class AssignmentSubmissionSerializer(serializers.ModelSerializer):
        student_name = serializers.CharField(source='student.get_full_name', read_only=True)
        feedbacks = AssignmentFeedbackSerializer(many=True, read_only=True)

        class Meta:
            model = AssignmentSubmission
            fields = ('id', 'assignment', 'student', 'student_name', 'submitted_file', 'submission_text', 'status', 'submitted_at', 'version', 'feedbacks')
            read_only_fields = ('id', 'status', 'submitted_at', 'version')

    class ExamSerializer(serializers.ModelSerializer):
        course_title = serializers.CharField(source='course.title', read_only=True)

        class Meta:
            model = Exam
            fields = ('id', 'course', 'course_title', 'title', 'description', 'exam_type', 'duration_minutes', 'passing_score')

    class ExamAttemptSerializer(serializers.ModelSerializer):
        exam_title = serializers.CharField(source='exam.title', read_only=True)

        class Meta:
            model = ExamAttempt
            fields = ('id', 'student', 'exam', 'exam_title', 'attempt_number', 'score', 'percentage', 'passed', 'expires_at', 'is_completed')
            read_only_fields = ('id', 'attempt_number', 'score', 'percentage', 'passed', 'expires_at', 'is_completed')

    class LearningPathSerializer(serializers.ModelSerializer):
        total_courses = serializers.IntegerField(read_only=True)

        class Meta:
            model = LearningPath
            fields = ('id', 'title', 'slug', 'description', 'icon', 'estimated_months', 'level', 'total_courses')

    class StudentLearningPathSerializer(serializers.ModelSerializer):
        path_title = serializers.CharField(source='learning_path.title', read_only=True)

        class Meta:
            model = StudentLearningPath
            fields = ('id', 'student', 'learning_path', 'path_title', 'enrolled_at', 'progress_percentage', 'status')

    class CertificateSerializer(serializers.ModelSerializer):
        course_title = serializers.CharField(source='course.title', read_only=True)
        student_name = serializers.CharField(source='student.get_full_name', read_only=True)

        class Meta:
            model = Certificate
            fields = ('id', 'certificate_number', 'student_name', 'course_title', 'issued_date', 'status', 'verification_token')

    class AchievementSerializer(serializers.ModelSerializer):
        class Meta:
            model = Achievement
            fields = ('id', 'code', 'title', 'description', 'icon', 'badge_type', 'points')

    class NotificationSerializer(serializers.ModelSerializer):
        class Meta:
            model = Notification
            fields = ('id', 'title', 'message', 'notification_type', 'link', 'is_read', 'created_at')

    class AnnouncementSerializer(serializers.ModelSerializer):
        created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)

        class Meta:
            model = Announcement
            fields = ('id', 'title', 'content', 'created_by_name', 'published_at', 'is_pinned')

    class CourseReviewSerializer(serializers.ModelSerializer):
        student_name = serializers.CharField(source='student.get_full_name', read_only=True)

        class Meta:
            model = CourseReview
            fields = ('id', 'course', 'student', 'student_name', 'rating', 'comment', 'created_at')
            read_only_fields = ('id', 'student', 'created_at')

except ImportError:
    pass


