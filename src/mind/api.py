"""The typed HTTP contract.

Thin by design. Every rule lives in `services` and `queries`; this layer parses,
authorises, and serialises. Nothing here decides anything — which is what keeps a
second client from inventing its own version of the rules, and what makes the shell,
the web page and any future client agree by construction.

Two properties are worth reading before adding an endpoint.

**`GET /review` mutates, and that is correct.** It returns the proposals to show *and*
marks them shown. A conventionally-pure read here would mean `first_surfaced_at` stays
null while a person looks straight at a proposal, after which inaction is
indistinguishable from never having seen it and every rule built on the review window
silently means nothing. The HTTP idiom loses to the invariant.

**Capture is idempotent on a client-supplied id.** A phone that never saw its request
succeed retries with the same `public_id` and gets the same node back, not a second
one. That is the whole reason the column exists.

Session authentication only. A mobile *browser* handles cookies, which covers the
capture path that matters; token auth for a native client is deferred rather than
half-built.
"""

from __future__ import annotations

import uuid as uuid_module
from datetime import datetime

from django.contrib.auth import authenticate
from django.contrib.postgres.search import SearchQuery
from django.db.models import Q
from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from django.utils import timezone
from ninja import Header, NinjaAPI, Schema, Status
from ninja.errors import HttpError
from ninja.security import django_auth
from ninja.throttling import AnonRateThrottle

from . import instrumentation, queries, services
from .auth import BearerAuth
from .models import (
    ApiToken,
    ConnectionHypothesis,
    EventType,
    MissContext,
    Node,
    NodeSource,
)

api = NinjaAPI(
    title="Second Mind",
    version="1",
    description=(
        "The connection lab. Capture is idempotent on a client-supplied id; "
        "GET /review deliberately marks what it returns as surfaced."
    ),
    # Bearer first, then session. Order matters: a token request carries no CSRF token
    # and needs none, and when the bearer check succeeds Ninja never reaches the
    # session backend that would demand one. Requests with no Authorization header fall
    # through to the session path unchanged, CSRF included.
    auth=[BearerAuth(), django_auth],
)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class CaptureIn(Schema):
    content: str = ""
    public_id: uuid_module.UUID | None = None
    captured_at: datetime | None = None
    source: str = NodeSource.API


class ReviseIn(Schema):
    body: str


class MissIn(Schema):
    query_text: str
    context: str = MissContext.SEARCH


class NodeOut(Schema):
    public_id: uuid_module.UUID
    body: str
    original_content: str
    captured_at: datetime
    source: str
    revisions: int
    attention_tier: str


class CitationOut(Schema):
    public_id: uuid_module.UUID
    quote: str
    """The cited span, not the whole note.

    A claim has to be checkable against the passage that supports it; sending the
    entire note back would make the reader do the work the citation exists to save.
    """
    is_source: bool
    reason: str | None
    captured_at: datetime


class ProposalOut(Schema):
    public_id: uuid_module.UUID
    detector: str
    label: str
    confidence: float
    index_version: str
    first_surfaced_at: datetime | None
    review_window_expires_at: datetime | None
    citations: list[CitationOut]


class SummaryOut(Schema):
    nodes: int
    confirmed_connections: int
    explicit_links: int
    retrieval_misses: int
    detectors: list[dict]
    gate: list[dict]


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------


def _node_out(node: Node, *, now: datetime) -> dict:
    return {
        "public_id": node.public_id,
        "body": queries.current_body(node),
        "original_content": node.original_content,
        "captured_at": node.captured_at,
        "source": node.source,
        "revisions": node.revisions.count(),
        "attention_tier": queries.attention_tier(node, now=now),
    }


def _proposal_out(hypothesis: ConnectionHypothesis) -> dict:
    citations = []
    members = sorted(
        hypothesis.members.all(), key=lambda m: m.node.captured_at, reverse=True
    )
    for position, member in enumerate(members):
        body = member.node.original_content
        quote = (
            body[member.span_start : member.span_end]
            if member.span_start is not None
            else body
        )
        citations.append(
            {
                "public_id": member.node.public_id,
                "quote": quote,
                # The newest member is the note that triggered the proposal.
                "is_source": position == 0,
                "reason": member.contribution_reason,
                "captured_at": member.node.captured_at,
            }
        )
    return {
        "public_id": hypothesis.public_id,
        "detector": hypothesis.detector,
        "label": hypothesis.label,
        "confidence": hypothesis.confidence,
        "index_version": hypothesis.index_version,
        "first_surfaced_at": hypothesis.first_surfaced_at,
        "review_window_expires_at": hypothesis.review_window_expires_at,
        "citations": citations,
    }


