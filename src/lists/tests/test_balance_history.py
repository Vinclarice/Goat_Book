"""Twelve months of balances, and six months of arithmetic about them.

`money-module-plan.md` increment 11. Vince: *"a table with accounts listed, and
balances over say a 12 month period. And I'd like to have a prediction for the
next six months."*

**The projection is arithmetic and says so.** The average monthly change over
the readings there are, carried forward. Not a model and not a fit -- nothing
here learns, so `design-concept.md`'s ML policy is not engaged, and a straight
line somebody can check in their head is worth more than a better curve they
cannot.

**It refuses under three readings**, which is the part worth testing hardest.
Two points make a line through whatever noise those two months contained, and
that line looks exactly as confident as one drawn from twelve. *Not enough
history yet* keeps the other projections worth believing.

**And it names the crossing.** For something owed, the month the line reaches
zero is what a person actually wants -- *at this rate, clear in March 2027* --
and it is worth more than the six figures behind it.
"""
import datetime
from decimal import Decimal

from django.test import TestCase

from accounts.models import User
from lists import money as money_reader, services
from lists.models import AccountKind

TODAY = datetime.date(2026, 8, 15)


def month(year, month_number):
    return datetime.date(year, month_number, 1)


class BalanceHistoryTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )

    def account(self, name="Car loan", kind=AccountKind.LOAN):
        return services.create_account(self.user, name=name, kind=kind)

    def readings(self, account, figures, start_month=3, year=2026):
        for offset, figure in enumerate(figures):
            services.record_balance(
                account,
                on_date=month(year, start_month + offset),
                amount=Decimal(figure),
            )

    def history(self, today=TODAY, months=12):
        return money_reader.history_for(self.user, today=today, months=months)

    def row_for(self, name, **kwargs):
        return next(
            row for row in self.history(**kwargs).rows if row.account.name == name
        )

    def test_it_lists_the_months_in_order_oldest_first(self):
        """A table read left to right is read forwards."""
        found = self.history()

        self.assertEqual(len(found.months), 12)
        self.assertEqual(found.months[0], month(2025, 9))
        self.assertEqual(found.months[-1], month(2026, 8))

    def test_a_month_with_no_reading_is_a_gap_and_not_a_zero(self):
        """Nothing recorded and nothing owed are different facts, and only one
        of them is a number."""
        loan = self.account()
        self.readings(loan, ["8000.00"], start_month=8)

        row = self.row_for("Car loan")

        self.assertIsNone(row.balances[month(2026, 7)])
        self.assertEqual(row.balances[month(2026, 8)], Decimal("8000.00"))

    def test_it_projects_the_average_monthly_change_forward(self):
        """Four readings falling 250 a month, so six more at 250 a month."""
        loan = self.account()
        self.readings(loan, ["8000.00", "7750.00", "7500.00", "7250.00"])

        row = self.row_for("Car loan")

        self.assertEqual(row.projection.monthly_change, Decimal("-250.00"))
        self.assertEqual(len(row.projection.months), 6)
        self.assertEqual(row.projection.months[0][1], Decimal("7000.00"))
        self.assertEqual(row.projection.months[-1][1], Decimal("5750.00"))

    def test_it_says_what_the_projection_is_drawn_from(self):
        """A projection whose derivation is invisible is a claim rather than an
        estimate."""
        loan = self.account()
        self.readings(loan, ["8000.00", "7750.00", "7500.00", "7250.00"])

        row = self.row_for("Car loan")

        self.assertEqual(row.projection.readings_used, 4)

    def test_two_readings_are_not_enough_to_project_from(self):
        """The refusal that keeps the others worth believing. Two points make a
        line through whatever those two months happened to contain, and it
        looks exactly as confident as one drawn from twelve."""
        loan = self.account()
        self.readings(loan, ["8000.00", "7750.00"])

        row = self.row_for("Car loan")

        self.assertIsNone(row.projection)

    def test_three_readings_are(self):
        loan = self.account()
        self.readings(loan, ["8000.00", "7750.00", "7500.00"])

        self.assertIsNotNone(self.row_for("Car loan").projection)

    def test_it_names_the_month_a_debt_clears(self):
        """The one output worth more than the six figures behind it."""
        loan = self.account()
        self.readings(loan, ["900.00", "600.00", "300.00"])

        row = self.row_for("Car loan")

        self.assertEqual(row.projection.clears_on, month(2026, 6))

    def test_a_debt_going_the_wrong_way_never_clears(self):
        card = self.account(name="Amex", kind=AccountKind.CARD)
        self.readings(card, ["100.00", "200.00", "300.00"])

        self.assertIsNone(self.row_for("Amex").projection.clears_on)

    def test_savings_have_no_clearing_month(self):
        """Zero means nothing for something held, so the page is not offered a
        date that would read as a warning."""
        isa = self.account(name="Stocks ISA", kind=AccountKind.INVESTMENT)
        self.readings(isa, ["900.00", "600.00", "300.00"])

        self.assertIsNone(self.row_for("Stocks ISA").projection.clears_on)

    def test_a_projection_for_a_debt_does_not_go_below_zero(self):
        """A loan does not become a negative loan; it ends."""
        loan = self.account()
        self.readings(loan, ["600.00", "400.00", "200.00"])

        projected = [figure for _, figure in self.row_for("Car loan").projection.months]

        self.assertTrue(all(figure >= 0 for figure in projected), projected)

    def test_an_account_with_no_readings_at_all_still_appears(self):
        """Otherwise opening an account and forgetting it makes it invisible,
        which is the opposite of what a history table is for."""
        self.account(name="Untouched")

        row = self.row_for("Untouched")

        self.assertIsNone(row.projection)
        self.assertTrue(all(value is None for value in row.balances.values()))

    def test_one_persons_history_is_their_own(self):
        other = User.objects.create_user("bob", "bob@example.com", "a password")
        services.create_account(other, name="Theirs")

        self.assertEqual([row.account.name for row in self.history().rows], [])
