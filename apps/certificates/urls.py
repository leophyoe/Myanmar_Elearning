from django.urls import path
from .views import (
    CertificateListView, CertificateLookupView, CertificateQRView,
    CertificateVerificationView,
    AssociateCredentialVerificationView, AssociateCredentialQRView,
)

urlpatterns = [
    path('', CertificateListView.as_view(), name='certificate-list'),
    path('verify/', CertificateLookupView.as_view(), name='certificate-lookup'),
    path('verify/<uuid:cert_id>/', CertificateVerificationView.as_view(), name='certificate-verify'),
    path('verify/<uuid:cert_id>/qr.png', CertificateQRView.as_view(), name='certificate-qr'),
    path('verify/credential/<uuid:cred_id>/', AssociateCredentialVerificationView.as_view(), name='associate-verify'),
    path('verify/credential/<uuid:cred_id>/qr.png', AssociateCredentialQRView.as_view(), name='associate-qr'),
    path('verify/<str:code>/', CertificateVerificationView.as_view(), name='certificate-verify-code'),
]
