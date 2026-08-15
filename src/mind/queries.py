"""Read side: answers questions, never mutates.

Paired with services.py from the first slice. The split is not ceremony — it is
what keeps "reads never write" true by construction rather than by discipline,
and it is where every detector's candidate query will live.
"""

from datetime import datetime, timedelta

from django.db.models import Count, F, Max, Min, Q, QuerySet
from django.utils import timezone

from .models import (
    ConceptCandidate,
    ConnectionHypothesis,
    EventType,
    Facet,
    FacetKind,
    Mention,
    Node,
)

# How close a confirmed commitment's due date has to be before its node reaches
# the one tier allowed to interrupt outside a planning or review moment.
#
# Narrow on purpose, and the asymmetry is the reason: a commitment shown a day
# late is a missed reminder, while one that interrupts a week early teaches
# somebody to ignore the channel -- after which the tier is worth nothing at
# all. Overdue is included, since a commitment already past is not less
# time-bound than one arriving tomorrow.
#
# `design-concept.md` calls this "a short, configurable proximity window" and
# names no number. This is that number, in the one place it can be changed.
URGENT_PROXIMITY = timedelta(days=1)


def live_nodes(owner) -> QuerySet[Node]:
    """Everything not deleted and not archived, newest capture first."""
    return (
        Node.objects.filter(owner=owner, deleted_at__isnull=True, archived_at__isnull=True)
        .order_by("-captured_at")
    )


def current_body(node: Node) -> str:
    """A node's body as it now stands.

    The highest-seq revision, falling back to the original capture. Defined
    here once rather than recomputed at each call site, because "what does this
    node currently say" must have exactly one answer.
    """
    latest = node.revisions.order_by("-seq").values_list("body", flat=True).first()
    return latest if latest is not None else node.original_content


def canonical_concept(concept: ConceptCandidate) -> ConceptCandidate:
    """Resolve an alias to the concept it stands for.

    A single hop, never a loop: merge depth is capped at one by trigger, so
    there is no recursive walk to do here and no cycle to guard against.
    """
    return concept.merged_into or concept


def confirmed_concepts(owner) -> QuerySet[ConceptCandidate]:
    """Canonical, confirmed, live concepts.

    This is the corpus the matcher is allowed to search. Unconfirmed candidates
    are deliberately excluded: treating the system's own guesses as ground truth
    is how a classifier starts feeding on its own output with no correction
    path back.
    """
    return ConceptCandidate.objects.filter(
        owner=owner,
        confirmed_at__isnull=False,
        merged_into__isnull=True,
        retired_at__isnull=True,
    )


# How much a name has to recur before the system asks about it.
#
# Extraction over-generates on purpose -- a false candidate costs a row, which is
# what makes a crude rule-based extractor acceptable. That is only true while the
# surplus stays silent: at 30-40 captures a day, surfacing every capitalised run
# would put a hundred questions a month in front of somebody, and a confirmation
# queue that size is the inbox this whole design exists to avoid.
#
# Both conditions are needed and neither implies the other. The count says a name
# is not a one-off; the span says it is not one sitting. Four mentions inside a
# single brain dump is one moment of attention, and gravity is meant to find what
# *recurs*.
#
# Placeholders, deliberately: cold-start.md says these get set by the confirmation
# accept rate rather than guessed at, and they start conservative because a
# question nobody wanted is more expensive than one asked late.
MIN_MENTIONS_TO_ASK = 3
MIN_SPAN_TO_ASK = timedelta(days=1)


def concept_candidates(owner) -> QuerySet[ConceptCandidate]:
    """Extracted names that have earned a question, heaviest first.

    Deliberately not "every unconfirmed candidate". This is the only queue in the
    system, and the rule that keeps it from becoming an inbox is that a candidate
    earns its way here rather than arriving here by default.

    **Span rather than distinct calendar dates.** A date boundary depends on whose
    timezone you ask, and the question here is not "on how many days" but "over
    what stretch of time" -- which is the same question in the cases that matter
    and has no timezone in it at all.

    Mentions on deleted nodes do not count toward either condition. Gravity is
    supposed to measure present attention, and material somebody removed is the
    clearest statement that it is not that.
    """
    live = Q(mentions__node__deleted_at__isnull=True)
    return (
        ConceptCandidate.objects.filter(
            owner=owner,
            # Answered questions stop being asked, which is the only reason this
            # queue is finite. Retired is a person saying "not a thing" -- and
            # re-proposing it on the next extraction run would make that answer
            # worthless. An alias is already spoken for by what it merged into.
            confirmed_at__isnull=True,
            retired_at__isnull=True,
            merged_into__isnull=True,
        )
        .annotate(
            mention_count=Count("mentions", filter=live, distinct=True),
            first_seen=Min("mentions__node__captured_at", filter=live),
            last_seen=Max("mentions__node__captured_at", filter=live),
        )
        .annotate(span=F("last_seen") - F("first_seen"))
        .filter(mention_count__gte=MIN_MENTIONS_TO_ASK, span__gte=MIN_SPAN_TO_ASK)
        .order_by("-mention_count", "label")
    )


def confirmed_mentions_of(concept: ConceptCandidate) -> QuerySet[Mention]:
    return Mention.objects.filter(
        concept=concept, confirmed_at__isnull=False
    ).select_related("node")


