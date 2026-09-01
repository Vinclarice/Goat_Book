"""Crane 1 slice 2 — the day shows your work without owning a copy of it.

Action Items are the agenda's own query, read at display time. The Daily
Entry stores nothing about them: no checklist row, no cached status, no
task ids. That is the whole point of the slice, and it is why the
acceptance test here completes a task through `lists.services` -- the
ordinary path, nothing to do with the daily domain -- and then asks the day
what it shows.

Which buckets belong to a day is the daily domain's decision; what
"overdue" *means* stays in lists.agenda, which is the one authority for it.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase

from accounts.models import User
from daily import reads
from lists import bills, services as list_services
from lists.models import Item, List


AUGUST_3 = date(2026, 8, 3)


class ActionItemsTest(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.bob = User.objects.create_user(
            "bob", "bob@example.com", "another password"
        )
        self.list_ = List.objects.create(owner=self.alice, title="Home")

    def task(self, text, due_date=None, for_list=None):
        return list_services.create_item(
            for_list or self.list_, text, due_date=due_date
        )

    def texts(self, day=AUGUST_3):
        return [item.text for item in reads.action_items_for(self.alice, day)]

    def test_a_task_due_today_is_an_action_item(self):
        self.task("Pay rent", due_date=AUGUST_3)

        self.assertEqual(self.texts(), ["Pay rent"])

    def test_an_overdue_task_is_still_todays_work(self):
        self.task("Call the plumber", due_date=AUGUST_3 - timedelta(days=3))

        self.assertEqual(self.texts(), ["Call the plumber"])

    def test_overdue_work_comes_before_what_is_merely_due(self):
        self.task("Due today", due_date=AUGUST_3)
        self.task("Late", due_date=AUGUST_3 - timedelta(days=1))

        self.assertEqual(self.texts(), ["Late", "Due today"])

    def test_work_due_later_is_not_todays_problem(self):
        self.task("Next week sometime", due_date=AUGUST_3 + timedelta(days=3))
        self.task("No date at all")

        self.assertEqual(self.texts(), [])

    def test_completing_a_task_the_ordinary_way_takes_it_off_the_day(self):
        """Slice 2's acceptance condition.

        Completed through lists.services, which knows nothing about the
        daily domain. The day reflects it because both read the same row --
        if the Daily Entry owned a copy, this is the test that would fail.
        """
        task = self.task("Pay rent", due_date=AUGUST_3)
        self.assertEqual(self.texts(), ["Pay rent"])

        list_services.complete_item(task)

        self.assertEqual(self.texts(), [])

    def test_one_person_never_sees_anothers_work(self):
        bobs_list = List.objects.create(owner=self.bob, title="Bob's home")
        self.task("Bob's private task", due_date=AUGUST_3, for_list=bobs_list)

        self.assertEqual(self.texts(), [])

    def test_the_day_asked_about_decides_what_counts_as_overdue(self):
        """The clock is injected, not read in here -- so a page for the 1st
        and a page for the 5th disagree about the same task, correctly."""
        self.task("Due the 3rd", due_date=AUGUST_3)

        self.assertEqual(self.texts(day=AUGUST_3 - timedelta(days=2)), [])
        self.assertEqual(self.texts(day=AUGUST_3 + timedelta(days=2)), ["Due the 3rd"])


class BillsLeaveTheActionListAndStayOnTheDayTest(TestCase):
    """`bill-as-a-model-plan.md` decision 4, on the second daily surface.

    A bill was an action item because a bill was an `Item`. It stops being
    one, so it leaves this list -- and it arrives in the day payload's own
    `bills` array instead, because the decision is that bills stay on the
    surfaces where paying is a real thing to do on a day, not that they leave
    the product for a month.

    **The draft loses them and should.** `draft_day` proposes what to pin, and
    a pin is a `DailyFocus` with a foreign key to `Item`. A bill that is not an
    `Item` cannot be pinned at all, so proposing one would be offering a verb
    the model has taken away. Paying is the verb a bill has.
    """

    def setUp(self):
        self.alice = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.list_ = List.objects.create(owner=self.alice, title="Home")

    def bill(self, payee, due_date, amount="120.00"):
        return bills.record(
            self.alice,
            payee=payee,
            amount=Decimal(amount),
            due_date=due_date,
            recurrence=Item.Recurrence.MONTHLY,
        )

    def test_a_bill_is_not_an_action_item(self):
        self.bill("Landlord", AUGUST_3)
        list_services.create_item(self.list_, "Call the plumber", due_date=AUGUST_3)

        self.assertEqual(
            [item.text for item in reads.action_items_for(self.alice, AUGUST_3)],
            ["Call the plumber"],
        )

    def test_the_draft_does_not_propose_pinning_a_bill(self):
        """It cannot be pinned after the flip, so proposing it is offering a
        verb that will not be there."""
        self.bill("Landlord", AUGUST_3)

        draft = reads.draft_day(self.alice, AUGUST_3, today=AUGUST_3)

        self.assertEqual(draft.available, 0)
        self.assertEqual(draft.proposed, [])
