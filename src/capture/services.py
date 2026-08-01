"""What a capture can turn into, and how it turns back.

Every rule a capture or an idea has to satisfy lives here rather than in a
view, for the same reason lists.services exists: there are now several
entry points (the Inbox, the Ideas page, the API) and one of them being
subtly more permissive than the others is how data goes wrong quietly.
"""
from django.db import IntegrityError, transaction
from django.utils import timezone

from capture.models import Capture, Idea
from lists import services as list_services


EMPTY_CAPTURE_ERROR = "Write something down first"
EMPTY_IDEA_ERROR = "An idea needs some text"
ALREADY_RESOLVED_ERROR = "That capture has already been triaged"
NOT_RESOLVED_ERROR = "That capture is still in the inbox"
PROMOTED_IDEA_LOCKED_ERROR = "This idea is a task now -- edit the task instead"
ALREADY_PROMOTED_ERROR = "That idea has already become a task"


class CaptureConflict(Exception):
    pass


def normalize_capture_text(text):
    normalized = (text or "").strip()
    if not normalized:
        raise CaptureConflict(EMPTY_CAPTURE_ERROR)
    return normalized


def create_capture(owner, text):
    return Capture.objects.create(owner=owner, text=normalize_capture_text(text))


def create_capture_idempotent(owner, text, idempotency_key):
    """Bittern M1: a mobile client's retry-safe write.

    The browser path above is untouched -- CaptureForm always calls
    create_capture directly, with no key, exactly as it did before this
    existed. This is only for POST /api/v1/capture with an
    Idempotency-Key header: a request whose response got lost and was
    retried must produce one row, not two.

    Returns (capture, created) so the caller can answer 201 for a genuine
    write and 200 for a replay without a second query to tell them apart.
    """
    normalized = normalize_capture_text(text)
    try:
        with transaction.atomic():
            capture = Capture.objects.create(
                owner=owner, text=normalized, idempotency_key=idempotency_key
            )
        return capture, True
    except IntegrityError:
        # Lost the constraint race, or this genuinely is a retry: a row
        # for this (owner, key) already exists. Return it as recorded
        # rather than this call's text -- the first successful write is
        # the one of record, the same rule every other "already happened"
        # outcome in this app follows (see _triage's ALREADY_RESOLVED_ERROR
        # below).
        return (
            Capture.objects.get(owner=owner, idempotency_key=idempotency_key),
            False,
        )


def edit_capture(capture, text):
    """Fix a typo in something still sitting in the inbox.

    Guarded on resolution rather than on time: once a capture has become a
    task or an idea, that downstream record is the live one, and editing
    the capture behind it would leave the two disagreeing about what was
    actually captured. Same shape as lists.services.edit_item refusing to
    edit an archived task.
    """
    if capture.resolved_at is not None:
        raise CaptureConflict(ALREADY_RESOLVED_ERROR)
    capture.text = normalize_capture_text(text)
    capture.save(update_fields=["text"])
    return capture


def _resolve(capture, resolution, task=None, idea=None):
    capture.resolution = resolution
    capture.resolved_at = timezone.now()
    capture.promoted_task = task
    capture.promoted_idea = idea
    capture.save(
        update_fields=[
            "resolution", "resolved_at", "promoted_task", "promoted_idea",
        ]
    )
    return capture


def _require_unresolved(capture):
    # Every triage action checks this rather than trusting the Inbox to
    # only ever offer buttons for unresolved rows: a double-click, a stale
    # tab or a back button all reach these views with a capture that has
    # already moved on.
    if capture.resolved_at is not None:
        raise CaptureConflict(ALREADY_RESOLVED_ERROR)


