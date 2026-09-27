from django.contrib import admin
from .models import VpnProfile, VpnServerConfig


@admin.register(VpnProfile)
class VpnProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'virtual_ip', 'download_count', 'revoked', 'last_connected_at', 'created_at')
    search_fields = ('user__username', 'user__email', 'virtual_ip')
    list_filter = ('revoked', 'created_at')
    readonly_fields = ('client_cert', 'client_key', 'ovpn_content')


@admin.register(VpnServerConfig)
class VpnServerConfigAdmin(admin.ModelAdmin):
    list_display = ('server_host', 'server_port', 'protocol', 'vpn_subnet', 'lab_subnet')
    readonly_fields = ('ca_cert', 'ca_key', 'tls_auth_key')
