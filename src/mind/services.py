"""Write side: enforces invariants and makes mutations.

Paired with queries.py, which answers questions and never writes. Everything
here is the home for the rules that no database constraint can state — the ones
listed in docs/ddl-decisions.md under "Invariants that are deliberately not in
the schema". Each has its own test.

Two conventions hold throughout:

**The clock is injected.** Every function that needs the current time takes
`now` as a keyword argument. Nothing in this module reads the clock for itself,
so no test depends on when it runs, and a batch job can replay a specific day.

**Every mutation appends to the log.** `ActivityEvent` is append-only at the
database, so what is written here is permanent. That is the point: folded
projections are only trustworthy if the log cannot be edited afterwards.

Where a database trigger already enforces something, the service still checks it
first. The service check produces a clean domain error the caller can act on;
the trigger is the backstop that closes the race between two concurrent writers.
"""

from __future__ import annotations

import hashlib
import re
import uuid as uuid_module
from datetime import datetime, timedelta
from enum import Enum
from typing import Iterable, NamedTuple, Sequence

from django.db import transaction
from django.db.models import Count, Max, Q
from django.utils import timezone

from .commitments import find_commitment
from .models import (
    Facet,
    FacetKind,
    entry_body,
    ActivityEvent,
    Attachment,
    ConceptCandidate,
    ConceptType,
    ConnectionHypothesis,
    Edge,
    EdgeRelation,
    EventType,
    HypothesisMember,
    HypothesisResolution,
    InferenceOrigin,
    Mention,
    MissContext,
    Node,
    NodeSource,
    RetrievalMiss,
    Revision,
)

# ---------------------------------------------------------------------------
# Domain errors
# ---------------------------------------------------------------------------


class MindError(Exception):
    """Base for every rule this module enforces."""


class NotYours(MindError):
    """A record belongs to someone else, or two records disagree about owner.

    Raised rather than returning empty, and raised by the service directly so
    that the guard can be tested without going through a view. A view looks
    records up owner-scoped and 404s before ever reaching here, which means the
    view cannot construct the failing case — so this needs its own test.
    """


class EmptyNode(MindError):
    """A node must carry either content or at least one attachment."""


class InvalidHypothesis(MindError):
    """A hypothesis needs at least two members to be a connection at all."""


class HierarchyTooDeep(MindError):
    """`member_of` and concept aliases are both capped at depth one.

    Deep hierarchies are deferred, and this is that deferral enforced rather
    than merely intended.
    """


class AlreadyResolved(MindError):
    """A hypothesis is resolved once. Resolution is not a state to toggle."""


class Deleted(MindError):
    """Deleted material is not writable."""


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _record(
    owner,
    event_type: str,
    *,
    occurred_at: datetime,
    actor: str,
    node: Node | None = None,
    payload: dict | None = None,
) -> ActivityEvent:
    return ActivityEvent.objects.create(
        owner=owner,
        node=node,
        event_type=event_type,
        occurred_at=occurred_at,
        actor=actor,
        payload=payload or {},
    )


def _require_same_owner(*records) -> None:
    """Every record in one operation must belong to one person.

    This is the isolation invariant, and it is a cross-row check — not
    expressible as a database constraint, which is exactly why it lives here.
    """
    owners = {r.owner_id for r in records if r is not None}
    if len(owners) > 1:
        raise NotYours("records belong to different owners")


def _require_live(node: Node) -> None:
    if node.deleted_at is not None:
        raise Deleted(f"node {node.pk} is deleted")


# ---------------------------------------------------------------------------
# Capture
# ---------------------------------------------------------------------------


class AttachmentSpec(NamedTuple):
    kind: str
    mime_type: str
    byte_size: int
    checksum: str
    storage_key: str


@transaction.atomic
def capture(
    owner,
    *,
    captured_at: datetime,
    source: str,
    actor: str,
    content: str = "",
    public_id: uuid_module.UUID | None = None,
    import_key: str | None = None,
    attachments: Sequence[AttachmentSpec] = (),
) -> Node:
    """Record something, and return the node — new or already existing.

    Idempotent on two different keys, because there are two different ways the
    same capture can arrive twice:

    * `public_id` — a client retrying a request it never saw succeed. The client
      names the node, so the retry resolves to the same row.
    * `import_key` — an import being re-run over material already ingested.

    Both return the existing node rather than raising, because a retry is not an
    error. `captured_at` is when the thought happened, which for imported
    material is its original timestamp and not now — conflating the two makes
    every temporal detector wrong on exactly the material most likely to
    trigger one.
    """
    if public_id is not None:
        existing = Node.objects.filter(public_id=public_id).first()
        if existing is not None:
            if existing.owner_id != owner.pk:
                raise NotYours(f"public_id {public_id} belongs to someone else")
            return existing

    if import_key is not None:
        existing = Node.objects.filter(owner=owner, import_key=import_key).first()
        if existing is not None:
            return existing

    if not content.strip() and not attachments:
        raise EmptyNode("a node needs content or at least one attachment")

    node = Node.objects.create(
        owner=owner,
        public_id=public_id or uuid_module.uuid4(),
        original_content=content,
        captured_at=captured_at,
        source=source,
        import_key=import_key,
    )

    for spec in attachments:
        Attachment.objects.create(node=node, **spec._asdict())

    _record(
        owner,
        EventType.IMPORTED if source == NodeSource.IMPORT else EventType.CAPTURED,
        node=node,
        occurred_at=captured_at,
        actor=actor,
        payload={
            "source": source,
            "public_id": str(node.public_id),
            "attachments": len(attachments),
        },
    )

    _propose_any_commitment(node, now=captured_at, actor=actor)
    return node


