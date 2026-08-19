"""The review's five slots go to producers that have earned them — D3.

`planning-assistant-plan.md` §*D3, decided*, August 19, 2026. The caps were
never the problem; the **ordering** was.

`pending_hypotheses` sorted by `-confidence`, and confidence is not comparable
across detectors: `shared_referent` emits a flat 0.9, `open_question` a flat
0.55, `dormant_thread` a computed `shared_count / 8`. One states an evidence
*class*, another normalises a term count. So the five slots were rationed by
whichever constants somebody chose, while the measurement of what is actually
useful — per-detector accept rate — fed into nothing.

Now a detector below 50% accepted, over a sample somebody actually decided,
sorts behind the others. 50% is `retirement_gate`'s existing number rather than
a second one invented here.

**Quieter, never silent, and that is not a softening.** Demotion that starved a
detector would be self-confirming: fewer slots means fewer decisions means the
rate never recovers, and one unlucky early dismissal would bury a producer
permanently. A demoted detector still fills slots the others leave empty, so the
evidence that would rehabilitate it keeps arriving.

**Only detectors compete here.** The commitment parsers propose onto the capture
page and the day page, never into this queue, so their accept rates — measured
since August 19 — do not affect these five.
"""

from datetime import datetime, timedelta, timezone as dt_timezone

import pytest

from mind import queries, services
from mind.models import NodeSource

pytestmark = pytest.mark.django_db

UTC = dt_timezone.utc
NOW = datetime(2026, 6, 1, 9, 0, tzinfo=UTC)


def _node(owner, content, days_ago=1):
    return services.capture(
        owner,
        content=content,
        captured_at=NOW - timedelta(days=days_ago),
        source=NodeSource.WEB,
        actor="v",
    )


def _propose(owner, detector, confidence, label, days_ago=1):
    a = _node(owner, f"{label} first note", days_ago=days_ago)
    b = _node(owner, f"{label} second note", days_ago=days_ago + 1)
    return services.propose_hypothesis(
        owner,
        detector=detector,
        citations=[
            services.Citation(node=a, reason="a"),
            services.Citation(node=b, reason="b"),
        ],
        confidence=confidence,
        label=label,
        index_version="fts-v1",
        now=NOW,
        actor="v",
    )


def _make_rate(owner, detector, *, confirmed, dismissed):
    """Give `detector` a decided history without leaving pending rows behind."""
    for index in range(confirmed):
        services.confirm_hypothesis(
            _propose(owner, detector, 0.4, f"{detector}-ok-{index}", days_ago=40 + index),
            now=NOW,
            actor="v",
        )
    for index in range(dismissed):
        services.dismiss_hypothesis(
            _propose(owner, detector, 0.4, f"{detector}-no-{index}", days_ago=60 + index),
            now=NOW,
            actor="v",
        )


def _detectors_in_order(owner):
    return [h.detector for h in queries.pending_hypotheses(owner)]


def test_a_trusted_detector_outranks_a_more_confident_untrusted_one(owner):
    """The whole point, in one case.

    The noisy detector claims 0.9 and the trusted one 0.5, so confidence alone
    puts the noisy one first. What it has actually earned puts it second.
    """
    _make_rate(owner, "noisy", confirmed=1, dismissed=3)
    _make_rate(owner, "trusted", confirmed=3, dismissed=1)
    _propose(owner, "noisy", 0.9, "noisy-live")
    _propose(owner, "trusted", 0.5, "trusted-live")

    assert _detectors_in_order(owner)[:2] == ["trusted", "noisy"]


def test_confidence_still_orders_within_a_tier(owner):
    """Rationing replaces the *cross-detector* comparison, not the local one.

    Inside one detector the number means what its author meant, and it is the
    best ordering available.
    """
    _make_rate(owner, "trusted", confirmed=3, dismissed=1)
    _propose(owner, "trusted", 0.4, "lower")
    _propose(owner, "trusted", 0.8, "higher")

    labels = [h.label for h in queries.pending_hypotheses(owner)]
    assert labels.index("higher") < labels.index("lower")


def test_a_detector_with_no_decisions_is_not_demoted(owner):
    """No evidence is not bad evidence.

    A new detector has decided nothing, and starting it in the penalty tier
    would mean it was never seen enough to be judged -- the same reason
    `accept_rate` returns None rather than zero.
    """
    _make_rate(owner, "trusted", confirmed=3, dismissed=1)
    _propose(owner, "newcomer", 0.9, "newcomer-live")
    _propose(owner, "trusted", 0.5, "trusted-live")

    assert _detectors_in_order(owner)[0] == "newcomer"


def test_exactly_half_accepted_is_not_demoted(owner):
    """The boundary, stated. `retirement_gate` reads `>= 0.5` as holding, and
    two readings of one threshold is how a rule comes to mean two things."""
    _make_rate(owner, "even", confirmed=2, dismissed=2)
    _propose(owner, "even", 0.5, "even-live")

    assert _detectors_in_order(owner) == ["even"]


def test_demotion_is_not_starvation(owner):
    """Quieter, never silent.

    A demoted detector still fills slots nothing else claims. Otherwise
    demotion is self-confirming -- no slots, no decisions, no recovery -- and
    one unlucky early dismissal would bury a producer for good.
    """
    _make_rate(owner, "noisy", confirmed=1, dismissed=3)
    _propose(owner, "noisy", 0.6, "noisy-live")

    shown = services.open_review(owner, now=NOW, actor="v", limit=5)

    assert [h.label for h in shown] == ["noisy-live"]


def test_the_review_shows_the_earned_ones_first(owner):
    """End to end, through the surface that actually rations the slots."""
    _make_rate(owner, "noisy", confirmed=1, dismissed=3)
    _make_rate(owner, "trusted", confirmed=3, dismissed=1)
    _propose(owner, "noisy", 0.95, "noisy-live")
    _propose(owner, "trusted", 0.2, "trusted-live")

    shown = services.open_review(owner, now=NOW, actor="v", limit=1)

    assert [h.label for h in shown] == ["trusted-live"]


def test_one_person_s_rates_do_not_ration_another_s_slots(owner, other_owner):
    """Accept rates are per person, because "distinctive to them" is the whole
    premise of every producer here."""
    _make_rate(other_owner, "noisy", confirmed=0, dismissed=4)
    _make_rate(owner, "trusted", confirmed=3, dismissed=1)
    _propose(owner, "noisy", 0.9, "noisy-live")
    _propose(owner, "trusted", 0.5, "trusted-live")

    assert _detectors_in_order(owner)[0] == "noisy"
