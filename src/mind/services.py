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
from dataclasses import dataclass, field
import re
import uuid as uuid_module
from datetime import datetime, timedelta
from enum import Enum
from typing import Iterable, NamedTuple, Sequence

from django.db import transaction
from django.db.models import Count, Max, Q
from django.utils import timezone

from .commitments import find_commitment

# The two commitment producers, named once. Capture reads a date out of a terse
# note; the journal reads an undertaking out of prose. Separate names because
# their accept rates are separate questions -- see `Facet.producer`.
CAPTURE_COMMITMENT = "capture_commitment"
JOURNAL_COMMITMENT = "journal_commitment"
from .models import (
    CaptureSession,
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
    Decision,
    RetrievalMiss,
    Revision,
    Source,
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
    #: The bytes themselves -- D9's answer. See `Attachment.content`.
    content: bytes


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
    session=None,
    came_from=None,
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
        session=session,
        came_from=came_from,
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

    # **Rule 2: during a dump, create nothing that requires attention.**
    #
    # *Call the dentist by Friday* would normally offer a commitment on the way
    # back, which is right for one thought and wrong forty times in two
    # minutes -- that is the surface teaching somebody to skim past it, and the
    # plan calls that unrecoverable. The producers run once at the end
    # instead, over the whole sitting, under a budget.
    if session is None:
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
# DARK: no production caller. The put-away half of `capture`.
# Trigger: Track E increment 19. `queries.live_nodes` already excludes
# archived nodes everywhere, which is why nothing looks broken.
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
        producer=CAPTURE_COMMITMENT,
    )


# The two things a person can say about a note the question heuristic surfaced.
# Both are *corrections* to a read-time predicate rather than restatements of
# it, which is why they are stored while question-ness is not: a stored flag
# would be a second answer to what `looks_like_a_question` already answers, and
# the two would drift. A decision about one's own note should outlive any
# predicate; a predicate's own output should not outlive the predicate.
QUESTION_RESOLVED = "resolved"
NOT_A_QUESTION = "not_a_question"


@dataclass(frozen=True)
class Grew:
    """What came out of something you read — S15's other half."""

    notes: list = field(default_factory=list)
    tasks: list = field(default_factory=list)

    @property
    def has_anything(self):
        return bool(self.notes or self.tasks)


@dataclass(frozen=True)
class DueToRevisit:
    """Decisions worth looking at again, and the ones nothing can find.

    **Two lists and a count, never one number.** A decision waiting on a date
    and a decision waiting on *"if anyone asks for the meeting back"* are not
    the same state, and a read that returned them together would claim to have
    checked something it cannot check.
    """

    past_their_date: list = field(default_factory=list)
    #: How many are waiting on a condition in words. Counted rather than
    #: dropped -- the same absence discipline as `nights_not_recorded` and D5:
    #: silence about them would read as *no decision has a trigger*.
    waiting_on_a_condition: int = 0

    @property
    def about_conditions(self):
        if not self.waiting_on_a_condition:
            return ""
        return (
            f"{self.waiting_on_a_condition} more name a condition in words, "
            "which cannot be checked by anything -- they come back when you "
            "notice, not when Clarice does"
        )

    @property
    def has_anything(self):
        return bool(self.past_their_date or self.waiting_on_a_condition)


@transaction.atomic
def record_decision(
    owner,
    *,
    question: str,
    chose: str,
    considered: str = "",
    cites=None,
    revisit_when: str = "",
    revisit_after=None,
    supersedes=None,
    now: datetime,
) -> Decision:
    """Record what was chosen, over what, and what would bring it back — S11.

    **The citation is a snapshot as well as a link**, which is this codebase's
    existing move and a widening of the v3 plan's *"must cite a `Revision`"*.
    See `Decision` for why a `Revision` alone cannot carry it.

    **Superseding stamps the old one rather than deleting it.** *What he
    considered at the time* is only answerable if the time survives, and the
    recursion the product hangs from is that the previous answer stays
    available as evidence.
    """
    if not chose.strip():
        raise MindError("a decision needs something chosen")
    if supersedes is not None and supersedes.owner_id != owner.pk:
        raise NotYours("that decision belongs to someone else")

    cited_text, cited_seq = "", None
    if cites is not None:
        from . import queries

        cited_text = queries.current_body(cites)
        cited_seq = (
            cites.revisions.order_by("-seq").values_list("seq", flat=True).first()
        )

    decision = Decision.objects.create(
        owner=owner,
        question=question.strip(),
        chose=chose.strip(),
        considered=considered.strip(),
        revisit_when=revisit_when.strip(),
        revisit_after=revisit_after,
        decided_at=now,
        supersedes=supersedes,
        cited_node=cites,
        cited_text=cited_text,
        cited_revision_seq=cited_seq,
    )

    if supersedes is not None and supersedes.revisited_at is None:
        supersedes.revisited_at = now
        supersedes.save(update_fields=["revisited_at"])

    return decision


