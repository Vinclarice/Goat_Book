"""The Money module, driven over HTTP rather than through its reads.

**Every defect this file was written for was invisible to a green suite**, and
they share one cause: the tests drove `money.py` and `services.py` directly, so
nothing ever asked whether the *endpoint* answered. Two of the five were 500s on
screens a person uses.

**`CLAUDE.md` already carried this lesson, in this module, from August 31,
2026** — *"Adding a field to `MoneyLandingOut` is not enough, because this dict
is hand-built rather than dumped from the dataclass — and the two disagreeing is
a 500, not a missing key... past 2009 green Django tests, because every test
drove `landing_for` and none made a request."* The identical mistake was made
nine hours later with `AccountOut`, in the same file, by the same hand. A note is
not a control. `TheHandBuiltResponsesTest` at the bottom is the control.
"""
import datetime
from decimal import Decimal

from django.test import Client, TestCase

from accounts.models import User
from lists import services
from money import services as bills
from money.models import AccountKind, Bill

AUGUST = datetime.date(2026, 8, 20)
PASSWORD = "a secure password"


class MoneyEndpointTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("alice", "alice@example.com", PASSWORD)
        self.client = Client()
        self.client.force_login(self.user)

    def bill(self, **kwargs):
        kwargs.setdefault("payee", "Landlord")
        kwargs.setdefault("due_date", AUGUST)
        return bills.record(self.user, **kwargs)


class AddingAnAccountAnswersTest(MoneyEndpointTest):
    """**Defect 1.** `AccountOut` gained `next_payment` in increment 7 and this
    endpoint's hand-built dict did not, so Ninja's response validation raised
    *after* `create_account` had committed.

    **The second failure is worse than the first**: the account exists, the
    caller sees a 500, and retrying answers *"you already have an account called
    that"* — so the product tells you the write failed and then tells you it
    happened.
    """

    def add(self, name="Dell Community"):
        return self.client.post(
            "/api/v1/money/accounts",
            data={"name": name, "kind": AccountKind.CARD},
            content_type="application/json",
        )

    def test_it_answers_201_rather_than_500(self):
        self.assertEqual(self.add().status_code, 201)

    def test_the_new_account_carries_every_field_its_schema_declares(self):
        body = self.add().json()

        for field in ("id", "name", "kind", "currency", "owes", "balance",
                      "previous", "next_payment"):
            self.assertIn(field, body)

    def test_a_new_account_has_nothing_paying_it_yet(self):
        """Null rather than absent: nothing is filed against an account that
        did not exist a moment ago."""
        self.assertIsNone(self.add().json()["next_payment"])

    def test_it_is_not_left_committed_behind_a_failed_response(self):
        """The regression that made this expensive. If the response raises after
        the write, the second attempt reports a duplicate -- so this asserts the
        first attempt is *reported* as the success it was."""
        self.assertEqual(self.add().status_code, 201)

        second = self.add()

        self.assertEqual(second.status_code, 409)
        self.assertIn("already", second.json()["detail"].lower())


