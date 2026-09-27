from django.views.generic import ListView, DetailView, View, CreateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.db.models import Q
from django.contrib import messages
from .models import Course, CourseModule, Lesson, CourseCategory, CourseResource
from apps.enrollments.models import Enrollment
from apps.progress.models import LessonProgress
from apps.core.permissions import InstructorRequiredMixin

class CourseListView(ListView):
    model = Course
    template_name = 'courses/course_list.html'
    context_object_name = 'courses'
    paginate_by = 12

    def get_queryset(self):
        queryset = Course.objects.filter(status='PUBLISHED').prefetch_related('categories', 'created_by')
        q = self.request.GET.get('q', '').strip()
        category = self.request.GET.get('category', '').strip()
        level = self.request.GET.get('level', '').strip()
        price_filter = self.request.GET.get('price', '').strip()

        if q:
            queryset = queryset.filter(
                Q(title__icontains=q) |
                Q(short_description__icontains=q) |
                Q(description__icontains=q) |
                Q(categories__name__icontains=q)
            ).distinct()

        if category:
            queryset = queryset.filter(categories__slug=category)

        if level:
            queryset = queryset.filter(level=level)

        if price_filter == 'free':
            queryset = queryset.filter(is_free=True)
        elif price_filter == 'paid':
            queryset = queryset.filter(is_free=False)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = CourseCategory.objects.all()
        context['search_query'] = self.request.GET.get('q', '')
        context['selected_category'] = self.request.GET.get('category', '')
        context['selected_level'] = self.request.GET.get('level', '')
        context['selected_price'] = self.request.GET.get('price', '')
        return context


class CourseDetailView(DetailView):
    model = Course
    template_name = 'courses/course_detail.html'
    context_object_name = 'course'
    slug_field = 'slug'
    slug_url_kwarg = 'slug'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        course = self.get_object()
        modules = course.modules.filter(is_published=True).prefetch_related('lessons')
        modules = course.modules.filter(is_published=True).prefetch_related(
            'lessons',
            'quizzes',
            'assignments',
            'module_exams'
        )
        from apps.courses.models import LearningObjective
        context['modules'] = modules
        context['learning_objectives'] = LearningObjective.objects.filter(module__course=course, is_active=True)

        # Check student enrollment status
        is_enrolled = False
        enrollment = None
        completed_lesson_ids = set()
        module_progress_map = {}

        if self.request.user.is_authenticated:
            enrollment = Enrollment.objects.filter(
                student=self.request.user,
                course=course,
                status__in=['ACTIVE', 'COMPLETED']
            ).first()
            if enrollment:
                is_enrolled = True
                completed_lesson_ids = set(
                    LessonProgress.objects.filter(
                        student=self.request.user,
                        lesson__module__course=course,
                        completed=True
                    ).values_list('lesson_id', flat=True)
                )
                from apps.progress.models import ModuleProgress
                module_progress_qs = ModuleProgress.objects.filter(student=self.request.user, module__course=course)
                module_progress_map = {mp.module_id: mp for mp in module_progress_qs}

        context['is_enrolled'] = is_enrolled
        context['enrollment'] = enrollment
        context['completed_lesson_ids'] = completed_lesson_ids
        context['module_progress_map'] = module_progress_map

        # First lesson link
        first_module = modules.first()
        if first_module and first_module.lessons.filter(is_published=True).exists():
            context['first_lesson'] = first_module.lessons.filter(is_published=True).first()
        # Reviews and ratings
        reviews = course.reviews.filter(is_approved=True).select_related('student')
        context['reviews'] = reviews
        context['reviews_count'] = reviews.count()
        context['user_review'] = reviews.filter(student=self.request.user).first() if self.request.user.is_authenticated else None

        return context


class CourseReviewCreateView(LoginRequiredMixin, View):
    def post(self, request, slug):
        course = get_object_or_404(Course, slug=slug, status='PUBLISHED')
        rating_val = request.POST.get('rating', '5')
        comment = request.POST.get('comment', '').strip()

        try:
            rating = int(rating_val)
            rating = max(1, min(5, rating))
        except ValueError:
            rating = 5

        if not comment:
            messages.error(request, "Please enter a comment for your review.")
            return redirect('course-detail', slug=slug)

        from .models import CourseReview
        review, created = CourseReview.objects.update_or_create(
            course=course,
            student=request.user,
            defaults={
                'rating': rating,
                'comment': comment,
                'is_approved': True,
            }
        )

        messages.success(request, "Thank you for reviewing this course!")
        return redirect('course-detail', slug=slug)



class LessonLearnView(LoginRequiredMixin, View):
    template_name = 'courses/lesson_learn.html'

    def get(self, request, course_slug, lesson_slug):
        course = get_object_or_404(Course, slug=course_slug, status='PUBLISHED')

        # Verify enrollment (instructors and admins have preview rights)
        enrollment = None
        if not (request.user.is_instructor or request.user.is_academy_admin):
            enrollment = get_object_or_404(
                Enrollment,
                student=request.user,
                course=course,
                status__in=['ACTIVE', 'COMPLETED']
            )

        lesson = get_object_or_404(
            Lesson,
            module__course=course,
            slug=lesson_slug,
            is_published=True
        )

        # Track or start progress
        progress, created = LessonProgress.objects.get_or_create(
            student=request.user,
            lesson=lesson
        )
        if not progress.started_at:
            progress.mark_started()

        # Build curriculum tree with completion status
        modules = course.modules.filter(is_published=True).prefetch_related('lessons')
        completed_lesson_ids = set(
            LessonProgress.objects.filter(
                student=request.user,
                lesson__module__course=course,
                completed=True
            ).values_list('lesson_id', flat=True)
        )

        # Flatten lessons to calculate Previous and Next navigation
        all_lessons = []
        for m in modules:
            for l in m.lessons.filter(is_published=True):
                all_lessons.append(l)

        current_index = -1
        for idx, item in enumerate(all_lessons):
            if item.id == lesson.id:
                current_index = idx
                break

        prev_lesson = all_lessons[current_index - 1] if current_index > 0 else None
        next_lesson = all_lessons[current_index + 1] if current_index < len(all_lessons) - 1 else None

        context = {
            'course': course,
            'module': lesson.module,
            'lesson': lesson,
            'modules': modules,
            'progress': progress,
            'completed_lesson_ids': completed_lesson_ids,
            'prev_lesson': prev_lesson,
            'next_lesson': next_lesson,
            'resources': lesson.resources.all(),
            'enrollment': enrollment,
        }
        return render(request, self.template_name, context)

