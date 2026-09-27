import json
from django.http import JsonResponse, HttpResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.shortcuts import get_object_or_404
from apps.accounts.models import User
from apps.courses.models import Course, CourseModule, Lesson
from apps.enrollments.models import Enrollment
from apps.progress.models import LessonProgress


class PlatformStatsAPIView(View):
    def get(self, request):
        return JsonResponse({
            'platform': 'Future Tech Cyber Security Academy',
            'phase': 'Phase 1: E-Learning Foundation',
            'total_students': User.objects.filter(role='STUDENT').count(),
            'published_courses': Course.objects.filter(status='PUBLISHED').count(),
            'total_lessons': Lesson.objects.filter(is_published=True).count(),
        })


class CourseListJsonView(View):
    def get(self, request):
        courses = Course.objects.filter(status='PUBLISHED')
        results = [
            {
                'id': str(c.id),
                'title': c.title,
                'slug': c.slug,
                'short_description': c.short_description,
                'level': c.level,
                'duration': c.duration,
                'is_free': c.is_free,
                'price': str(c.price),
                'total_lessons': c.total_lessons_count,
            }
            for c in courses
        ]
        return JsonResponse({'count': len(results), 'results': results})


class CourseDetailJsonView(View):
    def get(self, request, slug):
        c = get_object_or_404(Course, slug=slug, status='PUBLISHED')
        return JsonResponse({
            'id': str(c.id),
            'title': c.title,
            'slug': c.slug,
            'short_description': c.short_description,
            'description': c.description,
            'level': c.level,
            'duration': c.duration,
            'is_free': c.is_free,
            'price': str(c.price),
            'total_lessons': c.total_lessons_count,
            'modules': [
                {
                    'id': str(m.id),
                    'title': m.title,
                    'order': m.order,
                    'lessons_count': m.lessons.count()
                }
                for m in c.modules.filter(is_published=True)
            ]
        })


class EnrollmentListJsonView(View):
    def get(self, request):
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'Authentication required'}, status=401)
        enrollments = Enrollment.objects.filter(student=request.user)
        results = [
            {
                'id': str(e.id),
                'course_title': e.course.title,
                'course_slug': e.course.slug,
                'status': e.status,
                'progress_percentage': float(e.progress_percentage),
                'enrolled_at': e.enrolled_at.isoformat(),
            }
            for e in enrollments
        ]
        return JsonResponse({'count': len(results), 'results': results})


def get_course_by_lookup(lookup, published_only=False):
    import uuid
    qs = Course.objects.all()
    if published_only:
        qs = qs.filter(status='PUBLISHED')
    try:
        val = uuid.UUID(str(lookup))
        c = qs.filter(id=val).first()
        if c:
            return c
    except (ValueError, TypeError):
        pass
    return get_object_or_404(qs, slug=lookup)


def get_module_by_lookup(lookup):
    import uuid
    try:
        val = uuid.UUID(str(lookup))
        m = CourseModule.objects.filter(id=val).first()
        if m:
            return m
    except (ValueError, TypeError):
        pass
    return get_object_or_404(CourseModule, pk=lookup)


class CourseModulesJsonView(View):
    def get(self, request, lookup):
        course = get_course_by_lookup(lookup)
        modules = course.modules.filter(is_published=True).order_by('order')
        results = [
            {
                'id': str(m.id),
                'course': str(course.id),
                'title': m.title,
                'slug': m.slug,
                'description': m.description,
                'order': m.order,
                'learning_objectives': m.learning_objectives,
                'estimated_hours': m.estimated_hours,
                'is_published': m.is_published,
                'lessons': [
                    {
                        'id': str(l.id),
                        'title': l.title,
                        'slug': l.slug,
                        'lesson_type': l.lesson_type,
                        'order': l.order,
                    }
                    for l in m.lessons.filter(is_published=True).order_by('order')
                ]
            }
            for m in modules
        ]
        return JsonResponse(results, safe=False)


class ModuleLessonsJsonView(View):
    def get(self, request, pk):
        module = get_module_by_lookup(pk)
        lessons = module.lessons.filter(is_published=True).order_by('order')
        results = [
            {
                'id': str(l.id),
                'module': str(module.id),
                'title': l.title,
                'slug': l.slug,
                'lesson_type': l.lesson_type,
                'content': l.content,
                'video_url': l.video_url,
                'order': l.order,
                'estimated_minutes': l.estimated_minutes,
                'is_published': l.is_published,
            }
            for l in lessons
        ]
        return JsonResponse(results, safe=False)


