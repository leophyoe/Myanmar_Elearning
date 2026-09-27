from django.urls import path
from .views import LearningPathListView, LearningPathDetailView, EnrollLearningPathView

app_name = 'learning_paths'

urlpatterns = [
    path('', LearningPathListView.as_view(), name='path-list'),
    path('<slug:slug>/', LearningPathDetailView.as_view(), name='path-detail'),
    path('<slug:slug>/enroll/', EnrollLearningPathView.as_view(), name='path-enroll'),
]

