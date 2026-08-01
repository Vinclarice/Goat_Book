from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from capture import services
from capture.forms import CaptureForm, IdeaForm
from capture.models import Capture, Idea
from lists.models import List
from lists.services import TaskServiceError

# The two ways a triage action can refuse: a capture-side rule (already
# resolved, no text) or a lists-side one -- promoting into a list that
# already has a task by that name raises TaskConflict from create_item.
TRIAGE_ERRORS = (services.CaptureConflict, TaskServiceError)


def _owned_capture(request, capture_id):
    # Ownership lives in the lookup rather than in a check afterwards --
    # same shape as lists.api_v1._owned_list -- so no code path can load
    # someone else's capture in the first place, and an intruder gets the
    # 404 that doesn't confirm the row exists.
    return get_object_or_404(Capture, id=capture_id, owner=request.user)


def _owned_idea(request, idea_id):
    return get_object_or_404(Idea, id=idea_id, owner=request.user)


def _owned_list(request):
    """The list a promote-to-task action names, out of the POST body.

    The id arrives in a body rather than a path, which is the case
    lists/tests/test_isolation.py singles out as the one most likely to be
    resolved with an unscoped query. It isn't here.
    """
    return get_object_or_404(
        List, id=request.POST.get("list") or 0, owner=request.user
    )


def _render_inbox(request, form):
    """The Inbox and the capture box are one page, so both the GET and the
    invalid-POST path have to build the same context.
    """
    query = request.GET.get("q", "").strip()
    captures = Capture.objects.filter(owner=request.user, resolved_at__isnull=True)
    if query:
        captures = captures.filter(text__icontains=query)
    captures = list(captures)
    # Popped, not read: undo is offered for exactly one page load after a
    # triage action, which is also what makes it safe to delete whatever
    # that action created (see services.undo_resolution).
    undo_id = request.session.pop("undo_capture_id", None)
    return render(
        request,
        "capture/inbox.html",
        {
            "form": form,
            "captures": captures,
            "query": query,
            # The count the nav badge already shows, plus how long the
            # oldest one has been sitting there: an inbox is only useful if
            # it's visibly finite, and "12 waiting, oldest from March" says
            # something "12 waiting" doesn't.
            "oldest": min((each.created_at for each in captures), default=None),
            "lists": List.objects.filter(owner=request.user),
            "undo_capture": Capture.objects.filter(
                id=undo_id, owner=request.user, resolved_at__isnull=False
            ).first(),
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
def edit_capture(request, capture_id):
    """Fixing a typo in something you fired off in three seconds.

    Its own page rather than an inline form: the Inbox is a triage surface
    and every row already carries four buttons, so a fifth control that
    expands into a textarea would crowd out the decision the page exists
    to help you make.
    """
    capture = _owned_capture(request, capture_id)
    form = CaptureForm(data=request.POST or None, initial={"text": capture.text})
    if request.method == "POST" and form.is_valid():
        try:
            services.edit_capture(capture, form.cleaned_data["text"])
        except services.CaptureConflict as error:
            form.add_error(None, str(error))
        else:
            messages.success(request, "Capture updated.")
            return redirect("capture_inbox")

    return render(
        request, "capture/edit_capture.html", {"form": form, "capture": capture}
    )


def _triage(request, capture_id, action):
    """The shape every triage action shares: resolve it, offer one undo,
    and report a conflict rather than pretending it worked.
    """
    capture = _owned_capture(request, capture_id)
    try:
        action(capture)
    except TRIAGE_ERRORS as error:
        messages.error(request, str(error))
    else:
        request.session["undo_capture_id"] = capture.id
    return redirect("capture_inbox")


@login_required
@require_POST
def promote_capture_to_task(request, capture_id):
    for_list = _owned_list(request)
    return _triage(
        request, capture_id, lambda capture: services.promote_to_task(capture, for_list)
    )


@login_required
@require_POST
def promote_capture_to_idea(request, capture_id):
    status = request.POST.get("status")
    return _triage(
        request, capture_id, lambda capture: services.promote_to_idea(capture, status)
    )


@login_required
@require_POST
def discard_capture(request, capture_id):
    return _triage(request, capture_id, services.discard_capture)


@login_required
@require_POST
def undo_capture(request, capture_id):
    capture = _owned_capture(request, capture_id)
    try:
        services.undo_resolution(capture)
    except services.CaptureConflict as error:
        messages.error(request, str(error))
    else:
        messages.success(request, "Put back in your inbox.")
    return redirect("capture_inbox")


@login_required
def ideas(request):
    """Everything you kept that isn't a task.

    Promoted ideas drop out of the default view -- the task is the live
    record once one exists -- but the row survives and stays reachable
    under the Promoted filter, so the Capture -> Idea -> Task lineage can
    still be followed after the fact.
    """
    status = request.GET.get("status", "")
    query = request.GET.get("q", "").strip()
    found = Idea.objects.filter(owner=request.user)
    if status in Idea.Status.values:
        found = found.filter(status=status)
    else:
        status = ""
        found = found.exclude(status=Idea.Status.PROMOTED)
    if query:
        # Substring, not ranked full-text search: a reference archive
        # nobody can search fails at its one job, and ranking only starts
        # to matter at a volume this doesn't have yet.
        found = found.filter(Q(text__icontains=query) | Q(notes__icontains=query))
    return render(
        request,
        "capture/ideas.html",
        {
            # Every idea renders its own edit form on one page, so the
            # auto-generated field ids have to be per-idea or the labels
            # all point at whichever form rendered first.
            "ideas": [
                (
                    idea,
                    IdeaForm(
                        initial={"text": idea.text, "notes": idea.notes},
                        auto_id=f"idea-{idea.id}-%s",
                    ),
                )
                for idea in found
            ],
            "status": status,
            "query": query,
            "statuses": Idea.Status.choices,
            "lists": List.objects.filter(owner=request.user),
        },
    )


@login_required
@require_POST
def edit_idea(request, idea_id):
    idea = _owned_idea(request, idea_id)
    form = IdeaForm(data=request.POST)
    if not form.is_valid():
        messages.error(request, form.errors["text"][0])
        return redirect("ideas")
    try:
        services.edit_idea(idea, form.cleaned_data["text"], form.cleaned_data["notes"])
    except services.CaptureConflict as error:
        messages.error(request, str(error))
    else:
        messages.success(request, "Idea updated.")
    return redirect("ideas")


@login_required
@require_POST
def promote_idea(request, idea_id):
    idea = _owned_idea(request, idea_id)
    for_list = _owned_list(request)
    try:
        services.promote_idea_to_task(idea, for_list)
    except TRIAGE_ERRORS as error:
        messages.error(request, str(error))
    else:
        messages.success(request, f'"{idea.text}" is a task now.')
    return redirect("ideas")


@login_required
@require_POST
def delete_idea(request, idea_id):
    idea = _owned_idea(request, idea_id)
    services.delete_idea(idea)
    # No undo, unlike discarding a capture -- see services.delete_idea for
    # why that asymmetry is deliberate.
    messages.success(request, "Idea deleted.")
    return redirect("ideas")