@transaction.atomic
def capture_idempotent(
    owner,
    *,
    content: str,
    captured_at: datetime,
    source: str,
    actor: str,
    public_id: uuid_module.UUID | None = None,
    tags: Sequence[str] = (),
) -> tuple[Node, bool]:
    """Record something and say whether it was new. The whole of a retry-safe
    capture, in one place.

    `capture` alone cannot answer "was this new", because returning the existing
    node is exactly what it does for a retry. Both HTTP surfaces need that answer
    — 201 against 200 is how a phone learns its earlier attempt had in fact
    landed — and both need the same two rules on top of it, so they live here
    rather than being written out twice.

    **Tags only on a genuine create.** `record_typed_tags` is idempotent anyway,
    but the gravity gate counts mentions: a queue that retried six times must not
    manufacture a recurrence that never happened.

    **`captured_at` is the thought's own time**, not the moment it arrived. A
    capture can sit in an offline queue for hours, and dormancy is measured
    between notes — so stamping a drained queue with now collapses hours onto one
    instant on precisely the material a phone-first client produces most of.
    The caller decides what to do when nobody said; this does not guess.
    """
    existed = (
        public_id is not None
        and Node.objects.filter(public_id=public_id).exists()
    )
    node = capture(
        owner,
        content=content,
        captured_at=captured_at,
        source=source,
        actor=actor,
        public_id=public_id,
    )
    created = not existed

    if tags and created:
        record_typed_tags(node, tags, now=captured_at, actor=actor)

    return node, created


@transaction.atomic
def archive_node(node: Node, *, now: datetime, actor: str) -> Node:
    """Take a node out of the live set without deleting it.

    Distinct from deletion, and the distinction is the point: archived material
    is still searchable and still there, it just stops being offered. `Node`
    has carried `archived_at` and `EventType.ARCHIVED` since the first slice
    with nothing to set them; the Inbox migration is the first caller, for
    captures somebody explicitly discarded.

    **It does take them out of the detectors' reach**, since those read
    `live_nodes`. That is the right trade for material a person said no to
    once -- surfacing it again as a connection would be the system overruling
    that -- but it is a real cost to a corpus this small, which is why the
    migration reports how many it archived rather than doing it quietly.
    """
    if node.archived_at is not None:
        return node
    node.archived_at = now
    node.save(update_fields=["archived_at"])
    _record(
        node.owner,
        EventType.ARCHIVED,
        node=node,
        occurred_at=now,
        actor=actor,
        payload={},
    )
    return node


def _propose_any_commitment(node: Node, *, now: datetime, actor: str) -> Facet | None:
    """Offer an actionable facet if the words read as a commitment.

    Runs on the live path because the parser is deterministic -- rules and a
    regex, no model, no network, no per-call cost. That is what lets capture
    stay one box that returns immediately: the proposal is ready by the time the
    page comes back, and nothing was asked at the moment of entry.

    Read against `captured_at` rather than now, so "dentist tomorrow" in an
    imported 2019 note means the day after that note, not the day after today.
    Conflating the two puts a date nobody ever meant into next week, on exactly
    the material most likely to carry a relative one.
    """
    found = find_commitment(node.original_content, today=timezone.localdate(now))
    if found is None:
        return None

    return propose_facet(
        node,
        kind=FacetKind.ACTIONABLE,
        data={
            "due_date": found.due_date.isoformat(),
            "recurrence": found.recurrence,
        },
        now=now,
        actor=actor,
        reason=found.reason,
    )


@transaction.atomic
def revise(node: Node, *, body: str, actor: str, now: datetime) -> Revision:
    """Add a revision, leaving the original capture untouched.

    `seq` allocation locks the node rather than retrying on collision: two
    concurrent revisions to one node serialise, which is both simpler and
    cheaper than catching the unique violation and recomputing. The unique
    constraint remains as the backstop.
    """
    _require_live(node)
    locked = Node.objects.select_for_update().get(pk=node.pk)
    next_seq = (locked.revisions.aggregate(high=Max("seq"))["high"] or 0) + 1

    revision = Revision.objects.create(
        node=locked, seq=next_seq, body=body, actor=actor
    )
    _record(
        locked.owner,
        EventType.REVISED,
        node=locked,
        occurred_at=now,
        actor=actor,
        payload={"seq": next_seq},
    )
    return revision


# ---------------------------------------------------------------------------
# Concepts and aliases
# ---------------------------------------------------------------------------


@transaction.atomic
def propose_concept(
    owner,
    *,
    label: str,
    concept_type: str,
    now: datetime,
    actor: str,
    reason: str | None = None,
) -> ConceptCandidate:
    """Propose a concept. Unconfirmed, and therefore not yet trusted.

    An unconfirmed candidate is deliberately excluded from the corpus the
    matcher searches (see queries.confirmed_concepts). Without that exclusion
    the system's own guesses become the evidence for its next guess, and there
    is no path back.
    """
    concept = ConceptCandidate.objects.create(
        owner=owner, label=label, concept_type=concept_type, reason=reason
    )
    _record(
        owner,
        EventType.CONCEPT_PROPOSED,
        occurred_at=now,
        actor=actor,
        payload={"concept": str(concept.public_id), "label": label, "reason": reason},
    )
    return concept


@transaction.atomic
def confirm_concept(
    concept: ConceptCandidate, *, now: datetime, actor: str
) -> ConceptCandidate:
    """Admit a concept to the trusted corpus. Always a person's decision."""
    if concept.confirmed_at is None:
        concept.confirmed_at = now
        concept.save(update_fields=["confirmed_at"])
        _record(
            concept.owner,
            EventType.CONCEPT_CONFIRMED,
            occurred_at=now,
            actor=actor,
            payload={"concept": str(concept.public_id), "label": concept.label},
        )
    return concept


def retire_concept(
    concept: ConceptCandidate, *, now: datetime, actor: str
) -> ConceptCandidate:
    """Record that a name is not a thing, permanently.

    Extraction runs again after every batch of captures, so without this a
    rejected name would be re-proposed forever and answering it would be
    worthless -- the same reasoning that makes a dismissed hypothesis permanent
    through its fingerprint.

    Only ever a candidate. A confirmed concept has mentions resolving through it
    and detectors reading it, so removing one is a different and much larger act
    than saying "that was never a thing", and conflating the two here would make
    a stray tap capable of it.

    Retiring twice is harmless and keeps the first decision's time: two taps, or
    a tap against a stale page, are not errors and there is nothing to correct.
    """
    if concept.confirmed_at is not None:
        raise MindError(
            f"{concept.label!r} is confirmed; retiring it is not the same act"
        )
    if concept.retired_at is None:
        concept.retired_at = now
        concept.save(update_fields=["retired_at"])
        _record(
            concept.owner,
            EventType.CONCEPT_RETIRED,
            occurred_at=now,
            actor=actor,
            payload={"concept": str(concept.public_id), "label": concept.label},
        )
    return concept


