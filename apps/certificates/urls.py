from django.urls import path
from .views import CertificateListView, CertificateVerificationView

urlpatterns = [
    path('', CertificateListView.as_view(), name='certificate-list'),
    path('verify/<uuid:cert_id>/', CertificateVerificationView.as_view(), name='certificate-verify'),
]

