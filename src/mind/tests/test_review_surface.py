"""The review surface and its instrumentation.

Two things are being pinned here, and the first is the more important.

**Showing and surfacing are one operation.** If a proposal can be displayed without
being marked shown, then `first_surfaced_at` stays null while the person looks
straight at it — and after that, inaction is indistinguishable from never having
seen it. Every rule built on the review window silently means nothing. The tests
below assert that the display path marks, and that the diagnostic path is not a
display path.

**The instrumentation must distinguish "no evidence" from "bad".** A detector nobody
has ruled on and a detector that is always wrong call for opposite responses, so an
accept rate of `None` is not an accept rate of zero.
"""

from datetime import datetime, timedelta, timezone as dt_timezone

import pytest

from mind import instrumentation, queries, services
from mind.models import (
    ActivityEvent,
    ConnectionHypothesis,
    EventType,
    HypothesisResolution,
    Node,
)
from mind.services import ReviewResponse

pytestmark = pytest.mark.django_db

UTC = dt_timezone.utc
JAN = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)
FEB = datetime(2026, 2, 1, 9, 0, tzinfo=UTC)
NOW = datetime(2026, 8, 12, 12, 0, tzinfo=UTC)


def _capture(owner, content="a thought worth keeping around", when=JAN):
    return services.capture(
        owner, content=content, captured_at=when, source=Node.Source.WEB, actor="vince"
    )


def _hypothesis(owner, *, detector="dormant_thread", confidence=0.7, fingerprint=None):
    a, b = _capture(owner, "first thought"), _capture(owner, "second thought")
    return services.propose_hypothesis(
        owner,
        detector=detector,
        citations=[services.Citation(node=a), services.Citation(node=b)],
        confidence=confidence,
        label="shares: something",
        index_version="test",
        now=JAN,
    )


# ---------------------------------------------------------------------------
# Showing is surfacing
# ---------------------------------------------------------------------------


def test_opening_the_review_marks_what_it_returns(owner):
    """The whole point: there is no way to display without starting the clock."""
    hypothesis = _hypothesis(owner)
    assert hypothesis.first_surfaced_at is None

    [shown] = services.open_review(owner, now=FEB, actor="vince")

    shown.refresh_from_db()
    assert shown.pk == hypothesis.pk
    assert shown.first_surfaced_at == FEB
    assert shown.surface_count == 1
    assert shown.review_window_expires_at == FEB + services.DEFAULT_REVIEW_WINDOW


def test_the_diagnostic_query_does_not_count_as_surfacing(owner):
    """`pending_hypotheses` exists for counting, and must stay inert."""
    hypothesis = _hypothesis(owner)
    list(queries.pending_hypotheses(owner))

    hypothesis.refresh_from_db()
    assert hypothesis.first_surfaced_at is None
    assert hypothesis.surface_count == 0


def test_reopening_counts_the_view_without_extending_the_window(owner):
    _hypothesis(owner)
    services.open_review(owner, now=FEB, actor="vince")
    services.open_review(owner, now=FEB + timedelta(days=3), actor="vince")

    hypothesis = ConnectionHypothesis.objects.get()
    assert hypothesis.surface_count == 2
    assert hypothesis.first_surfaced_at == FEB
    assert hypothesis.review_window_expires_at == FEB + services.DEFAULT_REVIEW_WINDOW


def test_resolved_proposals_are_not_shown_again(owner):
    hypothesis = _hypothesis(owner)
    services.dismiss_hypothesis(hypothesis, now=JAN, actor="vince")

    assert services.open_review(owner, now=FEB, actor="vince") == []


def test_the_surface_is_a_handful_not_a_queue(owner):
    """A review that feels like an inbox has already failed."""
    for i in range(9):
        _hypothesis(owner, confidence=0.5 + i / 100)

    shown = services.open_review(owner, now=FEB, actor="vince", limit=3)
    assert len(shown) == 3
    assert ConnectionHypothesis.objects.filter(first_surfaced_at__isnull=True).count() == 6


def test_the_most_confident_proposals_come_first(owner):
    low = _hypothesis(owner, confidence=0.3)
    high = _hypothesis(owner, confidence=0.95)

    shown = services.open_review(owner, now=FEB, actor="vince", limit=2)
    assert [h.pk for h in shown] == [high.pk, low.pk]


def test_the_review_is_owner_scoped(owner, other_owner):
    mine = _hypothesis(owner)
    _hypothesis(other_owner)

    assert [h.pk for h in services.open_review(owner, now=FEB, actor="vince")] == [mine.pk]


