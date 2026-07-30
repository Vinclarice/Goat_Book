from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
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
def spa_shell(request, subpath=""):
    """Serves every /app/... path -- React Router owns routing from here.

    Deliberately not extending base.html: that still carries Bootstrap,
    and this shell has nothing to style yet (see the UI overhaul plan's
    Step 2c/Step 3 split).

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
