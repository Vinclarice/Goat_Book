"""Every producer measured, not just the detectors — the contract's last field.

`planning-assistant-plan.md` calls the shared contract the first deliverable and
names six fields. Four arrived with increment 2. These are the other two, and
they are a pair: **Producer** is what makes **Measurement** mean anything, since
a blended "are suggestions good" number cannot answer the question that matters,
which is *which* producer is worth hearing from.

**The gap this closes was stated in the plan and never fixed.**
`detector_performance` reads `ConnectionHypothesis` and nothing else, so the
commitment parser — which has proposed on every capture since the merger — has
never had an accept rate at all. `retirement_gate` reports "worst detector" from
a population that silently excludes it.

**And D3 cannot fire without this.** August 19's decision was that a producer
below 50% accept rate loses priority for the review's five slots rather than
being tuned. That rule needs a number per producer, and for two of the three
proposal types there was nowhere for one to come from.

**Two commitment producers, not one**, and the split is the point. Capture fires
on a date; the journal fires on an undertaking. They read different material
with different signals and their false positives look nothing alike — averaging
them would hide exactly the thing per-producer attribution exists to show.
"""

from datetime import date, datetime, timezone as dt_timezone

import pytest
from django.utils import timezone

from daily.models import DailyEntry
from mind import instrumentation, services
from mind.models import Facet, FacetKind, NodeSource

pytestmark = pytest.mark.django_db

UTC = dt_timezone.utc
NOW = datetime(2026, 6, 1, 9, 0, tzinfo=UTC)
DAY = date(2026, 6, 1)


def _capture(owner, content):
    return services.capture(
        owner, content=content, captured_at=NOW, source=NodeSource.WEB, actor="v"
    )


def _entry(owner, text):
    entry = DailyEntry.objects.create(owner=owner, date=DAY, happenings=text)
    services.propose_journal_commitments(entry, now=NOW, actor="v")
    return entry


def _by_producer(owner):
    return {p.producer: p for p in instrumentation.producer_performance(owner)}


def test_a_capture_commitment_names_its_producer(owner):
    _capture(owner, "Dentist on 4 June.")

    facet = Facet.objects.get(kind=FacetKind.ACTIONABLE)
    assert facet.producer == "capture_commitment"


def test_a_journal_commitment_names_a_different_one(owner):
    """Two producers, deliberately.

    Capture fires on a date, the journal on an undertaking. Their false
    positives look nothing alike, so one blended rate would hide the thing
    attribution exists to show.
    """
    _entry(owner, "I need to ring the venue on 4 June.")

    facet = Facet.objects.get(kind=FacetKind.ACTIONABLE)
    assert facet.producer == "journal_commitment"


def test_a_proposed_commitment_is_counted_and_undecided(owner):
    _capture(owner, "Dentist on 4 June.")

    row = _by_producer(owner)["capture_commitment"]
    assert row.proposed == 1
    assert row.pending == 1
    assert row.accept_rate is None


def test_accepting_and_dismissing_move_the_rate(owner):
    accepted = _capture(owner, "Dentist on 4 June.")
    rejected = _capture(owner, "Bought milk on 5 June.")
    services.confirm_actionable(
        accepted.facets.get(kind=FacetKind.ACTIONABLE), now=NOW, actor="v"
    )
    services.dismiss_facet(
        rejected.facets.get(kind=FacetKind.ACTIONABLE),
        now=timezone.now(),
        actor="v",
    )

    row = _by_producer(owner)["capture_commitment"]
    assert (row.confirmed, row.dismissed, row.decided) == (1, 1, 2)
    assert row.accept_rate == 0.5


def test_an_undecided_producer_reports_no_rate_rather_than_zero(owner):
    """None, not 0.0.

    Zero reads as "wrong every time" where it means "no evidence yet", and the
    two call for opposite responses -- the same distinction
    `DetectorPerformance` already makes and the reason this reuses it.
    """
    _capture(owner, "Dentist on 4 June.")

    assert _by_producer(owner)["capture_commitment"].accept_rate is None


def test_detectors_appear_in_the_same_reading(owner):
    """One list, or the comparison D3 needs cannot be made.

    Rationing five slots by accept rate means comparing a detector against a
    parser. Two separate readings would leave that comparison to whoever is
    looking, which is where a blended number comes from in the first place.
    """
    other = _capture(owner, "The venue was lovely in April.")
    second = _capture(owner, "We saw the venue again in April.")
    services.propose_hypothesis(
        owner,
        detector="dormant_thread",
        citations=[
            services.Citation(node=other, reason="shares venue, April"),
            services.Citation(node=second, reason="shares venue, April"),
        ],
        confidence=0.5,
        label="shares: venue",
        index_version="fts-v1",
        now=NOW,
        actor="v",
    )

    assert "dormant_thread" in _by_producer(owner)


def test_another_person_s_proposals_are_not_counted(owner, other_owner):
    services.capture(
        other_owner,
        content="Dentist on 4 June.",
        captured_at=NOW,
        source=NodeSource.WEB,
        actor="someone-else",
    )

    assert _by_producer(owner) == {}


def test_the_worst_rate_now_sees_every_producer(owner):
    """`retirement_gate` was reading a population that excluded the parser.

    Its second condition is "accept rates hold", worst producer first. While
    only hypotheses were measured, a parser accepting nothing could not lower
    it -- so the gate could report health for a system half of which was
    unmeasured.
    """
    rejected = _capture(owner, "Bought milk on 5 June.")
    services.dismiss_facet(
        rejected.facets.get(kind=FacetKind.ACTIONABLE),
        now=timezone.now(),
        actor="v",
    )

    conditions = {c.name: c for c in instrumentation.retirement_gate(owner, now=NOW)}
    assert not conditions["accept rates hold"].met
