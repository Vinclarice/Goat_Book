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
from accounts.views import contact, home
from lists import views as list_views

from clarice.api import api as api_v1
from clarice.health import healthz, healthz_scheduled


urlpatterns = [
    # A landing page, not the login form. See accounts.views.home and
    # product-stories.md S1; the form is at /accounts/login/, which is where it
    # was always also reachable and where its rate limit already lived.
    path("", home, name="home"),
    # No trailing slash, and no login. An uptime monitor has no account, and
    # APPEND_SLASH would answer a polled `/healthz` with a 301 that several
    # services record as a failure. See clarice/health.py for what it checks
    # and why it says so little.
    path("healthz", healthz, name="healthz"),
    # A second monitor, not a second reason for the first one to go red. See
    # the view: a late cron job is not the website being down, and a check that
    # conflates them is a check somebody learns to ignore.
    path("healthz/scheduled", healthz_scheduled, name="healthz_scheduled"),
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
    # The knowledge core. **This is where it lives** -- Heron step 5, Vince's
    # call, August 15, 2026, and the decision that ends the crossover.
    #
    # The prefix was called temporary for a year's worth of reasons that all
    # expired within a day. Second Mind's pages sat at the root in their own
    # project and could not here, because "/" is this site's front door and
    # /api/v1/capture was defined by both cores; 4a made that endpoint the
    # application's one endpoint and 4b freed /capture/ by deleting the Inbox.
    #
    # Freed, and deliberately not taken. Nine routes sit under here and only
    # one of them is capture -- review, concepts, search, numbers, share and
    # the manifest are the rest -- so /capture/ would have named the smallest
    # thing in the room. Against that stood a live PWA shortcut and every
    # bookmark, both of which a move breaks for no gain. "Temporary" was a
    # reason to reconsider the name once the collision was gone, not an
    # obligation to move.
    #
    # It stays one line, and everything under it stays relative, so this is
    # still cheap to change if a better answer turns up.
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
