from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.csrf import ensure_csrf_cookie


def _spa_path(subpath):
    return reverse("app_shell_path", kwargs={"subpath": subpath})


@login_required
def dashboard(request):
    """Where a session lands, and the only place that decides it.

    This is LOGIN_REDIRECT_URL, so the login form, a bookmark of /dashboard/
    and the Django shell's own "Today" link all agree without any of them
    knowing the rule. Crane made the Daily Page the default; the preference
    is what keeps a default from being a redirect trap -- both surfaces stay
    directly reachable either way.
    """
    surface = (
        "day"
        if request.user.landing_surface == request.user.LandingSurface.DAY
        else "agenda"
    )
    return redirect(_spa_path(surface))


@login_required
def archive(request):
    return redirect(_spa_path("archive"))


@login_required
@ensure_csrf_cookie
def spa_shell(request, subpath=""):
    """Serves every /app/... path -- React Router owns routing from here.

    ensure_csrf_cookie because the SPA's mutations send X-CSRFToken and can
    only do that if something has handed the browser the cookie. This page
    renders no Django form, so until now that depended on the user having
    passed through one on the way in -- true via the login page, but an
    accident rather than a guarantee, and one that would break the moment
    login itself moves into the SPA.

    Deliberately not extending base.html. The original reason was that
    base.html still carried Bootstrap; that stopped being true when
    Bootstrap was retired (fda6176). It stays standalone now for a simpler
    reason: base.html renders the Django chrome (nav, messages) and this
    shell hands the whole page to React, which draws its own.

    /app/dev/... (the component gallery) 404s outside DEBUG -- it's a
    development aid, not something to ship. The route still exists in the
    built JS bundle either way; this only stops the page from loading.
    """
    if subpath.startswith("dev/") and not settings.DEBUG:
        raise Http404
    return render(request, "app_shell.html")


@login_required
def view_list(request, list_id):
    return redirect(_spa_path(f"areas/{list_id}"))


@login_required
def edit_item(request, item_id):
    return redirect(_spa_path(f"tasks/{item_id}"))
