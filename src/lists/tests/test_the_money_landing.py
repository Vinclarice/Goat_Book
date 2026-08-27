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
from lists import money as money_reader, services
from lists.models import AccountKind, Item

TODAY = datetime.date(2026, 8, 25)


class TheMoneyLandingTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )

    def bill(self, payee, *, due, amount="100.00", recurrence=None, lead_days=0):
        return services.create_bill(
            self.user,
            payee=payee,
            amount=Decimal(amount),
            due_date=due,
            recurrence=recurrence or Item.Recurrence.MONTHLY,
            lead_days=lead_days,
        )

    def landing(self, today=TODAY):
        return money_reader.landing_for(self.user, today=today)

    def test_what_is_due_soon_crosses_a_month_boundary(self):
        """The defect this increment exists for: a fortnight from the 25th is
        mostly next month, and every other read here is keyed to one."""
        self.bill("Internet", due=datetime.date(2026, 8, 28))
        self.bill("Landlord", due=datetime.date(2026, 9, 1))

        soon = self.landing().due_soon

        self.assertEqual(
            [row.task.text for row in soon],
            ["Pay Internet", "Pay Landlord"],
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

        self.assertEqual([row.task.text for row in overdue], ["Pay Old subscription"])

    def test_a_paid_bill_is_neither_overdue_nor_soon(self):
        paid = self.bill("Internet", due=datetime.date(2026, 8, 20))
        services.pay_bill(paid)

        found = self.landing()

        self.assertEqual(found.overdue, [])
        self.assertEqual([row.task.text for row in found.due_soon], [])

    def test_it_says_what_renews_inside_its_lead_time(self):
        """The reason the module exists, on the page you arrive at."""
        self.bill(
            "Adobe",
            due=datetime.date(2026, 9, 20),
            recurrence=Item.Recurrence.ANNUAL,
            lead_days=30,
        )

        renewing = self.landing().renewing_soon

        self.assertEqual([row.task.text for row in renewing], ["Pay Adobe"])

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
        card = services.create_account(self.user, name="Amex", kind=AccountKind.CARD)
        services.record_balance(
            card, on_date=datetime.date(2026, 7, 1), amount=Decimal("4500.00")
        )
        services.record_balance(
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
        services.create_account(self.user, name="Amex")

        found = self.landing()

        self.assertEqual(found.owed_totals, {})
        self.assertEqual(found.unread_accounts, 1)

    def test_one_persons_money_is_their_own(self):
        other = User.objects.create_user("bob", "bob@example.com", "a password")
        services.create_bill(
            other, payee="Theirs", amount=Decimal("50.00"), due_date=TODAY
        )

        self.assertEqual(self.landing().due_soon, [])
