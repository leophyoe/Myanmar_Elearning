from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.views.generic import TemplateView, View

from .models import VpnProfile, VpnServerConfig
from .services import VpnCertificateService


class VpnDashboardView(LoginRequiredMixin, TemplateView):
    """
    User-facing VPN management dashboard.
    Displays client tunnel IP, OpenVPN connection guides, and download button.
    """
    template_name = 'vpn/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile = VpnCertificateService.generate_profile_for_user(self.request.user)
        config = VpnCertificateService.get_or_create_server_config()

        context.update({
            'profile': profile,
            'config': config,
            'filename': profile.filename,
        })
        return context


class VpnDownloadView(LoginRequiredMixin, View):
    """
    Downloads the personalized, ready-to-run .ovpn profile for the logged-in student.
    """
    def get(self, request, *args, **kwargs):
        profile = VpnCertificateService.generate_profile_for_user(request.user)
        profile.download_count += 1
        profile.save(update_fields=['download_count'])

        response = HttpResponse(
            profile.ovpn_content,
            content_type='application/x-openvpn-profile'
        )
        response['Content-Disposition'] = f'attachment; filename="{profile.filename}"'
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        return response


class VpnRegenerateView(LoginRequiredMixin, View):
    """
    Regenerates a fresh private key and signed certificate for the student.
    Invalidates any previously downloaded profile.
    """
    def post(self, request, *args, **kwargs):
        profile = VpnCertificateService.generate_profile_for_user(request.user, force_regenerate=True)
        messages.success(
            request,
            f"Your VPN certificate has been regenerated with new security keys! Virtual IP: {profile.virtual_ip}"
        )
        return redirect('vpn-dashboard')


class VpnStatusApiView(LoginRequiredMixin, View):
    """
    JSON API for the lab interface to query user's VPN provisioning status.
    """
    def get(self, request, *args, **kwargs):
        profile = VpnProfile.objects.filter(user=request.user).first()
        if not profile or not profile.ovpn_content:
            return JsonResponse({
                'provisioned': False,
                'virtual_ip': None,
                'download_count': 0,
            })
        return JsonResponse({
            'provisioned': True,
            'virtual_ip': profile.virtual_ip,
            'download_count': profile.download_count,
            'last_connected': profile.last_connected_at.isoformat() if profile.last_connected_at else None,
        })
