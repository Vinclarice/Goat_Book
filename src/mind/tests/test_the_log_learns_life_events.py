"""The append-only log learns to say what happened to a life, not just a note.

`temporal-substrate-plan.md` Track A increment 1 — **the vocabulary, emitting
nothing.** Nothing in this file makes an event; the next increment does that.

The finding it answers is exact: `EventType` had 23 values and every one was
about a note, so *"the most carefully guarded structure in the codebase is a
note log, not a life log."* The right structure with the wrong vocabulary.

**Subjects, not a payload convention.** The log gains the two subject foreign
keys `Facet` already carries — a task and a day's entry — because an id buried
in JSON cannot be indexed, joined or read by `around()`, which is what all of
this is for.

**Non-constraining, for the reason the `node` reference already gives.**
CASCADE, SET_NULL and SET_DEFAULT are each a *mutation* of the log, which the
trigger refuses — so a real foreign key would make any task with events
undeletable, and under increment 2 every completed task has one. Readers
tolerate a dangling id; an event asserts what happened, not what still exists.

**No exactly-one constraint, unlike `Facet`.** A facet citing two sources makes
*where did this come from* ambiguous. An event citing two subjects does not:
`confirm_actionable` turns a thought into a commitment, and that event genuinely
has both a node and a task. An owner-scoped event with no subject at all is
already legal and already shipped — `MAINTENANCE_RAN`.
"""

import datetime

import pytest
from django.db import DatabaseError, connection, transaction

from accounts import services as account_services
from daily import services as daily_services
from lists import services as list_services
from lists.models import Item, List
from mind.models import ActivityEvent, EventType

pytestmark = pytest.mark.django_db(transaction=True)

WHEN = datetime.datetime(2026, 6, 10, 9, 0, tzinfo=datetime.timezone.utc)
DAY = datetime.date(2026, 6, 10)


@pytest.fixture
def a_task(owner):
    area = List.objects.create(owner=owner, title="Home")
    return list_services.create_item(area, "Call the plumber")


def an_event(owner, event_type, **subjects):
    return ActivityEvent.objects.create(
        owner=owner,
        event_type=event_type,
        occurred_at=WHEN,
        actor=owner.get_username(),
        **subjects,
    )


# ---------------------------------------------------------------------------
# The vocabulary
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "event_type",
    [
        EventType.TASK_COMPLETED,
        EventType.TASK_REOPENED,
        EventType.TASK_ARCHIVED,
        EventType.COMMITMENT_CHANGED,
        EventType.COMMITMENT_ENDED,
        EventType.FOCUS_PINNED,
        EventType.FOCUS_RELEASED,
        EventType.WEEK_REVIEWED,
        EventType.INTENTION_SET,
        EventType.OUTCOME_CHOSEN,
    ],
)
def test_the_check_constraint_accepts_every_life_event(owner, event_type):
    """`event_type_valid` is a database check over `EventType.values`, so a
    value the enum knows and the constraint does not is a runtime error rather
    than a type error -- exactly the failure a widened enum invites."""
    assert an_event(owner, event_type).pk is not None


def test_a_value_outside_the_vocabulary_is_still_refused(owner):
    """The regression guard on the widening itself: adding ten values must not
    turn the constraint into one that accepts anything."""
    with pytest.raises(DatabaseError):
        with transaction.atomic():
            an_event(owner, "task_dry_cleaned")


# ---------------------------------------------------------------------------
# The subjects
# ---------------------------------------------------------------------------


def test_an_event_can_name_the_task_it_is_about(owner, a_task):
    event = an_event(owner, EventType.TASK_COMPLETED, task=a_task)

    assert ActivityEvent.objects.get(pk=event.pk).task_id == a_task.pk


def test_an_event_can_name_the_day_it_is_about(owner):
    entry = daily_services.write_entry(owner, DAY, happenings="A written day.")

    event = an_event(owner, EventType.FOCUS_PINNED, entry=entry)

    assert ActivityEvent.objects.get(pk=event.pk).entry_id == entry.pk


def test_an_event_may_name_both_a_note_and_a_task(owner, a_task):
    """`confirm_actionable` is the case: a thought became a commitment, and an
    event about it has two honest subjects. `Facet`'s exactly-one rule is not
    copied here, and this is the reason."""
    from mind import services
    from mind.models import NodeSource

    node = services.capture(
        owner, content="Ring the plumber", captured_at=WHEN,
        source=NodeSource.WEB, actor=owner.get_username(),
    )

    event = an_event(owner, EventType.TASK_COMPLETED, node=node, task=a_task)

    assert (event.node_id, event.task_id) == (node.pk, a_task.pk)


def test_an_event_still_needs_no_subject_at_all(owner):
    """`MAINTENANCE_RAN` is owner-scoped and subject-less and must stay legal;
    a week that was reviewed has no task and no entry either."""
    assert an_event(owner, EventType.WEEK_REVIEWED).pk is not None


# ---------------------------------------------------------------------------
# What the widening must not cost
# ---------------------------------------------------------------------------


def test_deleting_the_task_leaves_the_event_standing(owner, a_task):
    """The whole reason these are non-constraining. A real foreign key would
    make any task with events undeletable -- and under increment 2 every
    completed task has one -- because a cascade is a mutation of the log and
    the trigger refuses it."""
    event = an_event(owner, EventType.TASK_COMPLETED, task=a_task)
    task_id = a_task.pk

    Item.objects.filter(pk=task_id).delete()

    survivor = ActivityEvent.objects.get(pk=event.pk)
    assert survivor.task_id == task_id
    assert not Item.objects.filter(pk=task_id).exists()


def test_the_widened_log_still_refuses_an_update(owner, a_task):
    event = an_event(owner, EventType.TASK_COMPLETED, task=a_task)

    with pytest.raises(DatabaseError):
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(
                "UPDATE mind_activityevent SET actor = 'someone else' WHERE id = %s",
                [event.pk],
            )


def test_the_widened_log_still_refuses_a_delete(owner, a_task):
    event = an_event(owner, EventType.TASK_COMPLETED, task=a_task)

    with pytest.raises(DatabaseError):
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM mind_activityevent WHERE id = %s", [event.pk]
            )


def test_erasing_the_account_still_takes_the_widened_log_with_it(owner, a_task):
    """The one hole in the trigger is `purge_account`, and a log carrying task
    and entry references must not become a log that survives its owner."""
    an_event(owner, EventType.TASK_COMPLETED, task=a_task)
    owner_id = owner.pk

    account_services.purge_account(owner, now=WHEN)

    assert not ActivityEvent.objects.filter(owner_id=owner_id).exists()
