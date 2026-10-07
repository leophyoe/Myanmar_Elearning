from django.contrib import admin
from .models import ArticleCategory, Article


@admin.register(ArticleCategory)
class ArticleCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'icon', 'order', 'created_at')
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name', 'description')


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = (
        'title', 'author', 'category', 'difficulty',
        'reading_time_minutes', 'is_featured', 'is_published', 'views_count', 'published_at'
    )
    list_filter = ('is_published', 'is_featured', 'difficulty', 'category')
    search_fields = ('title', 'summary', 'content', 'tags')
    prepopulated_fields = {'slug': ('title',)}
    raw_id_fields = ('author', 'related_course')
    date_hierarchy = 'published_at'