def _owned_node(request: HttpRequest, public_id) -> Node:
    """Owner-scoped lookup, so a wrong id is indistinguishable from someone else's.

    Not a nicety: scoping the query is what makes the service-layer owner guards
    unreachable from here, which is why those guards have their own direct tests.
    """
    return get_object_or_404(
        Node, public_id=public_id, owner=request.user, deleted_at__isnull=True
    )


# ---------------------------------------------------------------------------
# Identity and tokens
# ---------------------------------------------------------------------------


class LoginIn(Schema):
    username: str
    password: str
    label: str = "device"


class LoginOut(Schema):
    token: str
    username: str
    email: str


class IdentityOut(Schema):
    username: str
    email: str


@api.post("/login", response=LoginOut, auth=None, throttle=[AnonRateThrottle("6/m")])
def login(request, payload: LoginIn):
    """Exchange a username and password for a long-lived token.

    Unauthenticated by necessity — this is how a device gets its credential — and
    therefore throttled, since an unlimited password endpoint is an invitation.

    **One message for every kind of failure.** Wrong username, wrong password, and a
    deactivated account are deliberately indistinguishable: telling them apart confirms
    which usernames exist, and there is nothing a legitimate person can do with the
    distinction anyway.

    The token is returned exactly once. Nothing stored can reproduce it.
    """
    user = authenticate(
        request, username=payload.username, password=payload.password
    )
    if user is None or not user.is_active:
        raise HttpError(401, "Those details did not work.")

    _, raw = ApiToken.issue(user, label=payload.label)
    return {"token": raw, "username": user.get_username(), "email": user.email}


@api.get("/me", response=IdentityOut)
def me(request):
    """Whose token this is — how a client checks a credential before storing it.

    Validate-then-save matters: a token the server has already refused, sitting in a
    device's storage, produces an app where every capture fails and nothing explains
    why.
    """
    return {"username": request.user.get_username(), "email": request.user.email}


@api.get("/tokens", response=list[dict])
def list_tokens(request):
    """Issued devices, so one can be told from another when revoking."""
    return [
        {
            "id": token.pk,
            "label": token.label,
            "prefix": token.display_prefix,
            "created_at": token.created_at.isoformat(),
            "last_used_at": token.last_used_at.isoformat() if token.last_used_at else None,
        }
        for token in request.user.api_tokens.filter(revoked_at__isnull=True).order_by(
            "-created_at"
        )
    ]


@api.delete("/tokens/{token_id}", response={204: None})
def revoke_token(request, token_id: int):
    """Revoke immediately. A lost phone is the reason this endpoint exists."""
    token = get_object_or_404(
        ApiToken, pk=token_id, owner=request.user, revoked_at__isnull=True
    )
    token.revoked_at = timezone.now()
    token.save(update_fields=["revoked_at"])
    return Status(204, None)


# ---------------------------------------------------------------------------
# Capture
# ---------------------------------------------------------------------------


def _capture(request, payload: CaptureIn, *, tags: list[str] = ()) -> tuple[Node, bool]:
    """The one capture implementation. Returns the node and whether it is new.

    Shared by both capture endpoints rather than reimplemented, because two capture
    paths with two behaviours is how a retry quietly stops being idempotent — and the
    rules themselves now live one layer down, in `services.capture_idempotent`, so
    this API and the shared `/api/v1/capture` in `mind/api_v1.py` cannot drift either.
    """
    try:
        return services.capture_idempotent(
            request.user,
            content=payload.content,
            captured_at=payload.captured_at or timezone.now(),
            source=payload.source,
            actor=request.user.get_username(),
            public_id=payload.public_id,
            tags=tags,
        )
    # 400, not 422 or 409. A queued client treats anything other than 400/401/403 as
    # "retry later", so an unprocessable body returned as 422 would be retried forever
    # against a server that will never accept it. Both of these are permanent faults in
    # the request, which is exactly what 400 means to that client.
    except services.EmptyNode as exc:
        raise HttpError(400, str(exc))
    except services.NotYours:
        raise HttpError(400, "that id belongs to someone else")