@transaction.atomic
def merge_concept(
    alias: ConceptCandidate,
    into: ConceptCandidate,
    *,
    now: datetime,
    actor: str,
) -> ConceptCandidate:
    """Record that two labels name one thing: "my brother" is "Bob".

    Confirmed by a person, never inferred outright — general coreference is
    unreliable, and one confirmation resolves every past and future mention.

    Depth is capped at one so that resolution is a single join. The two checks
    below produce clean errors; the trigger behind them closes the race where
    two concurrent merges each pass their own snapshot check.
    """
    _require_same_owner(alias, into)
    if alias.pk == into.pk:
        raise HierarchyTooDeep("a concept cannot be an alias of itself")
    if into.merged_into_id is not None:
        raise HierarchyTooDeep(
            f"{into.label!r} is itself an alias; merge into its canonical concept"
        )
    if ConceptCandidate.objects.filter(merged_into=alias).exists():
        raise HierarchyTooDeep(
            f"{alias.label!r} has aliases of its own and cannot become an alias"
        )

    alias.merged_into = into
    alias.save(update_fields=["merged_into"])
    _record(
        alias.owner,
        EventType.ALIAS_MERGED,
        occurred_at=now,
        actor=actor,
        payload={
            "alias": str(alias.public_id),
            "canonical": str(into.public_id),
            "alias_label": alias.label,
            "canonical_label": into.label,
        },
    )
    return alias


# ---------------------------------------------------------------------------
# Facets
# ---------------------------------------------------------------------------


def propose_facet(
    node: Node,
    *,
    kind: str,
    data: dict,
    now: datetime,
    actor: str,
    reason: str,
    origin: str = InferenceOrigin.INFERRED,
) -> Facet:
    """Offer a node a capability. Soft-applied, except for one kind.

    **The actionable facet may be proposed but never attached outright.** Every
    other facet is applied immediately and dismissed in one tap, because being
    wrong about one costs a row. This one creates an obligation, and an
    obligation nobody agreed to is worse than a missing feature -- so
    `confirm_actionable` is the only way it becomes real, and passing
    `origin=explicit` here is refused rather than quietly honoured.
    """
    if kind == FacetKind.ACTIONABLE and origin == InferenceOrigin.EXPLICIT:
        raise MindError(
            "an actionable facet is never attached outright -- propose it and "
            "confirm it, because it is the one kind that creates an obligation"
        )

    facet, created = Facet.objects.get_or_create(
        node=node,
        kind=kind,
        retired_at=None,
        defaults={"data": data, "origin": origin, "reason": reason},
    )
    if created:
        _record(
            node.owner,
            EventType.FACET_PROPOSED,
            node=node,
            occurred_at=now,
            actor=actor,
            payload={"kind": kind, "reason": reason},
        )
    return facet


@transaction.atomic
def confirm_actionable(facet: Facet, *, area=None, now: datetime, actor: str) -> Facet:
    """Accept a commitment, and make it one.

    **`area` is optional, and defaulting it is the point.** Requiring one put a
    filing decision at exactly the moment a person has already made a different
    decision -- yes, that is a task -- and asking a second question there is the
    thing this design refuses to do. `Item.owner` (August 14, 2026) is what
    makes an unfiled task a real task rather than an orphan; filing stays
    available for anyone who wants it, but it is no longer the toll on accepting.

    The merger's payoff, and the reason the two cores had to become one database
    before this could exist. Node, facet and task are written in a single
    transaction, so "a confirmed actionable facet with no live task" is not a
    state anything can reach -- no outbox, no reconciler, and no window in which
    somebody believes they recorded a dentist appointment and only half of it
    happened.

    The node is not consumed. It leaves the quiet tier, not the graph: the facet
    keeps pointing at both ends, so a task can always answer where it came from.
    That backlink is the defect this whole design exists to escape.
    """
    # Imported here rather than at module scope: the knowledge core reaching
    # into the task core is a one-directional seam and should be visible at the
    # one call site that uses it, not in a header that suggests a wider coupling.
    from lists import services as task_services

    from . import queries

    if facet.kind != FacetKind.ACTIONABLE:
        raise MindError(f"{facet.kind!r} is not a commitment")
    _require_live(facet.node)
    if area is not None and area.owner_id != facet.node.owner_id:
        raise MindError("a commitment cannot be filed in somebody else's area")

    # Two taps, or a tap against a stale page. Neither should double a
    # commitment, and the first decision's task is the one that counts.
    if facet.task_id is not None:
        return facet

    due = facet.data.get("due_date") or None
    task = task_services.create_item(
        area,
        queries.current_body(facet.node),
        due_date=due,
        recurrence=facet.data.get("recurrence") or None,
        owner=facet.node.owner,
        # Step 2 of one-capture-surface-plan.md. The Inbox route carried a
        # capture's tags to its task; this route produced an untagged one, which
        # was the last functional gap between them. `lists.Tag` and the concept
        # layer are two vocabularies for the same act, and this is where they
        # meet -- a confirmed concept becomes a tag on the task it produced.
        tags=queries.confirmed_concept_labels(facet.node),
    )

    facet.task = task
    facet.confirmed_at = now
    facet.save(update_fields=["task", "confirmed_at"])
    _record(
        facet.node.owner,
        EventType.FACET_CONFIRMED,
        node=facet.node,
        occurred_at=now,
        actor=actor,
        payload={"kind": facet.kind, "task": task.pk},
    )
    return facet


def record_maintenance_run(owner, *, now: datetime, actor: str) -> ActivityEvent:
    """Write down that the scheduled pass happened.

    The only event here whose subject is the corpus rather than a note, which is
    why it carries no node. Nothing else can answer the question: a pass that
    found no concepts and a pass that never ran leave identical tables behind,
    and `detector_readiness` reports what a detector *could* say rather than
    whether it was ever asked.
    """
    return _record(
        owner,
        EventType.MAINTENANCE_RAN,
        occurred_at=now,
        actor=actor,
        payload={},
    )


