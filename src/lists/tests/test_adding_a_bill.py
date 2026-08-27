"""A bill can be created where bills are, without anybody saying "task".

`money-module-plan.md` increment 2. Until now the only way to make one was to
create a *task* somewhere else, open its detail page, and fill in amount and
payee -- so the page named after the concept could not produce one, and the
empty state was a dead end with two links, both to other empty months.

**The model is not what changes.** `architecture-trajectory.md` §4 decided a
bill is a sidecar on `Item` because its life cycle *is* a recurring task's, and
that stays. What changes is that the surface stops making the person live with
that decision: this service writes the `Item` and the `MoneyLine` together, and the
form above it asks only about money and dates.

**The name is derived from the payee** -- Vince's call, August 27, 2026 -- so
the form has one box fewer and never asks for a task title. `Landlord` becomes
*Pay Landlord*. A person who wants a different name can still rename the task
anywhere tasks are named; this is about what adding a bill costs, not about
taking the name away.

**Repeating is the default**, because the canonical bill is rent and the
vision document's own canonical recurring task is "pay rent every month".
"""
import datetime
from decimal import Decimal

from django.test import TestCase

from accounts.models import User
from lists import services
from lists.models import MoneyLine, Item

AUGUST = datetime.date(2026, 8, 10)


class AddingABillTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )

    def test_it_creates_the_task_and_the_bill_together(self):
        item = services.create_bill(
            self.user,
            payee="Landlord",
            amount=Decimal("1200.00"),
            currency="USD",
            due_date=AUGUST,
        )

        self.assertEqual(item.owner, self.user)
        self.assertEqual(item.due_date, AUGUST)
        bill = MoneyLine.objects.get(item=item)
        self.assertEqual(bill.amount, Decimal("1200.00"))
        self.assertEqual(bill.currency, "USD")
        self.assertEqual(bill.payee, "Landlord")

    def test_the_name_comes_from_the_payee(self):
        """So that adding a bill never asks for a task title."""
        item = services.create_bill(
            self.user, payee="Landlord", amount=Decimal("1200.00"), due_date=AUGUST
        )

        self.assertEqual(item.text, "Pay Landlord")

    def test_it_repeats_monthly_by_default(self):
        item = services.create_bill(
            self.user, payee="Landlord", amount=Decimal("1200.00"), due_date=AUGUST
        )

        self.assertEqual(item.recurrence, Item.Recurrence.MONTHLY)
        self.assertIsNotNone(
            item.commitment_id,
            "A repeating bill needs the series identity every repeating task "
            "gets, or it will not spawn its next occurrence.",
        )

    def test_a_one_off_bill_does_not_repeat(self):
        item = services.create_bill(
            self.user,
            payee="Plumber",
            amount=Decimal("90.00"),
            due_date=AUGUST,
            repeats=False,
        )

        self.assertEqual(item.recurrence, Item.Recurrence.NONE)

    def test_a_bill_with_no_amount_yet_is_allowed(self):
        """"The water bill, whatever it comes to" is a real bill, and the
        month's read already counts unpriced ones rather than totalling them."""
        item = services.create_bill(
            self.user, payee="City Utilities", amount=None, due_date=AUGUST
        )

        self.assertIsNone(MoneyLine.objects.get(item=item).amount)

    def test_it_needs_a_payee_because_the_name_depends_on_one(self):
        with self.assertRaises(services.TaskConflict):
            services.create_bill(
                self.user, payee="   ", amount=Decimal("10.00"), due_date=AUGUST
            )

    def test_it_belongs_to_no_area(self):
        """A bill is not filed. `create_item` gained a standing owner exactly
        so a task could exist without one, and asking which Area rent goes in
        is the filing question this page exists to avoid."""
        item = services.create_bill(
            self.user, payee="Landlord", amount=Decimal("1200.00"), due_date=AUGUST
        )

        self.assertIsNone(item.list_id)


class ARepeatingBillStaysABillTest(TestCase):
    """Paying rent must not stop rent being a bill.

    **Found while building increment 2, August 27, 2026, and it would have
    sunk it.** `_spawn_next_occurrence` never touched `MoneyLine`, so completing a
    repeating bill produced a plain task for next month with no sidecar -- and
    a task with no sidecar does not appear on the bills page at all. "Repeats
    monthly", on by default, would have given a page that emptied itself one
    payment at a time.

    **Payee and currency carry; the amount does not.** That is `set_bill`'s own
    reasoning and it is right: *what a bill comes to is a fact about this
    occurrence -- last quarter's was 500 and this one is 525* -- so inventing
    next month's number would state something nobody has been told. What
    arrives instead is an unpriced bill from a known payee, which is exactly
    the case `MonthOfBills.unpriced` was built to count.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )

    def test_paying_a_repeating_bill_leaves_next_months_bill_behind_it(self):
        rent = services.create_bill(
            self.user,
            payee="Landlord",
            amount=Decimal("1200.00"),
            due_date=AUGUST,
        )

        services.complete_item(rent)

        following = Item.objects.filter(
            owner=self.user, status=Item.Status.ACTIVE
        ).exclude(pk=rent.pk)
        self.assertEqual(following.count(), 1, "the next occurrence should exist")
        nxt = following.get()
        self.assertTrue(
            MoneyLine.objects.filter(item=nxt).exists(),
            "Next month's rent is not a bill, so it will never appear on the "
            "page that exists to show bills.",
        )

    def test_the_payee_and_currency_carry_and_the_amount_does_not(self):
        rent = services.create_bill(
            self.user,
            payee="Landlord",
            amount=Decimal("1200.00"),
            currency="GBP",
            due_date=AUGUST,
        )

        services.complete_item(rent)

        nxt = Item.objects.filter(owner=self.user, status=Item.Status.ACTIVE).get()
        carried = MoneyLine.objects.get(item=nxt)
        self.assertEqual(carried.payee, "Landlord")
        self.assertEqual(carried.currency, "GBP")
        self.assertIsNone(
            carried.amount,
            "An amount carried forward is a number nobody has been told yet.",
        )

    def test_a_one_off_bill_leaves_nothing_behind(self):
        plumber = services.create_bill(
            self.user,
            payee="Plumber",
            amount=Decimal("90.00"),
            due_date=AUGUST,
            repeats=False,
        )

        services.complete_item(plumber)

        self.assertFalse(
            Item.objects.filter(owner=self.user, status=Item.Status.ACTIVE).exists()
        )
