"""Deleting a bill, and the difference between one month and the standing one.

`bills-page-plan.md` increment 4, and Vince's decision of August 27, 2026: from
the person's side there is no task, so Delete removes the whole thing -- and if
it repeats, it asks once which thing is meant.

**The trap this file exists for.** A series only continues because completing an
occurrence spawns the next one. So deleting *this* occurrence would end the
series too, silently: no next month, no error, nothing to notice until a bill
failed to arrive. That is the same shape as the sidecar defect found an hour
earlier -- a correct piece of machinery not knowing about another one -- and it
would have shipped inside the fix for it.

**So "this month" keeps the series alive on the way out**: the next occurrence
is created before this one is removed. What a person means by removing August's
rent is *not this one*, never *stop paying rent*.

**"The standing bill" ends the series and removes this occurrence**, and leaves
every past one alone. A month that already happened is history, and
`architecture-trajectory.md` §4 rule 6 keeps a row whose existence answers
whether something happened.
"""
import datetime
from decimal import Decimal

from django.test import TestCase

from accounts.models import User
from lists import services
from lists.models import Bill, Item, RecurringCommitment

AUGUST = datetime.date(2026, 8, 10)


class DeletingABillTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )

    def a_bill(self, *, repeats=True, payee="Landlord"):
        return services.create_bill(
            self.user,
            payee=payee,
            amount=Decimal("1200.00"),
            due_date=AUGUST,
            repeats=repeats,
        )

    def live(self):
        return Item.objects.filter(owner=self.user).exclude(
            status=Item.Status.ARCHIVED
        )

    def test_a_one_off_bill_is_simply_gone(self):
        bill = self.a_bill(repeats=False)

        services.delete_bill(bill)

        self.assertFalse(Item.objects.filter(pk=bill.pk).exists())
        self.assertFalse(Bill.objects.filter(item_id=bill.pk).exists())

    def test_deleting_one_month_leaves_the_series_running(self):
        """The trap. Removing August's rent must not stop rent."""
        rent = self.a_bill()

        services.delete_bill(rent)

        self.assertFalse(Item.objects.filter(pk=rent.pk).exists())
        following = self.live()
        self.assertEqual(
            following.count(),
            1,
            "Deleting one month of a repeating bill ended the whole series. A "
            "series only continues because an occurrence was completed, so "
            "removing this one has to leave its successor behind it.",
        )

    def test_the_month_that_replaces_it_is_still_a_bill(self):
        """And it carries what a spawned occurrence carries: payee and
        currency, not the amount."""
        rent = self.a_bill()

        services.delete_bill(rent)

        nxt = self.live().get()
        carried = Bill.objects.get(item=nxt)
        self.assertEqual(carried.payee, "Landlord")
        self.assertIsNone(carried.amount)

    def test_deleting_the_standing_bill_stops_it_coming_round(self):
        rent = self.a_bill()

        services.delete_bill(rent, whole_series=True)

        self.assertFalse(Item.objects.filter(pk=rent.pk).exists())
        self.assertEqual(
            self.live().count(), 0, "Nothing should have replaced it."
        )
        commitment = RecurringCommitment.objects.get(owner=self.user)
        self.assertIsNotNone(
            commitment.ended_at,
            "The series should have been stopped, not merely left without an "
            "occupant.",
        )

    def test_ending_the_series_leaves_the_months_already_paid_alone(self):
        """What happened, happened. §4 rule 6."""
        rent = self.a_bill()
        services.complete_item(rent)
        following = self.live().get()

        services.delete_bill(following, whole_series=True)

        rent.refresh_from_db()
        # **Archived, not completed** -- `complete_item` archives a recurring
        # occupant so its successor can exist. What says it was paid is
        # `completed_at`, which is what the month's read keys on.
        self.assertIsNotNone(rent.completed_at)
        self.assertTrue(Bill.objects.filter(item=rent).exists())

    def test_it_refuses_a_task_that_is_not_a_bill(self):
        plain = services.create_item(None, "Not a bill", owner=self.user)

        with self.assertRaises(services.TaskConflict):
            services.delete_bill(plain)
