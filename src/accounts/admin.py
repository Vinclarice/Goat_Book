from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from unfold.admin import ModelAdmin

from accounts.forms import AdminUserChangeForm, AdminUserCreationForm
from accounts.models import Invitation, User


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
        # Explicit fieldsets mean a new field is invisible here until it is
        # named. time_zone in particular is worth reaching from admin: it
        # decides what "overdue" means for that person, so a wrong one is
        # something you may need to correct on their behalf.
        (
            "Preferences",
            {"fields": ("time_zone", "daily_digest", "closing_nudge", "theme")},
        ),
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


@admin.register(Invitation)
class InvitationAdmin(ModelAdmin):
    """Minting an invitation — **S1's other half**.

    **A surface, because the model without one is the seam this project keeps
    shipping.** `principles.md`: *a slice is not closed while nothing calls it*,
    and *check for a caller, not for existence*. Three things turned up switched
    off in two days before that rule was written.

    **The admin rather than a page of its own.** Account administration lives
    here already, this is the one thing on it, and there is exactly one person
    who mints these. A page would be a nicer home the day a second person can.

    **The link is a read-only field rather than a message on save**, because it
    has to be readable again: somebody who loses the link before sending it
    would otherwise have a live invitation they cannot use and cannot see is
    dead. That is what `Invitation`'s UUID buys over a hashed secret.
    """

    list_display = ("note", "state", "created_by", "created_at", "expires_at")
    list_filter = ("created_by",)
    readonly_fields = ("public_id", "link", "created_at", "redeemed_at", "redeemed_by")
    fields = (
        "note",
        "created_by",
        "link",
        "expires_at",
        "revoked_at",
        "redeemed_at",
        "redeemed_by",
        "created_at",
    )
    actions = ("revoke",)

    @admin.display(description="Invitation link")
    def link(self, invitation):
        """The whole URL, ready to paste into a message.

        Absolute, because a path is not something anybody can send. Falls back
        to the path before the row exists, where there is no id to build one
        from and nothing to copy yet.
        """
        if not invitation.pk:
            return "—"
        request = getattr(self, "_request", None)
        return (
            request.build_absolute_uri(invitation.path) if request else invitation.path
        )

    @admin.display(description="State")
    def state(self, invitation):
        """Said in words. `is_usable` is one boolean over four situations, and
        *spent* and *expired* need different things done about them."""
        if invitation.redeemed_at:
            return f"used by {invitation.redeemed_by or 'a deleted account'}"
        if invitation.revoked_at:
            return "revoked"
        return "live" if invitation.is_usable else "expired"

    @admin.action(description="Revoke selected invitations")
    def revoke(self, request, queryset):
        """Revoked, never deleted. The row is how *who have I invited* stays
        answerable, and deleting it would make the question quietly
        unanswerable — which is the model's whole reason for existing."""
        from django.utils import timezone

        updated = queryset.filter(revoked_at__isnull=True, redeemed_at__isnull=True)
        count = updated.update(revoked_at=timezone.now())
        self.message_user(request, f"{count} invitation(s) revoked.")

    def get_form(self, request, obj=None, **kwargs):
        # Stashed so `link` can build an absolute URL. ModelAdmin display
        # callables take only the object, and the host is not knowable without
        # the request.
        self._request = request
        return super().get_form(request, obj, **kwargs)

    def get_changelist_instance(self, request):
        self._request = request
        return super().get_changelist_instance(request)

    def save_model(self, request, obj, form, change):
        if not change and not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