def test_opening_the_review_is_recorded(owner):
    _hypothesis(owner)
    services.open_review(owner, now=FEB, actor="vince")

    event = ActivityEvent.objects.get(
        event_type=EventType.REVIEWED, payload__kind="connection_review"
    )
    assert event.payload["surfaced"] == 1
    assert event.occurred_at == FEB


# ---------------------------------------------------------------------------
# Spaced review, folded from the log
# ---------------------------------------------------------------------------


def test_a_never_reviewed_node_is_not_due(owner):
    """Resurfacing is opt-in. Otherwise a whole corpus falls due the moment the
    feature exists."""
    node = _capture(owner)
    state = queries.review_state(node)

    assert state["reviews"] == 0
    assert state["due_at"] is None
    assert queries.is_due_for_review(node, now=NOW) is False


def test_the_schedule_is_derived_from_events(owner):
    node = _capture(owner)
    services.mark_reviewed(node, now=JAN, actor="vince")

    state = queries.review_state(node)
    assert state["reviews"] == 1
    assert state["last_reviewed_at"] == JAN
    assert state["due_at"] == JAN + queries.BASE_REVIEW_INTERVAL * queries.KEPT_GROWTH


def test_each_review_stretches_the_interval(owner):
    node = _capture(owner)
    services.mark_reviewed(node, now=JAN, actor="vince")
    first = queries.review_state(node)["interval"]
    services.mark_reviewed(node, now=FEB, actor="vince")
    second = queries.review_state(node)["interval"]

    assert second > first


def test_burying_a_node_stretches_it_much_harder(owner):
    """Burying is the person saying "less often". Honouring that is the difference
    between a review surface and a nag."""
    kept, buried = _capture(owner, "one"), _capture(owner, "two")
    services.mark_reviewed(kept, response=ReviewResponse.KEPT, now=JAN, actor="vince")
    services.mark_reviewed(buried, response=ReviewResponse.BURIED, now=JAN, actor="vince")

    assert (
        queries.review_state(buried)["interval"]
        > queries.review_state(kept)["interval"]
    )


def test_the_interval_is_capped(owner):
    node = _capture(owner)
    for month in range(1, 13):
        services.mark_reviewed(
            node,
            response=ReviewResponse.BURIED,
            now=datetime(2026, month, 1, tzinfo=UTC),
            actor="vince",
        )
    assert queries.review_state(node)["interval"] == queries.MAX_REVIEW_INTERVAL


def test_a_node_becomes_due_once_its_interval_elapses(owner):
    node = _capture(owner)
    services.mark_reviewed(node, now=JAN, actor="vince")

    assert queries.is_due_for_review(node, now=JAN + timedelta(days=1)) is False
    assert queries.is_due_for_review(node, now=JAN + timedelta(days=400)) is True


def test_deleted_material_cannot_be_marked_reviewed(owner):
    node = _capture(owner)
    services.delete_node(node, now=JAN, actor="vince")
    with pytest.raises(services.Deleted):
        services.mark_reviewed(node, now=FEB, actor="vince")


# ---------------------------------------------------------------------------
# Attention tiers
# ---------------------------------------------------------------------------


def test_an_ordinary_note_is_quiet_knowledge(owner):
    """The default for most captures: stored, searchable, never pushed."""
    assert queries.attention_tier(_capture(owner), now=NOW) == "quiet knowledge"


def test_a_note_cited_by_an_open_proposal_is_a_review_candidate(owner):
    hypothesis = _hypothesis(owner)
    node = hypothesis.members.first().node
    assert queries.attention_tier(node, now=NOW) == "review candidate"


def test_resolving_the_proposal_returns_the_note_to_quiet(owner):
    hypothesis = _hypothesis(owner)
    node = hypothesis.members.first().node
    services.dismiss_hypothesis(hypothesis, now=JAN, actor="vince")

    assert queries.attention_tier(node, now=NOW) == "quiet knowledge"


def test_a_node_due_for_review_is_a_review_candidate(owner):
    node = _capture(owner)
    services.mark_reviewed(node, now=JAN, actor="vince")
    assert queries.attention_tier(node, now=NOW) == "review candidate"


def test_deleted_material_is_never_surfaced_by_a_tier(owner):
    node = _capture(owner)
    services.mark_reviewed(node, now=JAN, actor="vince")
    services.delete_node(node, now=FEB, actor="vince")
    node.refresh_from_db()

    assert queries.attention_tier(node, now=NOW) == "quiet knowledge"


# ---------------------------------------------------------------------------
# Instrumentation
# ---------------------------------------------------------------------------


