from django.urls import path
from .views import (
    VpnDashboardView,
    VpnDownloadView,
    VpnRegenerateView,
    VpnStatusApiView,
)

urlpatterns = [
    path('', VpnDashboardView.as_view(), name='vpn-dashboard'),
    path('download/', VpnDownloadView.as_view(), name='vpn-download'),
    path('regenerate/', VpnRegenerateView.as_view(), name='vpn-regenerate'),
    path('status/', VpnStatusApiView.as_view(), name='vpn-status'),
]
