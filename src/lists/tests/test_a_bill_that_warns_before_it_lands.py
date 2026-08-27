"""An annual subscription says so before it renews, not after it charges.

`bills-page-plan.md` increment 7, and the thing the money module is actually
for -- Vince, August 27, 2026: *"in particular when I sign up for an annual
subscription when it's about to expire."* Sign up in March, forget, get charged
the following March is the failure; a month's warning is the fix.

**The whole mechanism already existed and nothing reached it.** `Item.lead_days`
means *how many days before its due date this should be mentioned*;
`agenda.py` surfaces anything inside its lead time; `_spawn_next_occurrence`
carries it to the next occurrence. What was missing is that a person creating a
bill could not set either the cadence or the lead time, because the form offered
one checkbox meaning monthly.

**`lead_days` stays on the task and not on the bill**, which the field's own
comment settled before this: *a lead time is not a property of costing money --
"remind me before the MOT" is the same sentence.* This test exists to make sure
a bill can reach it, not to move it.
"""
import datetime
from decimal import Decimal

from django.test import TestCase

from accounts.models import User
from lists import services
from lists.models import Item

MARCH = datetime.date(2027, 3, 14)


class ABillThatWarnsBeforeItLandsTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )

    def test_an_annual_subscription_can_be_created(self):
        """Quarterly and annual are what the model has always offered and the
        form never did -- and they are the ones a person genuinely forgets."""
        sub = services.create_bill(
            self.user,
            payee="Adobe",
            amount=Decimal("239.88"),
            due_date=MARCH,
            recurrence=Item.Recurrence.ANNUAL,
        )

        self.assertEqual(sub.recurrence, Item.Recurrence.ANNUAL)

    def test_it_can_be_told_to_speak_up_early(self):
        sub = services.create_bill(
            self.user,
            payee="Adobe",
            amount=Decimal("239.88"),
            due_date=MARCH,
            recurrence=Item.Recurrence.ANNUAL,
            lead_days=30,
        )

        self.assertEqual(sub.lead_days, 30)

    def test_the_warning_survives_into_next_year(self):
        """The point of setting it once. A lead time that had to be re-entered
        every renewal would be forgotten in exactly the same way the renewal
        is."""
        sub = services.create_bill(
            self.user,
            payee="Adobe",
            amount=Decimal("239.88"),
            due_date=MARCH,
            recurrence=Item.Recurrence.ANNUAL,
            lead_days=30,
        )

        services.complete_item(sub)

        following = Item.objects.filter(
            owner=self.user, completed_at__isnull=True
        ).get()
        self.assertEqual(following.lead_days, 30)
        self.assertEqual(following.recurrence, Item.Recurrence.ANNUAL)

    def test_a_lead_time_is_optional_and_off_by_default(self):
        """Zero is off, not "the day itself" -- otherwise every dated bill in
        the product joins the advance reminder."""
        rent = services.create_bill(
            self.user, payee="Landlord", amount=Decimal("1200.00"), due_date=MARCH
        )

        self.assertEqual(rent.lead_days, 0)

    def test_it_refuses_a_cadence_that_is_not_one(self):
        with self.assertRaises(services.TaskConflict):
            services.create_bill(
                self.user,
                payee="Adobe",
                amount=Decimal("10.00"),
                due_date=MARCH,
                recurrence="fortnightly",
            )

    def test_the_lead_time_can_be_changed_later(self):
        """Thirty days turns out to be too late once, and then you want sixty."""
        sub = services.create_bill(
            self.user,
            payee="Adobe",
            amount=Decimal("239.88"),
            due_date=MARCH,
            recurrence=Item.Recurrence.ANNUAL,
            lead_days=30,
        )

        services.update_bill(sub, lead_days=60)

        sub.refresh_from_db()
        self.assertEqual(sub.lead_days, 60)
