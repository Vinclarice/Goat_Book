"""Money coming in, tracked beside money going out.

`money-module-plan.md`, after Vince widened the surface: *"I think I will want
to include income and investments."* This is the income half.

**One model, not two.** `architecture-trajectory.md` §4: a concept earns its own
model when it has a different life cycle, not when it has a different name.
Income recurs, has a date, has an amount, gets settled, can be late. That is a
bill's life cycle exactly, so `MoneyLine` carries a `direction` and income is
not a second table duplicating recurrence, dates and settlement.

**But it is not a task, and this is the difference that shows.** You do not tick
off being paid. Income is excluded from the day and the agenda -- Vince's call --
so it lives on Money alone, where it can still be seen and still be called late.
`agenda.open_items_for` is the single selection point both surfaces use, which
is why that costs one clause.

**The month answers three questions, not two**: what is still to pay, what has
already gone out, and what is expected in. The third is what makes *did this
month balance* answerable at all.
"""
import datetime
from decimal import Decimal

from django.test import TestCase

from accounts.models import User
from lists import agenda, money as money_reader, services
from lists.models import Direction, Item, MoneyLine

AUGUST = datetime.date(2026, 8, 28)


class IncomeTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )

    def a_salary(self, amount="3200.00", due=AUGUST, payer="Acme Ltd"):
        return services.create_income(
            self.user,
            payer=payer,
            amount=Decimal(amount),
            due_date=due,
        )

    def test_it_records_money_coming_in(self):
        salary = self.a_salary()

        line = MoneyLine.objects.get(item=salary)
        self.assertEqual(line.direction, Direction.IN)
        self.assertEqual(line.amount, Decimal("3200.00"))
        self.assertEqual(line.payee, "Acme Ltd")

    def test_the_name_comes_from_who_pays(self):
        """`Pay Landlord` for a bill; `From Acme Ltd` for income. Neither asks
        for a task title, which is the whole point of the module."""
        salary = self.a_salary()

        self.assertEqual(salary.text, "From Acme Ltd")

    def test_it_repeats_monthly_by_default(self):
        """The canonical income is a salary."""
        salary = self.a_salary()

        self.assertEqual(salary.recurrence, Item.Recurrence.MONTHLY)

    def test_it_never_appears_on_the_day_or_the_agenda(self):
        """You do not tick off being paid, and "Salary" on the day page every
        month is a line nobody can act on."""
        self.a_salary()
        services.create_bill(
            self.user, payee="Landlord", amount=Decimal("1200.00"), due_date=AUGUST
        )

        open_items = list(agenda.open_items_for(self.user))

        self.assertEqual([item.text for item in open_items], ["Pay Landlord"])

    def test_the_month_reports_what_is_expected_in(self):
        self.a_salary()

        found = money_reader.bills_for(self.user, AUGUST)

        self.assertEqual(found.expected_in_totals, {"USD": Decimal("3200.00")})

    def test_income_is_not_counted_as_money_owed(self):
        """The defect this separation exists to prevent: a salary in the
        *still to pay* column would make every month look catastrophic."""
        self.a_salary()
        services.create_bill(
            self.user, payee="Landlord", amount=Decimal("1200.00"), due_date=AUGUST
        )

        found = money_reader.bills_for(self.user, AUGUST)

        self.assertEqual(found.due_totals, {"USD": Decimal("1200.00")})

    def test_receiving_it_records_what_actually_arrived(self):
        """A bonus, a raise, a short month -- the same reason a bill records
        what was paid rather than what was expected."""
        salary = self.a_salary()

        services.pay_bill(salary, amount=Decimal("3450.00"))

        line = MoneyLine.objects.get(item=salary)
        self.assertEqual(line.paid_amount, Decimal("3450.00"))
        self.assertEqual(line.amount, Decimal("3200.00"))

    def test_received_income_is_totalled_apart_from_what_is_expected(self):
        self.a_salary()
        # A different payer, because the name is derived from it and two open
        # lines from one payee collide -- see `create_bill`'s own note on why
        # that is accepted rather than designed around.
        second = self.a_salary(amount="500.00", payer="A Client")
        services.pay_bill(second, amount=Decimal("500.00"))

        found = money_reader.bills_for(self.user, AUGUST)

        self.assertEqual(found.expected_in_totals, {"USD": Decimal("3200.00")})
        self.assertEqual(found.received_totals, {"USD": Decimal("500.00")})

    def test_income_that_has_not_arrived_can_be_late(self):
        """Expected on the 28th, and it is the 30th. Worth knowing, and the
        only reason income needs a date at all."""
        salary = self.a_salary(due=datetime.date(2026, 8, 1))

        row = next(
            r
            for r in money_reader.bills_for(self.user, AUGUST).bills
            if r.task.pk == salary.pk
        )

        self.assertTrue(row.overdue_on(datetime.date(2026, 8, 15)))


class TwoLinesFromOnePayeeTest(TestCase):
    """A real limitation, named so nobody rediscovers it as a bug.

    The name is derived from the payee and `unique_active_arealess_item` is
    `(owner, text)` over everything unfiled and unarchived -- so two open lines
    from the same payee cannot both exist. Two Amazon subscriptions, or a salary
    and a bonus from one employer, are the cases that meet it.

    **Accepted rather than designed around**: putting an amount or a number into
    every name to serve the rarer case makes *Pay Landlord* worse for the common
    one. What this test holds is that the refusal *says something useful*, since
    the underlying message is about a list and there is no list here.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )

    def test_a_second_open_bill_from_one_payee_is_refused_in_words(self):
        services.create_bill(
            self.user, payee="Amazon", amount=Decimal("7.99"), due_date=AUGUST
        )

        with self.assertRaises(services.TaskConflict) as caught:
            services.create_bill(
                self.user, payee="Amazon", amount=Decimal("4.99"), due_date=AUGUST
            )

        message = str(caught.exception)
        self.assertIn("already an open bill from Amazon", message)
        # **It has to say how to get through it.** A refusal that only refuses
        # sends somebody back to a form with no idea what to change.
        self.assertIn("Amazon (Prime)", message)

    def test_income_says_income_rather_than_bill(self):
        services.create_income(
            self.user, payer="Acme Ltd", amount=Decimal("3200.00"), due_date=AUGUST
        )

        with self.assertRaises(services.TaskConflict) as caught:
            services.create_income(
                self.user, payer="Acme Ltd", amount=Decimal("50.00"), due_date=AUGUST
            )

        message = str(caught.exception)
        self.assertIn("already an open income from Acme Ltd", message)
        self.assertIn("Acme Ltd (Prime)", message)
