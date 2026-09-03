"""What the money module says when you arrive at it.

`money-module-plan.md` increment 8. The module was described as *"a landing page
for relevant information -- if I need to check on financial information, I know
exactly where to go"*, and what `/money` showed was August. Answering *how am I
doing* meant reading three lists and doing arithmetic.

**Everything here is a read.** Nothing is stored, nothing is cached, and no row
exists because this page exists -- the same rule the Daily Page follows: *a lens
over durable records, not a new place to copy them.*

**And it crosses months on purpose.** Every other read in this module is keyed to
one, which is why *what is due in the next fortnight* could not be answered at
all: a fortnight from the 25th is mostly next month.
"""
import datetime
from decimal import Decimal

from django.test import TestCase

from accounts.models import User
from money import services as bills
from money import reads as money_reader
from lists.models import Item
from money.models import AccountKind, Direction

TODAY = datetime.date(2026, 8, 25)


class TheMoneyLandingTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )

    def bill(self, payee, *, due, amount="100.00", recurrence=None, lead_days=0):
        return bills.record(
            self.user,
            payee=payee,
            amount=Decimal(amount),
            due_date=due,
            recurrence=recurrence or Item.Recurrence.MONTHLY,
            lead_days=lead_days,
        )

    def landing(self, today=TODAY):
        return money_reader.landing_from_bills(self.user, today=today)

    def test_what_is_due_soon_crosses_a_month_boundary(self):
        """The defect this increment exists for: a fortnight from the 25th is
        mostly next month, and every other read here is keyed to one."""
        self.bill("Internet", due=datetime.date(2026, 8, 28))
        self.bill("Landlord", due=datetime.date(2026, 9, 1))

        soon = self.landing().due_soon

        self.assertEqual(
            [row.payee for row in soon],
            ["Internet", "Landlord"],
            "A bill due in six days was invisible because it falls in September.",
        )

    def test_a_bill_further_out_than_a_fortnight_is_not_soon(self):
        self.bill("Insurance", due=datetime.date(2026, 9, 30))

        self.assertEqual(self.landing().due_soon, [])

    def test_overdue_is_every_month_not_this_one(self):
        """An unpaid June bill is still owed in August, and a page that only
        reads August cannot say so."""
        self.bill("Old subscription", due=datetime.date(2026, 6, 3))

        overdue = self.landing().overdue

        self.assertEqual([row.payee for row in overdue], ["Old subscription"])

    def test_a_paid_bill_is_neither_overdue_nor_soon(self):
        paid = self.bill("Internet", due=datetime.date(2026, 8, 20))
        bills.settle(paid)

        found = self.landing()

        self.assertEqual(found.overdue, [])
        self.assertEqual([row.payee for row in found.due_soon], [])

    def test_it_says_what_renews_inside_its_lead_time(self):
        """The reason the module exists, on the page you arrive at."""
        self.bill(
            "Adobe",
            due=datetime.date(2026, 9, 20),
            recurrence=Item.Recurrence.ANNUAL,
            lead_days=30,
        )

        renewing = self.landing().renewing_soon

        self.assertEqual([row.payee for row in renewing], ["Adobe"])

    def test_something_outside_its_lead_time_stays_quiet(self):
        """Eleven months of silence is the whole point of a lead time."""
        self.bill(
            "Adobe",
            due=datetime.date(2027, 3, 20),
            recurrence=Item.Recurrence.ANNUAL,
            lead_days=30,
        )

        self.assertEqual(self.landing().renewing_soon, [])

    def test_it_totals_what_the_recurring_things_cost_a_year(self):
        """Increment 9. Monthly twelve times, quarterly four, annual once --
        the number that makes somebody cancel something."""
        self.bill("Netflix", due=TODAY, amount="10.00")
        self.bill(
            "Water", due=TODAY, amount="60.00", recurrence=Item.Recurrence.QUARTERLY
        )
        self.bill(
            "Adobe", due=TODAY, amount="240.00", recurrence=Item.Recurrence.ANNUAL
        )

        self.assertEqual(
            self.landing().yearly_totals,
            {"USD": Decimal("600.00")},
            "10x12 + 60x4 + 240 = 600.",
        )

    def test_a_one_off_bill_is_not_a_yearly_cost(self):
        """It happens once. Counting it as annual would inflate the figure a
        person is meant to act on."""
        self.bill("Plumber", due=TODAY, recurrence=Item.Recurrence.NONE)

        self.assertEqual(self.landing().yearly_totals, {})

    def test_balances_come_with_what_they_were_last_month(self):
        card = bills.create_account(self.user, name="Amex", kind=AccountKind.CARD)
        bills.record_balance(
            card, on_date=datetime.date(2026, 7, 1), amount=Decimal("4500.00")
        )
        bills.record_balance(
            card, on_date=datetime.date(2026, 8, 1), amount=Decimal("4200.00")
        )

        found = self.landing()

        self.assertEqual(found.owed_totals, {"USD": Decimal("4200.00")})
        self.assertEqual(
            found.owed_change,
            {"USD": Decimal("-300.00")},
            "Down three hundred, which is the only thing a balance page is for.",
        )

    def test_an_account_with_no_reading_yet_does_not_invent_one(self):
        bills.create_account(self.user, name="Amex")

        found = self.landing()

        self.assertEqual(found.owed_totals, {})
        self.assertEqual(found.unread_accounts, 1)

    def test_one_persons_money_is_their_own(self):
        other = User.objects.create_user("bob", "bob@example.com", "a password")
        bills.record(
            other, payee="Theirs", amount=Decimal("50.00"), due_date=TODAY
        )

        self.assertEqual(self.landing().due_soon, [])