def dismiss_facet(facet: Facet, *, now: datetime, actor: str) -> Facet:
    """Say no to a proposal, without arguing about it.

    Retired rather than deleted, because "this was offered and declined" is a
    different fact from "this was never offered" -- and the second one cannot
    tell you the parser is wrong about something. `propose_facet` only ever
    matches a live facet, so retiring frees the same kind to be proposed again
    if the note is later edited into something that does read as a commitment.
    """
    if facet.retired_at is not None:
        return facet
    facet.retired_at = now
    facet.save(update_fields=["retired_at"])
    _record(
        # `facet.owner`, not `facet.node.owner`. A facet may cite a journal
        # entry instead of a node since increment 2, and reaching through the
        # node raised on every one of those -- the exact breakage the accessor
        # was added to prevent, found by the first producer that made one.
        facet.owner,
        EventType.FACET_DISMISSED,
        # Still the node where there is one: the log's own column is a node
        # reference and stays null for an entry-backed facet, whose source is
        # named in the payload instead.
        node=facet.node,
        occurred_at=now,
        actor=actor,
        payload={
            "kind": facet.kind,
            "reason": facet.reason,
            **({"entry": facet.entry_id} if facet.entry_id else {}),
        },
    )
    return facet


def commitments_without_tasks(owner) -> int:
    """Confirmed commitments whose task has gone. Should always be zero.

    The invariant is enforced by the transaction above, so this exists to say so
    in a number rather than to be trusted. A task deleted directly in the admin,
    or a future write path that forgets, shows up here instead of in a missed
    appointment -- which is the difference between finding a broken guarantee and
    being told about it by its consequence.
    """
    return Facet.objects.filter(
        node__owner=owner,
        kind=FacetKind.ACTIONABLE,
        confirmed_at__isnull=False,
        task__isnull=True,
    ).count()


# ---------------------------------------------------------------------------
# Mentions
# ---------------------------------------------------------------------------


@transaction.atomic
def propose_mention(
    node: Node,
    concept: ConceptCandidate,
    *,
    index_version: str,
    now: datetime,
    actor: str,
    span: tuple[int, int] | None = None,
    reason: str | None = None,
    origin: str = InferenceOrigin.INFERRED,
) -> Mention:
    _require_same_owner(node, concept)
    _require_live(node)
    start, end = span if span else (None, None)

    mention = Mention.objects.create(
        node=node,
        concept=concept,
        span_start=start,
        span_end=end,
        origin=origin,
        index_version=index_version,
        reason=reason,
        confirmed_at=now if origin == InferenceOrigin.EXPLICIT else None,
    )
    _record(
        node.owner,
        EventType.MENTION_PROPOSED,
        node=node,
        occurred_at=now,
        actor=actor,
        payload={
            "concept": str(concept.public_id),
            "span": list(span) if span else None,
            "reason": reason,
        },
    )
    return mention


@transaction.atomic
def extract_and_record_concepts(
    node: Node,
    *,
    now: datetime,
    actor: str = "system",
    index_version: str = "rules-v1",
) -> list[Mention]:
    """Find the referents a node names, and record them as unconfirmed candidates.

    Every concept and mention this creates is a proposal. Nothing downstream
    treats them as fact until the person confirms, which is what makes a crude
    extractor safe: over-generation costs a row and a line in a review list, never
    a wrong connection.

    Existing labels are passed back into the extractor so the concept layer
    bootstraps itself — once "Bob" has been established mid-sentence anywhere, the
    much commoner "Bob called today." resolves to the same referent instead of
    yielding nothing.
    """
    from .extraction import extract_concepts

    _require_live(node)

    known = list(
        ConceptCandidate.objects.filter(
            owner=node.owner, retired_at__isnull=True
        ).values_list("label", flat=True)
    )

    recorded: list[Mention] = []
    for found in extract_concepts(node.original_content, known_labels=known):
        concept = _concept_for_label(node.owner, found.label, now=now, actor=actor)
        mention, created = Mention.objects.get_or_create(
            node=node,
            concept=concept,
            span_start=found.span_start,
            span_end=found.span_end,
            defaults={
                "origin": InferenceOrigin.INFERRED,
                "index_version": index_version,
                "reason": f"capitalised as {found.label!r}",
            },
        )
        if created:
            recorded.append(mention)

    if recorded:
        _record(
            node.owner,
            EventType.MENTION_PROPOSED,
            node=node,
            occurred_at=now,
            actor=actor,
            payload={"count": len(recorded)},
        )
    return recorded


TYPED_TAG_REASON = "typed as a tag at capture"


@transaction.atomic
def record_typed_tags(
    node: Node, labels: Sequence[str], *, now: datetime, actor: str
) -> list[Mention]:
    """Turn tags somebody typed into confirmed concepts on this node.

    Step 1 of `design/one-capture-surface-plan.md`. It replaces a placeholder
    that wrote the strings onto the activity log under "tags kept, not yet
    modelled" -- honest about discarding nothing, and read by nothing.

    **A typed tag skips the gravity gate, and that is the whole decision.** A
    candidate normally earns its question with three mentions across a day,
    because *extraction* over-generates on purpose and an unfiltered queue would
    be the inbox this design avoids. That gate exists to filter the system's
    guesses. Somebody typing a label is not a guess; it is the confirmation the
    gate was waiting for. So the concept is confirmed outright and the mention
    is explicit.

    Reuses an existing candidate rather than making a second referent, matched
    the same case-insensitive way the concept layer already matches -- and
    **confirms one that extraction had guessed at and was still waiting on**,
    which is the case that most obviously should not produce a duplicate.

    Forgiving about its input on purpose. Tags arrive from a phone where a
    trailing comma is ordinary, and none of that is worth failing a capture
    over: the thought matters more than the tidiness of its labels.
    """
    mentions = []
    seen = set()
    for raw in labels or []:
        label = (raw or "").strip()
        if not label or label.casefold() in seen:
            continue
        seen.add(label.casefold())

        concept = _concept_for_label(node.owner, label, now=now, actor=actor)
        # Through the alias, never at it. A tag matching something already
        # merged into another concept belongs to the surviving one -- otherwise
        # typing an old name quietly rebuilds the split that merging fixed.
        concept = concept.merged_into or concept

        if concept.confirmed_at is None:
            concept.reason = TYPED_TAG_REASON
            concept.save(update_fields=["reason"])
            confirm_concept(concept, now=now, actor=actor)

        # One mention per node per concept. A retried capture, or somebody
        # adding a tag that is already there, must not deepen the evidence.
        existing = Mention.objects.filter(node=node, concept=concept).first()
        if existing is not None:
            mentions.append(existing)
            continue

        mentions.append(
            propose_mention(
                node,
                concept,
                index_version="typed",
                now=now,
                actor=actor,
                reason=TYPED_TAG_REASON,
                origin=InferenceOrigin.EXPLICIT,
            )
        )
    return mentions


