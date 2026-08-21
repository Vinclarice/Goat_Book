"""Giving the log the history the task core already held.

`temporal-substrate-plan.md` Track A increment 3, and the answer to its **D2**.

**How far back: as far as the data goes, and there is no date cutoff.** The
limit is not age, it is whether a timestamp exists -- a horizon would throw
away real records to satisfy a number nobody chose. So the rule is the
increment's own and no more than it: **nothing invented. No recorded time, no
event.**

**How a reconstruction is marked: a column, `ActivityEvent.origin`**, copying
`Facet.origin`'s split rather than a payload key. Every read over the log will
want to label or exclude these, and a JSONB lookup with no index is not what
*"a reading can tell a record from a re-presentation"* should cost. The log is
append-only, so the cheap choice here would be the unfixable one.

**What cannot come back, and is therefore not invented:**

- `TASK_REOPENED` -- reopening clears `completed_at`, which erases the only
  evidence there was.
- `COMMITMENT_CHANGED` -- nothing records when a task started repeating.
- Every rewrite of an intention but the first. `WeeklyIntention` is one row per
  week edited in place, so `created_at` is when an intention was first set and
  the rewrites left no trace.
- Any release before the last, for the same reason: repinning clears
  `released_at`.

**Under-recording is the safe direction**, and that is the whole shape of this
increment. A log that says less than happened can be added to; one that says
more cannot be corrected.

**A management command rather than a data migration**, departing from this
repository's habit on purpose. The backfills in `lists/migrations` fix columns
and can be fixed again; this one inserts into a table whose trigger refuses
`UPDATE` and `DELETE`, so a wrong run is permanent. `--dry-run` is the
read-only diagnosis that has to come first.
"""

import datetime
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from daily import services as daily_services
from daily.models import DailyEntry, DailyFocus
from lists import services as list_services
from lists.models import Item, List
from mind.models import ActivityEvent, EventOrigin, EventType
from review.models import WeeklyIntention, WeeklyOutcome, WeeklyReview


LONG_AGO = datetime.datetime(2026, 3, 2, 11, 0, tzinfo=datetime.timezone.utc)
LATER = datetime.datetime(2026, 3, 5, 16, 0, tzinfo=datetime.timezone.utc)
DAY = datetime.date(2026, 3, 2)
ITS_MONDAY = datetime.date(2026, 3, 2)


