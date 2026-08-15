"""Measurement: is the connection mechanic working?

Read-only, and separated from `queries.py` because it answers a different kind of
question. `queries` serves the product; this serves the decision about whether the
product's premise holds.

The corpus problem is inherent to a second mind — material has to accumulate before
connections exist — so early output is sparse by nature. That is exactly why these
numbers matter more, not less: without them a slow start is indistinguishable from a
broken mechanic, and the honest response to an ambiguous disappointment is usually
to abandon the idea. With them, *"there isn't enough material yet"* and *"this
detector doesn't work"* stay separable claims.

**Per detector, never blended.** The useful question is *which* detectors earn their
place, and a single combined accept rate cannot answer it — a good detector and a
noisy one average into something meaningless.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from django.db.models import Count, Q

from django.db.models import Max, Min

from .models import (
    ActivityEvent,
    ConceptCandidate,
    ConnectionHypothesis,
    Edge,
    EventType,
    HypothesisResolution,
    InferenceOrigin,
    Mention,
    Node,
    RetrievalMiss,
)


@dataclass(frozen=True)
class DetectorPerformance:
    """One detector's record. Every field is a count of a decision, not a guess."""

    detector: str
    proposed: int
    confirmed: int
    dismissed: int
    expired: int
    pending: int

    @property
    def decided(self) -> int:
        """Proposals a person actually ruled on.

        Expired ones are excluded from the denominator: they were never judged, and
        counting them as rejections would flatter a detector nobody had time to
        look at, or punish one whose proposals arrived during a quiet month.
        """
        return self.confirmed + self.dismissed

    @property
    def accept_rate(self) -> float | None:
        """None rather than zero when nothing has been decided.

        Zero would read as "this detector is wrong every time" when it means "no
        evidence yet", and the two call for opposite responses.
        """
        return self.confirmed / self.decided if self.decided else None

    @property
    def unseen_rate(self) -> float | None:
        """Share of proposals that expired without ever being looked at.

        A high value says the review surface is not being opened often enough, which
        is a fact about the person's habits rather than about the detector — worth
        separating so a neglected surface is not mistaken for a bad mechanic.
        """
        return self.expired / self.proposed if self.proposed else None


def detector_performance(owner) -> list[DetectorPerformance]:
    """Every detector that has ever proposed anything, best accept rate first."""
    rows = (
        ConnectionHypothesis.objects.filter(owner=owner)
        .values("detector")
        .annotate(
            proposed=Count("id"),
            confirmed=Count("id", filter=Q(resolution=HypothesisResolution.CONFIRMED)),
            dismissed=Count("id", filter=Q(resolution=HypothesisResolution.DISMISSED)),
            expired=Count("id", filter=Q(resolution=HypothesisResolution.EXPIRED)),
            pending=Count("id", filter=Q(resolved_at__isnull=True)),
        )
        .order_by("detector")
    )

    performances = [
        DetectorPerformance(
            detector=row["detector"],
            proposed=row["proposed"],
            confirmed=row["confirmed"],
            dismissed=row["dismissed"],
            expired=row["expired"],
            pending=row["pending"],
        )
        for row in rows
    ]
    # Undecided detectors sort last rather than first: an accept rate of None means
    # "no evidence", which should not outrank a measured one in either direction.
    performances.sort(key=lambda p: (p.accept_rate is None, -(p.accept_rate or 0)))
    return performances


def retrieval_miss_trend(
    owner, *, now: datetime, window: timedelta = timedelta(days=30), periods: int = 6
) -> list[tuple[datetime, int]]:
    """Recorded misses per period, oldest first.

    A miss is a moment the person knew they had written something and could not find
    it — the strongest evidence available about retrieval, because the correct answer
    is known. Whether this falls over time is one of the three retirement-gate
    conditions, and it is the only one measurable without interpretation.
    """
    buckets: list[tuple[datetime, int]] = []
    for index in range(periods, 0, -1):
        start = now - window * index
        end = start + window
        count = RetrievalMiss.objects.filter(
            owner=owner, created_at__gte=start, created_at__lt=end
        ).count()
        buckets.append((start, count))
    return buckets


