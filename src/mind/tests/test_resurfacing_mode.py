"""The present cues it — **Resurfacing, and D17's answer**.

Five of the six modes in Part 2's table have had rules since Track B increment
8. **Resurfacing has raised `NotImplementedError` ever since**, and the reason
recorded there was exact:

> Planning, Reflection and Resurfacing each need context this module does not
> yet take — outcomes, a period, **a present**.

**D17 supplies the present, and it turns out to be the date.** *This time last
year* is human temporal cueing at its cheapest and most reliable, it derives
from `occurred_at` alone, and it needs no ML, no floors nobody can defend, no
budget and nothing switched on. `clarice.recall.this_time_before` is the read;
this is the mode built on it.

**The failure that matters here is *interrupting for nothing***, which is what
the eligibility rule below trades against — and it is the opposite trade from
Lookup, where every floor is a way to produce a miss. Nobody asked for this.
Something that arrives unbidden has to be worth the interruption, so a floor is
justified here in a way it never is there.

**A note reaches this mode only by surviving a year**, which is the strongest
relevance signal available without a guess: the anniversary is a recorded fact,
not a similarity score. That is why `semantic_echo` is not involved and why this
mode could ship while D14 is still open.
"""

import datetime

import pytest

from mind import retrieval, services
from mind.models import Node


NEW_YORK = "America/New_York"

#: Saturday August 22, 2026.
NOW = datetime.datetime(2026, 8, 22, 15, 0, tzinfo=datetime.timezone.utc)

LONG_ENOUGH = (
    "The venue wants a deposit by the end of the month and I still have not "
    "heard back from the other two, which means the decision is really about "
    "whether waiting is worth the risk of losing this one."
)


@pytest.fixture
def vince(owner):
    owner.time_zone = NEW_YORK
    owner.save(update_fields=["time_zone"])
    return owner


@pytest.fixture
def signed_in(client, vince):
    client.force_login(vince)
    return client


def a_note(owner, content=LONG_ENOUGH, *, when):
    return services.capture(
        owner, content=content, captured_at=when, source=Node.Source.WEB, actor="vince"
    )


def a_year_ago(**offset):
    return datetime.datetime(2025, 8, 22, 15, 0, tzinfo=datetime.timezone.utc) + (
        datetime.timedelta(**offset) if offset else datetime.timedelta()
    )


def resurfacing(owner, *, now=NOW):
    return retrieval.retrieve(
        retrieval.Moment(owner=owner, mode=retrieval.Mode.RESURFACING, now=now)
    )


# ---------------------------------------------------------------------------
# The mode exists
# ---------------------------------------------------------------------------


def test_resurfacing_no_longer_refuses(db, vince):
    """It raised `NotImplementedError` from increment 8 until D17 was answered.
    The refusal was right — falling back to Lookup's *admit everything* would
    have been four modes sharing one contract."""
    a_note(vince, when=a_year_ago())

    assert resurfacing(vince)


def test_it_returns_what_was_written_a_year_ago_today(db, vince):
    note = a_note(vince, when=a_year_ago())

    assert [result.node for result in resurfacing(vince)] == [note]


def test_it_says_why_it_is_here(db, vince):
    """Increment 9's rule, and it matters more here than anywhere: this is the
    one mode nobody asked. An interruption that cannot say why it interrupted
    is the thing that teaches somebody to dismiss the surface unread."""
    a_note(vince, when=a_year_ago())

    (result,) = resurfacing(vince)

    assert "a year ago today" in result.why


def test_a_note_from_further_back_says_how_far(db, vince):
    a_note(vince, when=a_year_ago().replace(year=2023))

    (result,) = resurfacing(vince)

    assert "three years ago today" in result.why


def test_the_nearest_year_comes_first(db, vince):
    older = a_note(vince, "Older. " + LONG_ENOUGH, when=a_year_ago().replace(year=2023))
    newer = a_note(vince, "Newer. " + LONG_ENOUGH, when=a_year_ago())

    assert [r.node for r in resurfacing(vince)] == [newer, older]


def test_a_note_from_another_day_is_not_cued(db, vince):
    a_note(vince, when=a_year_ago(days=-3))

    assert resurfacing(vince) == []


