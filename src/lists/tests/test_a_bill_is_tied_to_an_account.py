"""Increment 7 of `design/bill-as-a-model-plan.md` — the disconnect Vince
actually reported.

> *"I've added Dell Commenity and its showing up but now there's a disconnect.
> Like it should be tied to the payments."* — August 31, 2026

Two things were tangled in that sentence and the plan separated them. The
**diagnosis** — a bill should not be a task — was increments 1 to 6. This is
the **disconnect** itself: an account and the bill that pays it were unrelated
records, so a card could sit on the balances screen with nothing on it saying
what pays it down.

**`Account.paid_by` existed for one evening.** Written August 27, 2026 and
deleted the same day by `d50d6eb`, because it was *"set by nothing and read by
nothing"* through two screens that were each supposed to give it a purpose.
That commit is explicit about the terms of its return: *"it comes back the day
a surface actually wants it."* So this file tests **both halves** — something
that sets it and something that reads it — because one without the other is the
same mistake with a longer runway.

**What the link means, stated once.** `Bill.account` is *the account this bill
moves money against*: an outgoing bill against a card reduces what is owed, an
incoming one against an investment increases what is held. **Not "paid from"**,
which was the other reading available and is the one the original field
rejected — its docstring said it *"linked an account to the recurring bill that
pays it"*. Recording which current account the money left is a second fact this
product does not have, and inventing a field that could mean either would make
every reader guess.

**On the occurrence and on the series, and they are different facts.** The
series is what pays the card *as a standing arrangement*; the occurrence is
what pays it in September. §4 rule 3 is why: editing August does not rewrite
the rule, so filing one month against a different account leaves the
arrangement alone.
"""
import datetime
from decimal import Decimal

from django.db import connection
from django.test import Client, TestCase
from django.test.utils import CaptureQueriesContext

from accounts.models import User
from lists import bills, services
from lists.models import AccountKind, Bill, Direction, Item

AUGUST = datetime.date(2026, 8, 20)
PASSWORD = "a secure password"


class TyingABillToAnAccountTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("alice", "alice@example.com", PASSWORD)
        self.card = services.create_account(
            self.user, name="Dell Community", kind=AccountKind.CARD
        )

    def bill(self, **kwargs):
        kwargs.setdefault("payee", "Dell Community")
        kwargs.setdefault("amount", Decimal("80.00"))
        kwargs.setdefault("due_date", AUGUST)
        return bills.record(self.user, **kwargs)

    def test_a_bill_can_name_the_account_it_pays(self):
        bill = self.bill(account=self.card)

        self.assertEqual(bill.account, self.card)

    def test_a_repeating_bill_puts_it_on_the_standing_rule_too(self):
        """The card is paid by an *arrangement*, not by one month of it. If only
        the occurrence carried it, the link would vanish the first time the bill
        came round."""
        bill = self.bill(account=self.card, recurrence=Item.Recurrence.MONTHLY)

        self.assertEqual(bill.series.account, self.card)

    def test_the_successor_inherits_it(self):
        bill = self.bill(account=self.card, recurrence=Item.Recurrence.MONTHLY)

        bills.settle(bill, today=AUGUST)

        successor = Bill.objects.get(owner=self.user, paid_at__isnull=True)
        self.assertEqual(successor.account, self.card)

    def test_a_replayed_occurrence_inherits_it(self):
        """The other producer. `catch_up` builds from the series, so a link the
        series carries reaches every period it replays."""
        self.bill(
            account=self.card,
            due_date=datetime.date(2026, 6, 20),
            recurrence=Item.Recurrence.MONTHLY,
        )

        bills.catch_up(self.user, today=AUGUST)

        self.assertEqual(
            Bill.objects.filter(owner=self.user, account=self.card).count(), 3
        )

    def test_it_can_be_filed_and_refiled_and_cleared(self):
        other = services.create_account(self.user, name="Amex", kind=AccountKind.CARD)
        bill = self.bill()

        bills.update(bill, account=self.card)
        bill.refresh_from_db()
        self.assertEqual(bill.account, self.card)

        bills.update(bill, account=other)
        bill.refresh_from_db()
        self.assertEqual(bill.account, other)

        bills.update(bill, account=None)
        bill.refresh_from_db()
        self.assertIsNone(bill.account)

    def test_refiling_one_month_leaves_the_arrangement_alone(self):
        """§4 rule 3, which is what occurrences snapshot *for*. Paying August
        off a different card does not change what pays the card every month."""
        other = services.create_account(self.user, name="Amex", kind=AccountKind.CARD)
        bill = self.bill(account=self.card, recurrence=Item.Recurrence.MONTHLY)

        bills.update(bill, account=other)

        bill.refresh_from_db()
        self.assertEqual(bill.account, other)
        self.assertEqual(bill.series.account, self.card)

    def test_closing_an_account_does_not_erase_what_was_paid_to_it(self):
        """SET_NULL, and the reason for it: those rows are a record of money
        that moved. Losing them because a card was closed would be the past
        being rewritten by a live decision -- `principles.md` refuses it."""
        bill = self.bill(account=self.card)
        bills.settle(bill, today=AUGUST)

        self.card.delete()

        bill.refresh_from_db()
        self.assertIsNone(bill.account)
        self.assertIsNotNone(bill.paid_at)


