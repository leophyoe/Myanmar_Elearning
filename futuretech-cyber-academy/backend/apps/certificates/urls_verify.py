from django.urls import path
from .views import PublicCertificateVerificationView

urlpatterns = [
    path('', PublicCertificateVerificationView.as_view(), name='public-verify'),
]

