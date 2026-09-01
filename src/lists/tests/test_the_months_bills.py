"""What is due this month, and what it comes to.

The last piece of bills, and the one a person actually opens. Everything under
it exists already: a bill is a task with a sidecar, so this is a read rather
than a model.

**Totals are per currency, never across them.** Adding 500 USD to 40 GBP
produces 540 of nothing. One number would be easier to render and would be
wrong, which is the trade `SearchRank` across two document sets already
refused once.

**An unpriced bill is counted and not totalled**, and the count says so. "The
water bill, whatever it comes to" is a real bill, and a total that silently
omitted it would be a number somebody plans against and should not.

**Open bills only.** A paid one is not still due, the same definition of open
the agenda uses everywhere else.
"""

import datetime
from decimal import Decimal

from django.test import TestCase

from accounts.models import User
from lists import bills
from lists import money as money_reader
from lists import services
from lists.models import List


AUGUST = datetime.date(2026, 8, 1)
MID_AUGUST = datetime.date(2026, 8, 14)


class TheMonthsBillsTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.other = User.objects.create_user("bob", "bob@example.com", "a password")
        self.list_ = List.objects.create(owner=self.user, title="Home")

    def bill(self, payee, *, due=MID_AUGUST, amount="100.00", currency="USD", owner=None):
        """One bill. **The payee is the identity now**, where this used to take
        a task title and attach a sidecar with the payee `Someone` -- which is
        the shape the split removed: the thing a person names was the thing the
        model did not store.
        """
        return bills.record(
            owner or self.user,
            payee=payee,
            amount=Decimal(amount) if amount is not None else None,
            currency=currency,
            due_date=due,
            repeats=False,
        )

    def month(self, day=MID_AUGUST, owner=None):
        return money_reader.month_from_bills(owner or self.user, day)

    def test_a_month_with_no_bills_says_so_rather_than_showing_zero(self):
        """Zero due and nothing due are different, and only one of them
        deserves a total."""
        found = self.month()

        self.assertEqual(found.bills, [])
        self.assertEqual(found.due_totals, {})
        self.assertEqual(found.paid_totals, {})

    def test_it_lists_the_months_bills_soonest_first(self):
        self.bill("Later", due=datetime.date(2026, 8, 20))
        self.bill("Sooner", due=datetime.date(2026, 8, 3))

        self.assertEqual(
            [row.payee for row in self.month().bills], ["Sooner", "Later"]
        )

    def test_it_leaves_out_other_months(self):
        self.bill("September", due=datetime.date(2026, 9, 1))

        self.assertEqual(self.month().bills, [])

    def test_it_totals_what_is_due(self):
        self.bill("Rent", amount="1200.00")
        self.bill("Water", amount="45.50")

        self.assertEqual(self.month().due_totals, {"USD": Decimal("1245.50")})

    def test_currencies_are_totalled_apart_never_together(self):
        """Adding 500 USD to 40 GBP produces 540 of nothing."""
        self.bill("Rent", amount="500.00", currency="USD")
        self.bill("Subscription", amount="40.00", currency="GBP")

        self.assertEqual(
            self.month().due_totals,
            {"USD": Decimal("500.00"), "GBP": Decimal("40.00")},
        )

    def test_an_unpriced_bill_is_counted_and_not_totalled(self):
        """A total that silently omitted it would be a number somebody plans
        against and should not."""
        self.bill("Rent", amount="500.00")
        self.bill("Water", amount=None)

        found = self.month()

        self.assertEqual(found.due_totals, {"USD": Decimal("500.00")})
        self.assertEqual(found.unpriced, 1)
        self.assertEqual(len(found.bills), 2)

    def test_a_paid_bill_stays_in_the_month(self):
        """**Changed August 27, 2026** -- this asserted the opposite, and the
        opposite was `money-module-plan.md`'s defect 3.

        It read `test_a_paid_bill_is_not_still_due`, and the sentence is true:
        a paid bill is not still due. What was wrong is the conclusion drawn
        from it -- that it therefore leaves the page. *Not due* and *not this
        month's* are different facts, and a bills page is asked both
        *what do I owe* and *what did this month cost.*
        """
        paid = self.bill("Rent", amount="1200.00")
        bills.settle(paid)

        found = self.month()

        self.assertEqual([row.payee for row in found.bills], ["Rent"])
        self.assertTrue(found.bills[0].paid)

    def test_what_is_still_due_and_what_is_already_paid_are_separate_totals(self):
        """The defect this increment exists for, as a number.

        Rent paid on the first and internet outstanding: the month **cost**
        1264.99 and 64.99 is **left**, and the page showed the second under a
        heading that said total. Two totals rather than one, because a single
        figure has to pick which question it is answering and cannot say which
        it picked.
        """
        paid = self.bill("Rent", amount="1200.00")
        bills.settle(paid)
        self.bill("Internet", amount="64.99")

        found = self.month()

        self.assertEqual(found.due_totals, {"USD": Decimal("64.99")})
        self.assertEqual(found.paid_totals, {"USD": Decimal("1200.00")})

    def test_a_paid_repeating_bill_is_still_in_the_month(self):
        """The bill this page most exists for, and the one a status check
        would have hidden.

        **Found sideways on August 27, 2026**, while building delete: a
        completed *recurring* task is `ARCHIVED`, not `COMPLETED`, because
        `unique_active_arealess_item` will not have the spawned successor
        sitting beside a live predecessor. So the first version of this read
        filtered on status and would have hidden every paid rent -- while
        passing every test, because the fixtures here do not repeat.

        Keyed on `completed_at` instead, which survives that archive.
        """
        rent = bills.record(
            self.user,
            payee="Landlord",
            amount=Decimal("1200.00"),
            due_date=MID_AUGUST,
            repeats=True,
        )

        bills.settle(rent)

        found = self.month()
        rows = {row.pk: row for row in found.bills}
        self.assertIn(
            rent.pk,
            rows,
            "A paid repeating bill left the month. It is archived rather than "
            "completed, which is a fact about recurrence and not about money.",
        )
        self.assertTrue(rows[rent.pk].paid)
        self.assertEqual(found.paid_totals, {"USD": Decimal("1200.00")})

    def test_a_bill_you_neither_pay_nor_delete_is_simply_owed(self):
        """**A concept that went with the split, recorded rather than
        absorbed.**

        This used to read *a task archived without being paid stays out*: the
        old read excluded tasks archived without completion, because *put away*
        is a task state and a bill inherited it. A `Bill` has no such state --
        `bill-as-a-model-plan.md` increment 3 says so out loud -- so the two
        answers a bill can give are settled and owed. Nothing was affected when
        it went: development and production both held zero archived bills when
        the conversion ran.
        """
        self.bill("Old subscription", amount="9.00")

        self.assertEqual([row.payee for row in self.month().bills],
                         ["Old subscription"])
        self.assertFalse(self.month().bills[0].paid)

    def test_an_unpaid_bill_is_not_marked_paid(self):
        """The other side of the flag, so `paid` cannot be a constant."""
        self.bill("Internet", amount="64.99")

        self.assertFalse(self.month().bills[0].paid)

    def test_an_ordinary_task_is_not_here(self):
        """It never could be now -- a task is not in this table at all -- which
        is the guarantee the sidecar shape could only approximate with a
        filter."""
        services.create_item(self.list_, "Ordinary task", due_date=MID_AUGUST)

        self.assertEqual(self.month().bills, [])

    def test_one_person_never_sees_anothers_bills(self):
        """The isolation test principles.md asks of every owner-scoped read."""
        self.bill("Bob's rent", owner=self.other)

        found = self.month()

        self.assertEqual(found.bills, [])
        self.assertEqual(found.due_totals, {})
        self.assertEqual(found.paid_totals, {})