class TheApiSetsAndReadsItTest(TestCase):
    """**Both halves, which is the whole reason this increment exists.**
    `d50d6eb` deleted the first version because nothing set it and nothing read
    it. A test that only proved the service accepts a value would have passed
    for that version too."""

    def setUp(self):
        self.user = User.objects.create_user("alice", "alice@example.com", PASSWORD)
        self.card = services.create_account(
            self.user, name="Dell Community", kind=AccountKind.CARD
        )
        # A plain client, like every other endpoint test in this app. CSRF is
        # `test_api_token_auth.py`'s subject and asserting it again here would
        # be a second copy of somebody else's contract.
        self.client = Client()
        self.client.force_login(self.user)

    def add_bill(self, **body):
        body.setdefault("payee", "Dell Community")
        body.setdefault("amount", "80.00")
        body.setdefault("due_date", AUGUST.isoformat())
        return self.client.post(
            "/api/v1/money/bills", data=body, content_type="application/json"
        )

    def test_a_bill_is_created_against_an_account(self):
        response = self.add_bill(account_id=self.card.id)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["account_id"], self.card.id)
        self.assertEqual(response.json()["account"], "Dell Community")

    def test_a_bill_with_no_account_says_so_rather_than_faking_one(self):
        response = self.add_bill()

        self.assertIsNone(response.json()["account_id"])
        self.assertIsNone(response.json()["account"])

    def test_an_account_that_is_not_yours_is_not_found(self):
        bob = User.objects.create_user("bob", "bob@example.com", PASSWORD)
        theirs = services.create_account(bob, name="Theirs", kind=AccountKind.CARD)

        self.assertEqual(self.add_bill(account_id=theirs.id).status_code, 404)

    def test_an_existing_bill_can_be_filed_against_an_account(self):
        bill_id = self.add_bill().json()["id"]

        response = self.client.patch(
            f"/api/v1/money/bills/entry/{bill_id}",
            data={"account_id": self.card.id},
            content_type="application/json",
        )

        self.assertEqual(response.json()["account_id"], self.card.id)

    def test_clearing_it_is_an_explicit_act(self):
        """The same partial-write contract the category has, and for its reason:
        absent means *leave alone*, so *no account* has to be said out loud."""
        bill_id = self.add_bill(account_id=self.card.id).json()["id"]

        response = self.client.patch(
            f"/api/v1/money/bills/entry/{bill_id}",
            data={"account_id": None, "clear_account": True},
            content_type="application/json",
        )

        self.assertIsNone(response.json()["account_id"])

    def test_a_null_account_id_alone_leaves_it_alone(self):
        bill_id = self.add_bill(account_id=self.card.id).json()["id"]

        response = self.client.patch(
            f"/api/v1/money/bills/entry/{bill_id}",
            data={"account_id": None, "payee": "Dell"},
            content_type="application/json",
        )

        self.assertEqual(response.json()["account_id"], self.card.id)


