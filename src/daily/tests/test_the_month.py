"""A month you can look at, and land on a day from — S13's second require.

`/app/day/:date` has had no UI entry point at all: reaching a day twelve weeks
back meant clicking "the week before" twelve times, which
`commercial-blueprint.md` Part 2 names by that description. The day search
results already link to their own date; what has never existed is a way to
reach a date you have not searched for.

**A view over what is already there, not a new model.** Open tasks by due date
and days that were written in -- two queries over rows that exist. The calendar
that carries *events* is `clarice-v3-plan.md`'s later work and needs a model
this does not.

**Any day of the month addresses the same month**, the same courtesy
`intention_for` gives a week: a client that had to know which day a month
starts on would be a second definition of the calendar.

**Deferred by name rather than forgotten**: routines, which are measured over a
period rather than due on a date, and bills, which do not exist yet.
"""

from datetime import date, timedelta

from django.test import TestCase

from accounts.models import User
from daily import reads, services
from decimal import Decimal

from lists import services as list_services
from money import services as bills
from lists.models import List


AUGUST = date(2026, 8, 1)
MID_AUGUST = date(2026, 8, 14)


class TheMonthTest(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.bob = User.objects.create_user(
            "bob", "bob@example.com", "another password"
        )
        self.list_ = List.objects.create(owner=self.alice, title="Home")

    def due(self, on, text="Pay rent", owner=None):
        area = self.list_
        if owner is not None:
            area = List.objects.create(owner=owner, title="Theirs")
        return list_services.create_item(area, text, due_date=on)

    def month(self, day=MID_AUGUST, owner=None):
        return reads.month_for(owner or self.alice, day)

    def on(self, days, when):
        return next(day for day in days if day.date == when)

    def test_it_covers_the_whole_month_and_only_that_month(self):
        days = self.month()

        self.assertEqual(len(days), 31)
        self.assertEqual(days[0].date, AUGUST)
        self.assertEqual(days[-1].date, date(2026, 8, 31))

    def test_any_day_of_the_month_asks_about_the_same_month(self):
        """The courtesy `intention_for` gives a week. A client that had to
        know which day a month starts on would be a second definition of the
        calendar."""
        self.assertEqual(
            [day.date for day in self.month(AUGUST)],
            [day.date for day in self.month(date(2026, 8, 31))],
        )

    def test_a_day_says_how_much_is_due_on_it(self):
        self.due(MID_AUGUST)
        self.due(MID_AUGUST, text="Call the plumber")
        self.due(MID_AUGUST + timedelta(days=1), text="Elsewhere")

        days = self.month()

        self.assertEqual(self.on(days, MID_AUGUST).due, 2)

    def test_finished_work_does_not_still_count_as_due(self):
        """The agenda's own definition of open, not a second one: a calendar
        that kept counting completed tasks would show a month that never
        empties."""
        done = self.due(MID_AUGUST)
        list_services.complete_item(done)

        self.assertEqual(self.on(self.month(), MID_AUGUST).due, 0)

    def test_a_bill_counts_towards_the_day_it_is_due_on(self):
        """**The docstring above said bills "do not exist yet" while the count
        was already including them**, because a bill was a task with a due
        date and this query asks for tasks with due dates. Increment 4 of
        bill-as-a-model-plan.md would have quietly ended that inclusion, so it
        is made deliberate instead: a day with rent due is a day with
        something on it, which is decision 4 on the surface that shows
        thirty-one days at once."""
        bills.record(
            self.alice, payee="Landlord", amount=Decimal("1200.00"),
            due_date=MID_AUGUST,
        )

        self.assertEqual(self.on(self.month(), MID_AUGUST).due, 1)

    def test_a_settled_bill_does_not_still_count_as_due(self):
        """The `Bill` half of `finished work does not still count`. Read from
        `paid_at`, which needs no paragraph about ARCHIVED versus COMPLETED."""
        bill = bills.record(
            self.alice, payee="Landlord", amount=Decimal("1200.00"),
            due_date=MID_AUGUST,
        )
        bills.settle(bill)

        self.assertEqual(self.on(self.month(), MID_AUGUST).due, 0)

    def test_a_day_says_whether_anything_was_written_on_it(self):
        services.write_entry(self.alice, MID_AUGUST, happenings="Rained all day.")

        days = self.month()

        self.assertTrue(self.on(days, MID_AUGUST).written)
        self.assertFalse(self.on(days, AUGUST).written)

    def test_a_day_with_a_row_but_no_words_does_not_count_as_written(self):
        """A `DailyEntry` row exists as soon as anything is pinned, so an
        empty one is the ordinary state of a planned day -- the same call
        `written_in_week` makes for the review."""
        task = self.due(MID_AUGUST)
        services.pin_task(self.alice, MID_AUGUST, task)

        self.assertFalse(self.on(self.month(), MID_AUGUST).written)

    def test_one_person_never_sees_anothers_month(self):
        """The isolation test principles.md asks of every owner-scoped read."""
        self.due(MID_AUGUST, text="Bob's private task", owner=self.bob)
        services.write_entry(self.bob, MID_AUGUST, happenings="Bob's day.")

        days = self.month()

        self.assertEqual(self.on(days, MID_AUGUST).due, 0)
        self.assertFalse(self.on(days, MID_AUGUST).written)