@method_decorator(csrf_exempt, name='dispatch')
class LessonStartJsonView(View):
    def post(self, request, pk):
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'Authentication required'}, status=401)
        lesson = get_object_or_404(Lesson, pk=pk)
        progress, _ = LessonProgress.objects.get_or_create(
            student=request.user,
            lesson=lesson,
        )
        progress.mark_started()
        return JsonResponse({
            'status': 'started',
            'progress': {
                'id': str(progress.id),
                'lesson_id': str(lesson.id),
                'lesson_title': lesson.title,
                'started_at': progress.started_at.isoformat() if progress.started_at else None,
                'completed': progress.completed,
            }
        }, status=200)


@method_decorator(csrf_exempt, name='dispatch')
class LessonCompleteJsonView(View):
    def post(self, request, pk):
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'Authentication required'}, status=401)
        lesson = get_object_or_404(Lesson, pk=pk)
        progress, _ = LessonProgress.objects.get_or_create(
            student=request.user,
            lesson=lesson,
        )
        progress.mark_completed()
        from apps.progress.services import ProgressCalculationService
        if lesson.module:
            ProgressCalculationService.update_module_progress(request.user, lesson.module)
        return JsonResponse({
            'status': 'completed',
            'progress': {
                'id': str(progress.id),
                'lesson_id': str(lesson.id),
                'lesson_title': lesson.title,
                'completed': progress.completed,
                'completed_at': progress.completed_at.isoformat() if progress.completed_at else None,
            }
        }, status=200)


@method_decorator(csrf_exempt, name='dispatch')
class QuizStartJsonView(View):
    def post(self, request, pk):
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'Authentication required'}, status=401)
        from apps.assessments.models import Quiz, QuizAttempt
        quiz = get_object_or_404(Quiz, pk=pk, is_published=True)
        from apps.assessments.services import QuizGradingService
        can_attempt, remaining = QuizGradingService.can_attempt(quiz, request.user)
        if not can_attempt:
            return JsonResponse({'error': 'Maximum quiz attempts reached'}, status=400)
        attempt_num = QuizAttempt.objects.filter(student=request.user, quiz=quiz).count() + 1
        attempt = QuizAttempt.objects.create(
            student=request.user,
            quiz=quiz,
            attempt_number=attempt_num,
        )
        return JsonResponse({
            'id': str(attempt.id),
            'quiz': str(quiz.id),
            'quiz_title': quiz.title,
            'attempt_number': attempt.attempt_number,
            'started_at': attempt.started_at.isoformat(),
            'is_completed': attempt.is_completed,
        }, status=201)


@method_decorator(csrf_exempt, name='dispatch')
class QuizSubmitJsonView(View):
    def post(self, request, pk):
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'Authentication required'}, status=401)
        from apps.assessments.models import Quiz, QuizAttempt
        quiz = get_object_or_404(Quiz, pk=pk, is_published=True)
        try:
            body = json.loads(request.body.decode('utf-8')) if request.body else {}
        except Exception:
            body = {}
        attempt_id = body.get('attempt_id') or request.POST.get('attempt_id')
        answers = body.get('answers', {})
        if not attempt_id:
            attempt = QuizAttempt.objects.filter(student=request.user, quiz=quiz, is_completed=False).order_by('-started_at').first()
        else:
            attempt = get_object_or_404(QuizAttempt, id=attempt_id, student=request.user, quiz=quiz)
        if not attempt or attempt.is_completed:
            return JsonResponse({'error': 'No active quiz attempt found to submit'}, status=400)

        from apps.assessments.services import QuizGradingService
        graded = QuizGradingService.grade_attempt(attempt, answers)
        if quiz.module:
            from apps.progress.services import ProgressCalculationService
            ProgressCalculationService.update_module_progress(request.user, quiz.module)
        return JsonResponse({
            'id': str(graded.id),
            'quiz': str(quiz.id),
            'score': float(graded.score),
            'percentage': float(graded.percentage),
            'passed': graded.passed,
            'is_completed': graded.is_completed,
            'submitted_at': graded.submitted_at.isoformat() if graded.submitted_at else None,
        })


@method_decorator(csrf_exempt, name='dispatch')
class AssignmentSubmitJsonView(View):
    def post(self, request, pk):
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'Authentication required'}, status=401)
        from apps.assessments.models import Assignment, AssignmentSubmission
        assignment = get_object_or_404(Assignment, pk=pk, status='PUBLISHED')
        submission_text = request.POST.get('submission_text', '')
        submitted_file = request.FILES.get('submitted_file')
        if not submission_text and request.body:
            try:
                body = json.loads(request.body.decode('utf-8'))
                submission_text = body.get('submission_text', '')
            except Exception:
                pass
        existing_sub = AssignmentSubmission.objects.filter(student=request.user, assignment=assignment).order_by('-version').first()
        version = (existing_sub.version + 1) if existing_sub else 1
        sub = AssignmentSubmission.objects.create(
            assignment=assignment,
            student=request.user,
            submission_text=submission_text,
            submitted_file=submitted_file,
            version=version,
            status='SUBMITTED'
        )
        if assignment.module:
            from apps.progress.services import ProgressCalculationService
            ProgressCalculationService.update_module_progress(request.user, assignment.module)
        return JsonResponse({
            'id': str(sub.id),
            'assignment': str(assignment.id),
            'student_name': request.user.get_full_name(),
            'submission_text': sub.submission_text,
            'version': sub.version,
            'status': sub.status,
            'submitted_at': sub.submitted_at.isoformat(),
        }, status=201)