def test_todays_own_note_is_not_resurfaced(db, vince):
    """The present is the cue, never the thing cued."""
    a_note(vince, when=NOW)

    assert resurfacing(vince) == []


# ---------------------------------------------------------------------------
# Interrupting for nothing — the failure that matters
# ---------------------------------------------------------------------------


def test_a_scrap_is_not_worth_an_interruption(db, vince):
    """**The opposite trade from Lookup**, and the reason each mode gets its own
    rules. Under Lookup every floor is a way to produce a miss, because the
    person knows what they wrote and is asking for it. Nobody asked for this
    one, so it has to earn the interruption."""
    a_note(vince, "milk", when=a_year_ago())

    assert resurfacing(vince) == []


def test_a_deleted_note_does_not_come_back_from_the_dead(db, vince):
    note = a_note(vince, when=a_year_ago())
    services.delete_node(note, now=NOW, actor="vince")

    assert resurfacing(vince) == []


def test_it_does_not_resurface_another_persons_note(db, vince, other_owner):
    a_note(other_owner, when=a_year_ago())

    assert resurfacing(vince) == []


def test_the_clock_is_the_owners(db, vince):
    """**D16 underneath D17.** 21:00 on August 22 in New York is 01:00 on the
    23rd in UTC. A note written that evening is cued on the 22nd, because that
    is the evening it was written."""
    a_note(vince, when=datetime.datetime(2025, 8, 23, 1, 0, tzinfo=datetime.timezone.utc))

    assert len(resurfacing(vince)) == 1


# ---------------------------------------------------------------------------
# The surface
# ---------------------------------------------------------------------------


#: The page reads the clock at its edge, so the tests below tell the edge which
#: day it is rather than freezing time -- and rather than passing only while
#: the calendar happens to agree with the fixtures, which is what they did for
#: about twenty minutes.
ON_THE_DAY = "/mind/this-time-before/?on=2026-08-22"


def test_there_is_a_page_for_it(signed_in, vince):
    a_note(vince, when=a_year_ago())

    body = signed_in.get(ON_THE_DAY).content.decode()

    # Capitalised, because it is a heading. The same sentence a Resurfacing
    # result's `why` carries -- `retrieval.how_long_ago` is public so the page
    # and the interruption cannot drift into saying it two ways.
    assert "A year ago today" in body


def test_the_page_names_what_it_cannot_show(signed_in, vince):
    """A silent year and a year before you started are different facts, and an
    empty page says neither."""
    a_note(vince, when=datetime.datetime(2025, 3, 4, 15, 0, tzinfo=datetime.timezone.utc))

    body = signed_in.get(ON_THE_DAY).content.decode()

    assert "nothing recorded on this day" in body


def test_it_is_reachable_from_the_knowledge_core(signed_in, vince):
    body = signed_in.get("/mind/").content.decode()

    assert "/mind/this-time-before/" in body


def test_it_can_be_asked_about_another_day(signed_in, vince):
    """*What was I doing last Christmas* — a question the read could already
    answer, and one line to let somebody ask it."""
    a_note(vince, when=datetime.datetime(2025, 12, 25, 15, 0, tzinfo=datetime.timezone.utc))

    body = signed_in.get("/mind/this-time-before/?on=2026-12-25").content.decode()

    assert "A year ago today" in body


def test_a_nonsense_day_falls_back_to_today_rather_than_erroring(signed_in, vince):
    """A hand-edited URL is not an exception. `_parse_optional_date` already
    returns None for anything it cannot read, which is the behaviour the
    decisions form relies on."""
    assert signed_in.get("/mind/this-time-before/?on=banana").status_code == 200


def test_the_page_shows_what_the_mode_would_not_interrupt_for(signed_in, vince):
    """**Not a discrepancy — the opposite trade, deliberately.** Nothing here
    interrupts; somebody opened this. So the page is Lookup's bargain, where
    every floor is a way to produce a miss, and *milk* is a true thing that
    happened that morning. A surface that withheld it would be quietly editing
    somebody's own day.

    Noticed on the rendered page rather than here, which is why it is now
    asserted here.
    """
    a_note(vince, "milk", when=a_year_ago())

    body = signed_in.get(ON_THE_DAY).content.decode()

    assert "milk" in body
    assert resurfacing(vince) == []
