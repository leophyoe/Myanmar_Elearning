from django.urls import path
from .views import CertificateListView, CertificateDetailView, PublicCertificateVerificationView

app_name = 'certificates'

urlpatterns = [
    path('', CertificateListView.as_view(), name='certificate-list'),
    path('<str:certificate_number>/', CertificateDetailView.as_view(), name='certificate-detail'),
    path('verify/<str:certificate_number>/', PublicCertificateVerificationView.as_view(), name='public-verify'),
]
