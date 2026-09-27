from django.urls import path
from .views import (
    CertificateListView, CertificateLookupView, CertificateQRView,
    CertificateVerificationView,
)

urlpatterns = [
    path('', CertificateListView.as_view(), name='certificate-list'),
    path('verify/', CertificateLookupView.as_view(), name='certificate-lookup'),
    path('verify/<uuid:cert_id>/', CertificateVerificationView.as_view(), name='certificate-verify'),
    path('verify/<uuid:cert_id>/qr.png', CertificateQRView.as_view(), name='certificate-qr'),
]