def _concept_for_label(owner, label: str, *, now: datetime, actor: str):
    """The existing candidate for this label, or a new unconfirmed one.

    Matched case-insensitively against the live set, mirroring the partial unique
    index on `(owner, lower(label), concept_type)` — so "Mondly" and "mondly" are
    one referent rather than two.
    """
    existing = ConceptCandidate.objects.filter(
        owner=owner, label__iexact=label, retired_at__isnull=True
    ).first()
    if existing is not None:
        return existing

    return propose_concept(
        owner,
        label=label,
        concept_type=ConceptType.UNKNOWN,
        now=now,
        actor=actor,
        reason="named with a capital letter",
    )


@transaction.atomic
def confirm_mention(mention: Mention, *, now: datetime, actor: str) -> Mention:
    if mention.confirmed_at is None:
        mention.confirmed_at = now
        mention.save(update_fields=["confirmed_at"])
        _record(
            mention.node.owner,
            EventType.MENTION_CONFIRMED,
            node=mention.node,
            occurred_at=now,
            actor=actor,
            payload={"concept": str(mention.concept.public_id)},
        )
    return mention


# ---------------------------------------------------------------------------
# Edges
# ---------------------------------------------------------------------------

SYMMETRIC_RELATIONS = frozenset({EdgeRelation.RELATES_TO})


def _existing_edge(from_node: Node, to_node: Node, relation: str) -> Edge | None:
    """Find an edge already asserting this, in either direction if symmetric."""
    if relation in SYMMETRIC_RELATIONS:
        return Edge.objects.filter(relation=relation).filter(
            Q(from_node=from_node, to_node=to_node)
            | Q(from_node=to_node, to_node=from_node)
        ).first()
    return Edge.objects.filter(
        from_node=from_node, to_node=to_node, relation=relation
    ).first()


def _check_member_of_depth(from_node: Node, to_node: Node) -> None:
    """A node is either a container or a member, never both."""
    if Edge.objects.filter(
        relation=EdgeRelation.MEMBER_OF, to_node=from_node
    ).exists():
        raise HierarchyTooDeep(
            f"node {from_node.pk} already has members and cannot become a member"
        )
    if Edge.objects.filter(
        relation=EdgeRelation.MEMBER_OF, from_node=to_node
    ).exists():
        raise HierarchyTooDeep(
            f"node {to_node.pk} is already a member and cannot contain members"
        )


@transaction.atomic
def link(
    from_node: Node,
    to_node: Node,
    *,
    relation: str,
    now: datetime,
    actor: str,
    origin: str = InferenceOrigin.EXPLICIT,
    confidence: float | None = None,
) -> Edge:
    """Assert a confirmed relation between two nodes.

    Idempotent: asserting something already recorded returns the existing edge
    rather than failing. For a symmetric relation that includes the reverse
    direction, since A relates_to B and B relates_to A are one fact.
    """
    _require_same_owner(from_node, to_node)
    _require_live(from_node)
    _require_live(to_node)
    if from_node.pk == to_node.pk:
        raise MindError("a node cannot link to itself")

    existing = _existing_edge(from_node, to_node, relation)
    if existing is not None:
        return existing

    if relation == EdgeRelation.MEMBER_OF:
        _check_member_of_depth(from_node, to_node)

    edge = Edge.objects.create(
        owner=from_node.owner,
        from_node=from_node,
        to_node=to_node,
        relation=relation,
        origin=origin,
        confidence=confidence,
    )
    _record(
        from_node.owner,
        EventType.EDGE_CREATED,
        node=from_node,
        occurred_at=now,
        actor=actor,
        payload={
            "to_node": to_node.pk,
            "relation": relation,
            "origin": origin,
            "confidence": confidence,
        },
    )
    return edge


@transaction.atomic
def unlink(edge: Edge, *, now: datetime, actor: str) -> None:
    payload = {
        "from_node": edge.from_node_id,
        "to_node": edge.to_node_id,
        "relation": edge.relation,
    }
    owner = edge.owner
    edge.delete()
    _record(owner, EventType.EDGE_REMOVED, occurred_at=now, actor=actor, payload=payload)


# ---------------------------------------------------------------------------
# Connection hypotheses
# ---------------------------------------------------------------------------


class Citation(NamedTuple):
    """One node's contribution to a hypothesis, cited at the span level.

    The evidence is the sentence, not the whole note — which is what makes
    "assert only what the cited passages show" checkable by a reader.
    """

    node: Node
    span: tuple[int, int] | None = None
    reason: str | None = None


def hypothesis_fingerprint(
    detector: str, member_public_ids: Iterable[uuid_module.UUID], relation: str | None
) -> str:
    """A stable identity for "this detector proposing this set of nodes".

    Sorted, so member order cannot change the fingerprint. Unit-separator
    joined, since that byte appears in neither a UUID nor a detector name.

    This is what stops a batch run resurrecting last week's dismissals:
    uniqueness spans *resolved* hypotheses too, so dedupe is against everything
    ever seen rather than against what was confirmed.
    """
    parts = [detector, relation or "", *sorted(str(p) for p in member_public_ids)]
    return hashlib.sha256("\x1f".join(parts).encode()).hexdigest()


