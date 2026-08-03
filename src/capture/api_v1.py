"""The one capture endpoint a non-browser client needs.

Create-only, on purpose: reviewing and triaging what's been captured stays
browser-only (see design/capture-api-and-tokens-plan.md). A phone client
exists to get a thought out of your head in three seconds, which needs
exactly one verb.
"""
import uuid

from ninja import Router, Schema
from ninja.errors import HttpError

from accounts.auth import SessionAuthIfLoggedIn, TokenAuth
from capture.services import CaptureConflict, create_capture, create_capture_idempotent

router = Router()


class CaptureIn(Schema):
    text: str
    tags: list[str] = []


class CaptureOut(Schema):
    id: int
    created_at: str
    tags: list[str] = []


@router.post(
    "/capture",
    # 201 for a genuine write, 200 for an Idempotency-Key replay -- see
    # create_capture_idempotent. A caller that ignores the status and just
    # parses the body gets the same shape either way.
    response={201: CaptureOut, 200: CaptureOut},
    # Token first: ninja stops at the first auth that resolves, so a
    # bearer request never reaches the cookie auth's CSRF check, while a
    # browser request (no bearer header) falls through to it unchanged.
    # The session auth is the subclass rather than plain django_auth so a
    # *failed* token doesn't come back as "CSRF check Failed" -- see
    # accounts.auth.SessionAuthIfLoggedIn.
    auth=[TokenAuth(), SessionAuthIfLoggedIn()],
)
def new_capture(request, payload: CaptureIn):
    # Bittern M1: optional, mobile-only. A browser POST from CaptureForm's
    # own submit never sends this header, so that path is byte-for-byte
    # what it was before this existed -- see create_capture below.
    raw_key = request.headers.get("Idempotency-Key")
    idempotency_key = None
    if raw_key is not None:
        try:
            idempotency_key = uuid.UUID(raw_key)
        except ValueError:
            # The client owns retry identity; the server must not invent
            # or silently ignore a key it can't use.
            raise HttpError(400, "Idempotency-Key must be a UUID")

    try:
        if idempotency_key is not None:
            capture, created = create_capture_idempotent(
                request.user, payload.text, idempotency_key, tags=payload.tags
            )
        else:
            capture, created = (
                create_capture(request.user, payload.text, tags=payload.tags),
                True,
            )
    except CaptureConflict as error:
        # The same rule CaptureForm shows on the Inbox page, from the same
        # function -- there is one definition of "that's not a capture".
        raise HttpError(400, str(error))
    return (201 if created else 200), {
        "id": capture.id,
        "created_at": capture.created_at.isoformat(),
        # The replay branch's tags are already the original row's -- the
        # service layer, not this view, is what refuses to let a replay's
        # tags overwrite them.
        "tags": [tag.name for tag in capture.tags.all()],
    }
