from django.urls import path
from .views import PortfolioDetailView, PortfolioEditView, PortfolioNFCView, PortfolioQRView

urlpatterns = [
    path('edit/', PortfolioEditView.as_view(), name='portfolio-edit'),
    path('qr/', PortfolioQRView.as_view(), name='portfolio-qr'),
    path('nfc/', PortfolioNFCView.as_view(), name='portfolio-nfc'),
    path('<str:username>/qr.png', PortfolioQRView.as_view(), name='portfolio-user-qr'),
    path('<str:username>/nfc.txt', PortfolioNFCView.as_view(), name='portfolio-user-nfc'),
    path('<str:username>/', PortfolioDetailView.as_view(), name='portfolio-detail'),
]