@method_decorator(csrf_exempt, name='dispatch')
class ExamStartJsonView(View):
    def post(self, request, pk):
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'Authentication required'}, status=401)
        from apps.assessments.models import Exam
        exam = get_object_or_404(Exam, pk=pk, is_published=True)
        from apps.assessments.services import ExamTimerService
        attempt = ExamTimerService.start_attempt(request.user, exam)
        return JsonResponse({
            'id': str(attempt.id),
            'exam': str(exam.id),
            'exam_title': exam.title,
            'attempt_number': attempt.attempt_number,
            'started_at': attempt.started_at.isoformat(),
            'expires_at': attempt.expires_at.isoformat() if attempt.expires_at else None,
            'is_completed': attempt.is_completed,
        }, status=201)


@method_decorator(csrf_exempt, name='dispatch')
class ExamSubmitJsonView(View):
    def post(self, request, pk):
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'Authentication required'}, status=401)
        from apps.assessments.models import Exam, ExamAttempt
        exam = get_object_or_404(Exam, pk=pk, is_published=True)
        try:
            body = json.loads(request.body.decode('utf-8')) if request.body else {}
        except Exception:
            body = {}
        attempt_id = body.get('attempt_id') or request.POST.get('attempt_id')
        answers = body.get('answers', {})
        if not attempt_id:
            attempt = ExamAttempt.objects.filter(student=request.user, exam=exam, is_completed=False).order_by('-started_at').first()
        else:
            attempt = get_object_or_404(ExamAttempt, id=attempt_id, student=request.user, exam=exam)
        if not attempt or attempt.is_completed:
            return JsonResponse({'error': 'No active exam attempt found'}, status=400)

        from apps.assessments.services import ExamTimerService
        if ExamTimerService.check_expired(attempt):
            return JsonResponse({'error': 'Exam time has expired'}, status=400)

        total_score = 0
        questions = exam.questions.all()
        max_score = sum(q.points for q in questions) or 1
        for q in questions:
            selected_opt_id = answers.get(str(q.id))
            if selected_opt_id:
                opt = q.options.filter(id=selected_opt_id).first()
                if opt and opt.is_correct:
                    total_score += q.points

        from decimal import Decimal
        attempt.score = Decimal(str(total_score))
        attempt.percentage = Decimal(str((total_score / max_score) * 100)).quantize(Decimal('0.01'))
        attempt.passed = attempt.percentage >= exam.passing_score
        attempt.is_completed = True
        attempt.save()

        if exam.module:
            from apps.progress.services import ProgressCalculationService
            ProgressCalculationService.update_module_progress(request.user, exam.module)

        return JsonResponse({
            'id': str(attempt.id),
            'exam': str(exam.id),
            'score': float(attempt.score),
            'percentage': float(attempt.percentage),
            'passed': attempt.passed,
            'is_completed': attempt.is_completed,
        })


class StudentCoursesJsonView(View):
    def get(self, request):
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'Authentication required'}, status=401)
        enrollments = Enrollment.objects.filter(student=request.user).select_related('course')
        results = [
            {
                'enrollment_id': str(e.id),
                'course_id': str(e.course.id),
                'course_title': e.course.title,
                'course_slug': e.course.slug,
                'course_type': e.course.course_type,
                'progress_percentage': float(e.progress_percentage),
                'status': e.status,
                'enrolled_at': e.enrolled_at.isoformat() if e.enrolled_at else None,
                'completed_at': e.completed_at.isoformat() if e.completed_at else None,
            }
            for e in enrollments
        ]
        return JsonResponse({'count': len(results), 'results': results})


class StudentProgressJsonView(View):
    def get(self, request):
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'Authentication required'}, status=401)
        enrollments = Enrollment.objects.filter(student=request.user)
        total_enrolled = enrollments.count()
        completed_count = enrollments.filter(status='COMPLETED').count()
        total_lessons_completed = LessonProgress.objects.filter(student=request.user, completed=True).count()
        from apps.assessments.models import QuizAttempt
        total_quizzes_passed = QuizAttempt.objects.filter(student=request.user, passed=True).values('quiz').distinct().count()
        return JsonResponse({
            'total_enrolled_courses': total_enrolled,
            'completed_courses': completed_count,
            'total_lessons_completed': total_lessons_completed,
            'total_quizzes_passed': total_quizzes_passed,
        })


