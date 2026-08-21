"""C1-C4 from `code-review-2026-08-21.md` -- the four ways the log could be
told something untrue, permanently.

All four write, or wrongly skip writing, rows in a table whose trigger refuses
`UPDATE` and `DELETE`. **Over-recording there cannot be undone; under-recording
can.** That asymmetry is the plan's own *"under-recording is the safe
direction"*, and it is why C1 -- the one that fabricates -- is first.

**The gate question was answered before any of this was written.** The backfill
had already run against production, so these were live rather than theoretical.
None of the four fired, and the reason is not that they were harmless: at the
time of the run production held no recurring completion, one focus row, no
orphaned focus and no intention. **The data was too thin to reach any of
them.** The next recurring task completed would have written a retirement into
the record of a habit being kept.

Kept apart from `test_life_log_backfill.py` deliberately: that file states what
the increment decided, and this one states what it got wrong. Folding these in
would let the corrections read as though they had been the design.
"""

import datetime
from io import StringIO

from django.core.management import call_command

from clarice.testing import CrossCoreTestCase
from daily import services as daily_services
from daily.models import DailyEntry, DailyFocus
from lists import services as list_services
from lists.models import Item
from mind.models import ActivityEvent, EventOrigin, EventType
from review import services as review_services


LONG_AGO = datetime.datetime(2026, 3, 2, 11, 0, tzinfo=datetime.timezone.utc)
LATER = datetime.datetime(2026, 3, 9, 11, 0, tzinfo=datetime.timezone.utc)
MONDAY = datetime.date(2026, 3, 2)
TUESDAY = datetime.date(2026, 3, 3)


class RepairTest(CrossCoreTestCase):
    def backfill(self, *args):
        out = StringIO()
        call_command("backfill_life_log", *args, stdout=out)
        return out.getvalue()

    def events(self, event_type=None, **filters):
        rows = ActivityEvent.objects.filter(**filters).order_by("occurred_at", "id")
        if event_type is not None:
            rows = rows.filter(event_type=event_type)
        return list(rows)

    def focus_on(self, day, task, *, selected_at, released_at=None):
        entry, _ = DailyEntry.objects.get_or_create(owner=self.alice, date=day)
        focus = DailyFocus.objects.create(
            owner=self.alice, entry=entry, task=task, task_text=task.text if task else ""
        )
        DailyFocus.objects.filter(pk=focus.pk).update(
            selected_at=selected_at, released_at=released_at
        )
        return focus


class C1RecurringArchiveTest(RepairTest):
    """A recurring task is archived the instant it is completed, to free its
    text for the next occurrence. `complete_item` refuses to log that -- four
    lines of comment say why: *"logging that would put a retirement in the
    record of a habit somebody is keeping."* The backfill read the two
    timestamps independently and wrote exactly that retirement."""

    def a_recurring_completion(self, *, when=LONG_AGO):
        task = list_services.create_item(
            self.area, "Water the plants", due_date=MONDAY
        )
        list_services.set_recurrence(task, Item.Recurrence.WEEKLY)
        # Completed before the log was listening, the way the mechanism leaves
        # it: both stamps set, to the same instant.
        Item.objects.filter(pk=task.pk).update(
            status=Item.Status.ARCHIVED, completed_at=when, archived_at=when
        )
        return task

    def test_a_kept_habit_is_not_reconstructed_as_a_retirement(self):
        self.a_recurring_completion()

        self.backfill()

        self.assertEqual(self.events(EventType.TASK_ARCHIVED), [])
        self.assertEqual(len(self.events(EventType.TASK_COMPLETED)), 1)

    def test_the_dry_run_does_not_promise_it_either(self):
        """The count is what somebody reads before deciding to write to a
        table that cannot be corrected, so it has to be the truth."""
        self.a_recurring_completion()

        self.assertNotIn("task_archived", self.backfill("--dry-run"))

    def test_a_recurring_task_that_really_ended_still_gets_its_archive(self):
        """The narrow repair, not a blanket exemption: archived later than it
        was completed is somebody retiring the undertaking, which is a
        decision and belongs in the record."""
        task = self.a_recurring_completion()
        Item.objects.filter(pk=task.pk).update(archived_at=LATER)

        self.backfill()

        self.assertEqual(
            [e.occurred_at for e in self.events(EventType.TASK_ARCHIVED)], [LATER]
        )

    def test_a_one_off_task_that_was_archived_is_untouched_by_the_repair(self):
        task = list_services.create_item(self.area, "Old paperwork")
        Item.objects.filter(pk=task.pk).update(
            status=Item.Status.ARCHIVED, completed_at=LONG_AGO, archived_at=LONG_AGO
        )

        self.backfill()

        self.assertEqual(len(self.events(EventType.TASK_ARCHIVED)), 1)