class TheCategoriesScreenAnswersTest(MoneyEndpointTest):
    """**Defect 2.** The count of what a category holds still asked for
    `lines` — `MoneyLine`'s reverse accessor, deleted with the model in
    increment 8. `Bill.category` is `bills`.

    Both the listing and the rename used it, so the screen 500'd on load and on
    save. No test noticed, because every category test drove
    `services.categories_for`, which does not count anything.
    """

    def test_listing_categories_answers(self):
        self.assertEqual(self.client.get("/api/v1/money/categories").status_code, 200)

    def test_a_category_counts_the_bills_filed_under_it(self):
        housing = services.add_category(self.user, name="Housing")
        self.bill(category=housing)
        self.bill(payee="Water", category=housing)
        self.bill(payee="Unfiled")

        rows = {row["name"]: row for row in self.client.get(
            "/api/v1/money/categories").json()}

        self.assertEqual(rows["Housing"]["line_count"], 2)

    def test_an_empty_category_counts_nothing(self):
        services.add_category(self.user, name="Housing")

        rows = {row["name"]: row for row in self.client.get(
            "/api/v1/money/categories").json()}

        self.assertEqual(rows["Housing"]["line_count"], 0)

    def test_renaming_a_category_answers_with_its_count(self):
        housing = services.add_category(self.user, name="Housing")
        self.bill(category=housing)

        response = self.client.patch(
            f"/api/v1/money/categories/{housing.id}",
            data={"name": "Home"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["name"], "Home")
        self.assertEqual(response.json()["line_count"], 1)

    def test_only_this_owner_s_bills_are_counted(self):
        bob = User.objects.create_user("bob", "bob@example.com", PASSWORD)
        housing = services.add_category(self.user, name="Housing")
        theirs = services.add_category(bob, name="Housing")
        bills.record(bob, payee="Theirs", due_date=AUGUST, category=theirs)

        rows = {row["name"]: row for row in self.client.get(
            "/api/v1/money/categories").json()}

        self.assertEqual(rows["Housing"]["line_count"], 0)


class TheYearlyTotalCountsTheObligationTest(MoneyEndpointTest):
    """**Defect 4.** *What the recurring things cost a year* multiplied **every
    priced occurrence** by its cadence, so the figure grew every time a bill
    came round.

    A monthly bill first recorded at 10 and later at 12 reported **264** a year
    — `(10 + 12) x 12` — for one subscription. **Increment 6 made this worse on
    a schedule**: `catch_up` creates an occurrence a month, so the number a
    person is meant to act on inflates by itself.

    The existing test gave each series exactly one occurrence, which is the only
    shape that hides it.
    """

    def landing(self):
        return self.client.get("/api/v1/money").json()

    def test_a_series_counts_once_however_many_occurrences_it_has(self):
        netflix = self.bill(
            payee="Netflix", amount=Decimal("10.00"),
            due_date=datetime.date(2026, 6, 1), recurrence="monthly",
        )
        bills.settle(netflix, today=datetime.date(2026, 6, 2))
        later = Bill.objects.get(owner=self.user, paid_at__isnull=True)
        bills.update(later, amount=Decimal("12.00"))

        self.assertEqual(self.landing()["yearly_totals"], {"USD": "144.00"})

    def test_it_uses_what_the_series_says_rather_than_the_oldest_occurrence(self):
        """The standing rule is what recurs. An occurrence is one month of it,
        and the most recent priced one is the best evidence of what the next
        will cost."""
        netflix = self.bill(
            payee="Netflix", amount=Decimal("10.00"),
            due_date=datetime.date(2026, 6, 1), recurrence="monthly",
        )
        bills.settle(netflix, today=datetime.date(2026, 6, 2))
        later = Bill.objects.get(owner=self.user, paid_at__isnull=True)
        bills.update(later, amount=Decimal("12.00"))

        self.assertEqual(self.landing()["yearly_totals"]["USD"], "144.00")

    def test_two_different_series_are_both_counted(self):
        self.bill(payee="Netflix", amount=Decimal("10.00"), recurrence="monthly")
        self.bill(payee="Adobe", amount=Decimal("240.00"), recurrence="annual")

        self.assertEqual(self.landing()["yearly_totals"], {"USD": "360.00"})

    def test_a_one_off_is_still_not_a_yearly_cost(self):
        self.bill(payee="Plumber", amount=Decimal("90.00"), repeats=False)

        self.assertEqual(self.landing()["yearly_totals"], {})

    def test_an_unpriced_series_contributes_nothing_rather_than_zero(self):
        self.bill(payee="Water", amount=None, recurrence="monthly")

        self.assertEqual(self.landing()["yearly_totals"], {})


class AnUnpricedBillThatWasPaidIsCountedTest(MoneyEndpointTest):
    """**Defect 5.** The month's read counted an unpriced bill and moved on
    before looking at what was settled, so a real payment vanished from *already
    paid*.

    **Both halves of that are true and they are not in conflict**: *"the water
    bill, whatever it comes to"* is unpriced whether or not it has been paid —
    which is why `unpriced` counts it — and 50 went out, which is why the paid
    total must include it. The read did the first and skipped the second.
    """

    def month(self, day=AUGUST):
        return self.client.get(f"/api/v1/money/bills/{day.isoformat()}").json()

    def test_a_payment_against_an_unpriced_bill_reaches_the_paid_total(self):
        water = self.bill(payee="Water", amount=None, repeats=False)
        bills.settle(water, amount=Decimal("50.00"), today=AUGUST)

        self.assertEqual(self.month()["paid_totals"], {"USD": "50.00"})

    def test_it_is_still_counted_as_unpriced(self):
        """Paying it does not price it. What it was *expected* to come to is
        still unknown, and the month says so."""
        water = self.bill(payee="Water", amount=None, repeats=False)
        bills.settle(water, amount=Decimal("50.00"), today=AUGUST)

        self.assertEqual(self.month()["unpriced"], 1)

    def test_income_received_against_an_unpriced_line_reaches_its_own_total(self):
        gift = self.bill(payee="A client", amount=None, direction="in", repeats=False)
        bills.settle(gift, amount=Decimal("300.00"), today=AUGUST)

        body = self.month()
        self.assertEqual(body["received_totals"], {"USD": "300.00"})
        self.assertEqual(body["paid_totals"], {})

    def test_an_unpriced_bill_settled_with_no_figure_adds_nothing(self):
        """Reachable, and the row that disproved this model's first constraint:
        settling an unpriced bill without a number records that it happened and
        no amount. There is nothing to add and nothing to invent."""
        water = self.bill(payee="Water", amount=None, repeats=False)
        bills.settle(water, today=AUGUST)

        body = self.month()
        self.assertEqual(body["paid_totals"], {})
        self.assertEqual(body["unpriced"], 1)

    def test_an_unpriced_and_unpaid_bill_still_adds_nothing_to_due(self):
        self.bill(payee="Water", amount=None, repeats=False)

        body = self.month()
        self.assertEqual(body["due_totals"], {})
        self.assertEqual(body["unpriced"], 1)


class TheHandBuiltResponsesTest(MoneyEndpointTest):
    """**The control, rather than a fifth repair.**

    Four of this module's responses are dicts written out by hand instead of
    dumped from a dataclass, and **a field added to the schema without a matching
    key is a 500 rather than a missing value.** `CLAUDE.md` records that
    happening on August 31, 2026 to `MoneyLandingOut`; `AccountOut` did the
    identical thing on September 1 with the note already written.

    So this asks every money endpoint that answers to answer, rather than
    trusting anybody to remember. It is deliberately shallow — a 200 and a body —
    because the failure it catches is total.
    """

    def test_every_money_read_answers(self):
        housing = services.add_category(self.user, name="Housing")
        card = services.create_account(
            self.user, name="Dell Community", kind=AccountKind.CARD
        )
        paid = self.bill(amount=Decimal("80.00"), category=housing, account=card)
        bills.settle(paid, today=AUGUST)
        self.bill(payee="Water", amount=None, repeats=False)
        services.record_balance(
            card, on_date=datetime.date(2026, 8, 1), amount=Decimal("220.00")
        )

        for path in (
            "/api/v1/money",
            f"/api/v1/money/bills/{AUGUST.isoformat()}",
            f"/api/v1/money/accounts/{AUGUST.isoformat()}",
            "/api/v1/money/categories",
            "/api/v1/money/history",
        ):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200, response.content[:200])

    def test_every_money_write_answers(self):
        card = services.create_account(self.user, name="Amex", kind=AccountKind.CARD)
        housing = services.add_category(self.user, name="Housing")

        created = self.client.post(
            "/api/v1/money/bills",
            data={"payee": "Landlord", "amount": "1200.00",
                  "due_date": AUGUST.isoformat(), "account_id": card.id},
            content_type="application/json",
        )
        self.assertEqual(created.status_code, 201, created.content[:200])
        bill_id = created.json()["id"]

        for name, response in [
            ("add income", self.client.post(
                "/api/v1/money/income",
                data={"payer": "Work", "amount": "3000.00",
                      "due_date": AUGUST.isoformat()},
                content_type="application/json")),
            ("edit bill", self.client.patch(
                f"/api/v1/money/bills/entry/{bill_id}",
                data={"category_id": housing.id},
                content_type="application/json")),
            ("pay bill", self.client.post(
                f"/api/v1/money/bills/entry/{bill_id}/pay",
                data={}, content_type="application/json")),
            ("add account", self.client.post(
                "/api/v1/money/accounts",
                data={"name": "Barclays", "kind": AccountKind.SAVINGS},
                content_type="application/json")),
            ("record balances", self.client.post(
                "/api/v1/money/balances",
                data={"on_date": "2026-08-01",
                      "readings": [{"account_id": card.id, "amount": "220.00"}]},
                content_type="application/json")),
            ("add category", self.client.post(
                "/api/v1/money/categories",
                data={"name": "Utilities"}, content_type="application/json")),
        ]:
            with self.subTest(write=name):
                self.assertIn(response.status_code, (200, 201),
                              response.content[:200])


