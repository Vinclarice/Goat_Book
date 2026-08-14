"""Facets, and the one that creates an obligation.

A facet gives a node a capability without putting it in an exclusive bucket: a
node can carry several at once, or none, and nothing about capture asks which.
That is the design's answer to `Capture → Idea → Task`, whose terminus made
everything inside it point at actionability.

**The actionable facet is the exception to soft-apply, and the only one.** Every
other proposal in this system is applied immediately, labelled, and dismissed in
one tap, because being wrong costs a row. This one creates a commitment, so it is
never attached without a person saying so — and confirming it is what
materialises a task in the other core.

That materialisation is the merger's whole payoff. One database means node, facet
and task go in a single transaction, so "a confirmed actionable facet with no
live task" is not a state that can be reached — no outbox, no reconciler, no
window where a person believes they recorded a dentist appointment and nothing
did.
"""

from datetime import date, datetime, timedelta, timezone as dt_timezone

import pytest
from django.db import transaction

from lists.models import Item, List
from mind import services
from mind.models import ActivityEvent, EventType, Facet, FacetKind, InferenceOrigin, NodeSource

pytestmark = pytest.mark.django_db

UTC = dt_timezone.utc
NOW = datetime(2026, 6, 1, 9, 0, tzinfo=UTC)


@pytest.fixture
def area(owner):
    return List.objects.create(owner=owner, title="Home")


@pytest.fixture
def node(owner):
    """Deliberately undated.

    It was "Dentist next Wednesday at 2pm" until the parser started running at
    capture, at which point every test using this fixture had an actionable
    facet it did not ask for -- and `propose_facet` is get_or_create on the live
    facet, so a test proposing its own data quietly received the parser's
    instead. The parser has its own tests; these are about what a facet *is*.
    """
    return services.capture(
        owner,
        content="Ring the dentist about a cleaning",
        captured_at=NOW,
        source=NodeSource.MOBILE,
        actor="vince",
    )


# ---------------------------------------------------------------------------
# Facets in general
# ---------------------------------------------------------------------------


def test_a_node_can_carry_several_facets_at_once(owner, node):
    """Not an exclusive bucket. The whole point of a facet is that a thought can
    be a media note and a commitment without being filed as either."""
    services.propose_facet(node, kind=FacetKind.MEDIA, data={"title": "Dune"},
                           now=NOW, actor="vince", reason="matched keyword 'movie'")
    services.propose_facet(node, kind=FacetKind.EPISTEMIC, data={"status": "question"},
                           now=NOW, actor="vince", reason="ends with a question mark")

    assert Facet.objects.filter(node=node).count() == 2


def test_a_proposed_facet_is_not_confirmed(owner, node):
    """Soft-applied: visible, labelled, dismissible, and not treated as fact by
    anything downstream."""
    facet = services.propose_facet(node, kind=FacetKind.MEDIA, data={"title": "Dune"},
                                   now=NOW, actor="vince", reason="matched 'movie'")

    assert facet.confirmed_at is None
    assert facet.origin == InferenceOrigin.INFERRED


def test_a_proposal_carries_the_signal_that_produced_it(owner, node):
    """Every proposal explains itself. A facet with no reason is an assertion."""
    facet = services.propose_facet(node, kind=FacetKind.MEDIA, data={"title": "Dune"},
                                   now=NOW, actor="vince", reason="matched keyword 'movie'")

    assert "movie" in facet.reason


# ---------------------------------------------------------------------------
# The actionable facet
# ---------------------------------------------------------------------------


def test_confirming_an_actionable_facet_creates_a_task(owner, node, area):
    """The merger's payoff. The node stays where it is; the commitment appears
    in the core that knows what to do with one."""
    facet = services.propose_facet(
        node, kind=FacetKind.ACTIONABLE, data={"due_date": "2026-06-10"},
        now=NOW, actor="vince", reason="parsed a date",
    )

    services.confirm_actionable(facet, area=area, now=NOW, actor="vince")

    task = Item.objects.get()
    assert task.text == "Ring the dentist about a cleaning"
    assert task.due_date == date(2026, 6, 10)
    assert task.list == area


def test_the_node_is_not_consumed_by_becoming_a_task(owner, node, area):
    """It leaves the quiet tier, not the graph. A task that cannot find where it
    came from is the defect this whole design exists to escape."""
    facet = services.propose_facet(node, kind=FacetKind.ACTIONABLE, data={},
                                   now=NOW, actor="vince", reason="parsed a date")

    services.confirm_actionable(facet, area=area, now=NOW, actor="vince")

    facet.refresh_from_db()
    assert facet.node == node
    assert facet.task == Item.objects.get()


def test_an_actionable_facet_is_never_soft_applied(owner, node):
    """The one exception to the soft-apply tier, because it is the one
    classification that creates an obligation rather than an organisational
    label. A proposal may suggest it; only a person may attach it."""
    with pytest.raises(services.MindError):
        services.propose_facet(
            node, kind=FacetKind.ACTIONABLE, data={}, now=NOW, actor="system",
            reason="parsed a date", origin=InferenceOrigin.EXPLICIT,
        )


