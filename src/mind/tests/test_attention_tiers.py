"""The two tiers a commitment reaches, which were unreachable until facets existed.

`design-concept.md`'s Attention Policy has four tiers. `attention_tier` returned
only the lower two and said so in its own docstring: *"Active commitment and
urgent / time-bound both require a confirmed actionable facet, and there is no
facet table."* There is one now -- facets landed on August 14, 2026 -- so the
gate was stale rather than the feature missing, and a node whose commitment a
person had explicitly accepted still reported as quiet knowledge.

The policy's own words for what these tiers buy: *active commitment* is
"eligible for the daily plan and for reminders"; *urgent* is "the only tier
allowed to interrupt outside of a planning or review moment". Getting the first
wrong means a commitment that never reaches a plan. Getting the second wrong
means interrupting somebody over a note.

**Tier is still derived, never stored**, which is what makes this a query change
and nothing else. The policy is explicit that a stored tier is a second source
of truth for something that changes with every capture.
"""

from datetime import date, datetime, timedelta, timezone as dt_timezone

import pytest

from lists.models import List
from mind import queries, services
from mind.models import FacetKind, NodeSource

pytestmark = pytest.mark.django_db

UTC = dt_timezone.utc
NOW = datetime(2026, 6, 10, 9, 0, tzinfo=UTC)
TODAY = date(2026, 6, 10)


@pytest.fixture
def node(owner):
    return services.capture(
        owner, content="Ring the dentist about a cleaning", captured_at=NOW,
        source=NodeSource.WEB, actor="vince",
    )


def commitment(node, *, due, confirmed=True, area=None):
    facet = services.propose_facet(
        node, kind=FacetKind.ACTIONABLE,
        data={"due_date": due.isoformat()} if due else {},
        now=NOW, actor="vince", reason="parsed a date",
    )
    if confirmed:
        services.confirm_actionable(facet, area=area, now=NOW, actor="vince")
    return facet


# ---------------------------------------------------------------------------
# Active commitment
# ---------------------------------------------------------------------------


def test_a_confirmed_commitment_is_an_active_commitment(owner, node):
    commitment(node, due=date(2026, 12, 1))

    assert queries.attention_tier(node, now=NOW) == "active commitment"


def test_a_proposal_is_not_a_commitment(owner, node):
    """The soft-apply rule, seen from the read side. Only a person's acceptance
    promotes a node here -- an inferred date must never reach a tier that is
    eligible for reminders."""
    commitment(node, due=date(2026, 12, 1), confirmed=False)

    assert queries.attention_tier(node, now=NOW) == "quiet knowledge"


def test_a_commitment_with_no_due_date_is_still_active(owner, node):
    """A commitment is a commitment whether or not it is dated. Only the
    *urgent* tier turns on proximity."""
    commitment(node, due=None)

    assert queries.attention_tier(node, now=NOW) == "active commitment"


def test_a_commitment_outranks_being_a_review_candidate(owner, node, other_owner):
    """`design-concept.md`: quiet knowledge is "anything with **no** confirmed
    actionable facet and no review due", so the facet decides first."""
    second = services.capture(
        owner, content="the dentist again", captured_at=NOW,
        source=NodeSource.WEB, actor="vince",
    )
    services.propose_hypothesis(
        owner,
        detector="dormant_thread",
        citations=[services.Citation(node=node), services.Citation(node=second)],
        confidence=0.8,
        label="shares: dentist",
        index_version="test",
        now=NOW,
    )
    commitment(node, due=date(2026, 12, 1))

    assert queries.attention_tier(node, now=NOW) == "active commitment"


# ---------------------------------------------------------------------------
# Urgent / time-bound
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "due,expected",
    [
        (TODAY, "urgent"),
        (TODAY + timedelta(days=1), "urgent"),
        (TODAY - timedelta(days=3), "urgent"),
        (TODAY + timedelta(days=2), "active commitment"),
        (TODAY + timedelta(days=30), "active commitment"),
    ],
)
def test_proximity_decides_urgency(owner, node, due, expected):
    """Overdue counts as urgent, which the policy does not spell out and which
    is the only sane reading: a commitment that has already passed is not less
    time-bound than one arriving tomorrow."""
    commitment(node, due=due)

    assert queries.attention_tier(node, now=NOW) == expected


def test_the_window_is_read_from_the_task_not_the_proposal(owner, node):
    """The facet's `data` records what was *proposed*. Once confirmed, the task
    is the live record and can be rescheduled in the task core -- so a
    commitment moved out to December must stop being urgent."""
    from lists.models import Item

    facet = commitment(node, due=TODAY)
    task = Item.objects.get()
    task.due_date = date(2026, 12, 1)
    task.save(update_fields=["due_date"])

    assert queries.attention_tier(node, now=NOW) == "active commitment"


# ---------------------------------------------------------------------------
# Where the tier stops applying
# ---------------------------------------------------------------------------


def test_a_deleted_node_is_quiet_whatever_it_committed_to(owner, node):
    """Deleted material is never pushed. The guard runs before the facet is
    consulted, so a commitment cannot resurrect a note somebody removed."""
    commitment(node, due=TODAY)
    services.delete_node(node, now=NOW, actor="vince")

    assert queries.attention_tier(node, now=NOW) == "quiet knowledge"


def test_a_retired_facet_no_longer_commits_anything(owner, node):
    facet = commitment(node, due=TODAY, confirmed=False)
    services.dismiss_facet(facet, now=NOW, actor="vince")

    assert queries.attention_tier(node, now=NOW) == "quiet knowledge"
