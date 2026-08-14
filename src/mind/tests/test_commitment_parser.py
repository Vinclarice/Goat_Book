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


# ---------------------------------------------------------------------------
# Day of the month
# ---------------------------------------------------------------------------


def test_the_example_the_design_documents_have_used_all_along():
    """*"change the furnace on the 4th of each month"* is the phrase both
    `design-concept.md` and `two-cores.md` reach for, and the first version of
    this parser could not read it. Worth its own test for that reason alone."""
    found = find_commitment(
        "change the furnace filter on the 4th of each month", today=TODAY
    )

    assert found is not None
    assert found.recurrence == "monthly"
    # June 4th has gone; the next one is July's.
    assert found.due_date == date(2026, 7, 4)


@pytest.mark.parametrize(
    "text,expected",
    [
        ("bins out on the 12th", date(2026, 6, 12)),
        # Today, which is a real answer and not an off-by-one.
        ("rent on the 10th of every month", date(2026, 6, 10)),
        ("call the dentist on the 1st", date(2026, 7, 1)),
    ],
)
def test_a_day_of_the_month_is_read(text, expected):
    assert find_commitment(text, today=TODAY).due_date == expected


def test_a_day_that_this_month_does_not_have_moves_to_one_that_does():
    """June has thirty days. Clamping "the 31st" to June 30th would put a date
    on the task that nobody said -- so this finds the next month that really
    has a 31st instead. The task core clamps when it *advances* a monthly
    series, which is its own documented behaviour; inventing the first one is
    a different thing and not ours to do."""
    found = find_commitment("the 31st of every month", today=TODAY)

    assert found.due_date == date(2026, 7, 31)


@pytest.mark.parametrize(
    "text",
    [
        "the 4th time I have tried this",
        "chapter 4",
        "the 3rd person to say that",
        "came 2nd again",
    ],
)
def test_an_ordinal_that_is_counting_rather_than_dating_is_ignored(text):
    """An ordinal only reads as a date when what follows it is nothing, a
    punctuation mark, "of", or a time. Everything else is silence, because a
    counter misread as a date is the expensive direction: it puts a commitment
    into somebody's week that they never made."""
    assert find_commitment(text, today=TODAY) is None


# ---------------------------------------------------------------------------
# The other ways people write a date
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text,expected",
    [
        ("dentist 24 June", date(2026, 6, 24)),
        ("dentist June 24", date(2026, 6, 24)),
        ("dentist 24 Jun", date(2026, 6, 24)),
        ("dentist on the 24th of June", date(2026, 6, 24)),
        # Already gone this year, so it means next year's.
        ("mum's birthday 5 June", date(2027, 6, 5)),
        # An explicit year is obeyed, including one in the past.
        ("the deadline was June 24 2025", date(2025, 6, 24)),
    ],
)
def test_a_named_month_is_read(text, expected):
    assert find_commitment(text, today=TODAY).due_date == expected


@pytest.mark.parametrize(
    "text,expected",
    [
        ("call back in 3 days", date(2026, 6, 13)),
        ("follow up in two weeks", date(2026, 6, 24)),
        ("chase this in a week", date(2026, 6, 17)),
        ("review in 1 month", date(2026, 7, 10)),
    ],
)
def test_a_relative_offset_is_read(text, expected):
    assert find_commitment(text, today=TODAY).due_date == expected


def test_this_weekday_means_the_coming_one():
    assert find_commitment("pay rent this Friday", today=TODAY).due_date == date(
        2026, 6, 12
    )


# ---------------------------------------------------------------------------
# Cadences, and the ones that must stay silent
# ---------------------------------------------------------------------------


def test_every_named_weekday_is_a_weekly_commitment():
    found = find_commitment("bins out every Monday", today=TODAY)

    assert found.recurrence == "weekly"
    assert found.due_date == date(2026, 6, 15)


def test_every_naming_today_starts_today():
    found = find_commitment("stand-up every Wednesday", today=TODAY)

    assert found.due_date == TODAY


@pytest.mark.parametrize("word", ["each day", "each week", "each month"])
def test_each_is_read_the_same_as_every(word):
    assert find_commitment(f"water the plants {word}", today=TODAY) is not None


@pytest.mark.parametrize(
    "text",
    [
        "bins every other week",
        "invoices every 2 weeks",
        "pay day biweekly",
        "supervision every fortnight",
        "I think about it every now and then",
    ],
)
def test_a_cadence_the_task_core_cannot_hold_is_not_rounded_to_one_it_can(text):
    """These are the expensive near-misses. `Item.Recurrence` has three values,
    so a fortnightly commitment recorded as weekly would put twenty-six extra
    tasks a year into somebody's agenda while looking like it understood them.

    Silence is not a failure here -- it is the parser declining to promise
    something the other core cannot keep."""
    found = find_commitment(text, today=TODAY)

    assert found is None or found.recurrence is None


# ---------------------------------------------------------------------------
# What it says it read
# ---------------------------------------------------------------------------


def test_the_reason_quotes_both_the_date_and_the_cadence():
    found = find_commitment("furnace filter on the 4th of each month", today=TODAY)

    assert "4th" in found.reason
    assert "monthly" in found.reason


# ---------------------------------------------------------------------------
# Refusals that are decisions, not gaps
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("text", ["dentist 12/06", "dentist on 06/12/2026"])
def test_a_slash_date_is_refused_because_it_cannot_be_read_safely(text):
    """`12/06` is the 12th of June to half the world and the 6th of December to
    the other half, and this application already has a user in Indonesia and a
    user in the United States. There is no locale to consult -- a capture is a
    string, and the person who typed it is not present to be asked.

    So neither reading is offered. Getting a date six months wrong on a
    commitment somebody is relying on is worse than the one tap that writing
    "12 June" instead would have cost.
    """
    assert find_commitment(text, today=TODAY) is None


@pytest.mark.parametrize(
    "text,expected",
    [
        ("dentist tomorrow at 2pm", date(2026, 6, 11)),
        ("standup at 09:30 every day", TODAY),
    ],
)
def test_a_time_of_day_is_read_past_rather_than_stored(text, expected):
    """`Item` has a `due_date` and no time, so an hour has nowhere to go. It is
    stepped over rather than allowed to break the date around it -- and it is
    not silently dropped from the task either, because the task text is the
    whole note: "dentist tomorrow at 2pm" still says 2pm on the agenda, it just
    is not a field."""
    found = find_commitment(text, today=TODAY)

    assert found.due_date == expected
