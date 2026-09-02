"""A bill's advance notice, which is the feature bills need most.

**Split out of `lists/tests/test_lead_time.py` on September 2, 2026**, step 3 of
the app extraction. That file tests a *task* inside its lead time and this class
tested a *bill*, sitting in the task core's test package and importing
`lists.bills` to do it. The two rules are genuinely parallel and deliberately
share `clarice.recurrence`; the tests belong to different apps.

The task half stays where it was, and says so.
"""
import datetime
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from clarice.recurrence import Recurrence
from money import reads as money
from money import services as bills


class ABillsLeadTimeSurvivesTheModelSplitTest(TestCase):
    """Advance notice is the feature bills need most, and the flip is where it
    could have gone quiet.

    `coming_up_for` reads `open_items_for`, which returns no bills after
    increment 4 of `bill-as-a-model-plan.md`. *"Property tax, in seven days"*
    is the archetypal case for a lead time and it is a bill, so losing it would
    have removed the reason lead times exist while every test named for one
    kept passing -- they all use tasks.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            "vince", "vince@example.com", "a secure password"
        )
        self.today = timezone.localdate()

    def bill(self, payee, *, due_in, lead=0, **kwargs):
        return bills.record(
            self.user,
            payee=payee,
            amount=Decimal("400.00"),
            due_date=self.today + datetime.timedelta(days=due_in),
            lead_days=lead,
            **kwargs,
        )

    def coming(self):
        return [row.payee for row in money.coming_bills_for(self.user, self.today)]

    def test_a_bill_inside_its_lead_time_is_coming_up(self):
        self.bill("Property tax", due_in=5, lead=7)

        self.assertEqual(self.coming(), ["Property tax"])

    def test_a_bill_outside_its_lead_time_is_not_mentioned_yet(self):
        self.bill("Property tax", due_in=30, lead=7)

        self.assertEqual(self.coming(), [])

    def test_a_bill_due_today_is_not_also_coming_up(self):
        """Strictly after today, the same rule the task version follows: a
        thing said twice in one email is how a reminder starts being skimmed.
        """
        self.bill("Property tax", due_in=0, lead=7)

        self.assertEqual(self.coming(), [])

    def test_no_lead_time_means_no_advance_notice(self):
        self.bill("Property tax", due_in=5)

        self.assertEqual(self.coming(), [])

    def test_a_settled_bill_is_not_coming_up(self):
        settled = self.bill("Property tax", due_in=5, lead=7)
        bills.settle(settled)

        self.assertEqual(self.coming(), [])
