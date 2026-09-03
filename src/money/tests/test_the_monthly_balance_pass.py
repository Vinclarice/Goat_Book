"""The end-of-month ritual, as one request.

Vince: *"typically at the end of the month I'll do a review and update all the
balances."* That is a batch, so the endpoint is a batch -- six separate requests
would be six chances to be half-done, and a page that saved four accounts and
failed on the fifth is worse than one that saved none.
"""
import datetime
import json
from decimal import Decimal

from django.test import Client, TestCase

from accounts.models import User
from money import services as bills
from money.models import AccountKind, BalanceReading

PASSWORD = "correct horse battery staple 47!"
AUGUST = datetime.date(2026, 8, 1)


class TheMonthlyBalancePassTest(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(
            username="alice", email="alice@example.com", password=PASSWORD
        )
        self.client = Client()
        self.client.force_login(self.alice)
        self.card = bills.create_account(self.alice, name="Amex")
        self.isa = bills.create_account(
            self.alice, name="Stocks ISA", kind=AccountKind.INVESTMENT
        )

    def save(self, readings, on_date=AUGUST):
        return self.client.post(
            "/api/v1/money/balances",
            data=json.dumps(
                {"on_date": on_date.isoformat(), "readings": readings}
            ),
            content_type="application/json",
        )

    def test_it_saves_every_figure_in_one_go(self):
        response = self.save(
            [
                {"account_id": self.card.id, "amount": "4200.00"},
                {"account_id": self.isa.id, "amount": "15300.00"},
            ]
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(BalanceReading.objects.count(), 2)

    def test_an_untouched_box_leaves_that_account_alone(self):
        """Null is *skip me*, not *blank me*. Nothing is served by being able
        to un-know what a balance was."""
        bills.record_balance(self.card, on_date=AUGUST, amount=Decimal("4200.00"))

        self.save(
            [
                {"account_id": self.card.id, "amount": None},
                {"account_id": self.isa.id, "amount": "15300.00"},
            ]
        )

        self.assertEqual(
            self.card.readings.get().amount,
            Decimal("4200.00"),
            "An untouched box erased a figure that had been recorded.",
        )

    def test_one_bad_figure_saves_none_of_them(self):
        """The failure a batch exists to prevent, and would otherwise quietly
        introduce: four saved, two not, and no way to tell which."""
        response = self.save(
            [
                {"account_id": self.card.id, "amount": "4200.00"},
                {"account_id": self.isa.id, "amount": "not a number"},
            ]
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            BalanceReading.objects.count(),
            0,
            "A bad figure in the second box left the first one saved.",
        )

    def test_the_refusal_says_which_account(self):
        """"That is not a number" over six boxes is not a message."""
        response = self.save(
            [{"account_id": self.isa.id, "amount": "twelve"}]
        )

        self.assertIn("Stocks ISA", response.json()["detail"])

    def test_it_returns_the_month_so_the_page_need_not_ask_again(self):
        body = self.save(
            [{"account_id": self.card.id, "amount": "4200.00"}]
        ).json()

        self.assertEqual(body["owed_totals"], {"USD": "4200.00"})

    def test_another_persons_account_is_refused(self):
        bob = User.objects.create_user("bob", "bob@example.com", "a password")
        theirs = bills.create_account(bob, name="Their card")

        response = self.save([{"account_id": theirs.id, "amount": "10.00"}])

        self.assertEqual(response.status_code, 400)
        self.assertEqual(BalanceReading.objects.count(), 0)

    def test_the_month_read_says_which_way_it_moved(self):
        bills.record_balance(
            self.card, on_date=datetime.date(2026, 7, 1), amount=Decimal("4500.00")
        )
        bills.record_balance(self.card, on_date=AUGUST, amount=Decimal("4200.00"))

        body = self.client.get("/api/v1/money/accounts/2026-08-15").json()

        row = next(a for a in body["accounts"] if a["name"] == "Amex")
        self.assertEqual(row["balance"], "4200.00")
        self.assertEqual(row["previous"], "4500.00")

    def test_owed_and_held_are_totalled_apart(self):
        """Subtracting one from the other is a net worth, which is a different
        claim from either and not one this page makes."""
        self.save(
            [
                {"account_id": self.card.id, "amount": "4200.00"},
                {"account_id": self.isa.id, "amount": "15300.00"},
            ]
        )

        body = self.client.get("/api/v1/money/accounts/2026-08-15").json()

        self.assertEqual(body["owed_totals"], {"USD": "4200.00"})
        self.assertEqual(body["held_totals"], {"USD": "15300.00"})