class AnAccountSaysWhatPaysItTest(TestCase):
    """**The read half, and the one Vince asked for.** The balances screen
    showed a card with a figure and nothing about how it gets paid, which is
    the disconnect in his own words."""

    def setUp(self):
        self.user = User.objects.create_user("alice", "alice@example.com", PASSWORD)
        self.card = services.create_account(
            self.user, name="Dell Community", kind=AccountKind.CARD
        )
        # A plain client, like every other endpoint test in this app. CSRF is
        # `test_api_token_auth.py`'s subject and asserting it again here would
        # be a second copy of somebody else's contract.
        self.client = Client()
        self.client.force_login(self.user)

    def accounts(self, day=AUGUST):
        return self.client.get(f"/api/v1/money/accounts/{day.isoformat()}").json()

    def account(self, day=AUGUST):
        return self.accounts(day)["accounts"][0]

    def test_an_account_with_nothing_against_it_says_nothing(self):
        """Null rather than an empty object: *nothing pays this* is a real
        state, and the page has a different sentence for it."""
        self.assertIsNone(self.account()["next_payment"])

    def test_it_names_the_soonest_unpaid_bill_against_it(self):
        bills.record(
            self.user, payee="Dell Community", amount=Decimal("80.00"),
            due_date=AUGUST, account=self.card,
        )

        payment = self.account()["next_payment"]

        self.assertEqual(payment["payee"], "Dell Community")
        self.assertEqual(payment["amount"], "80.00")
        self.assertEqual(payment["due_date"], AUGUST.isoformat())

    def test_it_links_to_the_bill_rather_than_only_naming_it(self):
        """A name a person cannot click is a fact they have to go and find."""
        bill = bills.record(
            self.user, payee="Dell Community", due_date=AUGUST, account=self.card,
        )

        self.assertEqual(self.account()["next_payment"]["bill_id"], bill.id)

    def test_a_settled_bill_is_not_what_is_next(self):
        paid = bills.record(
            self.user, payee="Dell Community", amount=Decimal("80.00"),
            due_date=AUGUST, account=self.card, repeats=False,
        )
        bills.settle(paid, today=AUGUST)

        self.assertIsNone(self.account()["next_payment"])

    def test_the_soonest_is_the_one_shown(self):
        for day in (datetime.date(2026, 9, 20), datetime.date(2026, 8, 20)):
            bills.record(
                self.user, payee=f"Dell {day.month}", due_date=day,
                account=self.card, repeats=False,
            )

        self.assertEqual(self.account()["next_payment"]["payee"], "Dell 8")

    def test_a_bill_against_another_account_is_not_shown_here(self):
        other = services.create_account(self.user, name="Amex", kind=AccountKind.CARD)
        bills.record(
            self.user, payee="Amex", due_date=AUGUST, account=other, repeats=False,
        )

        dell = next(
            row for row in self.accounts()["accounts"] if row["name"] == "Dell Community"
        )
        self.assertIsNone(dell["next_payment"])

    def test_money_coming_in_counts_too(self):
        """An investment is fed rather than paid down, and the field is named
        for the movement rather than for the direction. The page words it."""
        isa = services.create_account(
            self.user, name="ISA", kind=AccountKind.INVESTMENT
        )
        bills.record(
            self.user, payee="Monthly contribution", amount=Decimal("200.00"),
            due_date=AUGUST, account=isa, direction=Direction.IN, repeats=False,
        )

        row = next(r for r in self.accounts()["accounts"] if r["name"] == "ISA")
        self.assertEqual(row["next_payment"]["payee"], "Monthly contribution")

    def test_one_person_never_sees_anothers(self):
        bob = User.objects.create_user("bob", "bob@example.com", PASSWORD)
        theirs = services.create_account(bob, name="Theirs", kind=AccountKind.CARD)
        bills.record(bob, payee="Theirs", due_date=AUGUST, account=theirs)

        self.assertIsNone(self.account()["next_payment"])

    def test_the_cost_does_not_grow_with_the_number_of_accounts(self):
        """**Measured, not assumed, and asserted as the property rather than as
        a number.** This screen lists every account somebody has, so a
        per-account lookup is the shape that quietly turns eight accounts into
        eight queries. Comparing two counts says exactly that and cannot drift
        when something unrelated adds a query to the request.
        """
        def cost():
            with CaptureQueriesContext(connection) as queries:
                self.accounts()
            return len(queries)

        bills.record(
            self.user, payee="Dell Community", due_date=AUGUST, account=self.card,
        )
        with_one = cost()

        for n in range(6):
            account = services.create_account(
                self.user, name=f"Card {n}", kind=AccountKind.CARD
            )
            bills.record(
                self.user, payee=f"Bill {n}", due_date=AUGUST, account=account,
            )

        self.assertEqual(cost(), with_one)


class IncomeIsFiledAgainstAnAccountToo(TestCase):
    """**The defect this increment nearly repeated.** The flip found that
    `POST /money/bills` declared `recurrence` and `lead_days`, the form sent
    both, and the endpoint passed neither on -- so every test of those fields
    passed while the feature did nothing.

    `POST /money/income` is the same endpoint's twin and takes its own schema,
    so wiring one and not the other reproduces that exactly: an investment
    filed on the form, accepted with a 201, and linked to nothing.
    """

    def setUp(self):
        self.user = User.objects.create_user("alice", "alice@example.com", PASSWORD)
        self.isa = services.create_account(
            self.user, name="Stocks ISA", kind=AccountKind.INVESTMENT
        )
        self.client = Client()
        self.client.force_login(self.user)

    def add_income(self, **body):
        body.setdefault("payer", "Monthly contribution")
        body.setdefault("amount", "200.00")
        body.setdefault("due_date", AUGUST.isoformat())
        return self.client.post(
            "/api/v1/money/income", data=body, content_type="application/json"
        )

    def test_income_can_name_the_account_it_feeds(self):
        response = self.add_income(account_id=self.isa.id)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["account_id"], self.isa.id)

    def test_an_account_that_is_not_yours_is_not_found(self):
        bob = User.objects.create_user("bob", "bob@example.com", PASSWORD)
        theirs = services.create_account(bob, name="Theirs", kind=AccountKind.CARD)

        self.assertEqual(self.add_income(account_id=theirs.id).status_code, 404)

    def test_it_reaches_the_balances_screen(self):
        """End to end, because *accepted* and *linked* are what came apart the
        last time this shape appeared."""
        self.add_income(account_id=self.isa.id)

        accounts = self.client.get(
            f"/api/v1/money/accounts/{AUGUST.isoformat()}"
        ).json()["accounts"]

        row = next(r for r in accounts if r["name"] == "Stocks ISA")
        self.assertEqual(row["next_payment"]["payee"], "Monthly contribution")
