"""Every two weeks, which a salary often is and the model had no word for.

`money-module-plan.md` increment 12. Vince, on seeing the module: *"for income,
there needs to be a bi-weekly frequency option."*

**Cheap, and worth saying why.** `_nth_occurrence_after` already advances weekly
by `timedelta(weeks=n)`, so a fortnight is one more branch and not a new kind of
arithmetic. And **recurrence is not one of the rules mirrored across three
languages** — the phone does not model it at all — so this is Python plus a
label in TypeScript, rather than the three-way hand-port
`mirrored-rules-brief.md` describes.

**26 a year**, which matters for the landing page's yearly figure: a fortnightly
salary is not a monthly one, and counting it twelve times would understate it by
a sixth.
"""
import datetime
from decimal import Decimal

from django.test import TestCase

from accounts.models import User
from lists import money as money_reader, services
from lists.models import Item

AUGUST = datetime.date(2026, 8, 14)


class FortnightlyTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )

    def test_it_is_a_cadence_a_person_can_choose(self):
        salary = services.create_income(
            self.user,
            payer="Acme Ltd",
            amount=Decimal("1600.00"),
            due_date=AUGUST,
            recurrence=Item.Recurrence.FORTNIGHTLY,
        )

        self.assertEqual(salary.recurrence, Item.Recurrence.FORTNIGHTLY)

    def test_the_next_one_lands_two_weeks_later(self):
        salary = services.create_income(
            self.user,
            payer="Acme Ltd",
            amount=Decimal("1600.00"),
            due_date=AUGUST,
            recurrence=Item.Recurrence.FORTNIGHTLY,
        )

        services.pay_bill(salary)

        following = Item.objects.filter(
            owner=self.user, completed_at__isnull=True
        ).get()
        self.assertEqual(following.due_date, datetime.date(2026, 8, 28))

    def test_it_counts_twenty_six_times_a_year(self):
        """Twelve would understate a fortnightly figure by a sixth, which is
        the sort of error a yearly total exists to avoid rather than make."""
        services.create_bill(
            self.user,
            payee="Cleaner",
            amount=Decimal("50.00"),
            due_date=AUGUST,
            recurrence=Item.Recurrence.FORTNIGHTLY,
        )

        found = money_reader.landing_for(self.user, today=AUGUST)

        self.assertEqual(found.yearly_totals, {"USD": Decimal("1300.00")})

    def test_it_carries_into_the_next_occurrence(self):
        """Set once, like every other cadence."""
        salary = services.create_income(
            self.user,
            payer="Acme Ltd",
            amount=Decimal("1600.00"),
            due_date=AUGUST,
            recurrence=Item.Recurrence.FORTNIGHTLY,
        )

        services.pay_bill(salary)

        following = Item.objects.filter(
            owner=self.user, completed_at__isnull=True
        ).get()
        self.assertEqual(following.recurrence, Item.Recurrence.FORTNIGHTLY)
