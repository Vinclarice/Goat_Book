"""Crane 3 slice 9 — is this week usual?

One figure is a fact; five is a shape. A finish rate of two in three means
something different after three weeks of three in three than it does after
three weeks of one in five, and a review that could only show the current
week would leave every reading of it to memory.

Deliberately small. `architecture-trajectory.md` §4 lists six analytical
questions -- streaks and recovery time, cadence drift, completion rate by
list, load against closure, time-to-close, abandonment -- and puts their
home in release F. This is not a first instalment of those. It is the same
two figures the week already shows, for the four weeks before it, out of
queries that already exist and with no new table behind them.

Two rules keep it honest. A week from before there was anything to record
reads as no data rather than as nought, which is the distinction this entire
release is about. And a week whose review was completed reports the figure
that review recorded, so the product never shows two different numbers for
one week on adjacent lines.

**"Before the account existed" turned out to be a question the schema
cannot answer.** `accounts.User` carries no creation timestamp -- no
`date_joined`, no `created_at` -- which these tests found by asserting
against one that was not there. The line drawn instead is the owner's first
trace: the earliest day they wrote, task they made, routine they kept or
thought they captured. It is the better question anyway. A week before
somebody started using Clarice has nothing to say; an empty week after they
did is a real fact about that week, and reads as nought.
"""
import json
from datetime import date, datetime, timedelta

from django.test import Client, TestCase
from django.utils import timezone

from accounts.models import User
from daily import services as daily_services
from lists import services as list_services
from lists.models import Item, List
from routines import services as routine_services
from routines.models import Routine


PASSWORD = "correct horse battery staple 47!"

JULY_27 = date(2026, 7, 27)


def instant_on(day, hour=9):
    return timezone.make_aware(
        datetime.combine(day, datetime.min.time()) + timedelta(hours=hour)
    )


class RecentWeeksTest(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(
            "alice", "alice@example.com", PASSWORD
        )
        self.alices_list = List.objects.create(owner=self.alice, title="Home")
        self.client = Client()
        self.client.force_login(self.alice)

    def weeks(self, week=JULY_27):
        response = self.client.get(f"/api/v1/review/{week}")
        self.assertEqual(response.status_code, 200)
        return response.json()["recent_weeks"]

    def pin_on(self, day, text, finished_on=None):
        task = list_services.create_item(self.alices_list, text)
        daily_services.pin_task(self.alice, day, task)
        if finished_on is not None:
            list_services.complete_item(task)
            Item.objects.filter(pk=task.pk).update(
                completed_at=instant_on(finished_on)
            )
            task.refresh_from_db()
        return task

    def using_clarice_since(self, day):
        """Give the account a trace on ``day``, which is what the trend
        reads to decide where its history begins."""
        daily_services.write_entry(self.alice, day, happenings="Started here")

    def test_it_covers_the_week_shown_and_the_four_before_it(self):
        weeks = self.weeks()

        self.assertEqual(
            [each["week_start"] for each in weeks],
            ["2026-06-29", "2026-07-06", "2026-07-13", "2026-07-20", "2026-07-27"],
        )
        self.assertEqual(
            [each["is_shown_week"] for each in weeks],
            [False, False, False, False, True],
        )

    def test_each_week_carries_its_own_finish_rate(self):
        self.using_clarice_since(JULY_27 - timedelta(days=60))
        self.pin_on(JULY_27, "Pay rent", finished_on=JULY_27 + timedelta(days=2))
        self.pin_on(JULY_27, "Call the bank")
        self.pin_on(JULY_27 - timedelta(days=7), "Last week's thing")

        weeks = {each["week_start"]: each for each in self.weeks()}

        self.assertEqual(
            (weeks["2026-07-27"]["planned_met"], weeks["2026-07-27"]["planned_total"]),
            (1, 2),
        )
        self.assertEqual(
            (weeks["2026-07-20"]["planned_met"], weeks["2026-07-20"]["planned_total"]),
            (0, 1),
        )

    def test_habits_are_summed_across_every_routine(self):
        self.using_clarice_since(JULY_27 - timedelta(days=60))
        routine = routine_services.create_routine(
            self.alice, title="Practice Spanish", target_quantity=5, unit="lessons"
        )
        Routine.objects.filter(pk=routine.pk).update(
            created_at=instant_on(JULY_27 - timedelta(days=60))
        )
        routine.refresh_from_db()
        for offset in range(3):
            routine_services.log_progress(
                self.alice, routine, JULY_27 + timedelta(days=offset), amount=5
            )

        weeks = {each["week_start"]: each for each in self.weeks()}

        self.assertEqual(
            (
                weeks["2026-07-27"]["habits_met"],
                weeks["2026-07-27"]["habits_expected"],
            ),
            (3, 7),
        )

    def test_a_week_from_before_there_was_anything_reads_as_no_data(self):
        """Not nought. A week before somebody was using Clarice is not a
        week in which they planned nothing -- telling those apart is what
        the whole release is for."""
        self.using_clarice_since(JULY_27 - timedelta(days=7))

        weeks = {each["week_start"]: each for each in self.weeks()}

        self.assertIsNone(weeks["2026-07-06"]["planned_total"])
        self.assertIsNone(weeks["2026-07-06"]["habits_expected"])
        # The week it began in counts, and an empty one after that reads as
        # nought rather than as nothing -- that emptiness is a real fact.
        self.assertEqual(weeks["2026-07-20"]["planned_total"], 0)

    def test_a_reviewed_week_reports_the_figure_that_review_recorded(self):
        """Otherwise the product would show two different numbers for one
        week, on adjacent lines of the same page."""
        self.using_clarice_since(JULY_27 - timedelta(days=60))
        finished = self.pin_on(
            JULY_27 - timedelta(days=7),
            "Pay rent",
            finished_on=JULY_27 - timedelta(days=5),
        )
        self.client.post(f"/api/v1/review/{JULY_27 - timedelta(days=7)}/complete")
        list_services.archive_item(finished)
        list_services.delete_archived_item(finished)

        weeks = {each["week_start"]: each for each in self.weeks()}

        self.assertEqual(
            (weeks["2026-07-20"]["planned_met"], weeks["2026-07-20"]["planned_total"]),
            (1, 1),
        )

    def test_a_brand_new_account_sees_no_data_rather_than_a_wall_of_noughts(self):
        """Isolation and the no-data rule in one: somebody who has just
        arrived has nothing behind them, and five rows of "0 of 0" would be
        a report about a history they do not have."""
        self.using_clarice_since(JULY_27 - timedelta(days=60))
        self.pin_on(JULY_27, "Pay rent", finished_on=JULY_27 + timedelta(days=1))
        bob = User.objects.create_user("bob", "bob@example.com", PASSWORD)
        self.client.force_login(bob)

        weeks = self.weeks()

        self.assertEqual([each["planned_total"] for each in weeks], [None] * 5)
        self.assertEqual([each["habits_met"] for each in weeks], [None] * 5)
