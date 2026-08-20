"""The knowledge core's router on the *shared* `/api/v1/`.

Not to be confused with `mind/api.py`, which is this app's own `NinjaAPI`
mounted at `/mind/api/v1/`. One letter apart and easy to confuse, so: **this**
module is a `Router` added to `clarice.api`, alongside `lists`, `daily`,
`review` and the rest, and it is what serves `POST /api/v1/capture` — the URL
every phone and the SPA's Day page already post to.

It replaces `capture/api_v1.py`, which wrote a `Capture`. Same URL, same bearer
token, same `capture:write` scope; different row. That is what lets step 4b
delete the `capture` app without anybody rebuilding an APK or logging in twice.

`mind/urls.py` predicted this: two cores defining `/api/v1/capture` was "the
dual-write question arriving early, and it is answered when facets land — one
capture endpoint that writes a node and optionally a task."

**Create-only for a token, still**, which is what that sentence always meant. A
phone client exists to get a thought out of your head in three seconds and
needs exactly one verb, and `test_api_auth_surface.py` holds the token set at
exactly the operations that serve it.

The question dispositions below are **session-only** and were added for the
weekly planning session (`planning-assistant-v2-plan.md` increment 6), which
reaches a knowledge-core record from the task core's review. They live here
rather than on a second API because `CLAUDE.md` says a knowledge-core endpoint
belongs on `/api/v1/` as a router in this module -- and they call `mind`'s own
services, so the core that owns the record still decides what happens to it.
"""

import uuid
from datetime import datetime

from django.utils import timezone
from ninja import Header, Router, Schema, Status
from ninja.errors import HttpError

from accounts.auth import SessionAuthIfLoggedIn, TokenAuth
from accounts.models import SCOPE_CAPTURE_WRITE

from . import services
from .models import Node, NodeSource

router = Router()


class CaptureIn(Schema):
    """What the Android client sends.

    Its own field names — `text`, not `content` — kept rather than changed,
    because the point of this endpoint is that an app with an encrypted offline
    queue and a share-sheet handler already built needs no Kotlin changes.
    """

    text: str = ""
    tags: list[str] = []
    captured_at: datetime | None = None
    """When the thought was written, which for a queued client is not when it
    arrives.

    Optional, so a client that predates the field falls back to now — correct
    for anything captured while connected, and the only honest answer when
    nobody said otherwise.

    This endpoint used to omit the field entirely, so Ninja dropped it in
    silence while both Android call sites were faithfully sending it. Every
    thought that had waited in the queue was stamped with the moment the network
    came back; six of them landed on the same second during the August 14, 2026
    device pass, which is how it was found. The fix went to `/mind/api/v1/capture`,
    which nothing calls, and the defect stayed live here for a day.
    """


class CaptureOut(Schema):
    public_id: uuid.UUID
    captured_at: datetime


@router.post(
    "/capture",
    # 201 for a genuine write, 200 for an Idempotency-Key replay. Both mean the
    # thought is safe, and the client treats them identically -- see
    # CaptureContract.kt. The distinction exists so a phone can tell whether its
    # earlier attempt had in fact landed.
    response={201: CaptureOut, 200: CaptureOut},
    # Token first: ninja stops at the first auth that resolves, so a bearer
    # request never reaches the cookie auth's CSRF check, while a browser request
    # falls through to it unchanged. The session auth is the subclass rather than
    # plain django_auth so a *failed* token doesn't come back as "CSRF check
    # Failed" -- see accounts.auth.SessionAuthIfLoggedIn.
    #
    # capture:write, unchanged from when this endpoint wrote a Capture. That is
    # not incidental: it is what means every token already issued to a phone
    # keeps working, with no reconnect and no re-scoping.
    auth=[TokenAuth(SCOPE_CAPTURE_WRITE), SessionAuthIfLoggedIn()],
)
def new_capture(
    request,
    payload: CaptureIn,
    idempotency_key: str = Header(default="", alias="Idempotency-Key"),
):
    """Record a thought as a node.

    `Idempotency-Key` is a UUID the client owns, which is precisely what
    `public_id` already is — so retry safety here is the graph's own mechanism
    rather than a parallel one. The server must not invent or silently ignore a
    key it cannot use.
    """
    try:
        public_id = uuid.UUID(idempotency_key) if idempotency_key else None
    except ValueError:
        raise HttpError(400, "Idempotency-Key must be a UUID")

    # Which client this was, not which client this endpoint was built for. It
    # hard-coded MOBILE for every caller until August 16, 2026, so a thought
    # typed into the Day page's quick-capture box was recorded as having come
    # from a phone -- noticed by reading an account export, where the label is
    # shown to the person it is wrong about.
    #
    # A bearer token means a native client; a session means a browser. There is
    # no third case here, because those are the only two auth classes this
    # operation accepts.
    from_a_phone = getattr(request, "token_authenticated", False)

    try:
        node, created = services.capture_idempotent(
            request.user,
            content=payload.text,
            # Now only when nobody said. Guessing a time would be worse than
            # having none, because a temporal detector cannot tell the two apart.
            captured_at=payload.captured_at or timezone.now(),
            source=NodeSource.MOBILE if from_a_phone else NodeSource.WEB,
            actor=request.user.get_username(),
            public_id=public_id,
            tags=payload.tags,
        )
    # 400, never 422 or 409. A queued client treats anything other than
    # 400/401/403 as "retry later", so an unprocessable body returned as 422
    # would be retried forever against a server that will never accept it. Both
    # of these are permanent faults in the request, which is what 400 means to
    # that client.
    except services.EmptyNode as error:
        raise HttpError(400, str(error))
    except services.NotYours:
        raise HttpError(400, "that id belongs to someone else")

    return Status(
        201 if created else 200,
        {"public_id": node.public_id, "captured_at": node.captured_at},
    )


class QuestionOut(Schema):
    public_id: uuid.UUID


def _question_or_404(request, public_id):
    """This owner's live question, by public id.

    Owner-scoped in the lookup rather than checked afterwards: a read that
    fetched by id and then compared owners is one forgotten comparison away
    from a leak, which is `principles.md`'s rule for every ID-taking surface.
    """
    node = Node.objects.filter(
        owner=request.user,
        public_id=public_id,
        deleted_at__isnull=True,
        archived_at__isnull=True,
    ).first()
    if node is None:
        raise HttpError(404, "Question not found.")
    return node


@router.post("/questions/{public_id}/answered", response=QuestionOut, auth=SessionAuthIfLoggedIn())
def mark_question_answered(request, public_id: uuid.UUID):
    """"I settled this", with nothing to point at.

    The knowledge core's own service does the work, so the epistemic facet, the
    activity event and the actor are recorded exactly as they are when this is
    answered from `/mind/review/`. Two surfaces, one decision path.
    """
    node = _question_or_404(request, public_id)
    services.resolve_question(
        node, now=timezone.now(), actor=request.user.get_username()
    )
    return {"public_id": node.public_id}


@router.post("/questions/{public_id}/not-a-question", response=QuestionOut, auth=SessionAuthIfLoggedIn())
def mark_not_a_question(request, public_id: uuid.UUID):
    """"This was never a question."

    A different fact from answering it, deliberately, and the reason is at the
    service: this is the only correction the question heuristic will ever get,
    and collapsing the two would spend that signal to save a status value.
    """
    node = _question_or_404(request, public_id)
    services.dismiss_as_question(
        node, now=timezone.now(), actor=request.user.get_username()
    )
    return {"public_id": node.public_id}
