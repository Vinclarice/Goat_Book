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
from datetime import date, datetime

from django.utils import timezone
from ninja import Header, Router, Schema, Status
from ninja.errors import HttpError

from accounts.auth import SessionAuthIfLoggedIn, TokenAuth
from accounts.models import SCOPE_CAPTURE_WRITE
from clarice.search import to_query
from daily import reads as daily_reads
from lists import search as lists_search

from . import queries, services
from .models import ConceptCandidate, Facet, FacetKind, Node, NodeSource

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


class CommitmentOut(Schema):
    id: int


class ConceptOut(Schema):
    public_id: uuid.UUID


def _unanswered_commitment_or_404(request, facet_id):
    """This owner's undecided actionable facet, by id.

    Owner-scoped in the lookup, like `_question_or_404` above and for the
    identical reason. Also scoped to *undecided*: a facet already confirmed or
    already retired is not a loose end, and answering one twice from a stale
    page must not accept a commitment somebody dismissed an hour ago.
    """
    facet = Facet.objects.filter(
        id=facet_id,
        kind=FacetKind.ACTIONABLE,
        confirmed_at__isnull=True,
        retired_at__isnull=True,
    ).first()
    # `Facet.owner` is a property over its node or entry, not a column, so the
    # ownership check cannot go in the filter above -- the one place in this
    # module where it is after the lookup rather than in it.
    if facet is None or facet.owner != request.user:
        raise HttpError(404, "Commitment not found.")
    return facet


def _concept_or_404(request, public_id):
    concept = ConceptCandidate.objects.filter(
        owner=request.user, public_id=public_id, retired_at__isnull=True
    ).first()
    if concept is None:
        raise HttpError(404, "Name not found.")
    return concept


@router.post("/commitments/{facet_id}/accept", response=CommitmentOut, auth=SessionAuthIfLoggedIn())
def accept_commitment(request, facet_id: int):
    """Turn a proposal the review is showing into a real task.

    **No Area is asked for**, which is `confirm_actionable`'s own decision
    inherited rather than re-taken: requiring one puts a filing question at
    exactly the moment somebody has already made a different decision. `Item.owner`
    is what makes an unfiled task a real task.
    """
    facet = _unanswered_commitment_or_404(request, facet_id)
    services.confirm_actionable(
        facet, now=timezone.now(), actor=request.user.get_username()
    )
    return {"id": facet.id}


@router.post("/commitments/{facet_id}/dismiss", response=CommitmentOut, auth=SessionAuthIfLoggedIn())
def dismiss_commitment(request, facet_id: int):
    """"This was not a commitment." A different fact from accepting it, and
    the one signal the commitment parser will ever get about a false positive.
    """
    facet = _unanswered_commitment_or_404(request, facet_id)
    services.dismiss_facet(
        facet, now=timezone.now(), actor=request.user.get_username()
    )
    return {"id": facet.id}


@router.post("/concepts/{public_id}/confirm", response=ConceptOut, auth=SessionAuthIfLoggedIn())
def confirm_name(request, public_id: uuid.UUID):
    """Admit a recurring name to the trusted corpus -- always a person's
    decision, which is why it has never had an automatic path."""
    concept = _concept_or_404(request, public_id)
    services.confirm_concept(
        concept, now=timezone.now(), actor=request.user.get_username()
    )
    return {"public_id": concept.public_id}


@router.post("/concepts/{public_id}/retire", response=ConceptOut, auth=SessionAuthIfLoggedIn())
def retire_name(request, public_id: uuid.UUID):
    """"That is not a thing", permanently.

    Permanent because extraction runs again after every batch of captures, so
    without a record a rejected name would be re-proposed forever -- and a
    queue that re-asks answered questions is one somebody stops trusting.
    """
    concept = _concept_or_404(request, public_id)
    services.retire_concept(
        concept, now=timezone.now(), actor=request.user.get_username()
    )
    return {"public_id": concept.public_id}


# How many results any one section returns. The same number the page uses, so
# the API and `/mind/search/` cannot disagree about what "the closest matches"
# means for the same query.
SEARCH_LIMIT = 30


class TaskResultOut(Schema):
    id: int
    text: str
    notes: str
    # Carried because search returns every status where the agenda hides
    # finished work -- the older a task is, the more likely it is both done and
    # the one being looked for. A completed task in a result list with nothing
    # saying so is worse than not returning it.
    status: str
    due_date: date | None