@transaction.atomic
def promote_to_task(capture, for_list):
    """Capture -> Item, with the text carried across verbatim.

    Due date, tags and the rest get set afterwards through the normal task
    UI. Triage is about deciding *what a thing is*, and making it also be
    the moment you schedule it would put the friction back that capture
    exists to remove.
    """
    _require_unresolved(capture)
    # Deliberately not caught: a duplicate title raises TaskConflict, the
    # view reports it, and the capture stays in the inbox. Silently
    # resolving it against a task that already existed would lose the
    # thought.
    task = list_services.create_item(for_list, capture.text)
    return _resolve(capture, Capture.Resolution.TASK, task=task)


@transaction.atomic
def promote_to_idea(capture, status):
    _require_unresolved(capture)
    if status not in (Idea.Status.EXPLORING, Idea.Status.REFERENCE):
        # Not PROMOTED: that status is something an idea reaches later, by
        # becoming a task, never a state it can be born in.
        raise CaptureConflict("Choose exploring or reference")
    idea = Idea.objects.create(
        owner=capture.owner, text=capture.text, status=status
    )
    return _resolve(capture, Capture.Resolution.IDEA, idea=idea)


@transaction.atomic
def discard_capture(capture):
    """Soft: the row stays, marked discarded.

    A zero-friction capture box catches a lot of things that turn out to be
    nothing, and that's the box working, not failing. Keeping the row is
    what makes discard undoable like the other two outcomes, and what keeps
    "every capture says what happened to it" true.
    """
    _require_unresolved(capture)
    return _resolve(capture, Capture.Resolution.DISCARDED)


@transaction.atomic
def undo_resolution(capture):
    """Puts a capture back in the inbox exactly as it was.

    Deletes whatever the resolution created, which is safe precisely
    because undo is offered for one page load: nothing else has had time to
    reference the new task or idea. If the created row is already gone
    (SET_NULL left the FK null), there is simply nothing to delete.
    """
    if capture.resolved_at is None:
        raise CaptureConflict(NOT_RESOLVED_ERROR)
    if capture.promoted_task is not None:
        capture.promoted_task.delete()
    if capture.promoted_idea is not None:
        capture.promoted_idea.delete()
    capture.resolution = ""
    capture.resolved_at = None
    capture.promoted_task = None
    capture.promoted_idea = None
    capture.save(
        update_fields=[
            "resolution", "resolved_at", "promoted_task", "promoted_idea",
        ]
    )
    return capture


def normalize_idea_text(text):
    normalized = (text or "").strip()
    if not normalized:
        raise CaptureConflict(EMPTY_IDEA_ERROR)
    return normalized


def edit_idea(idea, text, notes):
    """Ideas stay editable for as long as they're ideas -- unlike captures,
    which lock the moment they're triaged.

    The difference is deliberate: a capture is a record of what you wrote
    down, an idea is a thing you're actively working on. Promotion is what
    ends that, because from then on the task is the live record.
    """
    if idea.status == Idea.Status.PROMOTED:
        raise CaptureConflict(PROMOTED_IDEA_LOCKED_ERROR)
    idea.text = normalize_idea_text(text)
    idea.notes = (notes or "").strip()
    idea.save(update_fields=["text", "notes"])
    return idea


@transaction.atomic
def promote_idea_to_task(idea, for_list):
    """Idea -> Item, carrying the notes across so thinking already recorded
    isn't stranded on a page you stop visiting.
    """
    if idea.status == Idea.Status.PROMOTED:
        raise CaptureConflict(ALREADY_PROMOTED_ERROR)
    task = list_services.create_item(for_list, idea.text)
    if idea.notes:
        list_services.set_item_notes(task, idea.notes)
    idea.status = Idea.Status.PROMOTED
    idea.promoted_task = task
    idea.save(update_fields=["status", "promoted_task"])
    return idea


def delete_idea(idea):
    """Hard, immediate, no undo -- unlike discarding a capture.

    By the time something is a standalone idea you're managing it, not
    moving it through a queue, and "not worth keeping" should mean it.
    A capture that promoted into this idea keeps its own history: its
    resolution still reads "idea", and SET_NULL just empties the pointer.
    """
    idea.delete()
