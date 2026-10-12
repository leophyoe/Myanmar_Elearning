from django.urls import path
from .views import (
    CertificateListView, CertificateLookupView, CertificateQRView,
    CertificateVerificationView,
    AssociateCredentialVerificationView, AssociateCredentialQRView,
    CertificateTemplateListView, CertificateTemplateCreateView,
    CertificateTemplateUpdateView, CertificateTemplateDeleteView,
    CertificateTemplatePreviewView, CertificateTemplateDuplicateView,
    InstructorCertificateListView, InstructorCertificateExportCSVView,
)

urlpatterns = [
    path('', CertificateListView.as_view(), name='certificate-list'),
    path('instructor/', InstructorCertificateListView.as_view(), name='instructor-certificate-list'),
    path('instructor/export/csv/', InstructorCertificateExportCSVView.as_view(), name='instructor-certificate-export-csv'),
    path('templates/', CertificateTemplateListView.as_view(), name='certificate-template-list'),
    path('templates/new/', CertificateTemplateCreateView.as_view(), name='certificate-template-create'),
    path('templates/<uuid:pk>/edit/', CertificateTemplateUpdateView.as_view(), name='certificate-template-edit'),
    path('templates/<uuid:pk>/duplicate/', CertificateTemplateDuplicateView.as_view(), name='certificate-template-duplicate'),
    path('templates/<uuid:pk>/delete/', CertificateTemplateDeleteView.as_view(), name='certificate-template-delete'),
    path('templates/<uuid:pk>/preview/', CertificateTemplatePreviewView.as_view(), name='certificate-template-preview'),
    path('verify/', CertificateLookupView.as_view(), name='certificate-lookup'),
    path('verify/<uuid:cert_id>/', CertificateVerificationView.as_view(), name='certificate-verify'),
    path('verify/<uuid:cert_id>/qr.png', CertificateQRView.as_view(), name='certificate-qr'),
    path('verify/credential/<uuid:cred_id>/', AssociateCredentialVerificationView.as_view(), name='associate-verify'),
    path('verify/credential/<uuid:cred_id>/qr.png', AssociateCredentialQRView.as_view(), name='associate-qr'),
    path('verify/<str:code>/', CertificateVerificationView.as_view(), name='certificate-verify-code'),
]