@transaction.atomic
def revisit_decision(decision, *, now: datetime) -> Decision:
    """Mark that a decision has been looked at again, without replacing it.

    Looking again and changing your mind are different acts: one stops it being
    due, the other produces a new decision that supersedes it. Folding them
    would mean you could not confirm a decision still stands.
    """
    if decision.revisited_at is None:
        decision.revisited_at = now
        decision.save(update_fields=["revisited_at"])
    return decision


def decisions_citing(node):
    """The decisions a note provoked — the first third of S11's done-means."""
    return Decision.objects.filter(cited_node=node).order_by("decided_at")


def decisions_to_revisit(owner, *, on) -> "DueToRevisit":
    """What is worth looking at again — the third of S11's done-means.

    **Only the dated ones can be found**, and the rest are counted rather than
    ignored. A condition in words is what makes a decision honest and is
    checkable by nobody but the person; saying so is the difference between a
    read that is incomplete and one that is misleading.
    """
    live = Decision.objects.filter(owner=owner, revisited_at__isnull=True)
    return DueToRevisit(
        past_their_date=list(
            live.exclude(revisit_after=None)
            .filter(revisit_after__lte=on)
            .order_by("revisit_after")
        ),
        waiting_on_a_condition=live.filter(revisit_after=None)
        .exclude(revisit_when="")
        .count(),
    )


@transaction.atomic
def record_source(owner, *, title: str, url: str = "", author: str = "", now: datetime) -> Source:
    """Record something you read — S15.

    **Idempotent on the URL**, because a person reads an article, notes
    something, comes back a week later and notes something else. Two rows would
    split what grew out of it in half, which is the whole value of the model.

    A title is required and a URL is not: a row with a URL and no title is a
    bookmark, and what this records is something you read, which you can name.
    """
    if not title.strip():
        raise MindError("a source needs a title")
    if url.strip():
        existing = Source.objects.filter(owner=owner, url=url.strip()).first()
        if existing is not None:
            return existing
    return Source.objects.create(
        owner=owner,
        title=title.strip(),
        url=url.strip(),
        author=author.strip(),
        created_at=now,
    )


def what_grew_from(source) -> "Grew":
    """The notes that came out of a source, and the tasks those became.

    **The tasks are reached rather than stored**, along the chain the merger
    already records: `Node` → confirmed actionable `Facet` → `Item`. A source
    carrying its own task list would be a copy free to disagree with it.

    Live notes only. A source page is not a way round `live_nodes`.
    """
    from . import queries

    notes = list(
        queries.live_nodes(source.owner).filter(came_from=source).order_by("captured_at")
    )
    tasks = [
        facet.task
        for facet in Facet.objects.filter(
            node__in=notes, kind=FacetKind.ACTIONABLE, task__isnull=False
        )
        .exclude(confirmed_at=None)
        .select_related("task")
        .order_by("confirmed_at")
    ]
    return Grew(notes=notes, tasks=tasks)


# DARK: no production caller. **Not an undo half** -- a read whose surface was
# never built. `Source` and `came_from` are live and `grew_from` above has a
# caller, so the chain this walks is real; nothing asks a *task* the question.
# Trigger: anywhere a task is read in the task core saying where it came from
# -- which is the second half of *six months later he can still tell*, and the
# half `product-stories.md` scores.
def what_a_task_was_read_in(task):
    """The source a task ultimately came out of, if it came out of one.

    *Six months later he can still tell where they came from.* Read along task,
    facet, node, source rather than stored on the task -- the chain exists, and
    a copy would be free to disagree with it.
    """
    facet = (
        Facet.objects.filter(task=task, node__isnull=False)
        .exclude(confirmed_at=None)
        .select_related("node__came_from")
        .first()
    )
    return facet.node.came_from if facet is not None else None


