"""Crane 3 slice 2 — what you planned, and what came of it.

The one number `daily-operating-system-vision.md` insists on getting right:
"60% finish rate" must mean *completed planned commitments / planned
commitments*, and the denominator "cannot be reconstructed after the fact
from a mutable due date". So it is not every task that was due, and it is
not every task in the backlog. It is the pins somebody deliberately put on a
day.

Which makes `DailyFocus.released_at` load-bearing here rather than
decorative. Deciding on Wednesday that something is not for this week is a
decommitment; never getting to it is a failure to finish. A denominator that
counted both would report a number that looks authoritative and is not --
that is the entire reason unpinning releases instead of deleting.
"""
from datetime import date, datetime, timedelta

from django.test import Client, TestCase
from django.utils import timezone

from accounts.models import User
from daily import services as daily_services
from lists import services as list_services
from lists.models import Item, List


PASSWORD = "correct horse battery staple 47!"

# A Monday, and days inside the week it starts.
JULY_27 = date(2026, 7, 27)
JULY_29 = date(2026, 7, 29)
AUGUST_2 = date(2026, 8, 2)
# The two Mondays before JULY_27, for building a capacity history.
JULY_20 = date(2026, 7, 20)
JULY_13 = date(2026, 7, 13)


def instant_on(day, hour=9):
    return timezone.make_aware(
        datetime.combine(day, datetime.min.time()) + timedelta(hours=hour)
    )