@dataclass(frozen=True)
class GateCondition:
    name: str
    met: bool
    value: str
    detail: str


def retirement_gate(owner, *, now: datetime) -> list[GateCondition]:
    """The three conditions for absorbing Clarice's domains, as computed values.

    Stated in the design document as prose, which is how a gate becomes indefinite.
    Computing them does not make the decision, but it does mean the decision can be
    checked rather than felt.

    The first condition is a **proxy, and a weak one.** What it is meant to capture
    is whether *"I did not put these together"* recurs often enough to be a reason to
    open the app — a subjective experience with no measurement. Confirmations are the
    nearest observable trace, and they undercount (a person can find a connection
    valuable and not confirm it) and overcount (a confirmation can be idle tidying).
    Read it as a floor on plausibility, not as evidence the moment happened.
    """
    recent = now - timedelta(days=90)

    confirmations = ConnectionHypothesis.objects.filter(
        owner=owner,
        resolution=HypothesisResolution.CONFIRMED,
        resolved_at__gte=recent,
    ).count()

    performances = [p for p in detector_performance(owner) if p.decided]
    worst = min((p.accept_rate for p in performances), default=None)

    trend = retrieval_miss_trend(owner, now=now, periods=6)
    first_half = sum(count for _, count in trend[:3])
    second_half = sum(count for _, count in trend[3:])

    return [
        GateCondition(
            name="the moment recurs",
            met=confirmations >= 6,
            value=f"{confirmations} confirmed in 90 days",
            detail="Proxy only — confirmations are the nearest observable trace of "
            "a subjective experience, and they both under- and overcount.",
        ),
        GateCondition(
            name="accept rates hold",
            met=worst is not None and worst >= 0.5,
            value="no decisions yet" if worst is None else f"worst detector {worst:.0%}",
            detail="Per detector, never blended: a good one and a noisy one average "
            "into a number that means nothing.",
        ),
        GateCondition(
            name="retrieval misses fall",
            met=bool(first_half) and second_half < first_half,
            value=f"{first_half} then {second_half} over two 90-day halves",
            detail="The only condition measurable without interpretation. Needs a "
            "non-zero baseline, or a quiet start reads as an improvement.",
        ),
    ]


@dataclass(frozen=True)
class Readiness:
    """Whether a detector can say anything yet, and if not what is missing."""

    detector: str
    ready: bool
    blocked_by: str = ""
    """Stated against this person's own corpus, never in the abstract.

    "Unavailable" is barely better than silence. What somebody needs in order to
    decide whether to keep waiting is the distance: needs two notes 548 days
    apart, your oldest is twelve.
    """