class BackfillTest(TestCase):
    def setUp(self):
        self.alice = get_user_model().objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.area = List.objects.create(owner=self.alice, title="Home")

    # -- helpers ---------------------------------------------------------

    def backfill(self, *args):
        out = StringIO()
        call_command("backfill_life_log", *args, stdout=out)
        return out.getvalue()

    def a_task(self, text="Call the plumber"):
        return list_services.create_item(self.area, text)

    def completed_before_the_log(self, text="Call the plumber", when=LONG_AGO):
        """A task finished when nothing was listening.

        `update` rather than the service, deliberately: the service writes a
        live event now, and the situation this whole increment exists for is
        the one where it did not.
        """
        task = self.a_task(text)
        Item.objects.filter(pk=task.pk).update(
            status=Item.Status.COMPLETED, completed_at=when
        )
        return task

    def pinned_before_the_log(self, task, *, selected_at, released_at=None):
        entry, _ = DailyEntry.objects.get_or_create(owner=self.alice, date=DAY)
        focus = DailyFocus.objects.create(
            owner=self.alice, entry=entry, task=task, task_text=task.text
        )
        DailyFocus.objects.filter(pk=focus.pk).update(
            selected_at=selected_at, released_at=released_at
        )
        return focus

    def events(self, event_type=None):
        rows = ActivityEvent.objects.order_by("occurred_at", "id")
        if event_type is not None:
            rows = rows.filter(event_type=event_type)
        return list(rows)

    def reconstructed(self):
        return [
            (e.event_type, e.occurred_at)
            for e in self.events()
            if e.origin == EventOrigin.RECONSTRUCTED
        ]

    # -- what comes back -------------------------------------------------

    def test_a_completion_from_before_the_log_comes_back(self):
        task = self.completed_before_the_log()

        self.backfill()

        event = self.events(EventType.TASK_COMPLETED)[0]
        self.assertEqual(event.task_id, task.pk)
        self.assertEqual(event.occurred_at, LONG_AGO)

    def test_a_reconstruction_says_that_it_is_one(self):
        """The half of D2 that matters most. A re-presentation that looks like
        a record makes every later reading about *when* untrustworthy, and the
        log cannot be corrected afterwards."""
        self.completed_before_the_log()

        self.backfill()

        self.assertEqual(
            self.events(EventType.TASK_COMPLETED)[0].origin,
            EventOrigin.RECONSTRUCTED,
        )

    def test_something_the_log_actually_witnessed_stays_a_record(self):
        list_services.complete_item(self.a_task("Book the dentist"))

        self.assertEqual(
            self.events(EventType.TASK_COMPLETED)[0].origin, EventOrigin.RECORDED
        )

    def test_an_archive_comes_back_at_the_time_it_was_archived(self):
        task = self.a_task()
        Item.objects.filter(pk=task.pk).update(
            status=Item.Status.ARCHIVED, archived_at=LONG_AGO
        )

        self.backfill()

        self.assertEqual(
            self.events(EventType.TASK_ARCHIVED)[0].occurred_at, LONG_AGO
        )

    def test_a_pin_and_its_release_both_come_back_in_order(self):
        self.pinned_before_the_log(
            self.a_task(), selected_at=LONG_AGO, released_at=LATER
        )

        self.backfill()

        self.assertEqual(
            self.reconstructed(),
            [(EventType.FOCUS_PINNED, LONG_AGO), (EventType.FOCUS_RELEASED, LATER)],
        )

    def test_a_pin_never_released_reconstructs_no_release(self):
        self.pinned_before_the_log(self.a_task(), selected_at=LONG_AGO)

        self.backfill()

        self.assertEqual(
            self.reconstructed(), [(EventType.FOCUS_PINNED, LONG_AGO)]
        )

    def test_a_reconstructed_pin_names_the_day_it_was_about(self):
        """The subject columns are the point of increment 1, and a backfill
        that filled only the timestamp would leave `around()` nothing to join
        on."""
        focus = self.pinned_before_the_log(self.a_task(), selected_at=LONG_AGO)

        self.backfill()

        event = self.events(EventType.FOCUS_PINNED)[0]
        self.assertEqual(event.entry_id, focus.entry_id)
        self.assertEqual(event.task_id, focus.task_id)

    def test_a_reviewed_week_comes_back_with_its_monday(self):
        WeeklyReview.objects.create(
            owner=self.alice, week_start=ITS_MONDAY, completed_at=LONG_AGO
        )

        self.backfill()

        event = self.events(EventType.WEEK_REVIEWED)[0]
        self.assertEqual(event.occurred_at, LONG_AGO)
        self.assertEqual(event.payload, {"week_start": ITS_MONDAY.isoformat()})

    def test_a_week_opened_but_never_reviewed_comes_back_as_nothing(self):
        """`completed_at` is null for a review somebody wrote in and did not
        finish, and opening the page is not a decision."""
        WeeklyReview.objects.create(
            owner=self.alice, week_start=ITS_MONDAY, reflections="Half a thought"
        )

        self.backfill()

        self.assertEqual(self.events(EventType.WEEK_REVIEWED), [])

    def test_an_outcome_comes_back_at_the_time_it_was_chosen(self):
        outcome = WeeklyOutcome.objects.create(
            owner=self.alice, week_start=ITS_MONDAY, text="Chapter three", position=0
        )
        WeeklyOutcome.objects.filter(pk=outcome.pk).update(created_at=LONG_AGO)

        self.backfill()

        self.assertEqual(
            self.events(EventType.OUTCOME_CHOSEN)[0].occurred_at, LONG_AGO
        )

    def test_an_intention_comes_back_once_however_often_it_was_rewritten(self):
        """One row per week, edited in place. `created_at` is when an intention
        was first set; every rewrite after it left no trace. Saying it once is
        honest, and guessing at the rest is not."""
        intention = WeeklyIntention.objects.create(
            owner=self.alice, week_start=ITS_MONDAY, text="Finish the chapter"
        )
        WeeklyIntention.objects.filter(pk=intention.pk).update(
            created_at=LONG_AGO, updated_at=LATER
        )

        self.backfill()

        self.assertEqual(
            [e.occurred_at for e in self.events(EventType.INTENTION_SET)], [LONG_AGO]
        )

    # -- what is never invented ------------------------------------------

    def test_a_task_never_completed_reconstructs_nothing(self):
        self.a_task()

        self.backfill()

        self.assertEqual(self.events(), [])

    def test_a_reopening_is_never_reconstructed(self):
        """Reopening clears `completed_at`, which erases the only evidence
        there was. Nothing to read means nothing to write."""
        task = self.completed_before_the_log()
        Item.objects.filter(pk=task.pk).update(
            status=Item.Status.ACTIVE, completed_at=None
        )

        self.backfill()

        self.assertEqual(self.events(), [])

    def test_a_change_of_commitment_is_never_reconstructed(self):
        """Nothing records when a task started repeating, so nothing may say
        it did."""
        list_services.set_recurrence(self.a_task(), Item.Recurrence.WEEKLY)

        self.backfill()

        self.assertEqual(self.reconstructed(), [])

    # -- running it twice ------------------------------------------------

    def test_running_it_twice_does_not_say_everything_twice(self):
        """The property that matters most, because the log cannot be cleaned up
        afterwards -- the trigger refuses both `UPDATE` and `DELETE`."""
        self.completed_before_the_log()

        self.backfill()
        self.backfill()

        self.assertEqual(len(self.events(EventType.TASK_COMPLETED)), 1)

    def test_it_leaves_alone_what_the_log_already_witnessed(self):
        """A task completed since increment 2 already has its event, and a
        reconstruction beside it would be one fact twice with two different
        provenances."""
        list_services.complete_item(self.a_task("Book the dentist"))

        self.backfill()

        events = self.events(EventType.TASK_COMPLETED)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].origin, EventOrigin.RECORDED)

    # -- looking before leaping ------------------------------------------

    def test_a_dry_run_writes_nothing_and_says_what_it_would_have_done(self):
        """An append-only insert is not something to find out about
        afterwards."""
        self.completed_before_the_log()

        output = self.backfill("--dry-run")

        self.assertEqual(self.events(), [])
        self.assertIn("task_completed", output)
        self.assertIn("1", output)

    def test_it_does_not_reach_into_another_persons_history(self):
        bob = get_user_model().objects.create_user("bob", "bob@example.com", "pw")
        their_area = List.objects.create(owner=bob, title="Theirs")
        their_task = list_services.create_item(their_area, "Their task")
        Item.objects.filter(pk=their_task.pk).update(
            status=Item.Status.COMPLETED, completed_at=LONG_AGO
        )

        self.backfill("--owner", "alice")

        self.assertEqual(self.events(), [])
