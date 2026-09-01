"""`Bill` and `BillSeries` — increment 1 of `bill-as-a-model-plan.md`.

**These tables are deliberately dark.** Nothing reads or writes them; the
declared trigger is that plan's increment 3, which moves the Money surfaces
onto them. `principles.md` permits exactly one form of built-and-dark — a
deferral with a named trigger — and this file plus both model docstrings are
where it is named.

**So what is there to test?** The promises a migration makes and a later
increment would otherwise discover the hard way: that the constraint holds,
that the deletion decisions are the ones the docstrings claim, and that a
person's bills are their own. `architecture-trajectory.md` §4's rules are
mostly structural and checked by reading; these are the three that are
behaviour.
"""
import datetime
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from lists.models import (
    Account,
    AccountKind,
    Bill,
    BillSeries,
    CadenceMode,
    Direction,
    Item,
    MoneyCategory,
)

DUE = datetime.date(2026, 9, 1)


class BillSeriesTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )

    def test_a_series_is_monthly_and_anchored_unless_told_otherwise(self):
        """Rent is the canonical bill and it is both. A default that has to be
        corrected for the common case is a default facing the wrong way."""
        series = BillSeries.objects.create(owner=self.user, payee="Landlord")

        self.assertEqual(series.cadence, Item.Recurrence.MONTHLY)
        self.assertEqual(series.cadence_mode, CadenceMode.ANCHORED)
        self.assertEqual(series.direction, Direction.OUT)
        self.assertIsNone(series.amount)

    def test_ending_a_series_is_a_date_rather_than_a_delete(self):
        series = BillSeries.objects.create(owner=self.user, payee="Gym")
        series.ended_at = timezone.now()
        series.save()

        self.assertTrue(BillSeries.objects.filter(pk=series.pk).exists())

    def test_losing_a_category_loses_a_label_and_not_the_series(self):
        category = MoneyCategory.objects.create(owner=self.user, name="Utilities")
        series = BillSeries.objects.create(
            owner=self.user, payee="Water", category=category
        )

        category.delete()

        series.refresh_from_db()
        self.assertIsNone(series.category_id)

    def test_closing_an_account_does_not_erase_what_was_paid_to_it(self):
        """The account link is the whole reason this plan exists, and it must
        not take the payment history with it when it goes."""
        account = Account.objects.create(
            owner=self.user, name="Dell Community", kind=AccountKind.CARD
        )
        series = BillSeries.objects.create(
            owner=self.user, payee="Dell Community", account=account
        )

        account.delete()

        series.refresh_from_db()
        self.assertIsNone(series.account_id)

    def test_a_series_belongs_to_its_owner_and_goes_with_them(self):
        BillSeries.objects.create(owner=self.user, payee="Landlord")

        self.user.delete()

        self.assertEqual(BillSeries.objects.count(), 0)


class BillTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )

    def bill(self, **overrides):
        fields = {
            "owner": self.user,
            "payee": "Landlord",
            "due_date": DUE,
            "amount": Decimal("1200.00"),
        }
        return Bill.objects.create(**{**fields, **overrides})

    def test_a_new_bill_is_owed_rather_than_settled(self):
        """Null `paid_at` is the outstanding state, and it stays null however
        long the date has been past -- which is the asymmetry with a task that
        this whole model exists for."""
        bill = self.bill(due_date=datetime.date(2026, 6, 1))

        self.assertIsNone(bill.paid_at)
        self.assertIsNone(bill.paid_amount)

    def test_settling_records_what_moved_and_when(self):
        bill = self.bill()

        bill.paid_amount = Decimal("1200.00")
        bill.paid_at = timezone.now()
        bill.save()

        bill.refresh_from_db()
        self.assertEqual(bill.paid_amount, Decimal("1200.00"))
        self.assertIsNotNone(bill.paid_at)

    def test_what_was_paid_may_differ_from_what_was_expected(self):
        """Two numbers rather than an overwrite: they stop being equal the
        moment somebody pays extra, and *"the electricity bill has been
        creeping up"* is unanswerable from a field with no history."""
        bill = self.bill(amount=Decimal("64.99"))

        bill.paid_amount = Decimal("71.40")
        bill.paid_at = timezone.now()
        bill.save()

        bill.refresh_from_db()
        self.assertEqual(bill.amount, Decimal("64.99"))
        self.assertEqual(bill.paid_amount, Decimal("71.40"))

    def test_a_figure_without_a_settlement_is_refused(self):
        """A number recorded against a bill nobody has settled is a claim about
        money that did not move."""
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.bill(paid_amount=Decimal("10.00"))

    def test_a_settlement_without_a_figure_is_allowed_and_means_something(self):
        """~~A date with no figure is not a state anything here means.~~

        **It is, and increment 2 found it in the data before the migration
        ran.** `services.pay_bill` defaults the figure to what was expected, so
        an *unpriced* bill -- *"the water bill, whatever it comes to"* -- paid
        without an explicit number settles with `paid_amount` still null. One
        of five development `MoneyLine` rows was in exactly that state.

        The honest reading is *paid, amount unrecorded*, and the alternatives
        were fabricating a zero or throwing away the fact that it was paid.
        `principles.md` refuses the first and the second loses history, so the
        constraint was wrong rather than the data.
        """
        bill = self.bill(amount=None, paid_at=timezone.now())

        bill.refresh_from_db()
        self.assertIsNotNone(bill.paid_at)
        self.assertIsNone(bill.paid_amount)

    def test_an_unpriced_bill_is_a_real_bill(self):
        """*"The water bill, whatever it comes to."* The row is what marks it,
        not the figure."""
        bill = self.bill(amount=None)

        self.assertIsNone(bill.amount)

    def test_an_occurrence_snapshots_what_the_series_expected(self):
        """§4 rule 3. Renaming a payee in March must not rewrite what January
        said, so the occurrence carries its own copy rather than reading
        through."""
        series = BillSeries.objects.create(
            owner=self.user, payee="Landlord", amount=Decimal("1200.00")
        )
        bill = self.bill(series=series)

        series.payee = "New Landlord"
        series.amount = Decimal("1300.00")
        series.save()

        bill.refresh_from_db()
        self.assertEqual(bill.payee, "Landlord")
        self.assertEqual(bill.amount, Decimal("1200.00"))

    def test_ending_a_series_does_not_delete_what_it_produced(self):
        """SET_NULL, not CASCADE: the occurrences are a record of money that
        actually moved, and that record outlives the rule that made them."""
        series = BillSeries.objects.create(owner=self.user, payee="Gym")
        bill = self.bill(series=series)

        series.delete()

        bill.refresh_from_db()
        self.assertIsNone(bill.series_id)
        self.assertEqual(bill.payee, "Landlord")

    def test_a_one_off_bill_needs_no_series(self):
        bill = self.bill(payee="Plumber", series=None)

        self.assertIsNone(bill.series_id)

    def test_a_bill_goes_with_its_owner(self):
        self.bill()

        self.user.delete()

        self.assertEqual(Bill.objects.count(), 0)

    def test_one_persons_bills_are_their_own(self):
        other = User.objects.create_user(
            "bob", "bob@example.com", "another secure password"
        )
        self.bill()
        Bill.objects.create(owner=other, payee="Theirs", due_date=DUE)

        self.assertEqual(Bill.objects.filter(owner=self.user).count(), 1)
        self.assertEqual(
            Bill.objects.filter(owner=self.user).get().payee, "Landlord"
        )


# `class NothingUsesTheseYetTest` stood here from August 31, 2026 until later
# the same day. It scanned production source for anything writing a `Bill` and
# failed the moment something did -- and its own docstring said that failure
# was the signal to delete it rather than a regression. `lists/bills.py` is
# what tripped it. The declaration it enforced now lives in
# `clarice/tests/test_dark_services_declare_their_deferral.py`, which is the
# guard that outlives this one.