def test_no_decisions_yet_is_not_an_accept_rate_of_zero(owner):
    """Zero would read as "wrong every time" when it means "no evidence", and the
    two call for opposite responses."""
    _hypothesis(owner)
    [performance] = instrumentation.detector_performance(owner)

    assert performance.proposed == 1
    assert performance.decided == 0
    assert performance.accept_rate is None


def test_accept_rate_counts_only_what_a_person_ruled_on(owner):
    """Expired proposals were never judged. Counting them as rejections would
    punish a detector nobody had time to look at."""
    confirmed = _hypothesis(owner, confidence=0.9)
    dismissed = _hypothesis(owner, confidence=0.8)
    expired = _hypothesis(owner, confidence=0.7)

    services.confirm_hypothesis(confirmed, now=FEB, actor="vince")
    services.dismiss_hypothesis(dismissed, now=FEB, actor="vince")
    services.surface_hypothesis(
        expired, now=JAN, actor="vince", review_window=timedelta(days=1)
    )
    services.expire_stale_hypotheses(owner, now=NOW, unsurfaced_after=timedelta(days=30))

    [performance] = instrumentation.detector_performance(owner)
    assert (performance.confirmed, performance.dismissed, performance.expired) == (1, 1, 1)
    assert performance.decided == 2
    assert performance.accept_rate == pytest.approx(0.5)


def test_performance_is_reported_per_detector_never_blended(owner):
    """A good detector and a noisy one average into a number that means nothing."""
    good = _hypothesis(owner, detector="shared_referent", confidence=0.9)
    bad = _hypothesis(owner, detector="dormant_thread", confidence=0.4)
    services.confirm_hypothesis(good, now=FEB, actor="vince")
    services.dismiss_hypothesis(bad, now=FEB, actor="vince")

    performances = {p.detector: p for p in instrumentation.detector_performance(owner)}
    assert performances["shared_referent"].accept_rate == 1.0
    assert performances["dormant_thread"].accept_rate == 0.0


def test_a_measured_detector_outranks_an_unmeasured_one(owner):
    measured = _hypothesis(owner, detector="shared_referent")
    _hypothesis(owner, detector="dormant_thread")
    services.dismiss_hypothesis(measured, now=FEB, actor="vince")

    ordered = [p.detector for p in instrumentation.detector_performance(owner)]
    assert ordered == ["shared_referent", "dormant_thread"]


def test_the_unseen_rate_separates_a_neglected_surface_from_a_bad_detector(owner):
    """A high value is a fact about habits, not about the mechanic."""
    ignored = _hypothesis(owner)
    services.surface_hypothesis(
        ignored, now=JAN, actor="vince", review_window=timedelta(days=1)
    )
    services.expire_stale_hypotheses(owner, now=NOW, unsurfaced_after=timedelta(days=30))

    [performance] = instrumentation.detector_performance(owner)
    assert performance.unseen_rate == 1.0
    assert performance.accept_rate is None


def test_the_miss_trend_is_bucketed_oldest_first(owner):
    services.record_retrieval_miss(
        owner, query_text="that thing about delay", now=NOW - timedelta(days=100)
    )
    services.record_retrieval_miss(owner, query_text="the scanner note", now=NOW - timedelta(days=5))

    trend = instrumentation.retrieval_miss_trend(owner, now=NOW, periods=6)
    assert len(trend) == 6
    assert [count for _, count in trend][-1] == 1
    assert sum(count for _, count in trend) == 2


def test_the_gate_reports_three_conditions_with_values(owner):
    """Stated as prose in the design document, which is how a gate becomes
    indefinite. Computing them does not make the decision; it makes it checkable."""
    conditions = instrumentation.retirement_gate(owner, now=NOW)

    assert [c.name for c in conditions] == [
        "the moment recurs",
        "accept rates hold",
        "retrieval misses fall",
    ]
    assert all(c.met is False for c in conditions), "an empty corpus meets nothing"
    assert all(c.value for c in conditions)


def test_a_quiet_start_does_not_read_as_improving_retrieval(owner):
    """Needs a non-zero baseline, or zero misses then zero misses looks like
    progress."""
    conditions = {c.name: c for c in instrumentation.retirement_gate(owner, now=NOW)}
    assert conditions["retrieval misses fall"].met is False


def test_the_summary_reports_corpus_size_alongside_everything_else(owner):
    """Every other figure is conditional on it: proposing nothing over forty notes
    and over four thousand are different findings."""
    _capture(owner)
    summary = instrumentation.lab_summary(owner, now=NOW)

    assert summary["nodes"] == 1
    assert summary["confirmed_connections"] == 0
    assert "gate" in summary and len(summary["gate"]) == 3
