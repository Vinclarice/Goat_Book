"""Read side: answers questions, never mutates.

Paired with services.py from the first slice. The split is not ceremony — it is
what keeps "reads never write" true by construction rather than by discipline,
and it is where every detector's candidate query will live.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from django.contrib.postgres.search import SearchRank
from django.db.models import (
    Case,
    Count,
    Exists,
    IntegerField,
    F,
    FloatField,
    Max,
    Min,
    OuterRef,
    Q,
    QuerySet,
    Subquery,
    Value,
    When,
)
from django.db.models.functions import Coalesce, Greatest
from django.utils import timezone

from .models import (
    ConceptCandidate,
    ConnectionHypothesis,
    Edge,
    EdgeRelation,
    EventType,
    Facet,
    FacetKind,
    HypothesisMember,
    Mention,
    Node,
    Revision,
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


def search_ranked(owner, query) -> QuerySet[Node]:
    """This owner's live notes matching `query`, best first.

    **Ranked, where this used to be a recency truncation.** `live_nodes` orders
    by `-captured_at`, nothing re-ordered it, and the view took the first
    thirty — so the thirty *newest* matches were kept rather than the thirty
    best, and which note you found depended on when you wrote it.

    The rank is the better of the two vectors. A node matches on its original
    capture or on any revision, and `Max` over the revision join is what
    collapses the several rows a multi-revision match produces — which also
    removes the `.distinct()` this used to need.
    """
    return (
        live_nodes(owner)
        .filter(Q(search_original=query) | Q(revisions__search_body=query))
        .annotate(
            rank=Greatest(
                SearchRank(F("search_original"), query),
                Coalesce(
                    Max(SearchRank(F("revisions__search_body"), query)),
                    Value(0.0, output_field=FloatField()),
                ),
            )
        )
        .order_by("-rank", "-captured_at")
    )


def current_text_matches(nodes, query) -> set[int]:
    """Of these nodes, the ids whose text *as it now stands* matches.

    The rest matched only in superseded text, which is not a bug to fix:
    `original_content` is never mutated precisely so what was first said
    survives, and finding it is that design working. What it needs is a label,
    because otherwise a search for a word somebody edited out returns the note
    and renders a body without the word in it.

    Mirrors `current_body`'s rule exactly — the highest-seq revision, falling
    back to the original — because two answers to "what does this node
    currently say" is how the label starts lying.
    """
    ids = [node.pk for node in nodes]
    if not ids:
        return set()

    revised = set(
        Revision.objects.filter(node_id__in=ids).values_list("node_id", flat=True)
    )
    latest_ids = list(
        Revision.objects.filter(node_id__in=ids)
        .order_by("node_id", "-seq")
        .distinct("node_id")
        .values_list("pk", flat=True)
    )
    matches = set(
        Revision.objects.filter(pk__in=latest_ids, search_body=query).values_list(
            "node_id", flat=True
        )
    )
    matches |= set(
        Node.objects.filter(pk__in=ids, search_original=query)
        .exclude(pk__in=revised)
        .values_list("pk", flat=True)
    )
    return matches


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


def confirmed_concept_labels(node: Node) -> list[str]:
    """The names a person has confirmed for this node, canonical and in order.

    **Confirmed only.** An inferred mention is the system's guess, and the
    soft-apply rule says a guess is never treated as fact by anything
    downstream -- a task is about as downstream as it gets.

    Resolved through aliases, so a node tagged with a name later merged into
    another arrives under the surviving one. Typing an old spelling should not
    put it back on a task; that is the split merging exists to undo.
    """
    labels = []
    mentions = (
        Mention.objects.filter(node=node, confirmed_at__isnull=False)
        .select_related("concept", "concept__merged_into")
        .order_by("created_at", "id")
    )
    for mention in mentions:
        concept = canonical_concept(mention.concept)
        if concept.retired_at is not None:
            continue
        if concept.label not in labels:
            labels.append(concept.label)
    return labels


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
        .annotate(unearned=_demotion_case(owner))
        .order_by("unearned", "-confidence", "created_at")
        .prefetch_related("members__node")
        .select_related("concept")
    )


# `retirement_gate`'s number, not a second one. Two readings of one threshold is
# how a rule comes to mean two things.
EARNED_ACCEPT_RATE = 0.5


def _demotion_case(owner):
    """0 for a detector that has earned its slots, 1 for one that has not.

    **This is D3, and it replaces a comparison that never meant anything.**
    Ordering was `-confidence` alone, and confidence is not comparable across
    detectors: `shared_referent` emits a flat 0.9, `open_question` a flat 0.55,
    `dormant_thread` a computed `shared_count / 8`. One states an evidence
    *class*, another normalises a term count — so the five slots were rationed
    by whichever constants somebody chose, while accept rate, the measurement of
    what is actually useful, fed into nothing.

    **Two tiers, not a score.** Blending an accept rate into the sort key would
    invent a second incomparable number to fix the first. A detector has either
    earned an equal claim on the slots or it has not, and inside a tier
    confidence still orders — there it means what its author meant, and it is
    the best signal available.

    **A detector with no decisions is not demoted.** No evidence is not bad
    evidence, and starting a newcomer in the penalty tier would keep it from
    being seen enough to be judged — the same reason `accept_rate` returns None
    rather than zero.

    **Demotion is not starvation.** A demoted detector still fills slots nothing
    else claims, because the alternative is self-confirming: no slots means no
    decisions means the rate never recovers, and one unlucky early dismissal
    would bury a producer permanently. *Quieter, never silent* is the rule, and
    this is the mechanism that keeps the second half true.

    Rates are per person. "Distinctive to them" is the premise every producer
    here rests on, so one person's dismissals cannot ration another's slots.
    """
    from .instrumentation import detector_performance

    unearned = [
        row.detector
        for row in detector_performance(owner)
        if row.accept_rate is not None and row.accept_rate < EARNED_ACCEPT_RATE
    ]
    if not unearned:
        return Value(0)
    return Case(
        When(detector__in=unearned, then=Value(1)),
        default=Value(0),
        output_field=IntegerField(),
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


def current_body_expression():
    """`current_body`, as SQL rather than as a Python call.

    The second definition of one rule, which `principles.md` forbids without a
    reason -- so here is the reason and the guard. `current_body` resolves one
    node with one query; a read that has to test every live note against a Python
    predicate would run that query per node, and the whole point of this read is
    that it scans the corpus. Expressed as a subquery it is one query instead.

    The two must agree, and `test_unresolved_questions.py` asserts they do for
    both a revised and an unrevised node. If this ever diverges from
    `current_body`, that test is the thing that says so.
    """
    return Coalesce(
        Subquery(
            Revision.objects.filter(node=OuterRef("pk"))
            .order_by("-seq")
            .values("body")[:1]
        ),
        F("original_content"),
    )


def unresolved_questions(owner) -> list[Node]:
    """Question-shaped notes nothing has answered yet, oldest first.

    **A view, not a proposal.** No hypothesis, no fingerprint, no review window
    and no confirm gate: "you asked this and nothing has answered it" is a fact
    about the graph, not a claim about it, so it carries none of the machinery
    that exists to make a guess accountable. It cannot be wrong the way a
    proposal can be wrong -- only stale, which the next read fixes.

    Three exclusions, each a different meaning of *resolved*:

    * **An `answers` edge into it.** The typed relation is the answer, and the
      direction is the whole content of it -- `confirm_hypothesis` links
      answer -> question, so a question is settled when it is the *target*.
    * **A pending `answers` proposal citing it.** Already on the review surface
      with a candidate answer and a confirm gate; listing it here as well is one
      loose end counted twice in one ritual. Pending only -- a *dismissed*
      proposal said that candidate was wrong, not that the question is closed,
      and the detector's fingerprint dedupe means it will never be re-proposed.
    * **Deleted or archived**, via `live_nodes`.

    Oldest first, inverting `live_nodes`' newest-first default on purpose: a
    loose end gets worse with age, where a capture gets less interesting.

    **Returns a list, because the predicate is Python.** `looks_like_a_question`
    is three text signals and no database can express it, so the shape test
    happens here. That is affordable at this corpus size and is the reason
    `planning-assistant-plan.md` increment 1 keeps question-shape evaluated on
    read; the swap to a stored epistemic facet is this function's body and
    nothing above it.
    """
    # Imported here rather than at module scope: `detectors` imports `queries`,
    # so the reverse at import time is a cycle.
    from .detectors.open_question import looks_like_a_question

    answered = Edge.objects.filter(
        to_node=OuterRef("pk"), relation=EdgeRelation.ANSWERS
    )
    # What a person said about it, which outranks what the predicate reads.
    # Either statement closes the loose end and they are different facts:
    # "resolved" means settled with nothing to point at, "not_a_question" means
    # the heuristic was wrong. Live facets only — reopening retires one rather
    # than deleting it, so a retired status must stop excluding.
    decided = Facet.objects.filter(
        node=OuterRef("pk"),
        kind=FacetKind.EPISTEMIC,
        retired_at__isnull=True,
        data__status__in=["resolved", "not_a_question"],
    )
    proposed_against = HypothesisMember.objects.filter(
        node=OuterRef("pk"),
        hypothesis__relation=EdgeRelation.ANSWERS,
        hypothesis__resolved_at__isnull=True,
    )

    candidates = (
        live_nodes(owner)
        .annotate(body=current_body_expression())
        .filter(~Exists(answered), ~Exists(proposed_against), ~Exists(decided))
        .order_by("captured_at", "id")
    )
    return [node for node in candidates if looks_like_a_question(node.body)]


@dataclass(frozen=True)
class RelevantMaterial:
    """One note a stated purpose reaches, and the evidence for it."""

    node: Node
    distinctive_terms: tuple[str, ...]
    shared_count: int

    @property
    def reason(self) -> str:
        """A fact the person can check, not a score they must trust.

        The same sentence shape `dormant_thread` uses, and for the same reason:
        naming the overlap states the dimension of the connection plainly, so
        the reader can disagree with it.
        """
        shown = ", ".join(self.distinctive_terms)
        return (
            f"{len(self.distinctive_terms)} of {self.shared_count} shared terms "
            f"appear in almost none of your other notes: {shown}"
        )


# Three, matching `dormant_thread.DEFAULT_MIN_DISTINCTIVE_TERMS` rather than
# choosing a second number. That is the gate measured at 67% precision against a
# corpus with known answers, where every score threshold failed; a brief that
# relaxed it would become the vaguely-on-topic panel `detectors/__init__`
# describes as reliably ignored.
BRIEF_MIN_DISTINCTIVE_TERMS = 3
BRIEF_LIMIT = 8


def material_bearing_on(
    owner,
    statement: str,
    *,
    limit: int = BRIEF_LIMIT,
    min_distinctive_terms: int = BRIEF_MIN_DISTINCTIVE_TERMS,
    index=None,
) -> list[RelevantMaterial]:
    """Notes bearing on a statement the person wrote, strongest first.

    The retrieval behind a project brief (`planning-assistant-plan.md`
    increment 4), kept text-anchored rather than project-anchored so that this
    module does not have to know what a Project is — the caller supplies the
    purpose and gets material back.

    **This is deliberately not "show related notes."** That is a named failure
    (`detectors/__init__`), and three things separate this from it: one end is a
    statement of intent the person wrote, which is `precision.md`'s Tier 2; the
    brief is opened rather than pushed; and the gate is the rare-term one that
    took the lexical detector from 11% to 67%, not a similarity threshold.

    **An empty statement returns nothing**, rather than the corpus sorted by
    coincidence. Unanchored retrieval is Tier 3, where every measured failure
    lives, and a project nobody has described has not asked a question yet.

    Writes nothing — including no surfacing record. The neighbouring mechanic
    does the opposite deliberately (`services.open_review` stamps
    `first_surfaced_at`, because a proposal shown without starting its window
    makes silence meaningless), and the difference is that a brief proposes
    nothing: there is no window to start and no inaction to interpret.
    """
    from .similarity import default_index

    statement = (statement or "").strip()
    if not statement:
        return []

    index = index or default_index()
    matches = index.similar_to(
        statement,
        owner=owner,
        limit=limit,
        min_distinctive_terms=min_distinctive_terms,
    )
    if not matches:
        return []

    live = {
        node.pk: node
        for node in live_nodes(owner).filter(pk__in=[m.node_id for m in matches])
    }
    results = []
    for match in matches:
        node = live.get(match.node_id)
        if node is None:
            continue
        results.append(
            RelevantMaterial(
                node=node,
                distinctive_terms=tuple(match.distinctive_terms),
                shared_count=match.shared_count,
            )
        )
    return results[:limit]