@transaction.atomic
def propose_hypothesis(
    owner,
    *,
    detector: str,
    citations: Sequence[Citation],
    confidence: float,
    label: str,
    index_version: str,
    now: datetime,
    actor: str = "system",
    relation: str | None = None,
    concept: ConceptCandidate | None = None,
) -> ConnectionHypothesis:
    """Propose a connection, or return the one already proposed.

    Two members minimum: fewer is not a connection. That is a cross-row
    aggregate and so cannot be a database constraint, which is why it is here.

    Returns an existing hypothesis when the fingerprint matches — including one
    already dismissed. The caller is expected to look at `resolution` and move
    on. Re-running a detector must be free of side effects.

    `label` is extractive: the mediating concept, or the distinguishing terms.
    `claim_text` stays null — no generative producer exists, and articulation
    when it arrives is user-initiated and never durable.
    """
    unique_nodes = {c.node.pk: c for c in citations}
    if len(unique_nodes) < 2:
        raise InvalidHypothesis(
            f"a hypothesis needs at least two distinct nodes, got {len(unique_nodes)}"
        )

    for citation in citations:
        if citation.node.owner_id != owner.pk:
            raise NotYours(f"node {citation.node.pk} belongs to someone else")
    if concept is not None and concept.owner_id != owner.pk:
        raise NotYours("concept belongs to someone else")

    fingerprint = hypothesis_fingerprint(
        detector, (c.node.public_id for c in unique_nodes.values()), relation
    )
    existing = ConnectionHypothesis.objects.filter(
        owner=owner, fingerprint=fingerprint
    ).first()
    if existing is not None:
        return existing

    hypothesis = ConnectionHypothesis.objects.create(
        owner=owner,
        detector=detector,
        relation=relation,
        concept=concept,
        confidence=confidence,
        label=label,
        index_version=index_version,
        fingerprint=fingerprint,
        created_at=now,
    )
    for citation in unique_nodes.values():
        start, end = citation.span if citation.span else (None, None)
        HypothesisMember.objects.create(
            hypothesis=hypothesis,
            node=citation.node,
            span_start=start,
            span_end=end,
            contribution_reason=citation.reason,
        )

    _record(
        owner,
        EventType.HYPOTHESIS_PROPOSED,
        occurred_at=now,
        actor=actor,
        payload={
            "hypothesis": str(hypothesis.public_id),
            "detector": detector,
            "confidence": confidence,
            "members": len(unique_nodes),
        },
    )
    return hypothesis


@transaction.atomic
def surface_hypothesis(
    hypothesis: ConnectionHypothesis,
    *,
    now: datetime,
    actor: str,
    review_window: timedelta | None = None,
) -> ConnectionHypothesis:
    """Show a hypothesis to the person, and start its clock.

    **Silence is not consent.** The review window is anchored to the first time
    this was actually surfaced, never to when it was created. A window measured
    from creation would expire on hypotheses the person never saw, so
    "undismissed" would mean "unseen" rather than "accepted". Surfacing again
    counts the view but does not extend the window.
    """
    if hypothesis.resolved_at is not None:
        raise AlreadyResolved(f"hypothesis {hypothesis.pk} is already resolved")

    fields = ["surface_count"]
    hypothesis.surface_count += 1
    if hypothesis.first_surfaced_at is None:
        hypothesis.first_surfaced_at = now
        fields.append("first_surfaced_at")
        if review_window is not None:
            hypothesis.review_window_expires_at = now + review_window
            fields.append("review_window_expires_at")

    hypothesis.save(update_fields=fields)
    _record(
        hypothesis.owner,
        EventType.HYPOTHESIS_SURFACED,
        occurred_at=now,
        actor=actor,
        payload={
            "hypothesis": str(hypothesis.public_id),
            "surface_count": hypothesis.surface_count,
        },
    )
    return hypothesis


def _resolve(
    hypothesis: ConnectionHypothesis,
    resolution: str,
    *,
    now: datetime,
    actor: str,
    payload: dict | None = None,
) -> None:
    hypothesis.resolved_at = now
    hypothesis.resolution = resolution
    hypothesis.save(update_fields=["resolved_at", "resolution"])
    _record(
        hypothesis.owner,
        EventType.HYPOTHESIS_RESOLVED,
        occurred_at=now,
        actor=actor,
        payload={
            "hypothesis": str(hypothesis.public_id),
            "detector": hypothesis.detector,
            "resolution": resolution,
            **(payload or {}),
        },
    )


@transaction.atomic
def confirm_hypothesis(
    hypothesis: ConnectionHypothesis, *, now: datetime, actor: str
) -> list[Edge]:
    """Accept a hypothesis, promoting it into the confirmed graph.

    This is the boundary where a proposal becomes part of the person's own
    structure, and nothing generated crosses it: a two-member hypothesis becomes
    one edge, and a larger one becomes a meta-node carrying the *extractive*
    label with `member_of` edges to its members. Any `claim_text` is left
    behind — the person names a confirmed thread, or it keeps the extracted
    label.
    """
    if hypothesis.resolved_at is not None:
        raise AlreadyResolved(f"hypothesis {hypothesis.pk} is already resolved")

    citations = list(hypothesis.members.select_related("node"))
    if len(citations) < 2:
        raise InvalidHypothesis(
            "hypothesis no longer has two members; its evidence is incomplete"
        )

    created: list[Edge] = []

    if len(citations) == 2:
        a, b = citations[0].node, citations[1].node
        created.append(
            link(
                a,
                b,
                relation=hypothesis.relation or EdgeRelation.RELATES_TO,
                origin=InferenceOrigin.INFERRED,
                confidence=hypothesis.confidence,
                now=now,
                actor=actor,
            )
        )
        _resolve(
            hypothesis,
            HypothesisResolution.CONFIRMED,
            now=now,
            actor=actor,
            payload={"edges": len(created)},
        )
        return created

    # A thread: its own node, with the members belonging to it. Depth stays at
    # one, so a member that is already a container or already a member cannot
    # join — checked up front to give a clear error rather than a trigger's.
    thread = Node.objects.create(
        owner=hypothesis.owner,
        original_content=hypothesis.label,
        captured_at=now,
        source=NodeSource.THREAD,
    )
    for citation in citations:
        created.append(
            link(
                citation.node,
                thread,
                relation=EdgeRelation.MEMBER_OF,
                origin=InferenceOrigin.INFERRED,
                confidence=hypothesis.confidence,
                now=now,
                actor=actor,
            )
        )

    _resolve(
        hypothesis,
        HypothesisResolution.CONFIRMED,
        now=now,
        actor=actor,
        payload={"thread_node": thread.pk, "edges": len(created)},
    )
    return created


@transaction.atomic
def dismiss_hypothesis(
    hypothesis: ConnectionHypothesis, *, now: datetime, actor: str
) -> None:
    """Reject a hypothesis, permanently.

    Permanent because the fingerprint constraint spans resolved rows: the same
    detector proposing the same nodes will find this row and return it rather
    than asking again. A dismissal that had to be repeated weekly would train
    the person to ignore the review surface, which costs more than the
    connection was worth.
    """
    if hypothesis.resolved_at is not None:
        raise AlreadyResolved(f"hypothesis {hypothesis.pk} is already resolved")
    _resolve(hypothesis, HypothesisResolution.DISMISSED, now=now, actor=actor)