@api.post("/captures", response={201: NodeOut, 200: NodeOut})
def create_capture(request, payload: CaptureIn):
    """Record a thought. Returns 200 for a retry, 201 for something new.

    `captured_at` may be supplied so a client that captured while offline can send when
    the thought *happened* rather than when it managed to reach the server — without
    which every queued capture would arrive stamped with the moment the network came
    back.
    """
    node, created = _capture(request, payload)
    # 200 for a retry, 201 for something new — so a client can tell whether its earlier
    # attempt had in fact landed.
    return Status(201 if created else 200, _node_out(node, now=timezone.now()))


class MobileCaptureIn(Schema):
    """What the existing Android client sends.

    Its own field names, kept rather than changed, because the point of this endpoint is
    that an app which already has an encrypted offline queue and a share-sheet handler
    needs no Kotlin changes to talk to this server.
    """

    text: str = ""
    tags: list[str] = []
    # When the thought was written, which for a queued client is not when it arrives.
    # Optional, so a client that predates the field is unaffected and falls back to now
    # -- correct for anything captured while connected, and the only honest answer when
    # nobody told us otherwise.
    captured_at: datetime | None = None


@api.post("/capture", response={201: NodeOut, 200: NodeOut})
def create_capture_mobile(
    request,
    payload: MobileCaptureIn,
    idempotency_key: str = Header(default="", alias="Idempotency-Key"),
):
    """Capture, in the shape a queued mobile client already speaks.

    Deliberately an alias rather than a second implementation: it maps the header and
    field names onto `POST /captures` and shares every rule with it. Two capture paths
    with two behaviours is how a retry stops being idempotent.

    `Idempotency-Key` is a UUID from the client, which is precisely what `public_id`
    already is — so the retry safety is the same mechanism, not a parallel one.

    `tags` are recorded on the capture event rather than modelled. There is no tag table
    here, and structure is meant to emerge rather than be declared at entry; but a person
    typed them, so discarding them silently would be worse than keeping them somewhere
    honest until there is a reason to do more.

    `captured_at` is the thought's own time and is passed straight through. This endpoint
    used to hard-code `None` here, which meant every capture that had waited in a queue
    was stamped with the moment the queue drained — six of them landing on the same
    second during the August 14, 2026 device pass, which is how it was found. Dormancy is
    measured between notes, so collapsing a queue onto one instant destroys temporal
    spread on precisely the material a phone-first client produces most of.
    """
    try:
        public_id = uuid_module.UUID(idempotency_key) if idempotency_key else None
    except ValueError:
        raise HttpError(400, "Idempotency-Key must be a UUID")

    # Each tag becomes a confirmed concept and an explicit mention -- step 1 of
    # one-capture-surface-plan.md -- and only on a genuine create, so a retried
    # queue cannot manufacture a recurrence. Both rules live in
    # `services.capture_idempotent`, which is where the other capture endpoint
    # reads them from too.
    node, created = _capture(
        request,
        CaptureIn(
            content=payload.text,
            public_id=public_id,
            captured_at=payload.captured_at,
            source=NodeSource.MOBILE,
        ),
        tags=payload.tags,
    )

    return Status(201 if created else 200, _node_out(node, now=timezone.now()))


@api.get("/captures", response=list[NodeOut])
def list_captures(request, limit: int = 20):
    now = timezone.now()
    nodes = queries.live_nodes(request.user).prefetch_related("revisions")[:limit]
    return [_node_out(node, now=now) for node in nodes]


@api.get("/captures/{public_id}", response=NodeOut)
def get_capture(request, public_id: uuid_module.UUID):
    return _node_out(_owned_node(request, public_id), now=timezone.now())


@api.post("/captures/{public_id}/revisions", response=NodeOut)
def revise_capture(request, public_id: uuid_module.UUID, payload: ReviseIn):
    node = _owned_node(request, public_id)
    now = timezone.now()
    services.revise(node, body=payload.body, actor=request.user.get_username(), now=now)
    node.refresh_from_db()
    return _node_out(node, now=now)


@api.delete("/captures/{public_id}", response={204: None})
def delete_capture(request, public_id: uuid_module.UUID):
    """Soft, so a stated retention window governs the actual purge — but gone from
    results immediately, not a hidden flag."""
    node = _owned_node(request, public_id)
    services.delete_node(node, now=timezone.now(), actor=request.user.get_username())
    return Status(204, None)


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------


@api.get("/search", response=list[NodeOut])
def search(request, q: str, limit: int = 20):
    """Full-text over both the current body and the original capture.

    Both, so a thought stays findable by the words it was first written in.
    """
    now = timezone.now()
    if not q.strip():
        return []
    query = SearchQuery(q, config="english")
    nodes = (
        queries.live_nodes(request.user)
        .filter(Q(search_original=query) | Q(revisions__search_body=query))
        .distinct()[:limit]
    )
    return [_node_out(node, now=now) for node in nodes]