class DayResultOut(Schema):
    date: date
    intentions: str
    gratitude: str
    happenings: str


class NoteResultOut(Schema):
    public_id: uuid.UUID
    body: str
    captured_at: datetime
    # Matched only in text that has since been edited away. The original is
    # preserved on purpose, so this is the design working -- but without the
    # label a person is shown a note that does not contain the word they typed.
    superseded: bool


class SearchOut(Schema):
    """Three sections, each ranked and counted on its own.

    **Never one merged list.** `SearchRank` compares documents within one set
    and means nothing across two, so a combined ordering would be a number that
    does not exist, presented as relevance. `design/search-plan.md` rejects the
    merged list rather than deferring it: validating a weighting would need the
    retrieval evidence that does not exist yet.

    Each `*_total` is counted before slicing. A section showing three of thirty
    and saying nothing invites the miss button to be pressed for something it
    simply did not show, which records a truncation as a retrieval failure in
    the one signal where the right answer is known.
    """

    tasks: list[TaskResultOut]
    tasks_total: int
    days: list[DayResultOut]
    days_total: int
    notes: list[NoteResultOut]
    notes_total: int


# DARK: no client. Nothing calls this -- the SPA links to `/mind/search/`, the
# server-rendered page, and Android does not search at all. `/api/v1/search`
# appears in `frontend/src/api/schema.ts` only because that file is generated
# from this one.
#
# **Provable here, where it usually is not.** An endpoint's absent caller
# normally proves little, since a token in somebody's keystore or a script can
# call it without this repository knowing. The `auth=` below is what closes
# that: session only, so the sole possible caller is a browser holding a
# session, and the only browser code is the SPA.
#
# Kept rather than deleted because it is not a spare -- it is the same read the
# page performs, and `SEARCH_LIMIT` above exists so the two cannot disagree.
# Deleting it would make the SPA's eventual search a rebuild rather than a call.
# Trigger: the SPA searching in its own surface instead of linking out to the
# knowledge core's page -- which `search-plan.md`'s D4 declined to do as a
# command palette, on the grounds that a cleared precondition is not a trigger.
@router.get(
    "/search",
    response=SearchOut,
    # Session only, and deliberately not a token. `test_api_auth_surface.py`
    # holds the token set at the operations a phone needs, and this is not one:
    # a capture client exists to get a thought out of your head in three
    # seconds. Widening a bearer that sits in a keystore for ninety days to
    # read every task, day and note somebody owns is the largest single
    # widening available here, and it should be asked for rather than arrive
    # with a search box.
    auth=SessionAuthIfLoggedIn(),
)
def search(request, q: str = ""):
    """Everything this owner has written that matches `q`.

    D1's answer, August 20, 2026: here, in the knowledge core's router on the
    shared API, rather than in a new one. Search is not owned by either core --
    it reads `Item`, `DailyEntry` and `Node` -- and `CLAUDE.md`'s rule is one
    API with a knowledge-core endpoint as a router in this module. The
    alternative was `clarice` growing its first router, which is a bigger
    precedent than this needed to set.

    One query parse for all three sections, via `clarice.search`. Three sections
    that disagreed about whether a second word narrows would look like a ranking
    bug and would not be one.
    """
    query = to_query(q)
    if query is None:
        return {
            "tasks": [], "tasks_total": 0,
            "days": [], "days_total": 0,
            "notes": [], "notes_total": 0,
        }

    matching_tasks = lists_search.search_tasks(request.user, q)
    tasks_total = matching_tasks.count()

    matching_days = daily_reads.search_entries(request.user, q)
    days_total = matching_days.count()

    matching_notes = queries.search_ranked(request.user, query)
    notes_total = matching_notes.count()
    nodes = list(matching_notes[:SEARCH_LIMIT])
    current = queries.current_text_matches(nodes, query)

    return {
        "tasks": list(matching_tasks[:SEARCH_LIMIT]),
        "tasks_total": tasks_total,
        "days": list(matching_days[:SEARCH_LIMIT]),
        "days_total": days_total,
        "notes": [
            {
                "public_id": node.public_id,
                "body": queries.current_body(node),
                "captured_at": node.captured_at,
                "superseded": node.pk not in current,
            }
            for node in nodes
        ],
        "notes_total": notes_total,
    }
