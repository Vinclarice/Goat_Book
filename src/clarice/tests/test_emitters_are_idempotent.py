"""Doing the same thing twice is one fact -- a contract over every emitter.

`recommendations-2026-08-21.md` item 1, and the structural close of C1-C4.
Those four were caught by review; **nothing prevented the fifth.** They shared
one shape: a write into a table whose trigger refuses `UPDATE` and `DELETE`,
where over-recording is permanent and under-recording is recoverable.

So this file states the rule once, for every live emitter of the ten life
events: **perform the operation twice with identical input, and the log holds
one event.** A guard is not something each service remembers -- it is a
property this file will fail without.

**Two honest exceptions, named rather than excluded.** A second call is
sometimes a real second act, and a contract that pretended otherwise would push
somebody to add a wrong guard to satisfy it:

- **Repinning after a release.** Choosing something, putting it down, and
  choosing it again is three decisions and the review block is built on being
  able to tell them apart.
- **Choosing an outcome.** `choose_outcome` creates a row every time; two
  identical calls leave two commitments standing, and one event would then
  under-count what the week actually holds.

**Every emitter is covered, and the coverage is asserted rather than trusted.**
`test_every_life_event_has_a_test_here` fails when an `EventType` life value
gains an emitter nobody wrote a case for -- which is the same shape as
`recall.PERSON_EVENTS`' partition assertion, for the same reason: a list that
only fails on removal never fails on omission.
"""

import datetime

from clarice import life_log
from clarice.testing import CrossCoreTestCase
from daily import services as daily_services
from lists import services as list_services
from lists.models import Item
from mind.models import ActivityEvent
from review import services as review_services


MONDAY = datetime.date(2026, 3, 2)

#: The exceptions, and why each is a second act rather than a duplicate.
A_SECOND_CALL_IS_A_SECOND_ACT = {
    life_log.FOCUS_PINNED: "repinning after a release is a third decision",
    life_log.OUTCOME_CHOSEN: "each call leaves another commitment standing",
}


