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
from typing import Literal, get_args

from django.utils import timezone
from ninja import Header, Router, Schema, Status
from ninja.errors import HttpError

from accounts.auth import SessionAuthIfLoggedIn, TokenAuth
from accounts.models import SCOPE_CAPTURE_WRITE
from clarice import clocks, composer, orientation
from clarice.search import to_query
from daily import reads as daily_reads
from lists import search as lists_search

from . import queries, services
from .models import (
    ConceptCandidate,
    ConceptType,
    Decision,
    Facet,
    FacetKind,
    Node,
    NodeSource,
    Source,
)

router = Router()


#: Mirrored from `clarice.composer.DESTINATIONS` and asserted below, for the
#: reason `lists.api_v1.TaskRecurrence` gives: Ninja needs a static type, so the
#: duplication is real, and one that shouts when it drifts is a different thing
#: from one that waits to be noticed by somebody typing a destination into a box.
Destination = Literal["note", "did", "today", "pool"]
assert set(get_args(Destination)) == set(composer.DESTINATIONS), (
    "Destination has drifted from clarice.composer.DESTINATIONS: "
    f"{set(composer.DESTINATIONS) ^ set(get_args(Destination))}"
)


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

    destination: Destination = composer.NOTE
    """Where this line goes -- `superlists-2.0-plan.md` increment 4.

    **Defaulting to `note` is what leaves the phone alone.** A body with no
    destination behaves exactly as it did before this field existed, so the
    shipped Android build, its share-sheet handler and its encrypted offline
    queue need no change and no reconnect.

    **A bearer token may send any of the four**, and that is a widening worth
    stating rather than discovering: `capture:write` could previously only
    write a node, and can now also make a task, choose it for today and finish
    it. Allowed because the plan asks for one endpoint rather than two, because
    every one of those acts is the owner's own and visible and undoable on the
    day page -- and because the alternative refuses a queued capture, which
    `principles.md` puts above cleverness. `test_api_auth_surface.py` still
    holds *which* operations a token reaches; this is a note about what one of
    them now does.
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
        # **Through the composer, whatever the destination.** `note` is the
        # absence of the three task branches rather than a separate path, so
        # the capture a phone has always made and the one the day's box makes
        # are the same write -- and there is one place where "every line is a
        # `Node` first" is true rather than two that have to agree.
        node, created = composer.write_a_line(
            request.user,
            text=payload.text,
            destination=payload.destination,
            now=timezone.now(),
            # Now only when nobody said. Guessing a time would be worse than
            # having none, because a temporal detector cannot tell the two apart.
            captured_at=payload.captured_at,
            public_id=public_id,
            tags=payload.tags,
            from_a_phone=from_a_phone,
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


#: How many candidates the index offers, mirrored from `views.CANDIDATE_LIMIT`.
#:
#: **Not imported from `views`**, which would make this router depend on the
#: templates it exists to replace -- and 2b deletes that module's browsing half.
#:
#: **Unlike `Destination` above, this copy is not asserted, and that is a real
#: difference rather than an oversight.** `Destination` mirrors a value in
#: `clarice.composer`, which both sides keep; asserting this one would mean
#: importing `views` precisely to check a number, creating the dependency the
#: duplication exists to avoid. The exposure is bounded and temporary: two
#: numbers can disagree only until 2b retires the page, and if they disagree
#: before then the panel offers a different number of candidates from the
#: template -- visible, not silent.
CANDIDATE_LIMIT = 8


class ConceptNodeOut(Schema):
    """A note, as a concept page shows it."""

    public_id: uuid.UUID
    body: str
    captured_at: datetime

    @staticmethod
    def resolve_body(obj):
        # The current text, not `original_content`. A note that has been
        # corrected reads as it reads now, which is what the page does --
        # `views.note` takes the same route through `queries.current_body`.
        return queries.current_body(obj)


class ConceptKindOut(Schema):
    value: str
    label: str


class ConceptCandidateOut(Schema):
    """A name, whether or not it has been confirmed.

    One schema for both halves of the index rather than two, because a
    candidate and a confirmed name are the same row at different moments --
    `ConceptCandidate.confirmed_at` is the whole difference, and modelling it
    as two shapes would invite them to disagree.
    """

    public_id: uuid.UUID
    label: str
    concept_type: str
    confirmed: bool
    evidence: list[ConceptNodeOut]

    @staticmethod
    def resolve_confirmed(obj):
        return obj.confirmed_at is not None

    @staticmethod
    def resolve_evidence(obj):
        # Attached by the index to candidates only, the way `views.concepts`
        # attaches it -- "Indonesian, 4 mentions" asks somebody to take the
        # system's word for it, and the sentences let them check. A confirmed
        # name carries none, so this reads what may not be there rather than
        # letting the schema fail on the half that never has it.
        return list(getattr(obj, "evidence", []))


class ConceptsOut(Schema):
    candidates: list[ConceptCandidateOut]
    confirmed: list[ConceptCandidateOut]


class ConceptDetailOut(Schema):
    concept: ConceptCandidateOut
    nodes: list[ConceptNodeOut]
    aliases: list[ConceptCandidateOut]
    kinds: list[ConceptKindOut]
    is_a_person: bool


# DARK: no client yet. app-overhaul-plan.md increment 2a builds the knowledge
# core's reads and 2b is what consumes them; `/mind/concepts/` still serves the
# page. Declared rather than left to be noticed, and the trigger is named:
# these come alive when the concepts panel lands.
@router.get("/concepts", response=ConceptsOut, auth=SessionAuthIfLoggedIn())
def list_concepts(request):
    """The things a person keeps mentioning, and the few worth naming.

    Mirrors `views.concepts` rather than improving on it. Reading it changes
    nothing -- unlike the review, whose whole design is that showing and
    surfacing are one act -- so nothing here starts a clock and a candidate
    never confirmed simply stays a candidate.
    """
    candidates = list(queries.concept_candidates(request.user)[:CANDIDATE_LIMIT])
    for candidate in candidates:
        candidate.evidence = list(
            queries.nodes_mentioning(request.user, candidate)[:3]
        )

    return {
        "candidates": candidates,
        "confirmed": queries.confirmed_concepts(request.user).order_by("label"),
    }


# DARK: no client yet -- see `list_concepts` above, same trigger.
@router.get(
    "/concepts/{public_id}", response=ConceptDetailOut, auth=SessionAuthIfLoggedIn()
)
def read_concept(request, public_id: uuid.UUID):
    """Everything about one thing.

    The payoff the concept layer exists for: not a search result but the
    material itself, gathered without anybody having filed it anywhere.

    **404 where the page redirects.** `views.concept` sends an unknown id back
    to the index, which is right for a browser and wrong for an API -- a panel
    needs to know it asked for something that is not there, and `_concept_or_404`
    is the answer this module already gives everywhere else.
    """
    canonical = queries.canonical_concept(_concept_or_404(request, public_id))
    return {
        "concept": canonical,
        "nodes": queries.nodes_mentioning(request.user, canonical),
        "aliases": canonical.aliases.filter(retired_at__isnull=True),
        # Every value, not a curated few. The set is small and closed, and
        # offering four of seven would leave three unreachable in exactly the
        # way all seven were until somebody noticed.
        "kinds": [
            {"value": value, "label": label} for value, label in ConceptType.choices
        ],
        "is_a_person": canonical.concept_type == ConceptType.PERSON,
    }


class SourceOut(Schema):
    public_id: uuid.UUID
    title: str
    #: Text, never fetched -- `Source.url`'s own comment and D7.
    url: str
    author: str
    created_at: datetime


class GrewTaskOut(Schema):
    """A task a source's note became.

    Deliberately thin. This is a *citation* -- proof that something came of
    reading the thing -- and the task's own panel is one click away and owns
    the rest. A fuller copy here would be a second definition of a task, free
    to disagree with the one `lists` serves.
    """

    id: int
    text: str
    status: str


class GrewOut(Schema):
    """What came out of a source.

    Two lists rather than notes carrying their tasks, because that is the shape
    `services.what_grew_from` returns and the shape the page shows. The tasks
    are **reached rather than stored**, along `Node` -> confirmed actionable
    `Facet` -> `Item`, so this cannot disagree with the task core about what
    came of anything.
    """

    notes: list[ConceptNodeOut]
    tasks: list[GrewTaskOut]


class SourcesOut(Schema):
    sources: list[SourceOut]


class SourceDetailOut(Schema):
    source: SourceOut
    grew: GrewOut


class DecisionOut(Schema):
    public_id: uuid.UUID
    question: str
    chose: str
    #: The half a note cannot keep: six weeks later the alternatives are the
    #: part you have forgotten, and it is a third of S11's done-means.
    considered: str
    #: The condition in words, honest and uncheckable by anything.
    revisit_when: str
    #: A date, which is crude and is the only half a read can act on.
    revisit_after: date | None
    decided_at: datetime
    revisited_at: datetime | None


class DueToRevisitOut(Schema):
    """What has come back, and how much cannot be found this way.

    **The count is not decoration and must not be flattened away.**
    `services.decisions_to_revisit` returns both halves on purpose: only a
    dated decision can be found by a query, and a condition in words is what
    makes a decision honest while being checkable by nobody but the person.
    Saying how many are waiting on one is, in that function's own words, the
    difference between a read that is incomplete and one that is misleading.

    Written as a schema over the service's own shape rather than as a bare
    list, which is what this first was -- and a bare list would have passed its
    test while quietly dropping the honest half.
    """

    past_their_date: list[DecisionOut]
    waiting_on_a_condition: int


class DecisionsOut(Schema):
    """The due ones as their own thing, not a flag on the rows.

    `views.decisions` is explicit about why: *find decisions past their
    reconsideration trigger without hunting for them* is a third of S11, and a
    list sorted by date buries exactly that.
    """

    due: DueToRevisitOut
    all: list[DecisionOut]


class DecisionDetailOut(Schema):
    decision: DecisionOut


# DARK: no client yet -- app-overhaul-plan.md increment 2a, consumed by 2b.
# `/mind/sources/` still serves the page.
@router.get("/sources", response=SourcesOut, auth=SessionAuthIfLoggedIn())
def list_sources(request):
    """What you have read -- S15.

    **The read half only.** `views.sources` is a `GET` and a `POST` on one
    route, because recording a source is one line of a form above the list it
    joins. Recording stays there until 2b moves the surface whole; an endpoint
    that could show a list but not add to it would be a panel with a missing
    verb.
    """
    return {"sources": Source.objects.filter(owner=request.user)}


# DARK: no client yet -- see `list_sources` above, same trigger.
@router.get(
    "/sources/{public_id}", response=SourceDetailOut, auth=SessionAuthIfLoggedIn()
)
def read_source(request, public_id: uuid.UUID):
    """One thing you read, and everything that grew out of it -- S15."""
    found = Source.objects.filter(
        public_id=public_id, owner=request.user
    ).first()
    if found is None:
        raise HttpError(404, "Source not found.")
    return {"source": found, "grew": services.what_grew_from(found)}


# DARK: no client yet -- see `list_sources` above, same trigger.
@router.get("/decisions", response=DecisionsOut, auth=SessionAuthIfLoggedIn())
def list_decisions(request):
    """What you chose, over what, and what would bring it back -- S11."""
    return {
        # The owner's today -- D16. A decision due on the 5th became due some
        # hours early or late depending on which side of UTC they live on,
        # which is a small wrongness in the one read whose whole job is *has
        # this come back yet*.
        "due": services.decisions_to_revisit(
            request.user, on=clocks.today_for(request.user)
        ),
        "all": Decision.objects.filter(owner=request.user),
    }


# DARK: no client yet -- see `list_sources` above, same trigger.
@router.get(
    "/decisions/{public_id}", response=DecisionDetailOut, auth=SessionAuthIfLoggedIn()
)
def read_decision(request, public_id: uuid.UUID):
    """One decision, and what it was standing on."""
    found = (
        Decision.objects.filter(public_id=public_id, owner=request.user)
        .select_related("cited_node", "supersedes")
        .first()
    )
    if found is None:
        raise HttpError(404, "Decision not found.")
    return {"decision": found}


#: How many notes an index page returns at once.
#:
#: Same number as `SEARCH_LIMIT` and for the same reason -- a front door on six
#: hundred notes is a scroll, not a door -- but a separate constant, because
#: the two answer different questions and tying them together would make one
#: of them move for the other's reasons.
NOTES_PAGE = 30


class NotesOut(Schema):
    """The front door on capture, which has never had one.

    `app-overhaul-audit-2026-09-06.md`'s **G3**: `/mind/notes/<uuid>/` renders
    and `/mind/notes/` does not, so the thing capture writes is reachable only
    by arriving from somewhere else. This is the one part of increment 2a that
    mirrors no existing view, because there is none to mirror.

    **`total` is counted before slicing**, the way `SearchOut`'s section counts
    are: a page showing thirty of six hundred and saying nothing about the rest
    is a surface that lies quietly.
    """

    notes: list[ConceptNodeOut]
    total: int


class PeopleOut(Schema):
    people: list[ConceptCandidateOut]


# DARK: no client yet -- app-overhaul-plan.md increment 2a, consumed by 2b.
# Unlike its neighbours there is no page to keep working here; this is new.
@router.get("/notes", response=NotesOut, auth=SessionAuthIfLoggedIn())
def list_notes(request, limit: int = NOTES_PAGE):
    """Everything written, newest first.

    **`live_nodes` and nothing wider.** Deleted and archived stay out, and a
    new surface is not an exemption from a rule that already holds -- the same
    sentence `what_grew_from` writes about a source page.
    """
    notes = queries.live_nodes(request.user)
    # Counted before slicing, deliberately. See `NotesOut`.
    return {"notes": notes[: max(0, limit)], "total": notes.count()}


# DARK: no client yet -- see `list_notes` above, same trigger.
@router.get("/people", response=PeopleOut, auth=SessionAuthIfLoggedIn())
def list_people(request):
    """The people in your life, as the graph has them.

    **Confirmed only.** A candidate is the system's guess, and the soft-apply
    rule is that a guess is never treated as fact by anything downstream -- a
    directory of the people in somebody's life is about as downstream as it
    gets, and this is the same reason `confirmed_concept_labels` gives.

    **People only**, because `views.person` redirects a motif rather than
    rendering one: a page called *people* showing a motif would mean nothing.
    An index keeps that rule most cheaply by simply not listing them.
    """
    return {
        "people": ConceptCandidate.objects.filter(
            owner=request.user,
            concept_type=ConceptType.PERSON,
            confirmed_at__isnull=False,
            retired_at__isnull=True,
            merged_into__isnull=True,
        ).order_by("label")
    }


class CommitmentSummaryOut(Schema):
    """A commitment that grew out of a note about somebody.

    Thin, like `GrewTaskOut` and for the same reason: the task's own panel owns
    the rest, and a fuller copy here would be free to disagree with it.
    """

    id: int
    text: str

    @staticmethod
    def resolve_text(obj):
        # The passage the commitment was read out of, which is what the page
        # shows -- a facet has no text of its own.
        return obj.cited_text


class MonthSeenOut(Schema):
    """One month, and how often a name came up in it.

    **Months rather than a smoothed curve or a rate.** A count per month is a
    fact somebody can check against their own memory; anything smoothed is a
    number nobody can argue with, which `principles.md` warns about wherever a
    reading might be mistaken for evidence.
    """

    month: datetime
    seen: int


class PersonDetailOut(Schema):
    person: ConceptCandidateOut
    nodes: list[ConceptNodeOut]
    #: The first of the two joins Track E increment 20 names, and the one a
    #: list of mentions cannot give: notes about somebody become tasks, and the
    #: tasks are the part with consequences.
    commitments: list[CommitmentSummaryOut]
    #: The second. A name across time is what a second mind should be good at,
    #: and a flat list of mentions does not show it.
    months: list[MonthSeenOut]


class ConceptExplainedOut(Schema):
    name: str
    means: str
    #: Their own material that demonstrates it. **The reason this is a read**:
    #: a concept with no evidence is not explained at all.
    evidence: str


class StartOut(Schema):
    new_here: bool
    concepts: list[ConceptExplainedOut]


# DARK: no client yet -- app-overhaul-plan.md increment 2a, consumed by 2b.
@router.get(
    "/people/{public_id}", response=PersonDetailOut, auth=SessionAuthIfLoggedIn()
)
def read_person(request, public_id: uuid.UUID):
    """One person, across everything you have written -- Track E increment 20.

    **404 for a concept that is not a person**, where `views.person` redirects
    to the concept page. A redirect is right for a browser, which has somewhere
    real to land; a panel that asked for a person needs to be told it did not
    get one, and its caller can open the concept instead.
    """
    canonical = queries.canonical_concept(_concept_or_404(request, public_id))
    if canonical.concept_type != ConceptType.PERSON:
        raise HttpError(404, "That name is not a person.")

    return {
        "person": canonical,
        "nodes": queries.nodes_mentioning(request.user, canonical),
        "commitments": queries.commitments_involving(request.user, canonical),
        "months": [
            {"month": month, "seen": seen}
            for month, seen in queries.when_they_came_up(request.user, canonical)
        ],
    }


# DARK: no client yet -- see above, same trigger.
@router.get("/start", response=StartOut, auth=SessionAuthIfLoggedIn())
def read_start(request):
    """Two entrances, and only the words their own material has earned.

    Track D increment 15, and the answer to `commercial-blueprint.md`'s
    long-open *explain the six invented concepts somewhere in the product,
    once*. A tour was the obvious answer and the plan refuses it: a concept
    explained before it exists is a word attached to nothing.
    """
    return {
        "new_here": orientation.is_new_here(request.user),
        "concepts": orientation.what_their_material_demonstrates(request.user),
    }


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