@api.post("/misses", response={201: None})
def record_miss(request, payload: MissIn):
    """"I know I wrote this and cannot find it."

    The strongest evidence available about retrieval, because the correct answer is
    known — and the only place vocabulary drift shows up before it is too late.
    """
    services.record_retrieval_miss(
        request.user,
        query_text=payload.query_text,
        context=payload.context,
        now=timezone.now(),
    )
    return Status(201, None)


# ---------------------------------------------------------------------------
# Review
# ---------------------------------------------------------------------------


@api.get("/review", response=list[ProposalOut])
def open_review(request, limit: int = 5):
    """Proposals to consider — **and marking them as shown**.

    Deliberately not a pure read. See the module docstring: separating the two would
    let a proposal be displayed without its review window starting, and silence would
    stop meaning anything.
    """
    hypotheses = services.open_review(
        request.user,
        now=timezone.now(),
        actor=request.user.get_username(),
        limit=limit,
    )
    return [_proposal_out(h) for h in hypotheses]


@api.get("/review/pending", response={200: dict})
def pending_count(request):
    """How many proposals are waiting. Does **not** count as surfacing.

    Safe because it returns a number and no content: nothing can be read from it, so
    nothing can be shown without going through `/review`.
    """
    return {"pending": queries.pending_hypotheses(request.user).count()}


def _owned_hypothesis(request, public_id) -> ConnectionHypothesis:
    return get_object_or_404(
        ConnectionHypothesis, public_id=public_id, owner=request.user
    )


@api.post("/review/{public_id}/confirm", response={200: dict})
def confirm(request, public_id: uuid_module.UUID):
    """Accept a proposal, promoting it into the confirmed graph. The person's act."""
    hypothesis = _owned_hypothesis(request, public_id)
    try:
        edges = services.confirm_hypothesis(
            hypothesis, now=timezone.now(), actor=request.user.get_username()
        )
    except services.AlreadyResolved as exc:
        raise HttpError(409, str(exc))
    except (services.InvalidHypothesis, services.HierarchyTooDeep) as exc:
        raise HttpError(422, str(exc))
    return {"confirmed": True, "edges": len(edges)}


@api.post("/review/{public_id}/dismiss", response={200: dict})
def dismiss(request, public_id: uuid_module.UUID):
    """Reject a proposal, permanently — the same pair is never offered again."""
    hypothesis = _owned_hypothesis(request, public_id)
    try:
        services.dismiss_hypothesis(
            hypothesis, now=timezone.now(), actor=request.user.get_username()
        )
    except services.AlreadyResolved as exc:
        raise HttpError(409, str(exc))
    return {"dismissed": True}


@api.post("/captures/{public_id}/reviewed", response={200: dict})
def mark_reviewed(request, public_id: uuid_module.UUID, buried: bool = False):
    """Record that a resurfaced note was seen, and what was done with it.

    `buried` stretches the interval much harder — the person saying "less often", which
    is the difference between a review surface and a nag.
    """
    node = _owned_node(request, public_id)
    services.mark_reviewed(
        node,
        response=services.ReviewResponse.BURIED
        if buried
        else services.ReviewResponse.KEPT,
        now=timezone.now(),
        actor=request.user.get_username(),
    )
    return queries.review_state(node) | {"reviewed": True}


# ---------------------------------------------------------------------------
# Measurement
# ---------------------------------------------------------------------------


@api.get("/summary", response=SummaryOut)
def summary(request):
    """Is the mechanic working? Per detector, never blended."""
    data = instrumentation.lab_summary(request.user, now=timezone.now())
    return {
        "nodes": data["nodes"],
        "confirmed_connections": data["confirmed_connections"],
        "explicit_links": data["explicit_links"],
        "retrieval_misses": data["retrieval_misses"],
        "detectors": [
            {
                "detector": p.detector,
                "proposed": p.proposed,
                "confirmed": p.confirmed,
                "dismissed": p.dismissed,
                "expired": p.expired,
                "pending": p.pending,
                # None, never 0 — "no evidence yet" and "wrong every time" call for
                # opposite responses.
                "accept_rate": p.accept_rate,
                "unseen_rate": p.unseen_rate,
            }
            for p in data["detectors"]
        ],
        "gate": [
            {"name": c.name, "met": c.met, "value": c.value, "detail": c.detail}
            for c in data["gate"]
        ],
    }