def detector_readiness(owner, *, now: datetime) -> list[Readiness]:
    """What each detector is waiting for, if anything.

    The point is the difference between *no connections found* and *no
    connections possible*. A quiet mechanic and a broken one look identical from
    outside, and the honest response to an ambiguous disappointment is usually to
    abandon the idea -- which is the failure `cold-start.md` exists to prevent.

    **Every detector is reported, including the ready ones and especially the
    blocked ones.** Listing only what works would show a blank page on a new
    corpus, which is the ambiguity this is here to remove.

    Preconditions are read from each detector's own thresholds rather than
    restated, so this cannot drift from what the code actually enforces.
    """
    from .detectors import concept_assignment, dormant_thread, open_question
    from .detectors import semantic_echo

    live = Node.objects.filter(
        owner=owner, deleted_at__isnull=True, archived_at__isnull=True
    )

    # -- concept_assignment: a confirmed concept with enough behind it --------
    supported = [
        concept
        for concept in ConceptCandidate.objects.filter(
            owner=owner, confirmed_at__isnull=False, merged_into__isnull=True,
            retired_at__isnull=True,
        )
        if Mention.objects.filter(concept=concept).count()
        >= concept_assignment.DEFAULT_MIN_MEMBERS
    ]
    assignment = Readiness(
        detector=concept_assignment.DETECTOR,
        ready=bool(supported),
        blocked_by=(
            ""
            if supported
            else (
                f"needs a confirmed concept with at least "
                f"{concept_assignment.DEFAULT_MIN_MEMBERS} notes behind it — "
                f"confirm one on the Things page"
            )
        ),
    )

    # -- open_question: somebody has to have asked something -----------------
    asked = any(
        open_question.looks_like_a_question(node.original_content)
        for node in live.only("original_content")
    )
    questions = Readiness(
        detector=open_question.DETECTOR,
        ready=asked,
        blocked_by="" if asked else "no note reads as a question yet",
    )

    # -- shared_referent: exact evidence, so it waits on a confirmation -------
    has_alias = ConceptCandidate.objects.filter(
        owner=owner, merged_into__isnull=False, retired_at__isnull=True
    ).exists()
    referents = Readiness(
        detector="shared_referent",
        ready=has_alias,
        blocked_by=(
            "" if has_alias else "needs a confirmed alias — two labels merged into one"
        ),
    )

    # -- dormant_thread: the one that is gated on the calendar ---------------
    #
    # Reported as the age of the oldest note rather than the span between the
    # furthest two, and the difference matters on a young corpus: with one note
    # the span is zero, which tells somebody nothing, while "your oldest is 12
    # days" says exactly how far off this is. The age is also the ceiling the
    # span grows toward as capturing continues, so it never overstates.
    span = live.aggregate(first=Min("captured_at"), last=Max("captured_at"))
    required = dormant_thread.DEFAULT_MIN_DORMANCY
    reach = timedelta(0) if span["first"] is None else span["last"] - span["first"]
    oldest_days = 0 if span["first"] is None else (now - span["first"]).days
    dormant = Readiness(
        detector=dormant_thread.DETECTOR,
        ready=reach >= required,
        blocked_by=(
            ""
            if reach >= required
            else (
                f"needs two notes {required.days} days apart; your oldest note "
                f"is {oldest_days} days old"
            )
        ),
    )

    # -- semantic_echo: an optional dependency, already self-reporting -------
    embedded = semantic_echo.available()
    echoes = Readiness(
        detector=semantic_echo.DETECTOR,
        ready=embedded,
        blocked_by="" if embedded else "no sentence vectors — run manage.py embed_nodes",
    )

    return [assignment, questions, referents, dormant, echoes]


def last_maintenance_run(owner) -> datetime | None:
    """When the scheduled pass last completed for this person, or None.

    None means never, and that is a real and reportable state rather than a
    missing value -- extraction and detection were unscheduled for the whole
    first day the knowledge core was live, and nothing on this page could say
    so. `detector_readiness` answers what each detector *could* find; this
    answers whether anything ever looked.
    """
    return (
        ActivityEvent.objects.filter(
            owner=owner, event_type=EventType.MAINTENANCE_RAN
        )
        .order_by("-occurred_at")
        .values_list("occurred_at", flat=True)
        .first()
    )


def lab_summary(owner, *, now: datetime) -> dict:
    """Everything worth knowing about whether the lab is working, in one call.

    Includes the corpus size because every figure below it is conditional on that:
    a detector proposing nothing over forty notes and over four thousand are
    different findings, and the numbers alone do not distinguish them.
    """
    live = Node.objects.filter(
        owner=owner, deleted_at__isnull=True, archived_at__isnull=True
    )
    return {
        "nodes": live.count(),
        "confirmed_connections": Edge.objects.filter(
            owner=owner, origin=InferenceOrigin.INFERRED
        ).count(),
        "explicit_links": Edge.objects.filter(
            owner=owner, origin=InferenceOrigin.EXPLICIT
        ).count(),
        "detectors": detector_performance(owner),
        # Beside the accept rates on purpose. A detector with no proposals and a
        # detector that cannot run yet produce the same empty row above, and only
        # this distinguishes them.
        "readiness": detector_readiness(owner, now=now),
        # Beside readiness for the same reason readiness sits beside the accept
        # rates: a detector that has never been *asked* looks exactly like one
        # that found nothing, and only this separates them.
        "last_maintenance_run": last_maintenance_run(owner),
        "retrieval_misses": RetrievalMiss.objects.filter(owner=owner).count(),
        "gate": retirement_gate(owner, now=now),
    }
