"""A decision comes back — S11, and v3's *first question*.

> Six weeks ago he chose one approach over another and wrote down what would
> make him revisit. Something happens that touches the reason.

**Done means:** he can reach the decision from the work that provoked it, see
what he considered at the time and not only what he chose, and find decisions
past their reconsideration trigger without hunting for them.

**Not hypothetical.** S11's own entry says so: `architecture-trajectory.md` §7
and §8 are exactly this practice, done in Markdown *because the product cannot
hold it*.

**`Decision` earns its own model**, and the v3 plan already argued it:
*decided → held → returns on condition → revisited or superseded* is unlike
`Item` (open→done), `Facet` (proposed→confirmed→retired) or `Node`.

**The plan's one hard constraint, and a widening of it.** It says *"it must
cite a `Revision`, not a `Node`, or a note edited in October silently changes
what was on screen in August."* The concern is exactly right and citing a
`Revision` cannot deliver it: a `Revision` exists only for a note that has been
*edited*, and `revise` got its first door on August 21 — so almost no node has
one, and a decision could only cite a note somebody had happened to rewrite.

**So: cite the node, snapshot the text, and record the revision seq when there
is one.** The snapshot is what makes the record immune to a later edit, for
every note rather than for the edited few — and it is the move this codebase
already makes three times, in `DailyFocus.task_text`, `WeeklyOutcome.
project_title` and `Facet.cited_text`. The FK keeps navigation, which a
snapshot alone loses.
"""

import datetime

import pytest

from mind import services
from mind.models import Decision, Node


DECIDED = datetime.datetime(2026, 5, 4, 9, 0, tzinfo=datetime.timezone.utc)


def later(**offset):
    return DECIDED + datetime.timedelta(**offset)


@pytest.fixture
def signed_in(client, owner):
    client.force_login(owner)
    return client


@pytest.fixture
def note(owner):
    return services.capture(
        owner,
        content="the sync is taking three hours a week",
        captured_at=DECIDED,
        source=Node.Source.WEB,
        actor="vince",
    )


def a_decision(owner, node=None, **fields):
    return services.record_decision(
        owner,
        question=fields.pop("question", "how do we run the weekly sync?"),
        chose=fields.pop("chose", "written updates, no meeting"),
        considered=fields.pop("considered", "keep the meeting but halve it"),
        cites=node,
        now=fields.pop("now", DECIDED),
        **fields,
    )


# ---------------------------------------------------------------------------
# What he considered, not only what he chose
# ---------------------------------------------------------------------------


def test_a_decision_records_what_was_chosen(db, owner):
    decision = a_decision(owner)

    assert decision.chose == "written updates, no meeting"


def test_it_records_what_else_was_on_the_table(db, owner):
    """**The half a note cannot keep.** Six weeks later the alternatives are
    the part you have forgotten, and *what he considered at the time* is a
    third of this story's done-means."""
    decision = a_decision(owner)

    assert decision.considered == "keep the meeting but halve it"


def test_a_decision_needs_something_chosen(db, owner):
    with pytest.raises(services.MindError):
        a_decision(owner, chose="   ")


# ---------------------------------------------------------------------------
# Reaching it from the work that provoked it
# ---------------------------------------------------------------------------


def test_a_decision_can_cite_the_note_that_provoked_it(db, owner, note):
    decision = a_decision(owner, note)

    assert decision.cited_node == note


def test_the_note_can_find_the_decisions_it_provoked(db, owner, note):
    """*He can reach the decision from the work that provoked it.*"""
    decision = a_decision(owner, note)

    assert list(services.decisions_citing(note)) == [decision]


def test_the_citation_survives_the_note_being_edited(db, owner, note):
    """**The plan's constraint, and the reason for the snapshot.** *A note
    edited in October silently changes what was on screen in August.*"""
    decision = a_decision(owner, note)

    services.revise(note, body="actually it is four hours", now=later(days=60), actor="vince")

    decision.refresh_from_db()
    assert decision.cited_text == "the sync is taking three hours a week"


def test_the_citation_survives_the_note_being_deleted(db, owner, note):
    """A snapshot rather than a join, so the record of what was on screen
    outlives the thing that was on it."""
    decision = a_decision(owner, note)
    services.delete_node(note, now=later(days=1), actor="vince")

    decision.refresh_from_db()
    assert decision.cited_text == "the sync is taking three hours a week"


def test_a_decision_need_not_cite_anything(db, owner):
    """Not every decision comes out of something written down, and requiring
    a citation would push people to invent one."""
    decision = a_decision(owner, None)

    assert decision.cited_node is None
    assert decision.cited_text == ""


# ---------------------------------------------------------------------------
# Coming back — the reconsideration trigger
# ---------------------------------------------------------------------------


def test_a_decision_can_record_what_would_make_him_revisit(db, owner):
    decision = a_decision(owner, revisit_when="if anyone asks for the meeting back")

    assert decision.revisit_when == "if anyone asks for the meeting back"


