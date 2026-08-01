from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST

from lists.forms import NewListForm


def _spa_path(subpath):
    return reverse("app_shell_path", kwargs={"subpath": subpath})


@login_required
def dashboard(request):
    return redirect(_spa_path("agenda"))


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
@require_POST
def new_list(request):
    """Still a real Django view, not a Ninja endpoint: creating a list was
    never migrated onto the SPA/API -- AgendaWorkspace's "+ New list" form
    is a plain HTML POST straight here (see AgendaWorkspace.tsx), since
    the resulting navigation to the new list's page is exactly what a
    fetch-based flow would have to fake anyway.
    """
    form = NewListForm(data=request.POST)
    if form.is_valid():
        new_list = form.save(owner=request.user)
        return redirect(new_list)

    return render(request, "new_list_form.html", {"form": form})


@login_required
def view_list(request, list_id):
    return redirect(_spa_path(f"lists/{list_id}"))


@login_required
def edit_item(request, item_id):
    return redirect(_spa_path(f"tasks/{item_id}"))