class StudentCourseProgressJsonView(View):
    def get(self, request, lookup):
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'Authentication required'}, status=401)
        course = get_course_by_lookup(lookup)
        from apps.progress.services import ProgressCalculationService
        summary = ProgressCalculationService.get_student_course_summary(request.user, course)
        modules_data = []
        for m in summary['module_summaries']:
            p = m['progress']
            modules_data.append({
                'module_id': str(m['module'].id),
                'module_title': m['module'].title,
                'order': m['module'].order,
                'overall_progress': float(p.overall_progress),
                'lesson_progress': float(p.lesson_progress),
                'quiz_progress': float(p.quiz_progress),
                'assignment_progress': float(p.assignment_progress),
                'practical_progress': float(p.practical_progress),
                'exam_progress': float(p.exam_progress),
                'is_completed': p.is_completed,
            })
        return JsonResponse({
            'course_id': str(course.id),
            'course_title': course.title,
            'course_slug': course.slug,
            'overall_percentage': float(summary['overall_percentage']),
            'completed_modules_count': summary['completed_modules_count'],
            'total_modules_count': summary['total_modules_count'],
            'next_activity': summary['next_activity'],
            'modules': modules_data,
        })


class StudentModuleProgressJsonView(View):
    def get(self, request, pk):
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'Authentication required'}, status=401)
        module = get_module_by_lookup(pk)
        from apps.progress.services import ProgressCalculationService
        p = ProgressCalculationService.update_module_progress(request.user, module)
        return JsonResponse({
            'module_id': str(module.id),
            'module_title': module.title,
            'overall_progress': float(p.overall_progress),
            'lesson_progress': float(p.lesson_progress),
            'quiz_progress': float(p.quiz_progress),
            'assignment_progress': float(p.assignment_progress),
            'practical_progress': float(p.practical_progress),
            'exam_progress': float(p.exam_progress),
            'is_completed': p.is_completed,
            'completed_at': p.completed_at.isoformat() if p.completed_at else None,
        })


class StudentGradesJsonView(View):
    def get(self, request):
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'Authentication required'}, status=401)
        course_id = request.GET.get('course_id')
        course_slug = request.GET.get('course_slug')
        from apps.assessments.services import GradeCalculationService
        if course_id:
            courses = Course.objects.filter(id=course_id)
        elif course_slug:
            courses = Course.objects.filter(slug=course_slug)
        else:
            courses = Course.objects.filter(enrollments__student=request.user)
        results = []
        for c in courses:
            grade_data = GradeCalculationService.calculate_student_grade(request.user, c)
            component_scores = grade_data.get('component_scores', {})
            component_weights = grade_data.get('component_weights', {})
            results.append({
                'course_id': str(c.id),
                'course_title': c.title,
                'final_grade': float(grade_data['final_grade']),
                'final_letter_grade': grade_data['final_letter_grade'],
                'passed': grade_data['passed'],
                'component_scores': {k: float(v) for k, v in component_scores.items()},
                'component_weights': {k: float(v) for k, v in component_weights.items()},
            })
        return JsonResponse({'grades': results})


class StudentCertificateEligibilityJsonView(View):
    def get(self, request):
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'Authentication required'}, status=401)
        course_id = request.GET.get('course_id')
        course_slug = request.GET.get('course_slug')
        from apps.certificates.services import CertificateEligibilityService
        if course_id:
            courses = Course.objects.filter(id=course_id)
        elif course_slug:
            courses = Course.objects.filter(slug=course_slug)
        else:
            courses = Course.objects.filter(enrollments__student=request.user)
        results = []
        for c in courses:
            elig = CertificateEligibilityService.evaluate_eligibility(request.user, c)
            results.append({
                'course_id': str(c.id),
                'course_title': c.title,
                'eligible': elig['eligible'],
                'academically_passed': elig['academically_passed'],
                'final_grade': float(elig['grades']['final_grade']),
                'passing_percentage': float(c.passing_percentage),
                'details': elig.get('completion_details', {}),
            })
        return JsonResponse({'eligibility': results})


