"""The one capture endpoint a non-browser client needs.

Create-only, on purpose: reviewing and triaging what's been captured stays
browser-only (see design/capture-api-and-tokens-plan.md). A phone client
exists to get a thought out of your head in three seconds, which needs
exactly one verb.
"""
from ninja import Router, Schema
from ninja.errors import HttpError

from accounts.auth import SessionAuthIfLoggedIn, TokenAuth
from capture.services import CaptureConflict, create_capture

router = Router()


class CaptureIn(Schema):
    text: str


class CaptureOut(Schema):
    id: int
    created_at: str


@router.post(
    "/capture",
    response={201: CaptureOut},
    # Token first: ninja stops at the first auth that resolves, so a
    # bearer request never reaches the cookie auth's CSRF check, while a
    # browser request (no bearer header) falls through to it unchanged.
    # The session auth is the subclass rather than plain django_auth so a
    # *failed* token doesn't come back as "CSRF check Failed" -- see
    # accounts.auth.SessionAuthIfLoggedIn.
    auth=[TokenAuth(), SessionAuthIfLoggedIn()],
)
def new_capture(request, payload: CaptureIn):
    try:
        capture = create_capture(request.user, payload.text)
    except CaptureConflict as error:
        # The same rule CaptureForm shows on the Inbox page, from the same
        # function -- there is one definition of "that's not a capture".
        raise HttpError(400, str(error))
    return 201, {
        "id": capture.id,
        "created_at": capture.created_at.isoformat(),
    }