class PlannedWeekTest(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(
            "alice", "alice@example.com", PASSWORD
        )
        self.bob = User.objects.create_user("bob", "bob@example.com", PASSWORD)
        self.alices_list = List.objects.create(owner=self.alice, title="Home")
        self.bobs_list = List.objects.create(owner=self.bob, title="Home")
        self.client = Client()
        self.client.force_login(self.alice)

    def pin(self, owner, day, text, for_list=None):
        task = list_services.create_item(for_list or self.alices_list, text)
        daily_services.pin_task(owner, day, task)
        return task

    def complete_on(self, task, day):
        list_services.complete_item(task)
        Item.objects.filter(pk=task.pk).update(completed_at=instant_on(day))
        task.refresh_from_db()
        return task

    def unpin_on(self, owner, day, task, released_on):
        """Unpin, then move the release to the day being described.

        The service stamps the real clock, which is the correct thing for it
        to do and the wrong thing for a test about a week in the past to
        depend on.
        """
        daily_services.unpin_task(owner, day, task)
        task.refresh_from_db()
        owner.daily_focus.filter(task=task).update(
            released_at=instant_on(released_on)
        )

    def planned(self, week=JULY_27):
        response = self.client.get(f"/api/v1/review/{week}")
        self.assertEqual(response.status_code, 200)
        return response.json()["planned"]

    def _week_that_finished(self, monday, count):
        """A prior week with a plan in it, so capacity has evidence."""
        for index in range(count):
            task = self.pin(self.alice, monday, f"Done {monday} {index}")
            self.complete_on(task, monday + timedelta(days=1))

    def test_the_week_says_whether_it_held_more_than_his_weeks_hold(self):
        """S3's last clause: the review can separate *over-committed* from
        *under-delivered*.

        Finishing four of nine is honest as a rate, and by itself the two
        readings of that number are indistinguishable -- which is the exact
        confusion this story exists to resolve. `typical_week_for` was already
        computed on every review and pointed **forwards** at the draft; this is
        the same argument pointed backwards at the week being reviewed.

        It is strictly *before* the reviewed week, so a week is never its own
        evidence -- the same rule `typical_day_for` states for the day."""
        self._week_that_finished(JULY_20, 2)
        self._week_that_finished(JULY_13, 2)
        for index in range(5):
            self.pin(self.alice, JULY_27, f"Ambitious {index}")

        planned = self.planned()

        self.assertEqual(planned["typical"], 2)
        self.assertIs(planned["over_committed"], True)

    def test_a_week_within_its_usual_reach_is_not_called_over_committed(self):
        self._week_that_finished(JULY_20, 3)
        self._week_that_finished(JULY_13, 3)
        self.pin(self.alice, JULY_27, "One thing")

        planned = self.planned()

        self.assertEqual(planned["typical"], 3)
        self.assertIs(planned["over_committed"], False)

    def test_without_enough_history_capacity_is_absent_rather_than_zero(self):
        """The null-not-zero discipline, carried up from the read. "No evidence
        yet" and "you committed to more than you can hold" call for opposite
        responses, and a zero here would say the second while meaning the
        first."""
        for index in range(5):
            self.pin(self.alice, JULY_27, f"Ambitious {index}")

        planned = self.planned()

        self.assertIsNone(planned["typical"])
        self.assertIs(planned["over_committed"], False)

    def test_a_planned_commitment_that_was_finished_counts_as_met(self):
        task = self.pin(self.alice, JULY_27, "Pay rent")
        self.complete_on(task, JULY_29)

        planned = self.planned()

        self.assertEqual((planned["met"], planned["total"]), (1, 1))
        self.assertEqual([each["text"] for each in planned["met_tasks"]], ["Pay rent"])

    def test_unpinning_leaves_the_denominator_rather_than_failing_it(self):
        """Slice 2's acceptance condition, in one test.

        Two pinned, one finished, one deliberately taken off: the week reads
        one of one, not one of two and not two of two.
        """
        finished = self.pin(self.alice, JULY_27, "Pay rent")
        self.complete_on(finished, JULY_29)
        dropped = self.pin(self.alice, JULY_27, "Reorganise the shed")
        self.unpin_on(self.alice, JULY_27, dropped, JULY_29)

        planned = self.planned()

        self.assertEqual((planned["met"], planned["total"]), (1, 1))
        self.assertEqual(
            [each["text"] for each in planned["set_aside"]],
            ["Reorganise the shed"],
        )
        self.assertEqual(planned["unfinished"], [])

    def test_work_finished_after_the_week_still_reads_unfinished(self):
        """At the week's end it was unfinished, and that is what the week
        says. Otherwise a past week's figure would keep moving."""
        task = self.pin(self.alice, JULY_27, "Pay rent")
        self.complete_on(task, AUGUST_2 + timedelta(days=2))

        planned = self.planned()

        self.assertEqual((planned["met"], planned["total"]), (0, 1))
        self.assertEqual(
            [each["text"] for each in planned["unfinished"]], ["Pay rent"]
        )

    def test_a_pin_released_after_the_week_was_still_standing_in_it(self):
        """Released is judged at the week's end, not at read time. A pin
        dropped three weeks later was a commitment that week, and a report
        that changed its mind about that would be unstable by design."""
        task = self.pin(self.alice, JULY_27, "Pay rent")
        self.unpin_on(self.alice, JULY_27, task, AUGUST_2 + timedelta(days=14))

        planned = self.planned()

        self.assertEqual((planned["met"], planned["total"]), (0, 1))
        self.assertEqual(planned["set_aside"], [])

    def test_an_unfinished_commitment_says_how_long_it_has_been_waiting(self):
        """Age and due context, in the wording Crane 2 slice 5 settled --
        the review reuses that definition rather than inventing a second
        one."""
        task = self.pin(self.alice, JULY_27, "Pay rent")
        list_services.set_due_date(task, JULY_29)
        Item.objects.filter(pk=task.pk).update(
            created_at=instant_on(JULY_27 - timedelta(days=30))
        )

        [unfinished] = self.planned()["unfinished"]

        self.assertEqual(unfinished["due_date"], "2026-07-29")
        self.assertEqual(
            unfinished["age_in_days"],
            (timezone.localdate() - (JULY_27 - timedelta(days=30))).days,
        )

    def test_a_commitment_planned_in_another_week_is_not_in_this_one(self):
        task = self.pin(self.alice, JULY_27 - timedelta(days=7), "Last week")
        self.complete_on(task, JULY_27 - timedelta(days=5))

        planned = self.planned()

        self.assertEqual((planned["met"], planned["total"]), (0, 0))

    def test_another_accounts_plan_never_appears(self):
        task = self.pin(self.bob, JULY_27, "Bob's rent", for_list=self.bobs_list)
        self.complete_on(task, JULY_29)

        planned = self.planned()

        self.assertEqual((planned["met"], planned["total"]), (0, 0))
        self.assertEqual(planned["met_tasks"], [])

    def test_a_week_nobody_planned_reports_nothing_rather_than_zero_of_zero(self):
        """The distinction the whole release is about: a week with no plan
        is not a week that failed one."""
        planned = self.planned()

        self.assertEqual((planned["met"], planned["total"]), (0, 0))
        self.assertEqual(planned["unfinished"], [])
        self.assertEqual(planned["set_aside"], [])
