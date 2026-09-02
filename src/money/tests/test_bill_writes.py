"""Writing bills against `Bill` — increment 4 of `bill-as-a-model-plan.md`.

`lists/bills.py` is the service module `money.py` is the read half of, per §4
rule 4. Everything here is dark until the surfaces switch; these tests are what
make that switch a flip rather than a leap.

**The behaviour that has to survive the move** is what the task versions spent
a month getting right, and each of those decisions gets a test here rather than
a hope: the amount not carrying to the next occurrence, the two amounts staying
apart, absent meaning *keep* and null meaning *clear*, and deleting one month
not silently ending a habit.
"""
import datetime
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from money import services as bills
from lists.models import Account, AccountKind, Bill, BillSeries, Direction, Item
from money.services import BillConflict

DUE = datetime.date(2026, 8, 1)


class CreatingTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )

    def test_a_repeating_bill_gets_a_series_and_an_occurrence(self):
        bill = bills.record(
            self.user, payee="Landlord", amount=Decimal("1200.00"), due_date=DUE
        )

        self.assertEqual(Bill.objects.count(), 1)
        self.assertEqual(BillSeries.objects.count(), 1)
        self.assertEqual(bill.series.payee, "Landlord")
        self.assertEqual(
            bill.series.cadence, Item.Recurrence.MONTHLY, "Rent is the canonical bill."
        )

    def test_a_one_off_gets_no_series(self):
        bill = bills.record(
            self.user,
            payee="Plumber",
            amount=Decimal("300.00"),
            due_date=DUE,
            repeats=False,
        )

        self.assertIsNone(bill.series_id)
        self.assertEqual(BillSeries.objects.count(), 0)

    def test_both_rows_arrive_or_neither_does(self):
        """`modules.md`: a module links to work through its own create path or
        not at all, so membership cannot be forgotten."""
        with self.assertRaises(BillConflict):
            bills.record(self.user, payee="   ", due_date=DUE)

        self.assertEqual(Bill.objects.count(), 0)
        self.assertEqual(BillSeries.objects.count(), 0)

    def test_an_unpriced_bill_is_a_real_bill(self):
        bill = bills.record(self.user, payee="Water", amount=None, due_date=DUE)

        self.assertIsNone(bill.amount)

    def test_a_negative_amount_is_refused(self):
        with self.assertRaises(BillConflict):
            bills.record(
                self.user, payee="Landlord", amount=Decimal("-1"), due_date=DUE
            )

    def test_income_points_the_other_way(self):
        bill = bills.record(
            self.user,
            payee="Work",
            amount=Decimal("3000.00"),
            due_date=DUE,
            direction=Direction.IN,
        )

        self.assertEqual(bill.direction, Direction.IN)
        self.assertEqual(bill.series.direction, Direction.IN)

    def test_an_account_can_be_named_at_creation(self):
        """The link the whole plan started from, on the path that cannot
        forget it."""
        account = Account.objects.create(
            owner=self.user, name="Dell Community", kind=AccountKind.CARD
        )

        bill = bills.record(
            self.user, payee="Dell Community", due_date=DUE, account=account
        )

        self.assertEqual(bill.account_id, account.pk)
        self.assertEqual(bill.series.account_id, account.pk)


class SettlingTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )

    def test_settling_records_the_expected_figure_by_default(self):
        bill = bills.record(
            self.user, payee="Comcast", amount=Decimal("64.99"), due_date=DUE
        )

        bills.settle(bill)

        bill.refresh_from_db()
        self.assertEqual(bill.paid_amount, Decimal("64.99"))
        self.assertIsNotNone(bill.paid_at)

    def test_paying_extra_does_not_overwrite_what_was_expected(self):
        """The case that decided the two-amount design: the month loses the
        difference otherwise, and *"this has been creeping up"* stops being
        answerable."""
        bill = bills.record(
            self.user, payee="Comcast", amount=Decimal("64.99"), due_date=DUE
        )

        bills.settle(bill, amount=Decimal("71.40"))

        bill.refresh_from_db()
        self.assertEqual(bill.amount, Decimal("64.99"))
        self.assertEqual(bill.paid_amount, Decimal("71.40"))

    def test_an_unpriced_bill_settles_with_no_figure(self):
        bill = bills.record(self.user, payee="Water", amount=None, due_date=DUE)

        bills.settle(bill)

        bill.refresh_from_db()
        self.assertIsNotNone(bill.paid_at)
        self.assertIsNone(bill.paid_amount)

    def test_settling_twice_is_refused(self):
        bill = bills.record(self.user, payee="Comcast", due_date=DUE)
        bills.settle(bill)

        with self.assertRaises(BillConflict):
            bills.settle(bill)

    def test_settling_a_repeating_bill_produces_the_next_one(self):
        bill = bills.record(
            self.user, payee="Landlord", amount=Decimal("1200.00"), due_date=DUE
        )

        bills.settle(bill, today=datetime.date(2026, 8, 3))

        successor = Bill.objects.exclude(pk=bill.pk).get()
        self.assertEqual(successor.due_date, datetime.date(2026, 9, 1))
        self.assertEqual(successor.series_id, bill.series_id)
        self.assertIsNone(successor.paid_at)

    def test_the_amount_does_not_carry_to_the_next_occurrence(self):
        """Last quarter's was 500 and this one is 525. Carrying the number
        forward would state something nobody has been told; what lands is an
        unpriced bill from a known payee."""
        bill = bills.record(
            self.user, payee="Landlord", amount=Decimal("1200.00"), due_date=DUE
        )

        bills.settle(bill, today=datetime.date(2026, 8, 3))

        successor = Bill.objects.exclude(pk=bill.pk).get()
        self.assertEqual(successor.payee, "Landlord")
        self.assertEqual(successor.currency, "USD")
        self.assertIsNone(successor.amount)

    def test_a_one_off_produces_nothing(self):
        bill = bills.record(self.user, payee="Plumber", due_date=DUE, repeats=False)

        bills.settle(bill)

        self.assertEqual(Bill.objects.count(), 1)

    def test_an_ended_series_produces_nothing(self):
        bill = bills.record(self.user, payee="Gym", due_date=DUE)
        bill.series.ended_at = timezone.now()
        bill.series.save()

        bills.settle(bill)

        self.assertEqual(Bill.objects.count(), 1)


class UpdatingTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.bill = bills.record(
            self.user, payee="Comcast", amount=Decimal("64.99"), due_date=DUE
        )

    def test_absent_keeps_and_a_value_replaces(self):
        bills.update(self.bill, amount=Decimal("70.00"))

        self.bill.refresh_from_db()
        self.assertEqual(self.bill.amount, Decimal("70.00"))
        self.assertEqual(self.bill.payee, "Comcast", "Left out, so left alone.")

    def test_clearing_an_amount_is_an_explicit_act(self):
        """*"Whatever it comes to"* is a state somebody chooses rather than a
        field they forgot."""
        bills.update(self.bill, clear_amount=True)

        self.bill.refresh_from_db()
        self.assertIsNone(self.bill.amount)

    def test_the_four_fields_move_in_one_call(self):
        """The old version needed one service across two records so a caller
        could not leave a bill half-corrected. They are one record now."""
        bills.update(
            self.bill,
            payee="Xfinity",
            amount=Decimal("80.00"),
            currency="gbp",
            due_date=datetime.date(2026, 8, 25),
        )

        self.bill.refresh_from_db()
        self.assertEqual(self.bill.payee, "Xfinity")
        self.assertEqual(self.bill.amount, Decimal("80.00"))
        self.assertEqual(self.bill.currency, "GBP")
        self.assertEqual(self.bill.due_date, datetime.date(2026, 8, 25))

    def test_a_bill_cannot_lose_its_date(self):
        with self.assertRaises(BillConflict):
            bills.update(self.bill, due_date=None)

    def test_revising_the_series_leaves_what_already_happened_alone(self):
        """§4 rule 3, which is why occurrences snapshot rather than read
        through."""
        bills.revise_series(self.bill.series, payee="Xfinity", amount=Decimal("80.00"))

        self.bill.refresh_from_db()
        self.assertEqual(self.bill.payee, "Comcast")
        self.assertEqual(self.bill.amount, Decimal("64.99"))

    def test_a_revised_series_reaches_the_next_occurrence(self):
        bills.revise_series(self.bill.series, payee="Xfinity")

        bills.settle(self.bill, today=datetime.date(2026, 8, 3))

        successor = Bill.objects.exclude(pk=self.bill.pk).get()
        self.assertEqual(successor.payee, "Xfinity")


class RemovingTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )

    def test_deleting_one_month_does_not_silently_end_the_habit(self):
        """What somebody means by deleting August's rent is *not this one*.
        They would have said so if they meant stop paying rent."""
        bill = bills.record(
            self.user, payee="Landlord", amount=Decimal("1200.00"), due_date=DUE
        )

        # Injected: the successor's date depends on today, because
        # `_advance_due_date` will not produce one already overdue. This test
        # read the wall clock until September 1, 2026, when it started failing
        # for no reason but the date -- and it would have gone on passing for
        # the whole of August while proving nothing about the boundary.
        bills.remove(bill, today=DUE)

        self.assertFalse(Bill.objects.filter(pk=bill.pk).exists())
        successor = Bill.objects.get()
        self.assertEqual(successor.due_date, datetime.date(2026, 9, 1))

    def test_deleting_the_whole_series_ends_it_and_clears_what_is_owed(self):
        bill = bills.record(
            self.user, payee="Gym", amount=Decimal("40.00"), due_date=DUE
        )

        bills.remove(bill, whole_series=True)

        self.assertEqual(Bill.objects.count(), 0)
        series = BillSeries.objects.get()
        self.assertIsNotNone(
            series.ended_at, "Ended rather than deleted, so its history survives."
        )

    def test_ending_a_series_keeps_what_was_actually_paid(self):
        """Those rows are a record of money that moved, and `SET_NULL` on the
        occurrence exists precisely so ending a rule does not erase them."""
        july = bills.record(
            self.user,
            payee="Gym",
            amount=Decimal("40.00"),
            due_date=datetime.date(2026, 7, 1),
        )
        bills.settle(july, today=datetime.date(2026, 7, 2))
        august = Bill.objects.exclude(pk=july.pk).get()

        bills.remove(august, whole_series=True)

        july.refresh_from_db()
        self.assertIsNotNone(july.paid_at)
        self.assertEqual(Bill.objects.count(), 1, "The paid one, and not the owed one.")

    def test_deleting_a_one_off_leaves_nothing_behind(self):
        bill = bills.record(self.user, payee="Plumber", due_date=DUE, repeats=False)

        bills.remove(bill)

        self.assertEqual(Bill.objects.count(), 0)


