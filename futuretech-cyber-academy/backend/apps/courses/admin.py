from django.contrib import admin
from .models import CourseCategory, Course, CourseModule, Lesson, CourseResource
from .models import CourseCategory, Course, CourseModule, Lesson, CourseResource, LearningObjective

class LearningObjectiveInline(admin.TabularInline):
    model = LearningObjective
    extra = 1

class CourseModuleInline(admin.StackedInline):
    model = CourseModule
    extra = 1
    prepopulated_fields = {'slug': ('title',)}

class LessonInline(admin.StackedInline):
    model = Lesson
    extra = 1
    prepopulated_fields = {'slug': ('title',)}

class CourseResourceInline(admin.TabularInline):
    model = CourseResource
    extra = 1

@admin.register(CourseCategory)
class CourseCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'created_at')
    prepopulated_fields = {'slug': ('name',)}

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('title', 'level', 'status', 'duration', 'is_free', 'created_by', 'created_at')
    list_filter = ('level', 'status', 'is_free', 'categories')
    search_fields = ('title', 'description', 'short_description')
    list_display = ('title', 'course_type', 'level', 'status', 'duration', 'passing_percentage', 'is_free', 'created_by', 'created_at')
    list_filter = ('course_type', 'level', 'status', 'is_free', 'categories')
    search_fields = ('title', 'title_en', 'title_my', 'description')
    prepopulated_fields = {'slug': ('title',)}
    inlines = [CourseModuleInline]

@admin.register(CourseModule)
class CourseModuleAdmin(admin.ModelAdmin):
    list_display = ('title', 'course', 'order', 'estimated_hours', 'is_published')
    list_filter = ('course', 'is_published')
    search_fields = ('title', 'description')
    search_fields = ('title', 'title_en', 'title_my', 'description')
    prepopulated_fields = {'slug': ('title',)}
    inlines = [LessonInline]
    inlines = [LearningObjectiveInline, LessonInline]

@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ('title', 'module', 'lesson_type', 'order', 'estimated_minutes', 'is_published')
    list_filter = ('lesson_type', 'is_published', 'module__course')
    search_fields = ('title', 'content')
    list_display = ('title', 'module', 'lesson_type', 'order', 'is_required', 'estimated_minutes', 'is_published')
    list_filter = ('lesson_type', 'is_required', 'is_published', 'module__course')
    search_fields = ('title', 'title_en', 'title_my', 'content')
    prepopulated_fields = {'slug': ('title',)}
    inlines = [CourseResourceInline]

@admin.register(CourseResource)
class CourseResourceAdmin(admin.ModelAdmin):
    list_display = ('title', 'lesson', 'resource_type')
    list_filter = ('resource_type',)

@admin.register(LearningObjective)
class LearningObjectiveAdmin(admin.ModelAdmin):
    list_display = ('title_en', 'title_my', 'module', 'lesson', 'order', 'is_active')
    list_filter = ('module__course', 'is_active')
    search_fields = ('title_en', 'title_my', 'description_en', 'description_my')

