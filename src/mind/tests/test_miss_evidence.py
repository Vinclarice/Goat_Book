"""What a recorded miss is evidence *of*, now that the page searches three things.

`design/search-plan.md` D3, answered August 20, 2026 — and not the question the
brief posed. It asked whether `RetrievalMiss.resolved_node` should widen to
reach a task. It should not, because **nothing has ever populated that field**:
`services.resolve_retrieval_miss` has no caller outside its own tests and no
reader anywhere. Widening a seam that was never switched on is not the work.

The real problem was one increment 3 created. `retrieval_miss_trend` counts
every miss an owner has recorded, and it feeds `retirement_gate`'s "retrieval
misses fall" — one of three conditions on the semantic-retrieval decision, and
by its own comment the only one measurable without interpretation. That number
meant something exact while `/mind/search/` searched only notes: every miss was
a note-retrieval failure. Putting the same button under three sections made it
ambiguous, and **a miss cannot be re-interpreted after the fact** — which is why
this was fixed before the deploy rather than after it.

So a miss now records what each section actually returned, and the gate counts
the ones where the note index came back with nothing.
"""

import datetime

import pytest
from django.utils import timezone

from daily.models import DailyEntry
from lists.models import Item
from mind import instrumentation, services
from mind.models import RetrievalMiss


@pytest.fixture
def signed_in(client, owner):
    client.force_login(owner)
    return client


def press_the_button(client, q):
    return client.post("/mind/search/miss/", {"q": q})


def test_a_miss_records_what_each_section_returned(signed_in, owner, make_node):
    make_node("The restore drill is the rollback path")
    Item.objects.create(owner=owner, text="Rollback the deploy")

    press_the_button(signed_in, "rollback")

    miss = RetrievalMiss.objects.get(owner=owner)
    assert miss.notes_found == 1
    assert miss.tasks_found == 1
    assert miss.days_found == 0


def test_the_counts_are_computed_from_the_query_not_taken_from_the_form(
    signed_in, owner, make_node
):
    """The form could say anything. Recomputing from `q` costs three counts on
    a rare action and means the evidence is the server's own, which matters for
    the one signal a decision is measured against."""
    make_node("The restore drill is the rollback path")

    signed_in.post(
        "/mind/search/miss/", {"q": "rollback", "notes_found": "999", "tasks_found": "999"}
    )

    miss = RetrievalMiss.objects.get(owner=owner)
    assert miss.notes_found == 1
    assert miss.tasks_found == 0


def test_a_miss_where_the_notes_index_found_nothing_counts_toward_the_gate(
    signed_in, owner
):
    """The embeddings question stated precisely: would a semantic index have
    surfaced this? Only answerable when the lexical one surfaced nothing."""
    Item.objects.create(owner=owner, text="Rollback the deploy")

    press_the_button(signed_in, "rollback")

    trend = instrumentation.retrieval_miss_trend(owner, now=timezone.now())
    assert sum(count for _, count in trend) == 1


def test_a_miss_where_the_notes_index_found_something_does_not(
    signed_in, owner, make_node
):
    """Ambiguous, and excluded rather than guessed at. The notes section had
    answers; whether the person wanted one of them, or wanted the task below,
    is not recoverable — and a gate fed on guesses is worse than a narrower one."""
    make_node("The restore drill is the rollback path")

    press_the_button(signed_in, "rollback")

    assert RetrievalMiss.objects.filter(owner=owner).count() == 1
    trend = instrumentation.retrieval_miss_trend(owner, now=timezone.now())
    assert sum(count for _, count in trend) == 0


def test_a_miss_recorded_before_any_of_this_still_counts(owner):
    """History stays counted. Every miss recorded before August 20, 2026 came
    from a page that searched notes and nothing else, so each one is note
    evidence by construction — `None` means that, and must not be read as "the
    notes section had results"."""
    services.record_retrieval_miss(
        owner, query_text="rollback", now=timezone.now()
    )

    miss = RetrievalMiss.objects.get(owner=owner)
    assert miss.notes_found is None

    trend = instrumentation.retrieval_miss_trend(owner, now=timezone.now())
    assert sum(count for _, count in trend) == 1


def test_the_journal_and_task_misses_are_still_recorded(signed_in, owner, make_node):
    """Excluded from the note gate is not the same as thrown away. This is the
    only evidence available about whether task and journal search fail people,
    and there is no other way to get it."""
    make_node("The restore drill is the rollback path")

    press_the_button(signed_in, "rollback")

    miss = RetrievalMiss.objects.get(owner=owner)
    assert miss.tasks_found == 0
    assert miss.days_found == 0


def test_a_miss_is_scoped_to_the_person_who_pressed_it(
    signed_in, owner, other_owner
):
    Item.objects.create(owner=other_owner, text="Rollback the deploy")
    DailyEntry.objects.create(
        owner=other_owner, date=datetime.date(2026, 8, 20), happenings="rollback"
    )

    press_the_button(signed_in, "rollback")

    miss = RetrievalMiss.objects.get(owner=owner)
    assert miss.tasks_found == 0
    assert miss.days_found == 0
