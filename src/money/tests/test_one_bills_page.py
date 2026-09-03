"""`GET /api/v1/money/bills/entry/{task_id}` — one bill, on its own.

**Why a bill needs a page of its own**, and why now. Until August 31, 2026 a
bill was opened at `/app/tasks/{id}`, borrowing the task detail page — and that
page spent the morning being taught to call itself *Bill detail*, hide
Priority, Area and Checklist, and link back to Money, because none of it was
true for a bill.

`bill-as-a-model-plan.md` makes that borrowing impossible: a bill that is not
an `Item` has no `/tasks/{id}` to borrow. So the surface moves to the Money
module before the model does, which keeps the flip from having to invent a page
at the same moment it changes what a bill is.

**Keyed on `task_id` today and on a bill id after the flip.** The path already
carries `PATCH`, `POST /pay` and `DELETE` on that key, so the read joins them
rather than inventing a second address for the same thing.
"""
import datetime
from decimal import Decimal

from django.test import TestCase

from accounts.models import User
from money import services as bills
from lists import services
from money.models import MoneyCategory

AUGUST = datetime.date(2026, 8, 10)


class OneBillsPageTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.bill = bills.record(
            self.user,
            payee="Landlord",
            amount=Decimal("1200.00"),
            due_date=AUGUST,
        )
        self.client.force_login(self.user)

    def get(self, task_id=None):
        return self.client.get(
            f"/api/v1/money/bills/entry/{task_id or self.bill.id}"
        )

    def test_it_answers_with_everything_the_page_shows(self):
        response = self.get()

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["payee"], "Landlord")
        self.assertEqual(body["amount"], "1200.00")
        self.assertEqual(body["currency"], "USD")
        self.assertEqual(body["due_date"], "2026-08-10")
        self.assertFalse(body["paid"])
        self.assertTrue(body["repeats"], "Monthly by default -- rent is the canon.")

    def test_an_unpriced_bill_says_so_rather_than_showing_a_zero(self):
        water = bills.record(
            self.user, payee="Water", amount=None, due_date=AUGUST
        )

        body = self.get(water.id).json()

        self.assertIsNone(body["amount"])

    def test_it_reports_what_was_actually_paid(self):
        """The one thing a bill's own page shows that the month row does not,
        and the reason `paid_amount` is a second column rather than an
        overwrite: they stop being equal the moment somebody pays extra."""
        bills.settle(self.bill, amount=Decimal("1275.40"))

        body = self.get().json()

        self.assertTrue(body["paid"])
        self.assertEqual(body["paid_amount"], "1275.40")
        self.assertEqual(body["amount"], "1200.00", "What it was supposed to be.")

    def test_an_unsettled_bill_has_no_paid_amount(self):
        self.assertIsNone(self.get().json()["paid_amount"])

    def test_it_carries_the_category_by_name_and_id(self):
        """Both, because they serve different readers -- the heading needs no
        lookup and the picker is keyed on the id."""
        utilities = MoneyCategory.objects.create(owner=self.user, name="Utilities")
        bills.update(self.bill, category=utilities)

        body = self.get().json()

        self.assertEqual(body["category"], "Utilities")
        self.assertEqual(body["category_id"], utilities.pk)

    def test_somebody_elses_bill_is_not_found(self):
        other = User.objects.create_user(
            "bob", "bob@example.com", "another secure password"
        )
        theirs = bills.record(
            other, payee="Theirs", amount=Decimal("9.00"), due_date=AUGUST
        )

        self.assertEqual(self.get(theirs.id).status_code, 404)

    def test_a_task_that_is_not_a_bill_is_not_found(self):
        """The path is about bills. A plain task answering here would make
        *is this a bill* a question the caller has to ask afterwards."""
        plain = services.create_item(
            services.create_area(self.user, "Home"), "Call the vet"
        )

        self.assertEqual(self.get(plain.id).status_code, 404)

    def test_a_stranger_is_refused(self):
        self.client.logout()

        self.assertEqual(self.get().status_code, 401)
