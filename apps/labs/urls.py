from django.urls import path
from .views import (
    LabListView, LabDetailView, LabStartView, LabStopView, LabResetView,
    LabStatusApiView, LabExtendView,
)

urlpatterns = [
    path('', LabListView.as_view(), name='lab-list'),
    path('<slug:slug>/', LabDetailView.as_view(), name='lab-detail'),
    path('<uuid:lab_id>/start/', LabStartView.as_view(), name='lab-start'),
    path('instances/<uuid:instance_id>/stop/', LabStopView.as_view(), name='lab-stop'),
    path('instances/<uuid:instance_id>/reset/', LabResetView.as_view(), name='lab-reset'),
    path('instances/<uuid:instance_id>/extend/', LabExtendView.as_view(), name='lab-extend'),
    path('instances/<uuid:instance_id>/status/', LabStatusApiView.as_view(), name='lab-status-api'),
]