def test_a_proposed_actionable_facet_has_no_task_until_confirmed(owner, node):
    """Proposing is allowed -- the parser should be able to offer one. What is
    not allowed is that offer counting as a commitment."""
    services.propose_facet(node, kind=FacetKind.ACTIONABLE, data={},
                           now=NOW, actor="system", reason="parsed a date")

    assert Item.objects.count() == 0


def test_confirming_twice_does_not_make_two_tasks(owner, node, area):
    """Two taps, or a tap against a stale page. Neither should double a
    commitment."""
    facet = services.propose_facet(node, kind=FacetKind.ACTIONABLE, data={},
                                   now=NOW, actor="vince", reason="parsed a date")

    services.confirm_actionable(facet, area=area, now=NOW, actor="vince")
    services.confirm_actionable(facet, area=area, now=NOW, actor="vince")

    assert Item.objects.count() == 1


def test_the_confirmation_is_recorded_in_the_log(owner, node, area):
    facet = services.propose_facet(node, kind=FacetKind.ACTIONABLE, data={},
                                   now=NOW, actor="vince", reason="parsed a date")

    services.confirm_actionable(facet, area=area, now=NOW, actor="vince")

    event = ActivityEvent.objects.filter(event_type=EventType.FACET_CONFIRMED).get()
    assert event.payload["kind"] == FacetKind.ACTIONABLE
    assert event.payload["task"] == Item.objects.get().pk


def test_a_failure_creating_the_task_leaves_no_confirmed_facet(owner, node, area):
    """The invariant, exercised rather than asserted. One database means one
    transaction, so there is no window in which somebody believes they recorded
    a dentist appointment and only half of it exists."""
    Item.objects.create(list=area, owner=owner, text="Ring the dentist about a cleaning")
    facet = services.propose_facet(node, kind=FacetKind.ACTIONABLE, data={},
                                   now=NOW, actor="vince", reason="parsed a date")

    # create_item refuses a duplicate in the same area.
    with pytest.raises(Exception):
        services.confirm_actionable(facet, area=area, now=NOW, actor="vince")

    facet.refresh_from_db()
    assert facet.confirmed_at is None
    assert facet.task is None


def test_another_persons_area_cannot_receive_your_commitment(owner, other_owner, node):
    theirs = List.objects.create(owner=other_owner, title="Theirs")
    facet = services.propose_facet(node, kind=FacetKind.ACTIONABLE, data={},
                                   now=NOW, actor="vince", reason="parsed a date")

    with pytest.raises(services.MindError):
        services.confirm_actionable(facet, area=theirs, now=NOW, actor="vince")


def test_the_reconciliation_count_is_zero(owner, node, area):
    """A confirmed actionable facet with no live task should be impossible, so
    this number should always be zero. Reporting it is how a broken invariant
    is found in a number rather than in a missed appointment."""
    facet = services.propose_facet(node, kind=FacetKind.ACTIONABLE, data={},
                                   now=NOW, actor="vince", reason="parsed a date")
    services.confirm_actionable(facet, area=area, now=NOW, actor="vince")

    assert services.commitments_without_tasks(owner) == 0


# ---------------------------------------------------------------------------
# A commitment that needs nowhere to be filed
# ---------------------------------------------------------------------------


def test_a_commitment_can_be_accepted_without_choosing_an_area(owner, node):
    """The filing question, refused at the moment it would be asked.

    Accepting a commitment used to require naming an Area, which put a decision
    exactly where this design says there is none -- and worse, at the one moment
    a person has already decided (yes, that is a task) and is being asked
    something else instead. `Item.owner`, August 14 2026, is what makes this
    possible: the task belongs to a person rather than to a list.
    """
    facet = services.propose_facet(node, kind=FacetKind.ACTIONABLE, data={},
                                   now=NOW, actor="vince", reason="parsed a date")

    services.confirm_actionable(facet, area=None, now=NOW, actor="vince")

    task = Item.objects.get()
    assert task.list is None
    assert task.owner == owner


def test_an_unfiled_commitment_still_points_back_at_its_thought(owner, node):
    """Having no Area is not the same as having no provenance."""
    facet = services.propose_facet(node, kind=FacetKind.ACTIONABLE, data={},
                                   now=NOW, actor="vince", reason="parsed a date")

    services.confirm_actionable(facet, area=None, now=NOW, actor="vince")

    facet.refresh_from_db()
    assert facet.task == Item.objects.get()
    assert facet.node == node


def test_an_area_may_still_be_named_when_there_is_an_obvious_one(owner, node, area):
    """Optional, not removed. Filing stays available for the person who wants
    it; what changed is that it is no longer the toll on accepting."""
    facet = services.propose_facet(node, kind=FacetKind.ACTIONABLE, data={},
                                   now=NOW, actor="vince", reason="parsed a date")

    services.confirm_actionable(facet, area=area, now=NOW, actor="vince")

    assert Item.objects.get().list == area
