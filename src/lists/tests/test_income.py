"""Money coming in, tracked beside money going out.

`money-module-plan.md`, after Vince widened the surface: *"I think I will want
to include income and investments."* This is the income half.

**One model, not two.** `architecture-trajectory.md` §4: a concept earns its own
model when it has a different life cycle, not when it has a different name.
Income recurs, has a date, has an amount, gets settled, can be late. That is a
bill's life cycle exactly, so `Bill` carries a `direction` and income is not a
second table duplicating cadence, dates and settlement. **That argument held
through the split**: `bill-as-a-model-plan.md` separated bills from *tasks*, on
a life-cycle difference income does not have.

**But it is not a task, and this is the difference that shows.** You do not tick
off being paid. Income is excluded from the day and the agenda -- Vince's call --
so it lives on Money alone, where it can still be seen and still be called late.
`money.open_bills_for` is the single selection point both surfaces use, which is
why that costs one clause.

**The month answers three questions, not two**: what is still to pay, what has
already gone out, and what is expected in. The third is what makes *did this
month balance* answerable at all.
"""
import datetime
from decimal import Decimal

from django.test import TestCase

from accounts.models import User
from lists import agenda, bills, money as money_reader
from lists.models import Bill, Direction, Item

AUGUST = datetime.date(2026, 8, 28)


class IncomeTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )

    def a_salary(self, amount="3200.00", due=AUGUST, payee="Acme Ltd"):
        return bills.record(
            self.user,
            payee=payee,
            amount=Decimal(amount),
            due_date=due,
            direction=Direction.IN,
        )

    def a_bill(self):
        return bills.record(
            self.user, payee="Landlord", amount=Decimal("1200.00"), due_date=AUGUST
        )

    def test_it_records_money_coming_in(self):
        salary = self.a_salary()

        self.assertEqual(salary.direction, Direction.IN)
        self.assertEqual(salary.amount, Decimal("3200.00"))
        self.assertEqual(salary.payee, "Acme Ltd")

    def test_it_repeats_monthly_by_default(self):
        """The canonical income is a salary."""
        salary = self.a_salary()

        self.assertEqual(salary.series.cadence, Item.Recurrence.MONTHLY)

    def test_it_never_appears_on_the_day_or_the_agenda(self):
        """You do not tick off being paid, and "Salary" on the day page every
        month is a line nobody can act on.

        **Two reads now, not one.** A bill is not an `Item`, so this asks both
        the task selection and the bill selection, and income has to be absent
        from each. It was one clause in one query while a salary was a task;
        the exclusion moved to `money.open_bills_for` with the model.
        """
        self.a_salary()
        self.a_bill()

        self.assertEqual(list(agenda.open_items_for(self.user)), [])
        self.assertEqual(
            [row.payee for row in agenda.open_bill_rows_for(self.user)],
            ["Landlord"],
        )

    def test_the_month_reports_what_is_expected_in(self):
        self.a_salary()

        found = money_reader.month_from_bills(self.user, AUGUST)

        self.assertEqual(found.expected_in_totals, {"USD": Decimal("3200.00")})

    def test_income_is_not_counted_as_money_owed(self):
        """The defect this separation exists to prevent: a salary in the
        *still to pay* column would make every month look catastrophic."""
        self.a_salary()
        self.a_bill()

        found = money_reader.month_from_bills(self.user, AUGUST)

        self.assertEqual(found.due_totals, {"USD": Decimal("1200.00")})

    def test_receiving_it_records_what_actually_arrived(self):
        """A bonus, a raise, a short month -- the same reason a bill records
        what was paid rather than what was expected."""
        salary = self.a_salary()

        bills.settle(salary, amount=Decimal("3450.00"))

        salary.refresh_from_db()
        self.assertEqual(salary.paid_amount, Decimal("3450.00"))
        self.assertEqual(salary.amount, Decimal("3200.00"))

    def test_received_income_is_totalled_apart_from_what_is_expected(self):
        self.a_salary()
        second = self.a_salary(amount="500.00", payee="A Client")
        bills.settle(second, amount=Decimal("500.00"))

        found = money_reader.month_from_bills(self.user, AUGUST)

        self.assertEqual(found.expected_in_totals, {"USD": Decimal("3200.00")})
        self.assertEqual(found.received_totals, {"USD": Decimal("500.00")})

    def test_income_that_has_not_arrived_can_be_late(self):
        """Expected on the 1st, and it is the 15th. Worth knowing, and the
        only reason income needs a date at all."""
        salary = self.a_salary(due=datetime.date(2026, 8, 1))

        self.assertTrue(salary.overdue_on(datetime.date(2026, 8, 15)))


class TwoLinesFromOnePayeeTest(TestCase):
    """**A limitation this file used to name, removed by the split.**

    A salary and a bonus from one employer, or two Amazon subscriptions, could
    not both be open: the name was derived from the payee -- *From Acme Ltd* --
    and `unique_active_arealess_item` is `(owner, text)` over everything
    unfiled and unarchived. The refusal was the task core's rule reaching money
    through a title money never wanted.

    A `Bill` has no title and no such constraint. Kept as a test rather than
    deleted along with the old one, because *"two are allowed now"* is the sort
    of change worth being able to point at.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )

    def test_two_open_lines_from_one_payer_are_allowed(self):
        for amount in ("3200.00", "500.00"):
            bills.record(
                self.user,
                payee="Acme Ltd",
                amount=Decimal(amount),
                due_date=AUGUST,
                direction=Direction.IN,
            )

        self.assertEqual(Bill.objects.filter(payee="Acme Ltd").count(), 2)
