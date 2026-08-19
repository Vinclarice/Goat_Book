"""Accepting a commitment read out of the journal — increment 2, slice C.

`confirm_actionable` is the merger's payoff: node, facet and task written in one
transaction, so "a confirmed commitment with no live task" is not a state
anything can reach. This teaches it the second source without disturbing the
first — the node path is unchanged and its tests are the guard on that.

**No due date by default — Vince, August 19, 2026.** A promise without a date
is still a promise, and slice B stopped requiring one; so a task made from *"I
still need to ask Maya about the venue"* has no deadline and lands in the
agenda's someday bucket. Inventing one would be the parser guessing, which is
exactly what it refuses to do everywhere else, and the person can set a date on
a task they can now see.

**The entry is not consumed**, exactly as a node is not. `Facet.entry` keeps
pointing at the day it was read from, so a task can always answer where it came
from — the backlink this whole design exists to have.
"""

from datetime import date, datetime, timezone as dt_timezone

import pytest

from daily.models import DailyEntry
from lists.models import Item, List
from mind import services
from mind.models import Facet, FacetKind, InferenceOrigin

pytestmark = pytest.mark.django_db

UTC = dt_timezone.utc
NOW = datetime(2026, 6, 1, 9, 0, tzinfo=UTC)
DAY = date(2026, 6, 1)


@pytest.fixture
def entry(owner):
    return DailyEntry.objects.create(
        owner=owner,
        date=DAY,
        happenings="I still need to ask Maya about the venue.",
    )


@pytest.fixture
def proposed(owner, entry):
    services.propose_journal_commitments(entry, now=NOW, actor="vince")
    return Facet.objects.get(entry=entry, kind=FacetKind.ACTIONABLE)


def test_confirming_makes_a_task(owner, proposed):
    services.confirm_actionable(proposed, now=NOW, actor="vince")

    proposed.refresh_from_db()
    assert proposed.task is not None
    assert proposed.confirmed_at is not None


def test_the_task_says_what_the_sentence_said(owner, proposed):
    """The cited sentence, not the whole day.

    A task reading "I still need to ask Maya about the venue." is actionable.
    One carrying a paragraph of Tuesday is a wall of text somebody has to
    re-read to find the promise in.
    """
    services.confirm_actionable(proposed, now=NOW, actor="vince")

    proposed.refresh_from_db()
    assert proposed.task.text == "I still need to ask Maya about the venue."


def test_a_dateless_promise_makes_a_dateless_task(owner, proposed):
    services.confirm_actionable(proposed, now=NOW, actor="vince")

    proposed.refresh_from_db()
    assert proposed.task.due_date is None


def test_a_dated_promise_carries_its_date_through(owner, entry):
    entry.happenings = "I need to ring the venue on 4 June."
    entry.save()
    services.propose_journal_commitments(entry, now=NOW, actor="vince")
    facet = Facet.objects.get(entry=entry, kind=FacetKind.ACTIONABLE)

    services.confirm_actionable(facet, now=NOW, actor="vince")

    facet.refresh_from_db()
    assert facet.task.due_date == date(2026, 6, 4)


def test_the_task_belongs_to_the_person_who_wrote_the_entry(owner, proposed):
    services.confirm_actionable(proposed, now=NOW, actor="vince")

    proposed.refresh_from_db()
    assert proposed.task.owner == owner


def test_no_area_is_required(owner, proposed):
    """The same refusal the node path makes.

    Requiring an area puts a filing question at the moment somebody has
    already answered a different one -- yes, that is a task. `Item.owner` is
    what makes an unfiled task real rather than an orphan.
    """
    services.confirm_actionable(proposed, now=NOW, actor="vince")

    proposed.refresh_from_db()
    assert proposed.task.list is None


def test_an_area_may_still_be_chosen(owner, proposed):
    area = List.objects.create(owner=owner, title="Home")

    services.confirm_actionable(proposed, area=area, now=NOW, actor="vince")

    proposed.refresh_from_db()
    assert proposed.task.list == area


def test_somebody_else_s_area_is_refused(owner, other_owner, proposed):
    theirs = List.objects.create(owner=other_owner, title="Theirs")

    with pytest.raises(services.MindError):
        services.confirm_actionable(theirs and proposed, area=theirs, now=NOW, actor="v")


def test_confirming_twice_makes_one_task(owner, proposed):
    """Two taps, or a tap against a stale page.

    The first decision's task is the one that counts, and the second call is
    not an error -- the caller's intent is already satisfied.
    """
    services.confirm_actionable(proposed, now=NOW, actor="vince")
    first = proposed.task_id

    services.confirm_actionable(proposed, now=NOW, actor="vince")

    proposed.refresh_from_db()
    assert proposed.task_id == first
    assert Item.objects.filter(owner=owner).count() == 1


def test_the_entry_is_not_consumed(owner, entry, proposed):
    """A task can always answer where it came from."""
    services.confirm_actionable(proposed, now=NOW, actor="vince")

    proposed.refresh_from_db()
    assert proposed.entry == entry
    assert DailyEntry.objects.filter(pk=entry.pk).exists()


def test_a_confirmed_commitment_leaves_the_loose_ends(owner, entry, proposed):
    """The point of the whole slice, stated where it is visible.

    Slice B's proposals show up in the weekly review as commitments nobody
    answered. Accepting one has to remove it from that list, or the review goes
    on asking about a decision already made.
    """
    from review import reads

    services.confirm_actionable(proposed, now=NOW, actor="vince")

    ends = reads.loose_ends(owner, today=DAY)
    assert list(ends.unanswered_commitments) == []
