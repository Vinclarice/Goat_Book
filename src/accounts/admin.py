from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from unfold.admin import ModelAdmin

from accounts.forms import AdminUserChangeForm, AdminUserCreationForm
from accounts.models import User


@admin.register(User)
class UserAdmin(ModelAdmin, DjangoUserAdmin):
    """Admin for our slimmed-down custom User (no first/last name).

    The main job here is approving pending signups: they land with
    ``is_active=False`` (see accounts.forms.SignUpForm.save), so the
    quickest way to approve someone is to tick "Active" in the list view
    below and save.
    """

    form = AdminUserChangeForm
    add_form = AdminUserCreationForm
    ordering = ("username",)
    list_display = ("username", "email", "is_active", "is_staff", "last_login")
    list_filter = ("is_active", "is_staff", "is_superuser")
    list_editable = ("is_active",)
    search_fields = ("username", "email")
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Personal info", {"fields": ("email",)}),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ),
            },
        ),
        ("Important dates", {"fields": ("last_login",)}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("username", "email", "password1", "password2"),
            },
        ),
    )
