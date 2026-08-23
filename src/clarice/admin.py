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

from django.contrib.admin.apps import AdminConfig
from unfold.sites import UnfoldAdminSite


class VerifiedAdminSite(UnfoldAdminSite):
    def has_permission(self, request):
        """Staff **and** verified.

        `super()` still decides whether this is somebody who may see the admin
        at all; this only adds whether they have proved it is them. Alongside
        the existing check, never instead of it.
        """
        return super().has_permission(request) and request.user.is_verified()


class VerifiedAdminConfig(AdminConfig):
    default_site = "clarice.admin.VerifiedAdminSite"
