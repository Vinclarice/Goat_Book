"""The next occurrence is never born late.

`_advance_due_date` computed the successor from the *previous due date* and
stopped after one step. A monthly commitment due July 4 and completed August 10
therefore spawned its replacement due **August 4** — already six days overdue at
the instant it was created, on a task the person had just finished on time as
far as they were concerned.

`roadmap.md` has carried this since the merger planning as "one defect to fix on
the way in rather than port". The way in happened and it was not fixed.

**What this implements, and what it does not.** `design-concept.md` specifies
two recurrence modes and calls the distinction load-bearing: *anchored* keeps a
calendar rule regardless of when the last one was completed; *floating* counts
forward from the actual completion. Clarice has one cadence field and no way to
say which a commitment is.

So this fixes the defect without silently choosing a mode for everything. The
schedule advances from where it was, repeatedly, until it reaches the future —
anchored, with missed periods skipped rather than replayed. A commitment on the
4th stays on the 4th. For a genuinely floating commitment like a furnace filter
that is a few days early rather than wrong, which is the cheaper error;
implementing floating globally would instead drift "bins every Monday" off
Monday forever, one day per late completion.
"""

import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.test import TestCase

from accounts.models import User
from lists import services
from lists.models import Item, List

# Completed on August 10th, five weeks after a July 4th due date.
COMPLETED_AT = datetime.datetime(2026, 8, 10, 14, 0, tzinfo=ZoneInfo("UTC"))
TODAY = datetime.date(2026, 8, 10)


class ASeriesNeverSpawnsOverdueTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("alice", "a@example.com", "pw")
        self.area = List.objects.create(owner=self.user, title="House")

    def complete(self, *, due, cadence):
        task = services.create_item(self.area, "Change the furnace filter", due_date=due)
        services.set_recurrence(task, cadence)
        with patch("django.utils.timezone.now", return_value=COMPLETED_AT):
            return services.complete_item(task)._spawned

    def test_a_late_completion_does_not_spawn_an_overdue_successor(self):
        """The defect itself. July 4 + one month is August 4, which is behind
        the day it was created."""
        spawned = self.complete(due=datetime.date(2026, 7, 4), cadence=Item.Recurrence.MONTHLY)

        self.assertGreater(spawned.due_date, TODAY)

    def test_the_successor_keeps_the_day_of_the_month(self):
        """Skipped, not restarted. Somebody who changes a filter on the 4th of
        the month is still on the 4th afterwards, whatever month it took."""
        spawned = self.complete(due=datetime.date(2026, 7, 4), cadence=Item.Recurrence.MONTHLY)

        self.assertEqual(spawned.due_date, datetime.date(2026, 9, 4))

    def test_a_very_late_weekly_commitment_skips_every_missed_week(self):
        """Not one week forward and still overdue, and not one task per missed
        week either — the missed occurrences did not happen and inventing them
        would be a fabricated record."""
        spawned = self.complete(due=datetime.date(2026, 6, 1), cadence=Item.Recurrence.WEEKLY)

        self.assertEqual(spawned.due_date, datetime.date(2026, 8, 17))
        self.assertEqual(spawned.due_date.weekday(), 0)  # still a Monday

    def test_completing_on_time_is_unchanged(self):
        """The ordinary case, and the one that must not move: due today, so the
        next is exactly one interval out."""
        spawned = self.complete(due=TODAY, cadence=Item.Recurrence.WEEKLY)

        self.assertEqual(spawned.due_date, datetime.date(2026, 8, 17))

    def test_completing_early_still_advances_from_the_schedule(self):
        """Finishing on the 10th something due on the 20th does not pull the
        whole series forward — the next one is the slot after the one just
        satisfied."""
        spawned = self.complete(due=datetime.date(2026, 8, 20), cadence=Item.Recurrence.WEEKLY)

        self.assertEqual(spawned.due_date, datetime.date(2026, 8, 27))

    def test_month_end_clamping_still_applies(self):
        """A commitment on the 31st in a month that has none lands on the last
        day, which is the task core's existing documented behaviour."""
        spawned = self.complete(due=datetime.date(2026, 1, 31), cadence=Item.Recurrence.MONTHLY)

        self.assertEqual(spawned.due_date, datetime.date(2026, 8, 31))

    def test_a_series_with_no_due_date_still_starts_from_today(self):
        spawned = self.complete(due=None, cadence=Item.Recurrence.DAILY)

        self.assertEqual(spawned.due_date, datetime.date(2026, 8, 11))

    def test_the_slot_the_completion_lands_on_is_not_respawned(self):
        """**A regression guard: the behaviour already existed**, said plainly
        because a test passing on its first run is otherwise a smell. What is
        new is that this boundary is pinned deliberately rather than by
        coincidence.

        A daily commitment due yesterday, completed today, advances to
        *tomorrow*. Today's slot was satisfied by the completion that spawned
        this, so returning it would hand somebody a task due the day they did
        it -- bins done this morning, bins due this morning.

        `test_a_very_late_weekly_commitment_skips_every_missed_week` above
        depends on the same rule and does fail under `>=`, spawning August 10
        rather than August 17. But its subject is skipping missed weeks and it
        pins this only in passing, which is how `_advance_due_date` came to
        promise *"never already in the past"* while implementing something
        stricter. The docstring there now says which, and this says it in a
        test.
        """
        spawned = self.complete(
            due=datetime.date(2026, 8, 9), cadence=Item.Recurrence.DAILY
        )

        self.assertEqual(spawned.due_date, datetime.date(2026, 8, 11))
