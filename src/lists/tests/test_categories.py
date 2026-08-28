"""Categories for bills, and the list belongs to the person.

`money-module-plan.md` increment 13. Vince, on seeing the month view: *"there's
like no order to the bills. Like we need to have categories to make it easier to
look at"* — and then, on being offered a fixed list, *"let's do 1, however add a
setting that lets the user manually edit the list."*

**That second clause is what makes this a table.** A list somebody can edit is
created, renamed, reordered and deleted on its own schedule — which is §4's
life-cycle test met rather than argued around, and is why `MoneyCategory` earns
a row where a `TextChoices` would not. The knowledge core's `FacetKind` is the
counter-example: nobody edits that, so it is values.

**Seeded, not empty.** A person opening the module should find Housing,
Utilities and the rest already there. An empty list plus a form is a chore
handed to somebody who came to look at their bills — and the seeds are ordinary
rows from birth, so renaming or deleting one needs no special case.

**Nullable on the bill.** *Uncategorised* is a real state and the honest
default: a bill added in a hurry should not have to answer a filing question,
which is the same reason a bill has no Area.
"""
import datetime
from decimal import Decimal

from django.test import TestCase

from accounts.models import User
from lists import services
from lists.models import MoneyCategory

AUGUST = datetime.date(2026, 8, 10)


class CategoriesTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )

    def test_a_new_person_starts_with_a_usable_list(self):
        """Not empty. Somebody who came to look at their bills should not first
        have to invent a taxonomy."""
        categories = services.categories_for(self.user)

        self.assertIn("Housing", [each.name for each in categories])
        self.assertIn("Subscriptions", [each.name for each in categories])

    def test_seeding_happens_once_however_often_it_is_asked(self):
        services.categories_for(self.user)
        services.categories_for(self.user)

        self.assertEqual(
            MoneyCategory.objects.filter(owner=self.user).count(),
            len(services.SEED_CATEGORIES),
        )

    def test_the_seeds_are_ordinary_rows(self):
        """The whole point of a table rather than an enum: a seed can be
        renamed and deleted like anything else, with no special case."""
        housing = services.categories_for(self.user).get(name="Housing")

        services.rename_category(housing, "Home")

        housing.refresh_from_db()
        self.assertEqual(housing.name, "Home")

    def test_a_person_can_add_their_own(self):
        added = services.add_category(self.user, name="Boat")

        self.assertIn("Boat", [each.name for each in services.categories_for(self.user)])
        self.assertEqual(added.owner, self.user)

    def test_two_categories_cannot_share_a_name(self):
        services.categories_for(self.user)

        with self.assertRaises(services.TaskConflict):
            services.add_category(self.user, name="Housing")

    def test_one_persons_categories_are_their_own(self):
        other = User.objects.create_user("bob", "bob@example.com", "a password")
        services.categories_for(self.user)

        services.categories_for(other)

        self.assertEqual(
            MoneyCategory.objects.filter(owner=self.user).count(),
            len(services.SEED_CATEGORIES),
        )

    def test_a_bill_starts_uncategorised(self):
        """A bill added in a hurry does not have to answer a filing question."""
        bill = services.create_bill(
            self.user, payee="Landlord", amount=Decimal("1200.00"), due_date=AUGUST
        )

        self.assertIsNone(bill.money_line.category)

    def test_a_bill_can_be_filed_and_refiled(self):
        bill = services.create_bill(
            self.user, payee="Landlord", amount=Decimal("1200.00"), due_date=AUGUST
        )
        housing = services.categories_for(self.user).get(name="Housing")

        services.update_bill(bill, category=housing)

        bill.refresh_from_db()
        self.assertEqual(bill.money_line.category, housing)

    def test_deleting_a_category_leaves_its_bills_alone(self):
        """A category is a label, not a container. Losing the label must not
        lose the bill -- which is what SET_NULL says and what this asserts,
        because it is the kind of thing a later edit gets wrong."""
        bill = services.create_bill(
            self.user, payee="Landlord", amount=Decimal("1200.00"), due_date=AUGUST
        )
        housing = services.categories_for(self.user).get(name="Housing")
        services.update_bill(bill, category=housing)

        services.delete_category(housing)

        bill.refresh_from_db()
        self.assertIsNone(bill.money_line.category)
        self.assertEqual(bill.money_line.payee, "Landlord")

    def test_renaming_to_an_existing_name_is_refused(self):
        categories = services.categories_for(self.user)
        housing = categories.get(name="Housing")

        with self.assertRaises(services.TaskConflict):
            services.rename_category(housing, "Utilities")

    def test_a_category_needs_a_name(self):
        with self.assertRaises(services.TaskConflict):
            services.add_category(self.user, name="   ")