class ChangingWhetherABillRepeatsTest(TestCase):
    """Cadence lives on the series, so changing it is a series-level act even
    when somebody does it from one occurrence's edit form.

    **The old model could not express this at all**: `Item.recurrence` was on
    the occurrence, so "does this repeat" and "what does the rule say" were the
    same field. Splitting them is what makes *stop paying rent* different from
    *delete August's rent* — and it is why this needs a function rather than an
    assignment.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            "vince", "vince@example.com", "a secure password"
        )

    def bill(self, **kwargs):
        return bills.record(
            self.user, payee="Landlord", amount=Decimal("1200.00"),
            due_date=DUE, **kwargs,
        )

    def test_a_one_off_can_be_made_to_repeat(self):
        bill = self.bill(repeats=False)

        bills.set_cadence(bill, Item.Recurrence.MONTHLY)

        bill.refresh_from_db()
        self.assertIsNotNone(bill.series)
        self.assertEqual(bill.series.cadence, Item.Recurrence.MONTHLY)

    def test_a_new_series_carries_the_occurrence_it_was_made_from(self):
        """Otherwise the first thing it spawns is a bill for nobody, with no
        payee and no figure -- the series has to start from something."""
        bill = self.bill(repeats=False)

        bills.set_cadence(bill, Item.Recurrence.MONTHLY)

        series = bill.series
        self.assertEqual(series.payee, "Landlord")
        self.assertEqual(series.amount, Decimal("1200.00"))
        self.assertEqual(series.owner, self.user)

    def test_a_repeating_bill_can_change_its_cadence(self):
        bill = self.bill()

        bills.set_cadence(bill, Item.Recurrence.ANNUAL)

        bill.refresh_from_db()
        self.assertEqual(bill.series.cadence, Item.Recurrence.ANNUAL)

    def test_stopping_the_repeat_ends_the_series_and_keeps_this_one(self):
        """`ended_at` rather than a delete, for the reason `remove` gives: the
        occurrences it already produced are a record of money that moved."""
        bill = self.bill()
        series = bill.series

        bills.set_cadence(bill, Item.Recurrence.NONE)

        bill.refresh_from_db()
        series.refresh_from_db()
        self.assertIsNotNone(series.ended_at)
        self.assertIsNone(bill.series, "This occurrence is still owed and still here.")
        self.assertTrue(Bill.objects.filter(pk=bill.pk).exists())

    def test_an_unchanged_cadence_does_nothing(self):
        bill = self.bill()
        before = bill.series.pk

        bills.set_cadence(bill, Item.Recurrence.MONTHLY)

        bill.refresh_from_db()
        self.assertEqual(bill.series.pk, before)

    def test_a_cadence_that_is_not_one_is_refused(self):
        bill = self.bill()

        with self.assertRaises(bills.BillConflict):
            bills.set_cadence(bill, "fortnightlyish")


class WhatABillRefusesTest(TestCase):
    """The refusals that survived the split, and the one that did not."""

    def setUp(self):
        self.user = User.objects.create_user(
            "vince", "vince@example.com", "a secure password"
        )

    def test_a_bill_needs_a_payee(self):
        """It is the only thing a bill is named by. The task version derived a
        title from it -- *Landlord* became *Pay Landlord* -- so an empty one
        produced a task called *Pay*; here it would produce a row nobody could
        identify."""
        with self.assertRaises(bills.BillConflict):
            bills.record(self.user, payee="", amount=Decimal("10.00"), due_date=DUE)

    def test_whitespace_is_not_a_payee(self):
        with self.assertRaises(bills.BillConflict):
            bills.record(self.user, payee="   ", due_date=DUE)

    def test_an_edit_cannot_empty_the_payee_either(self):
        bill = bills.record(self.user, payee="Landlord", due_date=DUE)

        with self.assertRaises(bills.BillConflict):
            bills.update(bill, payee="")

    def test_two_open_bills_from_one_payee_are_allowed_now(self):
        """**A refusal that was an artifact, and is gone deliberately.**

        Until August 31, 2026 this raised *"there is already an open bill from
        Amazon"* and suggested writing *Amazon (Prime)* instead. Nothing in the
        money domain wanted that: it was `unique_active_item`, the task core's
        rule that one person cannot have two open tasks with the same text,
        reaching money through the derived title *Pay Amazon*.

        Two invoices from one supplier in a month is ordinary, and the old
        model could not record it. The refusal went with the derived title, and
        this test is here so that is a decision rather than something nobody
        noticed.
        """
        bills.record(self.user, payee="Amazon", amount=Decimal("7.99"), due_date=DUE)
        bills.record(self.user, payee="Amazon", amount=Decimal("4.99"), due_date=DUE)

        self.assertEqual(Bill.objects.filter(payee="Amazon").count(), 2)