class EveryDeclaredFieldIsSentTest(MoneyEndpointTest):
    """**The guard the note could not be.**

    `MoneyLandingOut` and `AccountOut` both gained fields their hand-built dicts
    did not, nine hours apart, with a `CLAUDE.md` paragraph about the first one
    already written. Both were 500s, and the second committed a row before
    failing.

    So this reads the schema rather than a list somebody maintains: every field
    a money response *declares* has to appear in what it actually sends. A field
    added to a schema without a matching key fails here instead of in
    production.

    **Deliberately over the wire and not over the function**, because that is
    the whole distinction the defects turned on -- `landing_for` was correct
    both times; the endpoint was not.

    **Mutation-tested, and the first attempt did not catch it** -- which is
    worth keeping, because it says exactly what this covers. Adding
    `a_field: str | None = None` to `AccountOut` passes: a field with a default
    is filled in by Ninja and cannot 500. Adding `a_field: str | None`, with no
    default, fails here and in four tests above. **The defect shape is a
    required field**, and that is what `next_payment` was.
    """

    def declared(self, schema):
        return set(schema.model_fields)

    def test_the_landing_sends_every_field_it_declares(self):
        from money.api_v1 import MoneyLandingOut

        body = self.client.get("/api/v1/money").json()

        self.assertEqual(self.declared(MoneyLandingOut) - set(body), set())

    def test_a_created_account_sends_every_field_it_declares(self):
        from money.api_v1 import AccountOut

        body = self.client.post(
            "/api/v1/money/accounts",
            data={"name": "Amex", "kind": AccountKind.CARD},
            content_type="application/json",
        ).json()

        self.assertEqual(self.declared(AccountOut) - set(body), set())

    def test_a_listed_account_sends_every_field_it_declares(self):
        from money.api_v1 import AccountOut

        services.create_account(self.user, name="Amex", kind=AccountKind.CARD)

        rows = self.client.get(
            f"/api/v1/money/accounts/{AUGUST.isoformat()}").json()["accounts"]

        self.assertEqual(self.declared(AccountOut) - set(rows[0]), set())

    def test_a_month_row_sends_every_field_it_declares(self):
        from money.api_v1 import MonthBillOut

        self.bill(amount=Decimal("80.00"))

        rows = self.client.get(
            f"/api/v1/money/bills/{AUGUST.isoformat()}").json()["bills"]

        self.assertEqual(self.declared(MonthBillOut) - set(rows[0]), set())

    def test_a_created_bill_sends_every_field_it_declares(self):
        from money.api_v1 import MonthBillOut

        body = self.client.post(
            "/api/v1/money/bills",
            data={"payee": "Landlord", "amount": "1200.00",
                  "due_date": AUGUST.isoformat()},
            content_type="application/json",
        ).json()

        self.assertEqual(self.declared(MonthBillOut) - set(body), set())

    def test_the_sweep_reads_real_schemas(self):
        """A positive control. Comparing an empty set against anything passes,
        so this proves the schemas were found and have fields."""
        from money.api_v1 import AccountOut, MonthBillOut, MoneyLandingOut

        for schema in (AccountOut, MonthBillOut, MoneyLandingOut):
            self.assertGreater(len(self.declared(schema)), 3)