def test_a_decision_past_its_date_is_found_without_hunting(db, owner):
    """*Find decisions past their reconsideration trigger without hunting for
    them* — the third of the done-means, and the one that needs a read."""
    decision = a_decision(owner, revisit_after=datetime.date(2026, 6, 1))

    due = services.decisions_to_revisit(owner, on=datetime.date(2026, 6, 2))

    assert list(due.past_their_date) == [decision]


def test_one_not_yet_due_is_left_alone(db, owner):
    a_decision(owner, revisit_after=datetime.date(2026, 6, 1))

    due = services.decisions_to_revisit(owner, on=datetime.date(2026, 5, 20))

    assert list(due.past_their_date) == []


def test_a_condition_in_words_cannot_be_found_and_the_read_says_so(db, owner):
    """**The honest half.** *If anyone asks for the meeting back* is not
    checkable by anything, and a read that quietly returned nothing for it
    would look like a decision with no trigger at all.

    So it is counted and named rather than dropped — the same absence
    discipline as `nights_not_recorded` and D5.
    """
    a_decision(owner, revisit_when="if anyone asks for the meeting back")

    due = services.decisions_to_revisit(owner, on=datetime.date(2026, 6, 2))

    assert due.waiting_on_a_condition == 1
    assert "cannot be checked" in due.about_conditions


def test_a_decision_already_revisited_does_not_come_back(db, owner):
    decision = a_decision(owner, revisit_after=datetime.date(2026, 6, 1))
    services.revisit_decision(decision, now=later(days=40))

    due = services.decisions_to_revisit(owner, on=datetime.date(2026, 6, 2))

    assert list(due.past_their_date) == []


# ---------------------------------------------------------------------------
# The recursion the product hangs from
# ---------------------------------------------------------------------------


def test_revisiting_can_produce_the_decision_that_replaces_it(db, owner):
    """*"The answer becomes part of the evidence available next time"* — the v3
    plan calls this the recursion the product hangs from."""
    first = a_decision(owner)

    second = services.record_decision(
        owner,
        question="how do we run the weekly sync?",
        chose="a fortnightly meeting",
        considered="written updates only, which we tried",
        supersedes=first,
        now=later(days=60),
    )

    first.refresh_from_db()
    assert second.supersedes == first
    assert first.revisited_at == later(days=60)


def test_the_superseded_one_is_still_there(db, owner):
    """A decision is not deleted by being replaced. *What he considered at the
    time* is only answerable if the record of the time survives."""
    first = a_decision(owner)
    services.record_decision(
        owner,
        question="again",
        chose="something else",
        considered="the first answer",
        supersedes=first,
        now=later(days=60),
    )

    assert Decision.objects.count() == 2


def test_one_person_never_supersedes_anothers(db, owner, other_owner):
    theirs = a_decision(other_owner)

    with pytest.raises(services.NotYours):
        services.record_decision(
            owner, question="q", chose="c", considered="", supersedes=theirs, now=DECIDED
        )


def test_it_does_not_read_another_persons_decisions(db, owner, other_owner):
    a_decision(other_owner, revisit_after=datetime.date(2026, 6, 1))

    due = services.decisions_to_revisit(owner, on=datetime.date(2026, 6, 2))

    assert list(due.past_their_date) == []


# ---------------------------------------------------------------------------
# The surface
# ---------------------------------------------------------------------------


def test_decisions_have_a_page(signed_in, owner):
    a_decision(owner)

    body = signed_in.get("/mind/decisions/").content.decode()

    assert "how do we run the weekly sync?" in body


def test_the_page_leads_with_what_is_due(signed_in, owner):
    a_decision(owner, revisit_after=datetime.date(2020, 1, 1))

    body = signed_in.get("/mind/decisions/").content.decode()

    assert "worth revisiting" in body.lower()


def test_the_page_says_what_cannot_be_checked(signed_in, owner):
    a_decision(owner, revisit_when="if anyone asks for the meeting back")

    body = signed_in.get("/mind/decisions/").content.decode()

    assert "cannot be checked" in body


def test_one_decision_has_its_own_page(signed_in, owner, note):
    decision = a_decision(owner, note)

    body = signed_in.get(f"/mind/decisions/{decision.public_id}/").content.decode()

    assert "keep the meeting but halve it" in body
    assert "the sync is taking three hours a week" in body


def test_the_note_page_shows_what_it_provoked(signed_in, owner, note):
    a_decision(owner, note)

    body = signed_in.get(f"/mind/notes/{note.public_id}/").content.decode()

    assert "how do we run the weekly sync?" in body


def test_one_person_cannot_open_anothers_decision(client, other_owner, owner):
    decision = a_decision(owner)
    client.force_login(other_owner)

    assert client.get(f"/mind/decisions/{decision.public_id}/").status_code == 404


def test_decisions_are_in_the_navigation(signed_in, owner):
    body = signed_in.get("/mind/").content.decode()

    assert "/mind/decisions/" in body
