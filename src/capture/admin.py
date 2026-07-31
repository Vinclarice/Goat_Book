from django.contrib import admin

from unfold.admin import ModelAdmin

from .models import Capture


@admin.register(Capture)
class CaptureAdmin(ModelAdmin):
    list_display = ("text", "owner", "created_at", "resolved_at")
    list_filter = ("owner",)
    search_fields = ("text", "owner__username", "owner__email")
    readonly_fields = ("created_at",)
