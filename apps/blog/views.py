from django.db.models import F, Q
from django.shortcuts import get_object_or_404
from django.views.generic import DetailView, ListView

from .models import Article, ArticleCategory


class ArticleListView(ListView):
    """
    Public Knowledge Hub directory of developer tutorials, cybersecurity articles,
    and technical guides.
    """
    model = Article
    template_name = 'blog/article_list.html'
    context_object_name = 'articles'
    paginate_by = 9

    def get_queryset(self):
        qs = Article.objects.filter(is_published=True).select_related(
            'author', 'category', 'related_course'
        )

        category_slug = self.kwargs.get('category_slug') or self.request.GET.get('category', '').strip()
        if category_slug:
            qs = qs.filter(category__slug=category_slug)

        difficulty = self.request.GET.get('difficulty', '').strip().lower()
        if difficulty in dict(Article.Difficulty.choices):
            qs = qs.filter(difficulty=difficulty)

        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(title__icontains=q) |
                Q(summary__icontains=q) |
                Q(tags__icontains=q) |
                Q(content__icontains=q)
            ).distinct()

        tag = self.request.GET.get('tag', '').strip()
        if tag:
            qs = qs.filter(tags__icontains=tag)

        return qs.order_by('-is_featured', '-published_at', '-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        category_slug = self.kwargs.get('category_slug') or self.request.GET.get('category', '').strip()
        active_category = None
        if category_slug:
            active_category = ArticleCategory.objects.filter(slug=category_slug).first()

        context.update({
            'categories': ArticleCategory.objects.all(),
            'active_category': active_category,
            'category_slug': category_slug,
            'q': self.request.GET.get('q', '').strip(),
            'active_difficulty': self.request.GET.get('difficulty', '').strip().lower(),
            'active_tag': self.request.GET.get('tag', '').strip(),
            'featured_articles': Article.objects.filter(
                is_published=True, is_featured=True
            ).select_related('author', 'category')[:3],
            'difficulties': Article.Difficulty.choices,
        })
        return context


class ArticleCategoryListView(ArticleListView):
    """Convenience class for category-specific URL routing."""
    pass


class ArticleDetailView(DetailView):
    """
    Comprehensive reader view for Knowledge Hub articles, including author credentials,
    tags, reading duration, and high-converting course funnel links.
    """
    model = Article
    template_name = 'blog/article_detail.html'
    context_object_name = 'article'
    slug_url_kwarg = 'slug'

    def get_queryset(self):
        user = self.request.user
        if user.is_authenticated and (user.is_staff or user.is_superuser):
            return Article.objects.all().select_related('author', 'category', 'related_course')
        return Article.objects.filter(is_published=True).select_related(
            'author', 'category', 'related_course'
        )

    def get_object(self, queryset=None):
        article = super().get_object(queryset=queryset)
        Article.objects.filter(pk=article.pk).update(views_count=F('views_count') + 1)
        article.refresh_from_db(fields=['views_count'])
        return article

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        article = self.object

        related_qs = Article.objects.filter(
            is_published=True
        ).exclude(pk=article.pk).select_related('author', 'category')

        if article.category:
            related_articles = list(related_qs.filter(category=article.category)[:3])
        else:
            related_articles = list(related_qs[:3])

        context.update({
            'related_articles': related_articles,
            'related_course': article.related_course,
            'author': article.author,
            'author_profile': getattr(article.author, 'student_profile', None),
            'author_teacher_profile': getattr(article.author, 'teacher_profile', None),
            'author_articles_count': Article.objects.filter(
                author=article.author, is_published=True
            ).count(),
        })
        return context
