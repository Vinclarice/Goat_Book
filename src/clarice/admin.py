"""The admin asks for a second factor — `admin-mfa-plan.md` increment 4.

**The whole of the enforcement, and deliberately small enough to read in one
sitting.** `OTPMiddleware` has supplied `request.user.is_verified()` since
increment 1; this is the one place that consults it.

**A subclass rather than `django_otp.admin.OTPAdminSite`** — §2.5: `unfold`
overrides admin templates, so `OTPAdminSite`'s bundled login form would render
into a template that does not know about it, and the screen would look like
neither core. Verification happens on `/accounts/verify/` instead, in this
application's own palette.

**Installed through `AdminConfig.default_site` rather than by assigning
`admin.site.__class__`.** django-otp's own README suggests the assignment and it
is wrong here: `django.contrib.admin.site` is a `DefaultAdminSite`, a lazy proxy
that builds the real site on first attribute access, so setting `__class__` on
it replaces the *proxy's* class and every request afterwards 302s to the login
page whatever the permissions say. Observed rather than reasoned about — the
first version of this did exactly that, and the admin index started returning
`NoReverseMatch` while changelists silently redirected. `default_site` is the
supported hook and resolves before the proxy ever materialises.

**Break-glass**, per §5 and written down before this shipped rather than after:
a lost phone *and* lost recovery codes leave one route — `docker exec clarice
./manage.py` on the droplet, deleting the device row. That is also the bound on
what this control is worth: shell on the host is equivalent to bypassing it. It
moves the bar from *knows a password* to *has shell on the host*, which is an
enormous move and not an unlimited one.
"""

from django.contrib.auth import REDIRECT_FIELD_NAME
from django.contrib.admin.apps import AdminConfig
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import urlencode
from unfold.sites import UnfoldAdminSite


class VerifiedAdminSite(UnfoldAdminSite):
    def has_permission(self, request):
        """Staff **and** verified.

        `super()` still decides whether this is somebody who may see the admin
        at all; this only adds whether they have proved it is them. Alongside
        the existing check, never instead of it.
        """
        return super().has_permission(request) and request.user.is_verified()

    def login(self, request, extra_context=None):
        """Send an unverified admin to `/accounts/verify/`, not back to a form.

        **Found in a production log, hours after this shipped.** Django's
        `AdminSite.login` redirects to the index only when `has_permission()` —
        which is precisely what is false for somebody who has a password and no
        second factor. So the sequence was `/admin/` → `/admin/login/` → log in
        → `/admin/` → `/admin/login/`, and the log shows five successful logins
        in a row. It reads to the person as *my password is not working*.

        **`/accounts/verify/` existed and nothing pointed at it** — the
        un-switched-on seam this codebase keeps shipping, committed by the very
        change meant to close one. Building the page is not wiring it up;
        `principles.md` says check for a caller, not for existence.

        **Only for somebody already authenticated and staff.** A stranger gets
        the ordinary login form: that a second factor exists is not a fact worth
        handing to somebody who has not proved they hold an account.
        """
        user = request.user
        if user.is_authenticated and user.is_active and user.is_staff:
            target = request.GET.get(REDIRECT_FIELD_NAME) or reverse(
                "admin:index", current_app=self.name
            )
            # `urlencode`, not an f-string: a `next` carrying a query of its
            # own -- a changelist with filters, which is most of them -- would
            # otherwise truncate at its first `&`.
            query = urlencode({REDIRECT_FIELD_NAME: target})
            return redirect(f"{reverse('verify')}?{query}")
        return super().login(request, extra_context)


class VerifiedAdminConfig(AdminConfig):
    default_site = "clarice.admin.VerifiedAdminSite"