try:
    from rest_framework import viewsets, permissions, status
    from rest_framework.decorators import action
    from rest_framework.views import APIView
    from rest_framework.response import Response
    from .serializers import (
        UserSerializer, CourseSerializer, CourseModuleSerializer,
        LessonSerializer, EnrollmentSerializer, LessonProgressSerializer
    )
    from .permissions import IsInstructorOrReadOnly, IsAcademyAdminUser

    class AuthStatusAPIView(APIView):
        permission_classes = [permissions.AllowAny]

        def get(self, request):
            if request.user.is_authenticated:
                return Response({
                    'authenticated': True,
                    'user': UserSerializer(request.user).data
                })
            return Response({'authenticated': False})

    class UserViewSet(viewsets.ReadOnlyModelViewSet):
        queryset = User.objects.filter(is_active=True)
        serializer_class = UserSerializer
        permission_classes = [IsAcademyAdminUser]

    class CourseViewSet(viewsets.ModelViewSet):
        queryset = Course.objects.all()
        serializer_class = CourseSerializer
        permission_classes = [IsInstructorOrReadOnly]
        lookup_field = 'slug'

        def get_queryset(self):
            if self.request.user.is_authenticated and (self.request.user.is_instructor or self.request.user.is_academy_admin):
                return Course.objects.all()
            return Course.objects.filter(status='PUBLISHED')

        def get_object(self):
            queryset = self.filter_queryset(self.get_queryset())
            lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
            lookup_value = self.kwargs[lookup_url_kwarg]
            import uuid
            try:
                uuid_val = uuid.UUID(str(lookup_value))
                obj = queryset.filter(id=uuid_val).first()
                if obj:
                    self.check_object_permissions(self.request, obj)
                    return obj
            except (ValueError, TypeError):
                pass
            filter_kwargs = {self.lookup_field: lookup_value}
            obj = get_object_or_404(queryset, **filter_kwargs)
            self.check_object_permissions(self.request, obj)
            return obj

        def perform_create(self, serializer):
            serializer.save(created_by=self.request.user)

        @action(detail=True, methods=['get'])
        def modules(self, request, **kwargs):
            course = self.get_object()
            modules = course.modules.filter(is_published=True).order_by('order')
            serializer = CourseModuleSerializer(modules, many=True, context={'request': request})
            return Response(serializer.data)

    class CourseModuleViewSet(viewsets.ModelViewSet):
        queryset = CourseModule.objects.all()
        serializer_class = CourseModuleSerializer
        permission_classes = [IsInstructorOrReadOnly]

        @action(detail=True, methods=['get'])
        def lessons(self, request, pk=None):
            module = self.get_object()
            lessons = module.lessons.filter(is_published=True).order_by('order')
            serializer = LessonSerializer(lessons, many=True, context={'request': request})
            return Response(serializer.data)

    class LessonViewSet(viewsets.ModelViewSet):
        queryset = Lesson.objects.all()
        serializer_class = LessonSerializer
        permission_classes = [IsInstructorOrReadOnly]

        @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
        def start(self, request, pk=None):
            lesson = self.get_object()
            progress, _ = LessonProgress.objects.get_or_create(
                student=request.user,
                lesson=lesson,
            )
            progress.mark_started()
            serializer = LessonProgressSerializer(progress)
            return Response({'status': 'started', 'progress': serializer.data}, status=status.HTTP_200_OK)

        @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
        def complete(self, request, pk=None):
            lesson = self.get_object()
            progress, _ = LessonProgress.objects.get_or_create(
                student=request.user,
                lesson=lesson,
            )
            progress.mark_completed()
            from apps.progress.services import ProgressCalculationService
            if lesson.module:
                ProgressCalculationService.update_module_progress(request.user, lesson.module)
            serializer = LessonProgressSerializer(progress)
            return Response({'status': 'completed', 'progress': serializer.data}, status=status.HTTP_200_OK)

    class EnrollmentViewSet(viewsets.ModelViewSet):
        queryset = Enrollment.objects.all()
        serializer_class = EnrollmentSerializer
        permission_classes = [permissions.IsAuthenticated]

        def get_queryset(self):
            user = self.request.user
            if user.is_academy_admin or user.is_superuser:
                return Enrollment.objects.all()
            return Enrollment.objects.filter(student=user)

        def perform_create(self, serializer):
            serializer.save(student=self.request.user)

    class LessonProgressViewSet(viewsets.ModelViewSet):
        queryset = LessonProgress.objects.all()
        serializer_class = LessonProgressSerializer
        permission_classes = [permissions.IsAuthenticated]

        def get_queryset(self):
            user = self.request.user
            if user.is_academy_admin or user.is_superuser:
                return LessonProgress.objects.all()
            return LessonProgress.objects.filter(student=user)

    # Phase 2 ViewSets
    from apps.assessments.models import (
        Quiz, QuizAttempt, Assignment, AssignmentSubmission, Exam, ExamAttempt
    )
    from apps.learning_paths.models import LearningPath, StudentLearningPath
    from apps.certificates.models import Certificate
    from apps.achievements.models import Achievement, StudentAchievement
    from apps.notifications.models import Notification, Announcement
    from apps.courses.models import CourseReview
    from .serializers import (
        QuizSerializer, QuizAttemptSerializer,
        AssignmentSerializer, AssignmentSubmissionSerializer,
        ExamSerializer, ExamAttemptSerializer,
        LearningPathSerializer, StudentLearningPathSerializer,
        CertificateSerializer, AchievementSerializer,
        NotificationSerializer, AnnouncementSerializer, CourseReviewSerializer
    )

    class QuizViewSet(viewsets.ReadOnlyModelViewSet):
        queryset = Quiz.objects.filter(is_published=True)
        serializer_class = QuizSerializer
        permission_classes = [permissions.IsAuthenticated]

        @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
        def start(self, request, pk=None):
            quiz = self.get_object()
            from apps.assessments.services import QuizGradingService
            can_attempt, remaining = QuizGradingService.can_attempt(quiz, request.user)
            if not can_attempt:
                return Response({'error': 'Maximum quiz attempts reached'}, status=status.HTTP_400_BAD_REQUEST)
            attempt_num = QuizAttempt.objects.filter(student=request.user, quiz=quiz).count() + 1
            attempt = QuizAttempt.objects.create(
                student=request.user,
                quiz=quiz,
                attempt_number=attempt_num,
            )
            return Response(QuizAttemptSerializer(attempt).data, status=status.HTTP_201_CREATED)

        @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
        def submit(self, request, pk=None):
            quiz = self.get_object()
            attempt_id = request.data.get('attempt_id')
            answers = request.data.get('answers', {})
            if not attempt_id:
                attempt = QuizAttempt.objects.filter(student=request.user, quiz=quiz, is_completed=False).order_by('-started_at').first()
            else:
                attempt = get_object_or_404(QuizAttempt, id=attempt_id, student=request.user, quiz=quiz)
            if not attempt or attempt.is_completed:
                return Response({'error': 'No active quiz attempt found to submit'}, status=status.HTTP_400_BAD_REQUEST)

            from apps.assessments.services import QuizGradingService
            graded_attempt = QuizGradingService.grade_attempt(attempt, answers)
            if quiz.module:
                from apps.progress.services import ProgressCalculationService
                ProgressCalculationService.update_module_progress(request.user, quiz.module)
            return Response(QuizAttemptSerializer(graded_attempt).data)

    class QuizAttemptViewSet(viewsets.ReadOnlyModelViewSet):
        serializer_class = QuizAttemptSerializer
        permission_classes = [permissions.IsAuthenticated]

        def get_queryset(self):
            user = self.request.user
            if user.is_instructor or user.is_academy_admin:
                return QuizAttempt.objects.all()
            return QuizAttempt.objects.filter(student=user)

    class AssignmentViewSet(viewsets.ReadOnlyModelViewSet):
        queryset = Assignment.objects.filter(status='PUBLISHED')
        serializer_class = AssignmentSerializer
        permission_classes = [permissions.IsAuthenticated]

        @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
        def submit(self, request, pk=None):
            assignment = self.get_object()
            submission_text = request.data.get('submission_text', '')
            submitted_file = request.FILES.get('submitted_file')
            existing_sub = AssignmentSubmission.objects.filter(student=request.user, assignment=assignment).order_by('-version').first()
            version = (existing_sub.version + 1) if existing_sub else 1
            submission = AssignmentSubmission.objects.create(
                assignment=assignment,
                student=request.user,
                submission_text=submission_text,
                submitted_file=submitted_file,
                version=version,
                status='SUBMITTED'
            )
            if assignment.module:
                from apps.progress.services import ProgressCalculationService
                ProgressCalculationService.update_module_progress(request.user, assignment.module)
            return Response(AssignmentSubmissionSerializer(submission).data, status=status.HTTP_201_CREATED)

    class AssignmentSubmissionViewSet(viewsets.ModelViewSet):
        serializer_class = AssignmentSubmissionSerializer
        permission_classes = [permissions.IsAuthenticated]

        def get_queryset(self):
            user = self.request.user
            if user.is_instructor or user.is_academy_admin:
                return AssignmentSubmission.objects.all()
            return AssignmentSubmission.objects.filter(student=user)

        def perform_create(self, serializer):
            serializer.save(student=self.request.user)

    class ExamViewSet(viewsets.ReadOnlyModelViewSet):
        queryset = Exam.objects.filter(is_published=True)
        serializer_class = ExamSerializer
        permission_classes = [permissions.IsAuthenticated]

        @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
        def start(self, request, pk=None):
            exam = self.get_object()
            from apps.assessments.services import ExamTimerService
            attempt = ExamTimerService.start_attempt(request.user, exam)
            return Response(ExamAttemptSerializer(attempt).data, status=status.HTTP_201_CREATED)

        @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
        def submit(self, request, pk=None):
            exam = self.get_object()
            attempt_id = request.data.get('attempt_id')
            answers = request.data.get('answers', {})
            if not attempt_id:
                attempt = ExamAttempt.objects.filter(student=request.user, exam=exam, is_completed=False).order_by('-started_at').first()
            else:
                attempt = get_object_or_404(ExamAttempt, id=attempt_id, student=request.user, exam=exam)
            if not attempt or attempt.is_completed:
                return Response({'error': 'No active exam attempt found'}, status=status.HTTP_400_BAD_REQUEST)

            from apps.assessments.services import ExamTimerService
            if ExamTimerService.check_expired(attempt):
                return Response({'error': 'Exam time has expired', 'attempt': ExamAttemptSerializer(attempt).data}, status=status.HTTP_400_BAD_REQUEST)

            total_score = 0
            questions = exam.questions.all()
            max_score = sum(q.points for q in questions) or 1
            for q in questions:
                selected_opt_id = answers.get(str(q.id))
                if selected_opt_id:
                    opt = q.options.filter(id=selected_opt_id).first()
                    if opt and opt.is_correct:
                        total_score += q.points

            from decimal import Decimal
            attempt.score = Decimal(str(total_score))
            attempt.percentage = Decimal(str((total_score / max_score) * 100)).quantize(Decimal('0.01'))
            attempt.passed = attempt.percentage >= exam.passing_score
            attempt.is_completed = True
            attempt.save()

            if exam.module:
                from apps.progress.services import ProgressCalculationService
                ProgressCalculationService.update_module_progress(request.user, exam.module)
            return Response(ExamAttemptSerializer(attempt).data)

    class ExamAttemptViewSet(viewsets.ReadOnlyModelViewSet):
        serializer_class = ExamAttemptSerializer
        permission_classes = [permissions.IsAuthenticated]

        def get_queryset(self):
            user = self.request.user
            if user.is_instructor or user.is_academy_admin:
                return ExamAttempt.objects.all()
            return ExamAttempt.objects.filter(student=user)

    class LearningPathViewSet(viewsets.ReadOnlyModelViewSet):
        queryset = LearningPath.objects.filter(is_published=True)
        serializer_class = LearningPathSerializer
        permission_classes = [permissions.AllowAny]
        lookup_field = 'slug'

    class CertificateViewSet(viewsets.ReadOnlyModelViewSet):
        serializer_class = CertificateSerializer
        permission_classes = [permissions.IsAuthenticated]

        def get_queryset(self):
            user = self.request.user
            if user.is_instructor or user.is_academy_admin:
                return Certificate.objects.all()
            return Certificate.objects.filter(student=user)

    class AchievementViewSet(viewsets.ReadOnlyModelViewSet):
        queryset = Achievement.objects.all()
        serializer_class = AchievementSerializer
        permission_classes = [permissions.AllowAny]

    class NotificationViewSet(viewsets.ModelViewSet):
        serializer_class = NotificationSerializer
        permission_classes = [permissions.IsAuthenticated]

        def get_queryset(self):
            return Notification.objects.filter(recipient=self.request.user)

    class AnnouncementViewSet(viewsets.ReadOnlyModelViewSet):
        queryset = Announcement.objects.filter(is_published=True)
        serializer_class = AnnouncementSerializer
        permission_classes = [permissions.AllowAny]


    # ==========================================================================
    # Student Learning Portal API Views
    # ==========================================================================
    class StudentCoursesAPIView(APIView):
        permission_classes = [permissions.IsAuthenticated]

        def get(self, request):
            enrollments = Enrollment.objects.filter(student=request.user).select_related('course')
            results = []
            for e in enrollments:
                results.append({
                    'enrollment_id': str(e.id),
                    'course_id': str(e.course.id),
                    'course_title': e.course.title,
                    'course_slug': e.course.slug,
                    'course_type': e.course.course_type,
                    'progress_percentage': float(e.progress_percentage),
                    'status': e.status,
                    'enrolled_at': e.enrolled_at.isoformat() if e.enrolled_at else None,
                    'completed_at': e.completed_at.isoformat() if e.completed_at else None,
                })
            return Response({'count': len(results), 'results': results})


    class StudentProgressAPIView(APIView):
        permission_classes = [permissions.IsAuthenticated]

        def get(self, request):
            enrollments = Enrollment.objects.filter(student=request.user)
            total_enrolled = enrollments.count()
            completed_count = enrollments.filter(status='COMPLETED').count()
            total_lessons_completed = LessonProgress.objects.filter(student=request.user, completed=True).count()
            total_quizzes_passed = QuizAttempt.objects.filter(student=request.user, passed=True).values('quiz').distinct().count()
            return Response({
                'total_enrolled_courses': total_enrolled,
                'completed_courses': completed_count,
                'total_lessons_completed': total_lessons_completed,
                'total_quizzes_passed': total_quizzes_passed,
            })


    class StudentCourseProgressAPIView(APIView):
        permission_classes = [permissions.IsAuthenticated]

        def get(self, request, lookup):
            import uuid
            course = None
            try:
                val = uuid.UUID(str(lookup))
                course = Course.objects.filter(id=val).first()
            except (ValueError, TypeError):
                pass
            if not course:
                course = get_object_or_404(Course, slug=lookup)

            from apps.progress.services import ProgressCalculationService
            summary = ProgressCalculationService.get_student_course_summary(request.user, course)

            modules_data = []
            for m in summary['module_summaries']:
                p = m['progress']
                modules_data.append({
                    'module_id': str(m['module'].id),
                    'module_title': m['module'].title,
                    'order': m['module'].order,
                    'overall_progress': float(p.overall_progress),
                    'lesson_progress': float(p.lesson_progress),
                    'quiz_progress': float(p.quiz_progress),
                    'assignment_progress': float(p.assignment_progress),
                    'practical_progress': float(p.practical_progress),
                    'exam_progress': float(p.exam_progress),
                    'is_completed': p.is_completed,
                })

            return Response({
                'course_id': str(course.id),
                'course_title': course.title,
                'course_slug': course.slug,
                'overall_percentage': float(summary['overall_percentage']),
                'completed_modules_count': summary['completed_modules_count'],
                'total_modules_count': summary['total_modules_count'],
                'next_activity': summary['next_activity'],
                'modules': modules_data,
            })


    class StudentModuleProgressAPIView(APIView):
        permission_classes = [permissions.IsAuthenticated]

        def get(self, request, pk):
            import uuid
            module = None
            try:
                val = uuid.UUID(str(pk))
                module = CourseModule.objects.filter(id=val).first()
            except (ValueError, TypeError):
                pass
            if not module:
                module = get_object_or_404(CourseModule, pk=pk)

            from apps.progress.services import ProgressCalculationService
            p = ProgressCalculationService.update_module_progress(request.user, module)
            return Response({
                'module_id': str(module.id),
                'module_title': module.title,
                'overall_progress': float(p.overall_progress),
                'lesson_progress': float(p.lesson_progress),
                'quiz_progress': float(p.quiz_progress),
                'assignment_progress': float(p.assignment_progress),
                'practical_progress': float(p.practical_progress),
                'exam_progress': float(p.exam_progress),
                'is_completed': p.is_completed,
                'completed_at': p.completed_at.isoformat() if p.completed_at else None,
            })


    class StudentGradesAPIView(APIView):
        permission_classes = [permissions.IsAuthenticated]

        def get(self, request):
            course_id = request.query_params.get('course_id')
            course_slug = request.query_params.get('course_slug')
            from apps.assessments.services import GradeCalculationService
            if course_id:
                courses = Course.objects.filter(id=course_id)
            elif course_slug:
                courses = Course.objects.filter(slug=course_slug)
            else:
                courses = Course.objects.filter(enrollments__student=request.user)

            results = []
            for c in courses:
                grade_data = GradeCalculationService.calculate_student_grade(request.user, c)
                component_scores = grade_data.get('component_scores', {})
                component_weights = grade_data.get('component_weights', {})
                results.append({
                    'course_id': str(c.id),
                    'course_title': c.title,
                    'final_grade': float(grade_data['final_grade']),
                    'final_letter_grade': grade_data['final_letter_grade'],
                    'passed': grade_data['passed'],
                    'component_scores': {
                        k: float(v) for k, v in component_scores.items()
                    },
                    'component_weights': {
                        k: float(v) for k, v in component_weights.items()
                    }
                })
            return Response({'grades': results})


    class StudentCertificateEligibilityAPIView(APIView):
        permission_classes = [permissions.IsAuthenticated]

        def get(self, request):
            course_id = request.query_params.get('course_id')
            course_slug = request.query_params.get('course_slug')
            from apps.certificates.services import CertificateEligibilityService
            if course_id:
                courses = Course.objects.filter(id=course_id)
            elif course_slug:
                courses = Course.objects.filter(slug=course_slug)
            else:
                courses = Course.objects.filter(enrollments__student=request.user)

            results = []
            for c in courses:
                elig = CertificateEligibilityService.evaluate_eligibility(request.user, c)
                results.append({
                    'course_id': str(c.id),
                    'course_title': c.title,
                    'eligible': elig['eligible'],
                    'academically_passed': elig['academically_passed'],
                    'final_grade': float(elig['grades']['final_grade']),
                    'passing_percentage': float(c.passing_percentage),
                    'details': elig.get('completion_details', {})
                })
            return Response({'eligibility': results})

except ImportError:
    pass


