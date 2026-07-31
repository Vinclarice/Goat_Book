from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from capture.forms import CaptureForm
from capture.models import Capture


def _render_inbox(request, form):
    """The Inbox and the capture box are one page, so both the GET and the
    invalid-POST path have to build the same context.

    Ownership is enforced in the queryset rather than checked afterwards --
    same shape as lists.api_v1._owned_list -- so there is no code path that
    can load someone else's capture in the first place.
    """
    return render(
        request,
        "capture/inbox.html",
        {
            "form": form,
            "captures": Capture.objects.filter(
                owner=request.user,
                resolved_at__isnull=True,
            ),
        },
    )


@login_required
def inbox(request):
    return _render_inbox(request, CaptureForm())


@login_required
@require_POST
def new_capture(request):
    """Post-Redirect-Get: a capture is something you fire off and walk away
    from, so a successful POST lands back on a fresh, empty Inbox that a
    reload won't re-submit.

    An invalid POST re-renders the Inbox at HTTP 200 with the bound form,
    matching lists.views.new_list -- the typed text is the thing being
    protected, and a redirect would throw it away.
    """
    form = CaptureForm(data=request.POST)
    if form.is_valid():
        form.save(owner=request.user)
        return redirect("capture_inbox")

    return _render_inbox(request, form)


@login_required
@require_POST
def resolve_capture(request, capture_id):
    """The only triage affordance there is: it takes a capture out of the
    Inbox without recording what became of it. Anything richer would be
    inventing the triage model the roadmap checkpoint defers.
    """
    # resolved_at__isnull is part of the lookup, not a check afterwards: a
    # re-POST (double-click, stale tab, back button) would otherwise
    # overwrite the original resolution time with a later one.
    capture = get_object_or_404(
        Capture, id=capture_id, owner=request.user, resolved_at__isnull=True
    )
    capture.resolved_at = timezone.now()
    capture.save(update_fields=["resolved_at"])
    messages.success(request, "Capture cleared.")
    return redirect("capture_inbox")