class ReviewResponse(Enum):
    """What the person did with a resurfaced node."""

    KEPT = "kept"
    """Worth seeing again, on the usual stretching schedule."""

    BURIED = "buried"
    """Less often. Honoured by stretching the interval much harder — the
    difference between a review surface and a nag."""


# The default window a surfaced proposal gets before it expires undecided. Starts
# when it is shown, never when it was created.
DEFAULT_REVIEW_WINDOW = timedelta(days=21)


@transaction.atomic
def open_review(
    owner,
    *,
    now: datetime,
    actor: str,
    limit: int = 5,
    review_window: timedelta | None = DEFAULT_REVIEW_WINDOW,
) -> list[ConnectionHypothesis]:
    """The review surface: return the proposals to show, and mark them shown.

    **Reading and surfacing are one operation, deliberately.** A separate read-only
    path would eventually be used to display proposals, and then `first_surfaced_at`
    would stay null while the person looked straight at them — after which inaction
    is indistinguishable from never having seen it, and every rule built on the
    review window silently means nothing. Making it impossible to display without
    marking is cheaper than remembering to mark.

    `limit` is small by default. Precision beats recall here, so the surface is a
    handful to consider rather than a queue to work through; a review that feels
    like an inbox has already failed.
    """
    from . import queries

    hypotheses = list(queries.pending_hypotheses(owner)[:limit])
    for hypothesis in hypotheses:
        surface_hypothesis(
            hypothesis, now=now, actor=actor, review_window=review_window
        )

    _record(
        owner,
        EventType.REVIEWED,
        occurred_at=now,
        actor=actor,
        payload={"surfaced": len(hypotheses), "kind": "connection_review"},
    )
    return hypotheses


@transaction.atomic
def mark_reviewed(
    node: Node,
    *,
    response: ReviewResponse = ReviewResponse.KEPT,
    now: datetime,
    actor: str,
) -> ActivityEvent:
    """Record that a node was resurfaced and what the person did with it.

    The event is the whole mechanism: `queries.review_state` folds these to derive
    when the node comes round again, so nothing needs a mutable schedule column and
    the reasoning behind any given due date stays reconstructible.
    """
    _require_live(node)
    return _record(
        node.owner,
        EventType.REVIEWED,
        node=node,
        occurred_at=now,
        actor=actor,
        payload={"response": response.value},
    )


@transaction.atomic
def expire_stale_hypotheses(
    owner, *, now: datetime, unsurfaced_after: timedelta, actor: str = "system"
) -> int:
    """Close out hypotheses that were never decided. Nothing is promoted.

    Two populations expire, and neither ripens into acceptance:

    * **Surfaced, window elapsed, still undecided.** The design document allows
      a soft-apply tier where this would promote automatically. It is
      deliberately *not* wired up in the lab: auto-promotion would manufacture
      confirmations that no one made, and per-detector accept rate is the
      measurement the lab exists to produce. Promoting on silence would corrupt
      the only evidence available about whether the mechanic works.
    * **Never surfaced and older than `unsurfaced_after`.** These the person had
      no chance to judge, so they age out without ever entering the graph.

    Returns how many were closed.
    """
    stale = ConnectionHypothesis.objects.filter(owner=owner, resolved_at__isnull=True).filter(
        Q(review_window_expires_at__lte=now)
        | Q(first_surfaced_at__isnull=True, created_at__lte=now - unsurfaced_after)
    )

    closed = 0
    for hypothesis in stale:
        _resolve(
            hypothesis,
            HypothesisResolution.EXPIRED,
            now=now,
            actor=actor,
            payload={"was_surfaced": hypothesis.first_surfaced_at is not None},
        )
        closed += 1
    return closed


# ---------------------------------------------------------------------------
# Instrumentation
# ---------------------------------------------------------------------------


@transaction.atomic
def record_retrieval_miss(
    owner,
    *,
    query_text: str,
    now: datetime,
    context: str = MissContext.SEARCH,
) -> RetrievalMiss:
    """Record that the person knew they had written something and could not
    find it.

    The strongest evidence available about whether semantic retrieval is needed,
    because the correct answer is known. Vocabulary drift — the same idea named
    twice — shows up here first and nowhere else, and full-text search cannot
    surface it by construction.
    """
    return RetrievalMiss.objects.create(
        owner=owner, query_text=query_text, context=context, created_at=now
    )


def resolve_retrieval_miss(miss: RetrievalMiss, node: Node) -> RetrievalMiss:
    """Attach the node that was being looked for, making the miss diagnosable.

    A miss with a known target is what the embeddings decision is measured
    against: would a semantic index have surfaced this?
    """
    _require_same_owner(miss, node)
    miss.resolved_node = node
    miss.save(update_fields=["resolved_node"])
    return miss


# ---------------------------------------------------------------------------
# Deletion
# ---------------------------------------------------------------------------


def _invalidate_hypotheses_citing(
    node: Node, *, now: datetime, actor: str, why: str
) -> int:
    """Close every undecided hypothesis whose evidence includes this node.

    Evidence must not dangle: a claim citing a passage that no longer exists
    cannot be judged, so it is expired rather than left standing. Note the
    contrast with the log, which deliberately keeps pointing at purged nodes —
    an event asserts what happened, while a hypothesis asserts what is true.
    """
    affected = ConnectionHypothesis.objects.filter(
        members__node=node, resolved_at__isnull=True
    ).distinct()
    count = 0
    for hypothesis in affected:
        _resolve(
            hypothesis,
            HypothesisResolution.EXPIRED,
            now=now,
            actor=actor,
            payload={"invalidated_by": why, "node": node.pk},
        )
        count += 1
    return count


@transaction.atomic
def delete_node(node: Node, *, now: datetime, actor: str) -> Node:
    """Remove a node from the working system immediately.

    Soft, so that a stated retention window governs the actual purge — but
    "gone from the working system" is immediate and real, not a hidden flag that
    still shows up in results. Undecided hypotheses citing it are invalidated at
    once, because their evidence has effectively vanished.
    """
    if node.deleted_at is not None:
        return node

    invalidated = _invalidate_hypotheses_citing(
        node, now=now, actor=actor, why="node_deleted"
    )
    node.deleted_at = now
    node.save(update_fields=["deleted_at"])
    _record(
        node.owner,
        EventType.DELETED,
        node=node,
        occurred_at=now,
        actor=actor,
        payload={"hypotheses_invalidated": invalidated},
    )
    return node