def nodes_mentioning(owner, concept: ConceptCandidate) -> QuerySet[Node]:
    """Live nodes that mention a concept, resolving through aliases."""
    canonical = canonical_concept(concept)
    return live_nodes(owner).filter(
        Q(mentions__concept=canonical) | Q(mentions__concept__merged_into=canonical)
    ).distinct()


# ---------------------------------------------------------------------------
# The review surface
# ---------------------------------------------------------------------------

# How long a node waits before its first resurfacing, and how fast that stretches.
# A starting point rather than a tuned schedule — SM-2 generalised beyond
# flashcards, with the parameters exposed so they can be moved on evidence.
BASE_REVIEW_INTERVAL = timedelta(days=7)
KEPT_GROWTH = 2.0
BURIED_GROWTH = 6.0
MAX_REVIEW_INTERVAL = timedelta(days=365 * 2)


def pending_hypotheses(owner) -> QuerySet[ConnectionHypothesis]:
    """Undecided proposals, most confident first.

    **Not a display path.** Reading this does not count as surfacing, so anything
    shown to a person from here would never start its review window and inaction on
    it could never be distinguished from never having seen it. Use
    `services.open_review`, which returns the same proposals and marks them. This
    exists for diagnostics and for counting.

    Oldest first among equal confidence, so nothing starves at the bottom of a
    queue forever.
    """
    return (
        ConnectionHypothesis.objects.filter(owner=owner, resolved_at__isnull=True)
        .order_by("-confidence", "created_at")
        .prefetch_related("members__node")
        .select_related("concept")
    )


def review_state(node: Node) -> dict:
    """A node's resurfacing schedule, folded from its `reviewed` events.

    Derived, never stored. The Attention Policy says a node's tier is computed at
    read time, and spaced repetition is the one part of it that needs history — so
    the history lives in the append-only log and the schedule is a fold over it.
    A mutable `next_review` column would be the obvious alternative and is exactly
    the kind of hidden state that drifts and cannot be explained afterwards.

    The interval stretches faster when a node was *buried* than when it was kept:
    burying is the person saying "less often", and honouring that is the difference
    between a review surface and a nag.
    """
    events = list(
        node.events.filter(event_type=EventType.REVIEWED).order_by("occurred_at")
    )
    if not events:
        return {
            "reviews": 0,
            "last_reviewed_at": None,
            "interval": BASE_REVIEW_INTERVAL,
            "due_at": None,
        }

    interval = BASE_REVIEW_INTERVAL
    for event in events:
        factor = (
            BURIED_GROWTH
            if (event.payload or {}).get("response") == "buried"
            else KEPT_GROWTH
        )
        interval = min(interval * factor, MAX_REVIEW_INTERVAL)

    last = events[-1].occurred_at
    return {
        "reviews": len(events),
        "last_reviewed_at": last,
        "interval": interval,
        "due_at": last + interval,
    }


def is_due_for_review(node: Node, *, now: datetime) -> bool:
    """Whether a node's spaced schedule has come round.

    A node never reviewed is not due: resurfacing is opt-in, and a corpus of
    thousands would otherwise all become due at once the moment the feature exists.
    Candidates for a *first* look come from the detectors, not from this.
    """
    state = review_state(node)
    return state["due_at"] is not None and state["due_at"] <= now


def attention_tier(node: Node, *, now: datetime) -> str:
    """Which tier of the Attention Policy this node currently sits in.

    Computed here, stored nowhere — the policy is explicit that tier is derived at
    read time, because a stored tier is a second source of truth for something that
    changes with every capture.

    All four tiers are reachable as of August 15, 2026. This used to return only
    the lower two and explain that *active commitment* and *urgent / time-bound*
    "both require a confirmed actionable facet, and there is no facet table".
    There is one — facets landed the day before — so the gate had become stale
    rather than the feature being absent, and a commitment somebody had
    explicitly accepted still reported as quiet knowledge.

    Order matters and follows the policy's own wording: quiet knowledge is
    "anything with **no** confirmed actionable facet and no review due", so the
    facet is consulted before review candidacy rather than after.
    """
    if node.deleted_at is not None or node.archived_at is not None:
        # Before anything else: deleted material is never pushed, so a
        # commitment must not resurrect a note somebody removed.
        return "quiet knowledge"

    committed = (
        Facet.objects.filter(
            node=node,
            kind=FacetKind.ACTIONABLE,
            confirmed_at__isnull=False,
            retired_at__isnull=True,
        )
        .select_related("task")
        .first()
    )
    if committed is not None:
        # The *task's* due date, not the facet's `data`. The facet records what
        # was proposed; once confirmed the task is the live record and can be
        # rescheduled in the other core, so reading the proposal would keep
        # calling something urgent after it had been moved.
        due = committed.task.due_date if committed.task_id else None
        if due is not None and due <= timezone.localdate(now) + URGENT_PROXIMITY:
            return "urgent"
        return "active commitment"

    if is_due_for_review(node, now=now):
        return "review candidate"

    cited = ConnectionHypothesis.objects.filter(
        members__node=node, resolved_at__isnull=True
    ).exists()
    return "review candidate" if cited else "quiet knowledge"
