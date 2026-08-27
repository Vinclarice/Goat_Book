"""A bill can be corrected where it is shown.

`money-module-plan.md` increment 3. Amount, payee, currency and due date are the
four things about a bill that change, and until now changing any of them meant
leaving the page: open the task's detail, find the bill fields, edit, come back.

**One service, because the four fields do not live in one place.** Amount,
payee and currency are the sidecar's; the due date is the task's. A page that
edits a bill should not have to know which is which, and a caller making two
writes can leave a bill half-corrected if the second fails.

**Editing does not rename the task.** The name was derived from the payee when
the bill was made, and changing a payee later is usually a correction to who
gets paid rather than a request to rename a commitment with history behind it --
`RecurringCommitment.text` is what the series is called, and rewriting it from
here would rename every past occurrence's series. Renaming stays where tasks are
renamed. Recorded because it is a real choice and the other answer is arguable.
"""
import datetime
from decimal import Decimal

from django.test import TestCase

from accounts.models import User
from lists import services
from lists.models import Bill

AUGUST = datetime.date(2026, 8, 10)
LATER = datetime.date(2026, 8, 24)


class EditingABillTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.bill = services.create_bill(
            self.user,
            payee="Landlord",
            amount=Decimal("1200.00"),
            currency="USD",
            due_date=AUGUST,
        )

    def test_it_changes_the_amount(self):
        services.update_bill(self.bill, amount=Decimal("1250.00"))

        self.assertEqual(Bill.objects.get(item=self.bill).amount, Decimal("1250.00"))

    def test_it_changes_the_due_date_which_lives_on_the_task(self):
        """The one field that is not the sidecar's, and the reason this is a
        service rather than two calls from the page."""
        services.update_bill(self.bill, due_date=LATER)

        self.bill.refresh_from_db()
        self.assertEqual(self.bill.due_date, LATER)

    def test_it_changes_payee_and_currency_together(self):
        services.update_bill(self.bill, payee="New Landlord", currency="GBP")

        bill = Bill.objects.get(item=self.bill)
        self.assertEqual(bill.payee, "New Landlord")
        self.assertEqual(bill.currency, "GBP")

    def test_an_unmentioned_field_keeps_its_value(self):
        """The partial-write contract the rest of this API already has: a page
        saving one field must not blank another."""
        services.update_bill(self.bill, amount=Decimal("1250.00"))

        bill = Bill.objects.get(item=self.bill)
        self.assertEqual(bill.payee, "Landlord")
        self.assertEqual(bill.currency, "USD")
        self.bill.refresh_from_db()
        self.assertEqual(self.bill.due_date, AUGUST)

    def test_an_amount_can_be_cleared_back_to_unpriced(self):
        """Explicitly `None`, which is different from not mentioning it: "the
        water bill, whatever it comes to" is a state somebody chooses."""
        services.update_bill(self.bill, amount=None, clear_amount=True)

        self.assertIsNone(Bill.objects.get(item=self.bill).amount)

    def test_it_refuses_a_negative_amount(self):
        with self.assertRaises(services.TaskConflict):
            services.update_bill(self.bill, amount=Decimal("-5.00"))

    def test_it_refuses_an_empty_payee(self):
        with self.assertRaises(services.TaskConflict):
            services.update_bill(self.bill, payee="  ")

    def test_it_does_not_rename_the_task(self):
        """Recorded as a decision rather than an omission -- see the module
        docstring. A series with history has a name, and correcting who gets
        paid is not a request to rewrite it."""
        services.update_bill(self.bill, payee="New Landlord")

        self.bill.refresh_from_db()
        self.assertEqual(self.bill.text, "Pay Landlord")