@transaction.atomic
def purge_node(node: Node, *, now: datetime, actor: str) -> list[str]:
    """Delete a node for real, once its retention window has passed.

    Returns the storage keys whose blobs the caller must remove. That boundary
    is deliberately visible rather than hidden behind an abstraction: object
    storage is not transactional with Postgres, so a purge that claimed to have
    removed bytes it had not would be a lie in the one place the product
    promises the most.

    The log keeps its rows, and they keep pointing at the vanished node id — an
    event asserts what happened, and that stays true. The purge event's payload
    retains no content.
    """
    owner = node.owner
    node_pk = node.pk
    storage_keys = list(node.attachments.values_list("storage_key", flat=True))

    _invalidate_hypotheses_citing(node, now=now, actor=actor, why="node_purged")
    node.delete()

    _record(
        owner,
        EventType.PURGED,
        occurred_at=now,
        actor=actor,
        payload={"node": node_pk, "attachments_to_remove": len(storage_keys)},
    )
    return storage_keys


# ---------------------------------------------------------------------------
# Commitments read out of a journal entry — planning-assistant-plan.md 2
# ---------------------------------------------------------------------------

# Sentence-ish, and deliberately not a parser. What this needs is offsets that
# fall on plausible boundaries; over-splitting costs a proposal somebody
# dismisses, while a real NLP dependency costs the determinism the whole live
# path rests on. Newlines end a sentence because journal writing uses them as
# punctuation.
_SENTENCE = re.compile(r"[^.!?\n]+[.!?]*")

# **The journal needs a different signal from capture, and this is it.**
#
# `find_commitment` fires on a date, which is right for a capture: somebody
# typing "dentist tomorrow" into a box has already decided it is a commitment,
# and the date is the only thing left to read. Journal writing is prose, and
# prose is full of dates that promise nothing — "nothing else today", "a quiet
# morning", "saw them on Tuesday" all carry one and commit to none. Proposing
# from those is the panel that gets ignored.
#
# It fails the other way too, and worse: *"I still need to ask Maya about the
# venue"* is the canonical example this increment was written around, and it
# has no date at all. Date-only would have missed the thing it is for while
# firing on the narrative around it.
#
# So a journal sentence must read as an undertaking. Deliberately first person
# and deliberately narrow: "the invoice must be paid" is a fact about the
# world, "I must pay the invoice" is a promise. Missing one costs a tap;
# inventing one puts a commitment nobody made into somebody's week, and those
# two failures are not symmetric.
_PROMISE = re.compile(
    r"\bi (?:need|have|want|ought|plan|intend|mean)\b"
    r"|\bi(?:'ll| will| must| should)\b"
    r"|\bneed to\b|\bmust\b|\bhave to\b|\bought to\b"
    r"|\bremember to\b|\bdon't forget\b|\bmake sure\b|\bchase up\b",
    re.IGNORECASE,
)


def _sentences(text: str):
    """``(start, end, text)`` per sentence, with offsets into ``text``."""
    for match in _SENTENCE.finditer(text):
        if match.group().strip():
            yield match.start(), match.end(), match.group()


def _commitment_fingerprint(text: str) -> str:
    """Stable over the sentence, and deliberately blind to where it sits.

    Typing a line at the top of an entry shifts every offset below it, so a
    fingerprint including the span would re-propose the whole day on one
    insertion — the same failure as not deduping at all. This hashes the words:
    editing a sentence re-proposes it, which is right, and moving it does not,
    which is also right.

    Two identical sentences in one entry therefore collide, and that is the
    correct reading — writing the same promise twice in a day is one promise.
    """
    return hashlib.sha256(
        " ".join(text.split()).casefold().encode("utf-8")
    ).hexdigest()[:64]


@transaction.atomic
def propose_journal_commitments(entry, *, now: datetime, actor: str) -> list[Facet]:
    """Offer an actionable facet for each sentence of a day that reads as one.

    **Per sentence, not per entry.** `find_commitment` returns one commitment
    for one piece of text; a day's writing is several, and running it over a
    whole field would find the first date in the day, attribute it to the entire
    page, and look confident doing so.

    **Read against the entry's own date, never the clock.** "Tomorrow" written
    on Tuesday means Wednesday whenever this runs — the same call
    `_propose_any_commitment` makes with `captured_at`, and for the same reason:
    a relative date is exactly the material a wrong "today" ruins.

    Idempotent by fingerprint, which matters more here than anywhere else. An
    entry is saved on every pause in typing, so a producer proposing afresh each
    time would make the surface unusable before lunch. Dismissed suggestions
    stay dismissed, because the constraint spans every state.
    """
    body = entry_body(entry)
    if not body.strip():
        return []

    proposed: list[Facet] = []
    for start, end, sentence in _sentences(body):
        if not _PROMISE.search(sentence):
            continue

        # The date is enrichment, not the trigger. A promise with one carries
        # it through to the task; a promise without one is still a promise,
        # and demanding a date would drop the example this was built for.
        found = find_commitment(sentence, today=entry.date)
        reason = (
            f"reads as a commitment — {found.reason}" if found else "reads as a commitment"
        )

        facet, created = Facet.objects.get_or_create(
            entry=entry,
            fingerprint=_commitment_fingerprint(sentence),
            defaults={
                "kind": FacetKind.ACTIONABLE,
                "origin": InferenceOrigin.INFERRED,
                "reason": reason,
                "span_start": start,
                "span_end": end,
                "data": {
                    # Null rather than absent when nothing was read, so a
                    # consumer never has to tell "no date" from "field missing".
                    "due_date": found.due_date.isoformat() if found else None,
                    "recurrence": found.recurrence if found else None,
                },
            },
        )
        if created:
            _record(
                entry.owner,
                EventType.FACET_PROPOSED,
                occurred_at=now,
                actor=actor,
                payload={
                    "kind": FacetKind.ACTIONABLE,
                    "reason": reason,
                    "entry": entry.pk,
                },
            )
            proposed.append(facet)
        elif facet.retired_at is None and facet.span_start != start:
            # The same sentence, moved. Keep the proposal and correct where it
            # points, so its quote does not drift off the words that caused it.
            facet.span_start, facet.span_end = start, end
            facet.save(update_fields=["span_start", "span_end"])

    return proposed
