from django.urls import path
from .views import ArticleListView, ArticleCategoryListView, ArticleDetailView

app_name = 'blog'

urlpatterns = [
    path('', ArticleListView.as_view(), name='article-list'),
    path('category/<slug:category_slug>/', ArticleCategoryListView.as_view(), name='article-category'),
    path('<slug:slug>/', ArticleDetailView.as_view(), name='article-detail'),
]
