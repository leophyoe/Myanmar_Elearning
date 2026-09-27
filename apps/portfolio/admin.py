from django.contrib import admin
from .models import ExternalCertificate, PortfolioLink, Skill


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ('owner', 'name', 'category', 'level')
    list_filter = ('category',)
    search_fields = ('name', 'owner__username')


@admin.register(PortfolioLink)
class PortfolioLinkAdmin(admin.ModelAdmin):
    list_display = ('owner', 'kind', 'label', 'url')
    search_fields = ('owner__username', 'label')


@admin.register(ExternalCertificate)
class ExternalCertificateAdmin(admin.ModelAdmin):
    list_display = ('owner', 'title', 'issuer', 'credential_id', 'is_verified')
    list_filter = ('is_verified',)
    search_fields = ('title', 'issuer', 'credential_id', 'owner__username')
    readonly_fields = ('verified_by', 'verified_at')