@transaction.atomic
# DARK: no production caller. **Not an undo half** -- a writer with no surface,
# which is why `FacetKind.GOAL` is still never written in production: this
# function is what would end that, and nothing calls it. A plan reading *GOAL
# was wired* is reading the writer, not a write.
# Trigger: the project surface choosing a note as the outcome -- one control
# beside `Project.desired_outcome`, whose text field is the second place this
# exists to stop drifting from.
def make_it_the_goal(node: Node, project, *, now: datetime, actor: str) -> Facet:
    """Say that this note is what a project is for -- v3's *Unify*.

    **`FacetKind.GOAL` has been declared since the merger and nothing ever
    wrote one**, which put it in the August 21 inventory's
    *declared-but-never-written vocabulary*. `EPISTEMIC` was in exactly that
    position and `_set_epistemic_status` below is the precedent this follows.

    **What it buys is the direction that did not exist.**
    `Project.desired_outcome` is a text field somebody types. A `GOAL` facet
    says *this note is that outcome*, so the sentence a person actually wrote
    -- with its capture time, its concepts and its own life -- becomes the
    project's stated end rather than a paraphrase living in a second place,
    free to drift from it.

    `origin=EXPLICIT`, always, for the reason `_set_epistemic_status` gives: a
    decision nobody can tell from a guess is one nobody can argue with later.

    **One live goal per node**, which is `facet_one_live_per_kind` doing what
    it was built for -- changing your mind is a change, not a second opinion
    beside the first.
    """
    _require_live(node)
    if project.owner_id != node.owner_id:
        raise NotYours("that project belongs to someone else")

    facet = node.facets.filter(
        kind=FacetKind.GOAL, retired_at__isnull=True
    ).first()
    already = facet is not None and facet.data.get("project") == project.pk
    if facet is None:
        facet = Facet.objects.create(
            node=node,
            kind=FacetKind.GOAL,
            origin=InferenceOrigin.EXPLICIT,
            confirmed_at=now,
            data={"project": project.pk},
        )
    elif not already:
        facet.data = {**facet.data, "project": project.pk}
        facet.origin = InferenceOrigin.EXPLICIT
        facet.confirmed_at = now
        facet.save(update_fields=["data", "origin", "confirmed_at"])

    # The note's own words become the project's stated end. Written through
    # rather than mirrored on a schedule: two copies that drift is the failure
    # this is meant to remove, not one it should introduce.
    # Imported here rather than at module scope, the way this file already
    # reaches for `queries` twice below: the two are paired and a top-level
    # import would make the cycle real.
    from . import queries

    body = queries.current_body(node)
    if project.desired_outcome != body:
        project.desired_outcome = body
        project.save(update_fields=["desired_outcome"])

    if not already:
        # Guarded, like every emitter since C4. A corrigible property re-saved
        # is not a second act, and this writes where DELETE is refused.
        _record(
            node.owner,
            EventType.FACET_CONFIRMED,
            node=node,
            occurred_at=now,
            actor=actor,
            payload={"kind": FacetKind.GOAL, "project": project.pk},
        )
    return facet


def _set_epistemic_status(node: Node, status: str, *, now: datetime, actor: str) -> Facet:
    """Record what a person decided about a note's epistemic standing.

    `FacetKind.EPISTEMIC` has been declared since the merger and nothing ever
    wrote one. `open_question.py` says its signal *should* have been a
    `question` epistemic status and settled for reading question-shaped text
    because "the lab has no facet table" — a substitution to revisit once one
    existed. It exists; this is the revisit, for the correction half.

    `origin=EXPLICIT`, always. A resolution nobody can tell from a guess is a
    resolution nobody can argue with later.

    Updates rather than accumulates: one live epistemic facet per node is the
    constraint, and changing your mind is a change of status, not a second
    opinion alongside the first.
    """
    facet = node.facets.filter(
        kind=FacetKind.EPISTEMIC, retired_at__isnull=True
    ).first()
    if facet is None:
        facet = Facet.objects.create(
            node=node,
            kind=FacetKind.EPISTEMIC,
            origin=InferenceOrigin.EXPLICIT,
            data={"status": status},
        )
    elif facet.data.get("status") != status:
        facet.data = {**facet.data, "status": status}
        facet.origin = InferenceOrigin.EXPLICIT
        facet.save(update_fields=["data", "origin"])

    _record(
        node.owner,
        EventType.FACET_CONFIRMED,
        node=node,
        occurred_at=now,
        actor=actor,
        payload={"kind": FacetKind.EPISTEMIC, "status": status},
    )
    return facet