class EmitterContractTest(CrossCoreTestCase):
    def count(self, event_type):
        return ActivityEvent.objects.filter(event_type=event_type).count()

    def assert_one(self, event_type):
        self.assertEqual(
            self.count(event_type),
            1,
            f"{event_type} was recorded {self.count(event_type)} times for one act",
        )

    # -- the task core ---------------------------------------------------

    def test_completing_twice_is_one_completion(self):
        task = self.a_task()
        list_services.complete_item(task)
        list_services.complete_item(task)

        self.assert_one(life_log.TASK_COMPLETED)

    def test_reopening_twice_is_one_reopening(self):
        task = self.a_task()
        list_services.complete_item(task)
        list_services.reopen_item(task)
        list_services.reopen_item(task)

        self.assert_one(life_log.TASK_REOPENED)

    def test_archiving_twice_is_one_archiving(self):
        task = self.a_task()
        list_services.archive_item(task)
        list_services.archive_item(task)

        self.assert_one(life_log.TASK_ARCHIVED)

    def test_letting_go_twice_is_one_letting_go(self):
        from clarice import leftovers

        task = self.a_task()
        leftovers.let_go(self.alice, task)
        leftovers.let_go(self.alice, task)

        self.assert_one(life_log.TASK_LET_GO)

    # -- the calendar ----------------------------------------------------

    def test_cancelling_twice_is_one_cancellation(self):
        import datetime

        from appointments import services as appointment_services

        appointment = appointment_services.make(
            self.alice, text="Parents' evening", starts_on=datetime.date(2026, 9, 4)
        )
        appointment_services.cancel(appointment)
        appointment_services.cancel(appointment)

        self.assert_one(life_log.APPOINTMENT_CANCELLED)

    def test_making_the_same_appointment_twice_is_one_appointment(self):
        """Idempotent on the id the client owns, like a capture: a retry the
        client never saw succeed must not put two Thursdays in the diary.
        """
        import datetime
        import uuid

        from appointments import services as appointment_services

        key = uuid.uuid4()
        for _ in range(2):
            appointment_services.make(
                self.alice,
                text="Call with the accountant",
                starts_on=datetime.date(2026, 9, 4),
                public_id=key,
            )

        self.assert_one(life_log.APPOINTMENT_MADE)

    def test_setting_the_same_cadence_twice_is_one_change(self):
        task = self.a_task()
        list_services.set_recurrence(task, Item.Recurrence.WEEKLY)
        list_services.set_recurrence(task, Item.Recurrence.WEEKLY)

        self.assert_one(life_log.COMMITMENT_CHANGED)

    def test_ending_a_commitment_twice_is_one_ending(self):
        task = self.a_task()
        list_services.set_recurrence(task, Item.Recurrence.WEEKLY)
        list_services.set_recurrence(task, Item.Recurrence.NONE)
        list_services.set_recurrence(task, Item.Recurrence.NONE)

        self.assert_one(life_log.COMMITMENT_ENDED)

    # -- the day ---------------------------------------------------------

    def test_pinning_twice_is_one_choice(self):
        task = self.a_task()
        daily_services.pin_task(self.alice, MONDAY, task)
        daily_services.pin_task(self.alice, MONDAY, task)

        self.assert_one(life_log.FOCUS_PINNED)

    def test_repinning_after_a_release_is_a_second_choice(self):
        """The first exception, asserted so nobody closes it by mistake.
        Choosing something, putting it down and choosing it again is three
        decisions, and telling them apart is what the review block is for."""
        task = self.a_task()
        daily_services.pin_task(self.alice, MONDAY, task)
        daily_services.unpin_task(self.alice, MONDAY, task)
        daily_services.pin_task(self.alice, MONDAY, task)

        self.assertEqual(self.count(life_log.FOCUS_PINNED), 2)

    def test_unpinning_twice_is_one_release(self):
        task = self.a_task()
        daily_services.pin_task(self.alice, MONDAY, task)
        daily_services.unpin_task(self.alice, MONDAY, task)
        daily_services.unpin_task(self.alice, MONDAY, task)

        self.assert_one(life_log.FOCUS_RELEASED)

    def test_accepting_the_same_draft_twice_is_one_set_of_choices(self):
        """`accept_draft` pins each task through `pin_task`, so it inherits
        the guard -- asserted rather than assumed, because a second accept is
        exactly what a double-tap on a phone produces."""
        tasks = [self.a_task("One"), self.a_task("Two")]
        daily_services.accept_draft(self.alice, MONDAY, tasks)
        daily_services.accept_draft(self.alice, MONDAY, tasks)

        self.assertEqual(self.count(life_log.FOCUS_PINNED), 2)

    # -- the week --------------------------------------------------------

    def test_completing_a_review_twice_is_one_review(self):
        review_services.complete_review(self.alice, MONDAY)
        review_services.complete_review(self.alice, MONDAY)

        self.assert_one(life_log.WEEK_REVIEWED)

    def test_setting_the_same_intention_twice_is_one_intention(self):
        """C4, kept closed. This is the case that shipped broken."""
        review_services.set_intention(self.alice, MONDAY, "Finish the chapter")
        review_services.set_intention(self.alice, MONDAY, "Finish the chapter")

        self.assert_one(life_log.INTENTION_SET)

    def test_choosing_two_outcomes_is_two_choices(self):
        """The second exception. `choose_outcome` creates a row every time, so
        two calls leave two commitments standing -- and one event would
        under-count what the week actually holds."""
        review_services.choose_outcome(self.alice, MONDAY, text="Chapter three")
        review_services.choose_outcome(self.alice, MONDAY, text="Chapter three")

        self.assertEqual(self.count(life_log.OUTCOME_CHOSEN), 2)

    # -- the coverage itself ---------------------------------------------

    def test_every_life_event_has_a_test_here(self):
        """A list that only fails on removal never fails on omission.

        The next life event added to `EventType` gets an emitter, and without
        this it gets no idempotency case and nobody notices -- which is exactly
        how C1-C4 came to be four rather than one.
        """
        covered = {
            life_log.TASK_COMPLETED,
            life_log.TASK_REOPENED,
            life_log.TASK_ARCHIVED,
            life_log.TASK_LET_GO,
            life_log.APPOINTMENT_MADE,
            life_log.APPOINTMENT_CANCELLED,
            life_log.COMMITMENT_CHANGED,
            life_log.COMMITMENT_ENDED,
            life_log.FOCUS_PINNED,
            life_log.FOCUS_RELEASED,
            life_log.WEEK_REVIEWED,
            life_log.INTENTION_SET,
            life_log.OUTCOME_CHOSEN,
        }

        self.assertEqual(covered, set(life_log.LIFE_EVENTS))

    def test_the_exceptions_are_a_subset_of_what_is_covered(self):
        """So an exception cannot be declared for an event nobody emits, which
        would read as a considered decision about a case that does not
        exist."""
        self.assertLessEqual(
            set(A_SECOND_CALL_IS_A_SECOND_ACT), set(life_log.LIFE_EVENTS)
        )