class C2FocusGrainTest(RepairTest):
    """`DailyFocus` is one row per task **per day** --
    `unique_daily_focus_per_entry_task` is on `(entry, task)`, and the
    constraint was there to be read. Keying idempotency on `(task, type)`
    collapsed every day a task was ever chosen into one."""

    def test_the_same_task_chosen_on_two_days_is_two_decisions(self):
        task = list_services.create_item(self.area, "Write the chapter")
        self.focus_on(MONDAY, task, selected_at=LONG_AGO)
        self.focus_on(TUESDAY, task, selected_at=LONG_AGO + datetime.timedelta(days=1))

        self.backfill()

        self.assertEqual(len(self.events(EventType.FOCUS_PINNED)), 2)

    def test_one_live_pin_does_not_erase_every_earlier_one(self):
        """The silent half. A task pinned once since increment 2 shipped has a
        live event, and the old key made that event stand for every pin of
        that task there had ever been."""
        task = list_services.create_item(self.area, "Write the chapter")
        self.focus_on(MONDAY, task, selected_at=LONG_AGO)
        daily_services.pin_task(self.alice, TUESDAY, task)

        self.backfill()

        events = self.events(EventType.FOCUS_PINNED)
        self.assertEqual(len(events), 2)
        self.assertEqual(
            {e.origin for e in events},
            {EventOrigin.RECORDED, EventOrigin.RECONSTRUCTED},
        )

    def test_two_days_of_releases_are_two_releases(self):
        task = list_services.create_item(self.area, "Write the chapter")
        self.focus_on(MONDAY, task, selected_at=LONG_AGO, released_at=LONG_AGO)
        self.focus_on(
            TUESDAY,
            task,
            selected_at=LONG_AGO + datetime.timedelta(days=1),
            released_at=LONG_AGO + datetime.timedelta(days=1, hours=2),
        )

        self.backfill()

        self.assertEqual(len(self.events(EventType.FOCUS_RELEASED)), 2)

    def test_it_is_still_idempotent_at_the_finer_grain(self):
        """The property the wrong key was buying, kept while the key is
        corrected."""
        task = list_services.create_item(self.area, "Write the chapter")
        self.focus_on(MONDAY, task, selected_at=LONG_AGO)
        self.focus_on(TUESDAY, task, selected_at=LONG_AGO + datetime.timedelta(days=1))

        self.backfill()
        self.backfill()

        self.assertEqual(len(self.events(EventType.FOCUS_PINNED)), 2)


class C3OrphanedFocusTest(RepairTest):
    """Hard-deleting a pinned task sets `DailyFocus.task` to NULL. The dedup
    set was built with `task__isnull=False`, so `(None, FOCUS_PINNED)` could
    never be in it and the same orphaned row re-emitted **on every run** --
    the one shape the loop's own comment says to expect."""

    def an_orphaned_focus(self):
        task = list_services.create_item(self.area, "Vanished")
        focus = self.focus_on(MONDAY, task, selected_at=LONG_AGO, released_at=LATER)
        Item.objects.filter(pk=task.pk).delete()
        focus.refresh_from_db()
        return focus

    def test_a_focus_whose_task_is_gone_is_reconstructed_once(self):
        self.an_orphaned_focus()

        self.backfill()

        self.assertEqual(len(self.events(EventType.FOCUS_PINNED)), 1)
        self.assertEqual(len(self.events(EventType.FOCUS_RELEASED)), 1)

    def test_and_not_again_on_the_next_run(self):
        """Duplicates here are permanent, which is what makes this the worst
        of the four rather than the smallest."""
        self.an_orphaned_focus()

        self.backfill()
        self.backfill()
        self.backfill()

        self.assertEqual(len(self.events(EventType.FOCUS_PINNED)), 1)

    def test_two_orphans_on_the_same_day_stay_two(self):
        """`unique_daily_focus_per_entry_task` permits them: ordinary SQL NULL
        semantics keep null tasks from colliding, which the model says out
        loud. So the repaired key must not collapse them either."""
        for text in ("One", "Two"):
            task = list_services.create_item(self.area, text)
            self.focus_on(MONDAY, task, selected_at=LONG_AGO)
            Item.objects.filter(pk=task.pk).delete()

        self.backfill()
        self.backfill()

        self.assertEqual(len(self.events(EventType.FOCUS_PINNED)), 2)


class C4IntentionNoOpTest(RepairTest):
    """Every other emitter in increment 2 guards on a state change.
    `set_intention` recorded unconditionally, on an endpoint whose own
    docstring promises *"sending it twice leaves the same state."* Every blur
    re-save, retry and double-click was a permanent duplicate."""

    def set_it(self, text):
        return review_services.set_intention(self.alice, MONDAY, text)

    def test_saying_the_same_thing_twice_is_one_decision(self):
        self.set_it("Finish the chapter")
        self.set_it("Finish the chapter")

        self.assertEqual(len(self.events(EventType.INTENTION_SET)), 1)

    def test_changing_your_mind_is_a_second_decision(self):
        self.set_it("Finish the chapter")
        self.set_it("Start the next one")

        self.assertEqual(len(self.events(EventType.INTENTION_SET)), 2)

    def test_clearing_it_is_still_something_that_happened(self):
        """The behaviour the inline comment defends, and the reason the row is
        kept at all: *"I set none this week"* and *"I never opened it"* are
        different facts, and only one says the practice lapsed."""
        self.set_it("Finish the chapter")
        self.set_it("")

        self.assertEqual(len(self.events(EventType.INTENTION_SET)), 2)

    def test_clearing_an_already_empty_intention_is_not_a_second_clearing(self):
        self.set_it("")
        self.set_it("")

        self.assertEqual(len(self.events(EventType.INTENTION_SET)), 1)

    def test_the_first_setting_is_recorded_however_empty(self):
        self.set_it("")

        self.assertEqual(len(self.events(EventType.INTENTION_SET)), 1)