def resolve_question(node: Node, *, now: datetime, actor: str) -> Facet:
    """"This is settled", with nothing to point at.

    The other route is better where it is available: an `answers` edge names
    *what* settled it and carries the connection, where this carries only the
    conclusion. But somebody who simply knows a thing is decided has no node to
    name, and demanding one would be asking for a citation they do not have —
    which is how a loose end stays on a list forever.
    """
    return _set_epistemic_status(node, QUESTION_RESOLVED, now=now, actor=actor)


def dismiss_as_question(node: Node, *, now: datetime, actor: str) -> Facet:
    """"This was never a question."

    `looks_like_a_question` is three text signals and a rhetorical question is
    a false positive by construction. This is the correction, and it is the
    only signal that heuristic will ever get — the count of notes it read as
    questions and a person did not.

    A different fact from `resolve_question`, deliberately. Collapsing "I
    settled this" into "this was never asked" would spend the correction signal
    to save one status value.
    """
    return _set_epistemic_status(node, NOT_A_QUESTION, now=now, actor=actor)


# DARK: no production caller. The undo half of `resolve_question`, which has two callers --
# `mind/api_v1.py` and `mind/views.py`. Trigger: Track E increment 19.
def reopen_question(node: Node, *, now: datetime, actor: str) -> None:
    """Undo either statement, keeping the record that it was made.

    Retired rather than deleted, the same call `dismiss_facet` makes: "this was
    settled and then was not" is a different fact from "this was never
    settled", and only one of them can tell you somebody changed their mind.
    """
    for facet in node.facets.filter(
        kind=FacetKind.EPISTEMIC, retired_at__isnull=True
    ):
        facet.retired_at = now
        facet.save(update_fields=["retired_at"])
        _record(
            node.owner,
            EventType.FACET_DISMISSED,
            node=node,
            occurred_at=now,
            actor=actor,
            payload={"kind": FacetKind.EPISTEMIC, "reopened": True},
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

    # **Saying the same thing again is not a correction.** C4's shape, one
    # module over: `set_intention` recorded a no-op save on an endpoint whose
    # own docstring promised idempotence, and every blur re-save wrote a
    # permanent row into a table that refuses `DELETE`. A correction surface is
    # exactly where a double-submit happens, so the guard arrives with the door
    # (Track E increment 21) rather than after somebody finds the duplicates.
    #
    # Returns the standing revision rather than None, so a caller can treat
    # "already said that" and "now says that" the same way.
    current = locked.revisions.order_by("-seq").first()
    if current is not None and current.body == body:
        return current
    if current is None and locked.original_content == body:
        return None

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


#: What kinds of memory a person can say a note is — Track B increment 6.
#:
#: Six of the brief's fourteen, and the rest are values away rather than work
#: away. **A capability is not a role**: `ACTIONABLE` carries a due date, a
#: recurrence and its own confirmation path, and routing it through here would
#: walk round `confirm_actionable` — the one facet that may never be attached
#: outright.
MEMORY_ROLES = (
    FacetKind.RECIPE,
    FacetKind.OCCASION,
    FacetKind.DREAM,
    FacetKind.FEAR,
    FacetKind.DESIRE,
    FacetKind.PREFERENCE,
)

#: **Nothing proposes a role yet, and that is declared rather than half-built.**
#:
#: The increment says *proposed after capture*, which needs a producer — and a
#: role classifier built with no evidence is a proposer whose accept rate
#: nobody can read. `Facet.producer` and the accept-rate machinery exist
#: precisely to judge one, and are the named trigger: when there is a corpus
#: worth classifying, a producer can be added and measured like every other.
#:
#: Until then a person says what a memory is, and nothing guesses. Which also
#: keeps the other half of the increment true without any effort: *never asked
#: for* — capture is untouched.
ROLE_PROPOSAL_IS_DEFERRED = True


#: What may be uploaded, and how much of it — Track D increment 16.
#:
#: **An allowlist, for the reason every allowlist here exists:** the next
#: dangerous type is the one nobody thought of. `image/svg+xml` is the worked
#: example — an image by every reasonable reading, and a script.
ALLOWED_ATTACHMENT_TYPES = frozenset(
    {"image/png", "image/jpeg", "image/gif", "image/webp", "application/pdf"}
)

#: Ten megabytes. The whole of what stands between an upload box and a full
#: disk on a one-host deployment where the database and the application share
#: it — and, since D9 made the bytes rows, the pressure valve on the decision
#: to keep them there.
MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024


def attachment_from_upload(uploaded):
    """An `AttachmentSpec` from an uploaded file, or None if it is not allowed.

    **None rather than an exception**, because the caller's right answer is to
    keep the note and drop the file: *capture is durable before it is clever*,
    and losing a thought because its photo was too large is the worst possible
    reading of a size limit.
    """
    if uploaded is None:
        return None
    if uploaded.size > MAX_ATTACHMENT_BYTES:
        return None
    if uploaded.content_type not in ALLOWED_ATTACHMENT_TYPES:
        return None

    content = uploaded.read()
    return AttachmentSpec(
        kind="image" if uploaded.content_type.startswith("image/") else "document",
        mime_type=uploaded.content_type,
        byte_size=len(content),
        # Over what was stored, not over what arrived, so a restore can be
        # checked against the bytes rather than against a byte count -- which
        # two different files share easily.
        checksum=hashlib.sha256(content).hexdigest(),
        content=content,
    )


#: What a whole sitting may materialise. Five is the plan's working number.
#:
#: **A budget on findings, never on fragments.** Every fragment is kept and
#: stays searchable; what is capped is how much of it comes back asking for
#: something. *Nothing valuable is discarded, because the person wrote
#: memories, not proposals.*
SESSION_TOTAL_BUDGET = 5

#: And no single producer may fill it. One loud proposer taking all five slots
#: is the same inbox with fewer rows.
SESSION_PRODUCER_BUDGET = 2

#: How many are shown at once, which is a different question from how many were
#: kept -- and collapsing the two is how a cap quietly becomes a queue. **No
#: slow-release backlog**: the rest are simply there, not scheduled.
SESSION_ATTENTION_BUDGET = 3


@transaction.atomic
def begin_capture_session(owner, *, now: datetime) -> CaptureSession:
    """Open a sitting — Track D increment 13.

    Before any surface can dump into one, which is the ordering the plan calls
    *the whole safety of the feature*.
    """
    return CaptureSession.objects.create(owner=owner, started_at=now)


@transaction.atomic
def end_capture_session(session, *, now: datetime, owner=None) -> list:
    """Run the producers over a whole sitting, once, under a budget.

    Returns what is worth showing immediately — at most
    `SESSION_ATTENTION_BUDGET` of the at most `SESSION_TOTAL_BUDGET`
    materialised.

    **Aggregated across the session, not per fragment**, which is rule 4 and
    the failure a dump invites most: *forty fragments about one project must
    not become forty findings about it.*

    **Idempotent by `processed_at`**, which is rule 7: a cap the nightly pass
    can step around is not a cap.
    """
    if owner is not None and session.owner_id != owner.pk:
        raise NotYours("that session belongs to someone else")
    if session.processed_at is not None:
        return []

    materialised = []
    per_producer = {}
    for node in session.fragments.order_by("captured_at", "pk"):
        if len(materialised) >= SESSION_TOTAL_BUDGET:
            break
        # The per-producer budget is checked **before** the call, so a
        # producer cannot exceed it -- and `_propose_any_commitment` already
        # returns None when it finds nothing, so a separate read-only pass
        # would only be a second way to ask the same question.
        producer = CAPTURE_COMMITMENT
        if per_producer.get(producer, 0) >= SESSION_PRODUCER_BUDGET:
            continue
        facet = _propose_any_commitment(
            node, now=now, actor=session.owner.get_username()
        )
        if facet is None:
            continue
        per_producer[producer] = per_producer.get(producer, 0) + 1
        materialised.append(facet)

    session.processed_at = now
    session.save(update_fields=["processed_at"])
    return materialised[:SESSION_ATTENTION_BUDGET]


# DARK: no production caller. The most misleading of the three -- **this one
# reads as a live safety mechanism.** Its docstring says what *"the nightly
# run"* must not touch; the nightly run is `run_mind_maintenance`, which calls
# `extract_concepts` and `run_detectors` and never this. So rule 7 is enforced
# by nothing having been built to break it, rather than by this.
# Decide before wiring: switching it on makes the nightly pass propose
# commitments over every unsessioned node, which is a behaviour change and not
# a repair -- and `_propose_any_commitment` is the synchronous producer the
# session budgets were written to bound in the first place.
def run_producers_over_unprocessed(owner, *, now: datetime) -> list:
    """The maintenance pass, and what it must not touch.

    **A processed session's fragments are skipped**, which is rule 7 in the one
    place it matters: the nightly run reaching those forty nodes one at a time
    would walk straight around the budget the sitting was given.

    A fragment outside any session is reached as before. The flag narrows what
    maintenance skips, never what it does.
    """
    proposed = []
    for node in Node.objects.filter(
        owner=owner, deleted_at__isnull=True, archived_at__isnull=True
    ).exclude(session__processed_at__isnull=False):
        facet = _propose_any_commitment(node, now=now, actor=owner.get_username())
        if facet is not None:
            proposed.append(facet)
    return proposed


@transaction.atomic
def say_what_this_is(node: Node, *, roles, now: datetime, actor: str) -> list:
    """Say what kinds of memory this note holds — Track B increment 6.

    **Multi-valued, which is the whole point of D6's answer.** One facet per
    role, so a note can be a recipe *and* an occasion; a single `ROLE` kind
    would have been limited to one by `facet_one_live_per_kind`.

    **Corrigible**: roles not named are retired rather than deleted, so a
    dismissed role can be proposed again later on new evidence — the same rule
    the constraint's own comment gives.

    **Re-saying the same roles changes nothing**, including `confirmed_at`. A
    corrigible property re-saved is not a second act, and moving the timestamp
    would make every later reading about *when* somebody decided this wrong.
    """
    _require_live(node)
    wanted = list(dict.fromkeys(roles))
    for role in wanted:
        if role not in MEMORY_ROLES:
            raise MindError(f"{role!r} is not a kind of memory")

    live = {
        facet.kind: facet
        for facet in Facet.objects.filter(
            node=node, retired_at__isnull=True, kind__in=MEMORY_ROLES
        )
    }

    for role in wanted:
        if role in live:
            continue
        Facet.objects.create(
            node=node,
            kind=role,
            data={},
            # A person's statement, not a producer's guess -- which is what
            # `origin` is for, and what the soft-apply rule turns on.
            origin=InferenceOrigin.EXPLICIT,
            confirmed_at=now,
            reason="said so",
        )

    for role, facet in live.items():
        if role not in wanted:
            facet.retired_at = now
            facet.save(update_fields=["retired_at"])

    return wanted


@transaction.atomic
def say_what_kind(concept: ConceptCandidate, *, kind: str) -> ConceptCandidate:
    """Say what kind of thing a concept is — Track E increment 20.

    `ConceptType` has seven values and until this existed nothing wrote
    anything but `UNKNOWN`: production held eleven concepts, every one of them
    untyped, because no surface could say otherwise. The field was in the
    August 21 inventory's *declared-but-never-written vocabulary*.

    **No event, and that is decided rather than forgotten.** A type is
    corrigible by design — the substrate brief refuses *asking what a thing is
    at capture*, because the answer arrives later and changes. Increment 1 drew
    the same line for the log: *a log recording every keystroke of a task's
    text is a log nobody can read*, and every correction of a corrigible
    property is that, written where it cannot be corrected.
    `ConceptCandidate.confirmed_at` already holds the decision that matters,
    which is that this is a thing at all.

    Raises rather than coercing an unknown value: a typo silently becoming
    `UNKNOWN` would be indistinguishable from the state this exists to end.
    """
    if kind not in ConceptType.values:
        raise MindError(f"{kind!r} is not a kind of thing")
    concept.concept_type = kind
    concept.save(update_fields=["concept_type"])
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
# DARK: no production caller. The de-duplication half of `confirm_concept`, which has three
# callers. Trigger: the concept page, which already exists at
# `/mind/concepts/<public_id>/` -- this is the smallest of the twelve to
# switch on, and the alias depth-one trigger already guards it.
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
    producer: str = "",
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
        defaults={
            "data": data,
            "origin": origin,
            "reason": reason,
            "producer": producer,
        },
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
    # Liveness is a node's question. A `DailyEntry` has no deleted or archived
    # state, deliberately -- "I wrote nothing on the 3rd" and "I have never
    # opened the 3rd" are different facts and neither is a deletion.
    if facet.node_id:
        _require_live(facet.node)
    owner = facet.owner
    if area is not None and area.owner_id != owner.pk:
        raise MindError("a commitment cannot be filed in somebody else's area")

    # Two taps, or a tap against a stale page. Neither should double a
    # commitment, and the first decision's task is the one that counts.
    if facet.task_id is not None:
        return facet

    # **Text, tags and date all differ by source, and each for its own reason.**
    #
    # A node's task says what the note currently says, revisions included. An
    # entry's says what the *cited sentence* said: a task carrying a paragraph
    # of Tuesday is a wall of text somebody has to re-read to find the promise
    # in, and the span exists precisely so it does not have to.
    #
    # Tags come from confirmed concepts, which are a property of the graph. A
    # journal entry is not in the graph, so there are none to carry -- an empty
    # list rather than a lookup that cannot answer.
    if facet.node_id:
        text = queries.current_body(facet.node)
        tags = queries.confirmed_concept_labels(facet.node)
    else:
        text = facet.cited_text.strip()
        tags = ()

    # **No date by default, and that is the decision rather than a fallback.**
    # Slice B stopped requiring a date, because a promise without one is still
    # a promise. So a task made from "I still need to ask Maya about the venue"
    # has no deadline and lands in the agenda's someday bucket. Inventing one
    # would be the parser guessing, which it refuses to do everywhere else, and
    # the person can set a date on a task they can now see.
    task = task_services.create_item(
        area,
        text,
        due_date=facet.data.get("due_date") or None,
        recurrence=facet.data.get("recurrence") or None,
        owner=owner,
        # Step 2 of one-capture-surface-plan.md. The Inbox route carried a
        # capture's tags to its task; this route produced an untagged one, which
        # was the last functional gap between them. `lists.Tag` and the concept
        # layer are two vocabularies for the same act, and this is where they
        # meet -- a confirmed concept becomes a tag on the task it produced.
        tags=tags,
    )

    facet.task = task
    facet.confirmed_at = now
    facet.save(update_fields=["task", "confirmed_at"])
    _record(
        owner,
        EventType.FACET_CONFIRMED,
        # Null for an entry-backed facet: the log's column is a node reference,
        # and the source is named in the payload instead.
        node=facet.node,
        occurred_at=now,
        actor=actor,
        payload={
            "kind": facet.kind,
            "task": task.pk,
            **({"entry": facet.entry_id} if facet.entry_id else {}),
        },
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


# DARK: no production caller. **Not an undo half.** An invariant monitor nobody monitors:
# its own docstring says it exists *"to say so in a number rather than to
# be trusted"*, and no number shows it. Trigger: a row on `/numbers/`,
# which is one line -- or delete it and let the transaction be the whole
# guarantee.
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
        # A decision logged as a decision. An `EXPLICIT` mention is created
        # with `confirmed_at` already stamped two lines above -- somebody typed
        # the tag -- and logging that as a proposal made a deliberate act of
        # naming indistinguishable from what a detector guessed overnight.
        #
        # `code-review-2026-08-21.md` R2, whose visible symptom was one layer
        # up: `clarice.recall.around` classifies proposals as machine activity,
        # so tagging an existing note vanished from its own morning. Fixed here
        # rather than by widening that set, because the set was right.
        (
            EventType.MENTION_CONFIRMED
            if origin == InferenceOrigin.EXPLICIT
            else EventType.MENTION_PROPOSED
        ),
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
# DARK: no production caller. The confirming half of `propose_mention`. Nothing else can
# confirm an *inferred* mention: `record_typed_tags` stamps `confirmed_at`
# directly for typed tags, and an `EXPLICIT` mention arrives confirmed.
# So a detector's guess can be proposed and never accepted.
# Trigger: the review surface, with D15.
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
# DARK: no production caller. The undo half of `link`, which has two callers.
# Trigger: Track E increment 19's connections section. Until then
# `EDGE_REMOVED` is a vocabulary word nothing can write.
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
    #
    # **`EventType.THREAD_ARTICULATED` is never written, and this is the act it
    # names.** Found August 24, 2026 by the enum sweep in
    # `clarice/tests/test_dark_enum_values_declare_their_deferral.py`, which
    # could not register it: `clarice/recall.py` lists the type among the
    # person's own acts and `mind/views.py` carries its label *"a thread
    # named"*, so it is mentioned — read by two places, written by none. The
    # thread node below is created with `NodeSource.THREAD`, which **is**
    # written, so the log records the node and not the articulating.
    #
    # Deliberately not fixed in passing. What the append-only log records is a
    # product decision rather than a tidy-up, and `ActivityEvent` is the one
    # table in this application a mistake cannot be taken back out of.
    # Vince's call.
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
# Dark from the day it was written until August 22, 2026, when **D15** was
# answered: `mind.views.this_time_before` calls it. Left noted rather than
# silently un-marked, because what it was waiting for is the useful part --
# every other piece of the loop existed and was tested, and production held two
# `reviewed` rows, both owner-scoped from `/mind/review/` and none node-scoped,
# so `review_state` returned zero for every node and the spaced schedule had
# never once run. The missing piece was a surface where a person says something,
# and Resurfacing could not be that surface until D17 built it.
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
# DARK: no production caller. **Not an undo half, and the one with a hazard.** Scheduled
# work that was never scheduled: no cron entry calls it. It also defaults
# to `actor="system"` while sharing `HYPOTHESIS_RESOLVED` with the
# person's own decisions, so wiring it to cron makes those two
# indistinguishable by event type -- `code-review-2026-08-21.md` R8.
# Decide before wiring, not after: a cron entry or a deletion.
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
    notes_found: int | None = None,
    tasks_found: int | None = None,
    days_found: int | None = None,
) -> RetrievalMiss:
    """Record that the person knew they had written something and could not
    find it.

    The strongest evidence available about whether semantic retrieval is needed,
    because the correct answer is known. Vocabulary drift — the same idea named
    twice — shows up here first and nowhere else, and full-text search cannot
    surface it by construction.

    The three counts say what each section of the search returned, and default
    to None so a caller that predates them records exactly what it always did.
    See the fields for why None is not the same as zero.
    """
    return RetrievalMiss.objects.create(
        owner=owner,
        query_text=query_text,
        context=context,
        created_at=now,
        notes_found=notes_found,
        tasks_found=tasks_found,
        days_found=days_found,
    )


# DARK: no production caller. The answering half of the live `/mind/search/miss/` route.
# **D3 already decided not to widen it** and nothing has ever populated
# `RetrievalMiss.resolved_node`, so a miss can be recorded and never
# answered. Trigger: a surface for reviewing misses, which no plan claims
# -- so this is the strongest deletion candidate of the twelve.
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
# DARK: no production caller. The undo half of `capture`.
# Trigger: Track E increment 19, the node page. `clarice/recall.py`
# already withholds a deleted node's content from both its reads, so the
# rule this service needs is written and tested ahead of the door.
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
# DARK: no production caller. Hard erasure for one node, where `accounts.services.purge_account`
# is the whole-account path and is live. Trigger: Track E increment 19.
def purge_node(node: Node, *, now: datetime, actor: str) -> list[str]:
    """Delete a node for real, once its retention window has passed.

    **Nothing is handed back for a caller to clean up**, which is D9's payoff.
    This returned storage keys whose blobs the caller had to remove, and the
    boundary was deliberately visible because object storage is not
    transactional with Postgres — a purge claiming to have removed bytes it had
    not would be a lie in the one place the product promises the most. The
    bytes are rows now, so `node.delete()` takes them, inside the transaction,
    and there is no boundary left to be honest about.

    The log keeps its rows, and they keep pointing at the vanished node id — an
    event asserts what happened, and that stays true. The purge event's payload
    retains no content.
    """
    owner = node.owner
    node_pk = node.pk
    removed = node.attachments.count()

    _invalidate_hypotheses_citing(node, now=now, actor=actor, why="node_purged")
    node.delete()

    _record(
        owner,
        EventType.PURGED,
        occurred_at=now,
        actor=actor,
        payload={"node": node_pk, "attachments_removed": removed},
    )
    return removed


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
                "producer": JOURNAL_COMMITMENT,
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
