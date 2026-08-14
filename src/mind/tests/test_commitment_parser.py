"""Reading a date out of a capture, so a commitment is one tap rather than a form.

Deterministic and rule-based, which is what lets it run on the live path.
`design-concept.md` is explicit that capture, routing and planning stay off any
model: no per-call cost, no prompt sensitivity, no hallucinated due date, and a
result a test can pin exactly.

**It proposes; it never commits.** The actionable facet is the one classification
that creates an obligation, so this offers one and a person accepts it. A parser
confident enough to attach a due date on its own would be putting things in
somebody's agenda that they never agreed to.

Two failure directions, and they are not symmetric. Missing a date costs a tap.
Inventing one puts a commitment somebody never made into their week, so
everything here prefers silence to a guess.
"""

from datetime import date

import pytest

from mind.commitments import find_commitment

# A Wednesday, so "next Wednesday" and "Wednesday" have unambiguous answers.
TODAY = date(2026, 6, 10)


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Dentist on 2026-06-24", date(2026, 6, 24)),
        ("dentist tomorrow", date(2026, 6, 11)),
        ("call the plumber today", date(2026, 6, 10)),
        # Wednesday is today, so the next one is a week out rather than now.
        ("bins next Wednesday", date(2026, 6, 17)),
        ("pay rent on Friday", date(2026, 6, 12)),
    ],
)
def test_a_date_is_read_out_of_ordinary_writing(text, expected):
    found = find_commitment(text, today=TODAY)
    assert found is not None
    assert found.due_date == expected


@pytest.mark.parametrize(
    "text",
    [
        "I like lucid cars",
        "the woman in 4B practises most evenings",
        # A number that is not a date, and the trap a looser rule would take.
        "read 40 pages of the Indonesian book",
        "",
    ],
)
def test_writing_with_no_commitment_in_it_proposes_nothing(text):
    assert find_commitment(text, today=TODAY) is None


def test_a_recurrence_is_read_and_named(): 
    found = find_commitment("change the furnace filter every month", today=TODAY)

    assert found is not None
    assert found.recurrence == "monthly"


@pytest.mark.parametrize(
    "text,recurrence",
    [
        ("water the plants every day", "daily"),
        ("bins every week", "weekly"),
        ("change the filter monthly", "monthly"),
    ],
)
def test_the_cadences_the_task_core_can_actually_hold(text, recurrence):
    """Only the three `Item.Recurrence` offers. A parser that read "every third
    Tuesday" would be promising something the other core cannot store, and a
    commitment silently recorded as the wrong cadence is worse than one not
    recognised at all."""
    assert find_commitment(text, today=TODAY).recurrence == recurrence


def test_the_reason_quotes_the_words_it_read():
    """Checkable, like every other proposal here. "Looks like a task" asks for
    trust; naming the phrase lets somebody see it read "Friday" and disagree."""
    found = find_commitment("pay rent on Friday", today=TODAY)

    assert "friday" in found.reason.lower()


def test_a_recurrence_with_no_date_still_starts_somewhere():
    """A repeating commitment needs a first occurrence, and today is the only
    honest default -- guessing a start date is inventing a commitment."""
    found = find_commitment("water the plants every day", today=TODAY)

    assert found.due_date == TODAY
