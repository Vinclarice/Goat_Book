"""Paying a bill where it is shown, and recording what actually went out.

`bills-page-plan.md` increment 5. Until now the page could add a bill and delete
a bill and not pay one -- the action a person does twelve times more often than
all the others together -- so marking rent paid meant leaving for the day page
or the task detail. That is the silo this slice exists to close, left sitting in
the middle of it.

**Two numbers, because they answer different questions.** `amount` is what a
bill is expected to come to; `paid_amount` is what went out. They stop being
equal the first time somebody pays extra, which Vince named as the ordinary case
rather than an edge one. Keeping both is what lets a month report *still to pay*
from expectations and *already paid* from facts -- and it is the only way
*"the electricity bill has been creeping up"* is ever answerable, since a field
that gets overwritten keeps no history to read.

**Paying is completing.** There is no second definition: `complete_item` is what
the day, the agenda and the review already read, it is what spawns the next
occurrence of a recurring bill, and `completed_at` is what this page keys *paid*
on. A bill-shaped copy of "done" would be a second answer to one question.
"""
import datetime
from decimal import Decimal

from django.test import TestCase

from accounts.models import User
from lists import bills as bills_reader
from lists import services
from lists.models import Bill, Item

AUGUST = datetime.date(2026, 8, 10)


class PayingABillTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.bill = services.create_bill(
            self.user,
            payee="City Utilities",
            amount=Decimal("64.99"),
            due_date=AUGUST,
            repeats=False,
        )

    def test_paying_it_marks_it_paid(self):
        services.pay_bill(self.bill)

        self.bill.refresh_from_db()
        self.assertIsNotNone(self.bill.completed_at)

    def test_what_went_out_defaults_to_what_was_expected(self):
        """The common case is one click: the bill came to what it said."""
        services.pay_bill(self.bill)

        self.assertEqual(
            Bill.objects.get(item=self.bill).paid_amount, Decimal("64.99")
        )

    def test_paying_extra_is_recorded_as_what_it_was(self):
        """The case that decides the design. Overwriting `amount` would lose
        what the bill was supposed to be; not recording anything would lose
        what actually left the account."""
        services.pay_bill(self.bill, amount=Decimal("80.00"))

        bill = Bill.objects.get(item=self.bill)
        self.assertEqual(bill.paid_amount, Decimal("80.00"))
        self.assertEqual(
            bill.amount,
            Decimal("64.99"),
            "The expected amount should survive being paid a different one.",
        )

    def test_an_unpriced_bill_can_be_paid_with_a_real_number(self):
        """"The water bill, whatever it comes to" -- and then it comes to
        something, which is the moment the number is known."""
        water = services.create_bill(
            self.user, payee="Water", amount=None, due_date=AUGUST, repeats=False
        )

        services.pay_bill(water, amount=Decimal("41.20"))

        self.assertEqual(Bill.objects.get(item=water).paid_amount, Decimal("41.20"))

    def test_the_month_totals_what_went_out_not_what_was_expected(self):
        services.pay_bill(self.bill, amount=Decimal("80.00"))

        found = bills_reader.bills_for(self.user, AUGUST)

        self.assertEqual(found.paid_totals, {"USD": Decimal("80.00")})

    def test_paying_a_repeating_bill_still_brings_the_next_one(self):
        """Paying is completing, so everything completing does still happens --
        including the successor this slice had to repair once already."""
        rent = services.create_bill(
            self.user, payee="Landlord", amount=Decimal("1200.00"), due_date=AUGUST
        )

        services.pay_bill(rent)

        following = Item.objects.filter(
            owner=self.user, completed_at__isnull=True, text="Pay Landlord"
        )
        self.assertEqual(following.count(), 1)

    def test_it_refuses_a_negative_payment(self):
        with self.assertRaises(services.TaskConflict):
            services.pay_bill(self.bill, amount=Decimal("-1.00"))

    def test_it_refuses_a_task_that_is_not_a_bill(self):
        plain = services.create_item(None, "Not a bill", owner=self.user)

        with self.assertRaises(services.TaskConflict):
            services.pay_bill(plain)
