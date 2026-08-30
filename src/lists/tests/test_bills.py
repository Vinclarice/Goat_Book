"""A task that is also a bill — v3's *The day*, and §4 said no to a primitive.

`architecture-trajectory.md` §4 asks whether a concept has a different *life
cycle*, and a bill's -- arrives, is due, is paid, comes round again -- **is** a
recurring task's. `daily-operating-system-vision.md` settles it by example:
*"'Pay rent every month' is a recurring task: one discrete commitment whose
completion creates the next."* A `MoneyLine` primitive would contradict the
product's own model and re-implement recurrence, due dates, completion and
snapshotting beside the thing that already does them.

So a one-to-one sidecar: it adds attributes without claiming a life cycle, and
keeps a decimal column that is null for almost every row off the hottest model
in the application.

**Not a facet either.** `Facet` carries *inferred capabilities* with a
confirmation flow, and a number somebody typed is a fact -- putting it in the
proposal table would muddy both.

**The row is the marker, not the amount.** An amount is optional, because "the
water bill, whatever it comes to" is a real bill; what makes a task a bill is
that somebody said so.
"""

import datetime
import json
from decimal import Decimal

from django.test import Client, TestCase

from accounts.models import User
from lists import services
from lists.models import MoneyLine, Item, List


PASSWORD = "a secure password"


class BillTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", PASSWORD
        )
        self.other = User.objects.create_user("bob", "bob@example.com", PASSWORD)
        self.list_ = List.objects.create(owner=self.user, title="Home")
        self.task = services.create_item(
            self.list_, "Property tax", due_date=datetime.date(2026, 10, 5)
        )
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.user)
        response = self.client.get("/accounts/password/change/")
        self.csrf = response.cookies["csrftoken"].value

    def patch(self, payload, task=None):
        return self.client.patch(
            f"/api/v1/tasks/{(task or self.task).id}",
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=self.csrf,
        )

    def test_a_task_is_not_a_bill_until_somebody_says_so(self):
        self.assertFalse(MoneyLine.objects.filter(item=self.task).exists())

    def test_marking_one_records_what_it_is_and_what_it_comes_to(self):
        response = self.patch(
            {"bill": {"amount": "500.00", "payee": "County", "currency": "USD"}}
        )

        self.assertEqual(response.status_code, 200)
        bill = MoneyLine.objects.get(item=self.task)
        self.assertEqual(bill.amount, Decimal("500.00"))
        self.assertEqual(bill.payee, "County")

    def test_a_bill_without_an_amount_is_still_a_bill(self):
        """"The water bill, whatever it comes to" is a real bill. The row is
        the marker; the amount is an attribute of it."""
        self.patch({"bill": {"payee": "Utilities"}})

        bill = MoneyLine.objects.get(item=self.task)
        self.assertIsNone(bill.amount)
        self.assertEqual(bill.payee, "Utilities")

    def test_marking_it_twice_edits_rather_than_duplicates(self):
        self.patch({"bill": {"amount": "500.00", "payee": "County"}})

        self.patch({"bill": {"amount": "525.00", "payee": "County"}})

        self.assertEqual(MoneyLine.objects.filter(item=self.task).count(), 1)
        self.assertEqual(
            MoneyLine.objects.get(item=self.task).amount, Decimal("525.00")
        )

    def test_it_can_stop_being_a_bill(self):
        self.patch({"bill": {"amount": "500.00", "payee": "County"}})

        response = self.patch({"bill": None})

        self.assertEqual(response.status_code, 200)
        self.assertFalse(MoneyLine.objects.filter(item=self.task).exists())

    def test_it_is_serialised_back_so_a_client_can_show_it(self):
        body = self.patch(
            {"bill": {"amount": "500.00", "payee": "County"}}
        ).json()["task"]

        self.assertEqual(body["bill"]["amount"], "500.00")
        self.assertEqual(body["bill"]["payee"], "County")

    def test_a_task_that_is_not_a_bill_says_so_rather_than_faking_one(self):
        """Null rather than an empty bill: "not a bill" and "a bill with
        nothing filled in" are different facts, and the second is reachable
        on purpose."""
        body = self.patch({"text": "Property tax"}).json()["task"]

        self.assertIsNone(body["bill"])

    def test_a_nonsense_amount_is_refused_rather_than_stored(self):
        response = self.patch({"bill": {"amount": "about five hundred"}})

        self.assertEqual(response.status_code, 400)
        # Ninja's single `detail` string, not the hand-rolled field map --
        # coherence-audit-2026-08-30.md F2.
        self.assertIn("amount", response.json()["detail"])
        self.assertFalse(MoneyLine.objects.filter(item=self.task).exists())

    def test_a_negative_amount_is_refused(self):
        """A bill is something owed. A negative one is a refund, which is a
        different thing and not this."""
        response = self.patch({"bill": {"amount": "-20.00"}})

        self.assertEqual(response.status_code, 400)

    def test_one_person_cannot_bill_anothers_task(self):
        """The isolation test principles.md asks of every id-taking surface --
        inherited from `_owned_item`, and asserted rather than assumed."""
        theirs = List.objects.create(owner=self.other, title="Theirs")
        their_task = services.create_item(theirs, "Their bill")

        response = self.patch({"bill": {"amount": "1.00"}}, task=their_task)

        self.assertEqual(response.status_code, 404)
        self.assertFalse(MoneyLine.objects.filter(item=their_task).exists())

    def test_the_bill_goes_when_the_task_does(self):
        """A sidecar with no task is a row nothing can reach."""
        self.patch({"bill": {"amount": "500.00"}})
        item_id = self.task.id

        Item.objects.filter(pk=item_id).delete()

        self.assertFalse(MoneyLine.objects.filter(item_id=item_id).exists())
