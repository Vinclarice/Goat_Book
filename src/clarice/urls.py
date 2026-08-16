"""
URL configuration for clarice project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView
from accounts.views import LandingLoginView, contact
from lists import views as list_views

from clarice.api import api as api_v1
from clarice.health import healthz


urlpatterns = [
    path("", LandingLoginView.as_view(), name="home"),
    # No trailing slash, and no login. An uptime monitor has no account, and
    # APPEND_SLASH would answer a polled `/healthz` with a 301 that several
    # services record as a failure. See clarice/health.py for what it checks
    # and why it says so little.
    path("healthz", healthz, name="healthz"),
    # Public and unauthenticated, hence the root rather than under
    # accounts/: a stranger with a question does not have an account.
    path("contact/", contact, name="contact"),
    path("dashboard/", list_views.dashboard, name="dashboard"),
    path("archive/", list_views.archive, name="archive"),
    path("app/", list_views.spa_shell, name="app_shell"),
    path("app/<path:subpath>", list_views.spa_shell, name="app_shell_path"),
    path("api/", include("lists.api_urls")),
    path("api/v1/", api_v1.urls),
    path("areas/", include("lists.urls")),
    # An Area used to be a List, and both of these paths only ever redirect
    # into the SPA anyway. Kept so a bookmark from before Release D slice 5
    # lands where it used to rather than 404ing; the url names stay on the
    # canonical /areas/ entries above, so nothing generates these.
    path(
        "lists/<int:list_id>/",
        RedirectView.as_view(pattern_name="view_list", permanent=False),
    ),
    path("accounts/", include("accounts.urls")),
    # The knowledge core, under a prefix during the crossover. Second Mind's
    # pages sat at the root in their own project and could not here: "/" is
    # this site's landing login, and /api/v1/capture was defined by both cores.
    #
    # Both halves of that are now resolved. Heron 4a made /api/v1/capture the
    # application's one endpoint, and 4b freed /capture/ by deleting the Inbox.
    # What remains is choosing where these pages sit, which is step 5 -- still
    # one line, and now an ordinary move rather than one that could break a
    # phone.
    path("mind/", include("mind.urls")),
    # Has to sit BEFORE the admin include, not just for tidiness:
    # admin.site.urls is itself a resolver mounted at admin/, so a later
    # entry would never be reached -- Django would look for
    # admin/password_reset/ inside the admin's own URLconf and 404. The
    # admin login template renders its "Forgot your password?" link with
    # {% url 'admin_password_reset' as ... %}, which silently renders
    # nothing when the name doesn't resolve, so registering the name here
    # is what makes that link appear at all.
    path(
        "admin/password_reset/",
        RedirectView.as_view(pattern_name="password_reset", permanent=False),
        name="admin_password_reset",
    ),
    path("admin/", admin.site.urls),
]