class TellingEmptyApartTest(TestCase):
    """*Nothing needs you* and *you have not started* are different answers.

    **What this page could not tell apart until August 31, 2026.** Every list
    and total it returns is empty in both cases, so it said *"Nothing is
    overdue, due soon, or about to renew"* to somebody with no bills at all --
    a tautology rather than information, on the module's own front door, with
    no way to create anything from it.

    Vince hit exactly that four days after the module shipped. Two counts are
    enough to separate the states, and they are counts rather than one boolean
    because the useful prompt differs: somebody with bills and no accounts is
    missing balances, not a start.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )

    def landing(self):
        return money_reader.landing_from_bills(self.user, today=TODAY)

    def test_a_new_account_has_nothing_of_either_kind(self):
        reading = self.landing()

        self.assertEqual(reading.line_count, 0)
        self.assertEqual(reading.account_count, 0)

    def test_a_bill_counts_as_a_line(self):
        bills.record(
            self.user, payee="Landlord", amount=Decimal("100.00"), due_date=TODAY
        )

        reading = self.landing()

        self.assertEqual(reading.line_count, 1)
        self.assertEqual(reading.account_count, 0)

    def test_income_counts_too(self):
        """`line_count` is money lines, not bills. Somebody who has only
        recorded income has started."""
        bills.record(
            self.user, direction=Direction.IN, payee="Work", amount=Decimal("2000.00"), due_date=TODAY
        )

        self.assertEqual(self.landing().line_count, 1)

    def test_an_account_counts_separately(self):
        bills.create_account(self.user, name="Amex", kind=AccountKind.CARD)

        reading = self.landing()

        self.assertEqual(reading.account_count, 1)
        self.assertEqual(reading.line_count, 0)

    def test_a_paid_bill_still_counts_as_having_started(self):
        """The counts answer *have you ever put anything here*, not *is
        anything outstanding* -- which the lists above already answer, and
        which is the distinction this whole class exists for.

        **Two, not one**, and this assertion was wrong when first written:
        settling a repeating bill produces its successor, so that is a real
        second row. Counting it is correct rather than an artefact --
        somebody who has paid one rent and owes the next has emphatically
        started.
        """
        bill = bills.record(
            self.user, payee="Landlord", amount=Decimal("100.00"), due_date=TODAY
        )
        bills.settle(bill)

        self.assertEqual(self.landing().line_count, 2)

    def test_counts_are_this_owner_s_alone(self):
        other = User.objects.create_user(
            "bob", "bob@example.com", "another secure password"
        )
        bills.record(
            other, payee="Theirs", amount=Decimal("50.00"), due_date=TODAY
        )
        bills.create_account(other, name="Theirs", kind=AccountKind.CARD)

        reading = self.landing()

        self.assertEqual(reading.line_count, 0)
        self.assertEqual(reading.account_count, 0)


class TheLandingEndpointTest(TestCase):
    """`GET /api/v1/money` over HTTP, which nothing covered until August 31,
    2026.

    **Every test above drives `money_reader.landing_for` directly**, and the
    endpoint hand-builds its own response dict from what that returns. So the
    two could disagree and the suite would not notice — which is exactly what
    happened the day `line_count` and `account_count` were added: 2009 Django
    tests passed while `/api/v1/money` answered 500 for every request, because
    `MoneyLandingOut` required two fields the dict did not carry.

    It was caught by opening the page, which is the argument for opening the
    page. This class is the argument for not needing to next time: a reader
    test proves the arithmetic, and only a request proves the contract.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.client.force_login(self.user)

    def test_it_answers_for_an_account_with_nothing_in_it(self):
        response = self.client.get("/api/v1/money")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["line_count"], 0)
        self.assertEqual(payload["account_count"], 0)

    def test_it_answers_with_bills_and_accounts_recorded(self):
        bills.record(
            self.user,
            payee="Landlord",
            amount=Decimal("1200.00"),
            due_date=datetime.date(2026, 8, 20),
        )
        bills.create_account(self.user, name="Amex", kind=AccountKind.CARD)

        response = self.client.get("/api/v1/money")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["line_count"], 1)
        self.assertEqual(payload["account_count"], 1)

    def test_every_declared_field_is_actually_sent(self):
        """The guard for the class of defect above, rather than for its
        instance: the response schema and the hand-built dict are two lists of
        keys that have to agree, and nothing made them."""
        from money.api_v1 import MoneyLandingOut

        payload = self.client.get("/api/v1/money").json()

        self.assertEqual(
            set(MoneyLandingOut.model_fields) - set(payload),
            set(),
            "MoneyLandingOut declares a field the endpoint does not send.",
        )

    def test_it_refuses_a_stranger(self):
        self.client.logout()

        self.assertEqual(self.client.get("/api/v1/money").status_code, 401)
