"""Accounts with balances, and a monthly reading of each.

Vince, August 27, 2026: *"for those with balances (like loans and credit cards),
I'd like to have the ability to add the current monthly balance -- so typically
at the end of the month I'll do a review and update all the balances."*

**A different animal from a bill, and `architecture-trajectory.md` §4 says so.**
Its test is a different life cycle: a `MoneyLine` is an expected movement on a
date that settles once, and an account is a value re-read forever that never
settles. A card's balance belongs to the card, not to this month's payment.

**And the same model serves investments**, which is the payoff. Both are a thing
whose value changes, re-read periodically; they differ in sign, and `owes` says
which way rather than a negative number carrying a convention nobody wrote down.

**The reading is a row, not a field.** *Is this loan actually going down* is a
question about a series, and a field overwritten each month keeps no series to
answer it with -- the same argument that gave `paid_amount` its own column.
"""
import datetime
from decimal import Decimal

from django.test import TestCase

from accounts.models import User
from lists import services
from money.models import Account, AccountKind, BalanceReading

AUGUST = datetime.date(2026, 8, 1)
SEPTEMBER = datetime.date(2026, 9, 1)


class AccountsTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )

    def test_an_account_can_be_opened(self):
        card = services.create_account(
            self.user, name="Amex", kind=AccountKind.CARD, currency="USD"
        )

        self.assertEqual(card.owner, self.user)
        self.assertTrue(card.owes, "A card is money owed by default.")

    def test_an_investment_is_the_same_model_pointing_the_other_way(self):
        """The reason this is one feature and not two."""
        isa = services.create_account(
            self.user, name="Stocks ISA", kind=AccountKind.INVESTMENT, owes=False
        )

        self.assertFalse(isa.owes)

    def test_a_balance_is_recorded_against_a_month(self):
        card = services.create_account(self.user, name="Amex")

        services.record_balance(card, on_date=AUGUST, amount=Decimal("4200.00"))

        self.assertEqual(
            BalanceReading.objects.get(account=card).amount, Decimal("4200.00")
        )

    def test_the_series_is_what_makes_it_worth_having(self):
        """Two readings, and the question the feature exists for becomes
        answerable: is this going down?"""
        loan = services.create_account(self.user, name="Car loan", kind=AccountKind.LOAN)
        services.record_balance(loan, on_date=AUGUST, amount=Decimal("8000.00"))
        services.record_balance(loan, on_date=SEPTEMBER, amount=Decimal("7750.00"))

        readings = list(loan.readings.order_by("on_date"))

        self.assertEqual([r.amount for r in readings], [Decimal("8000.00"), Decimal("7750.00")])

    def test_saving_the_same_month_twice_corrects_rather_than_duplicates(self):
        """The ritual is a monthly pass, and a person who mistypes and saves
        again means *that figure was wrong*, not *here is a second August*."""
        card = services.create_account(self.user, name="Amex")
        services.record_balance(card, on_date=AUGUST, amount=Decimal("4200.00"))

        services.record_balance(card, on_date=AUGUST, amount=Decimal("4250.00"))

        self.assertEqual(card.readings.count(), 1)
        self.assertEqual(card.readings.get().amount, Decimal("4250.00"))

    def test_a_reading_is_dated_to_the_first_of_its_month(self):
        """A balance is what it came to *in August*, not at 14:32 on the 31st.
        Storing the day would make two readings a day apart look like two
        months."""
        card = services.create_account(self.user, name="Amex")

        services.record_balance(
            card, on_date=datetime.date(2026, 8, 31), amount=Decimal("4200.00")
        )

        self.assertEqual(card.readings.get().on_date, AUGUST)

    def test_two_accounts_cannot_share_a_name(self):
        services.create_account(self.user, name="Amex")

        with self.assertRaises(services.TaskConflict):
            services.create_account(self.user, name="Amex")

    def test_one_persons_accounts_are_their_own(self):
        other = User.objects.create_user("bob", "bob@example.com", "a password")
        services.create_account(self.user, name="Amex")

        services.create_account(other, name="Amex")

        self.assertEqual(Account.objects.filter(owner=self.user).count(), 1)
        self.assertEqual(Account.objects.filter(owner=other).count(), 1)

    def test_closing_an_account_takes_its_readings(self):
        """§4 rule 6, hard delete: an account you closed and removed is not
        history you are keeping."""
        card = services.create_account(self.user, name="Amex")
        services.record_balance(card, on_date=AUGUST, amount=Decimal("4200.00"))

        services.close_account(card)

        self.assertEqual(BalanceReading.objects.count(), 0)
