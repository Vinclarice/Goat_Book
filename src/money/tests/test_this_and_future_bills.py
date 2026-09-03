"""Editing the standing arrangement, not just this month of it.

**The model has distinguished a `Bill` from its `BillSeries` since increment 1,
and the interface has only ever edited occurrences.** `revise_series` accepts
payee, amount, lead days, cadence, category and account; the only one anything
could reach was cadence, through `set_cadence` on the occurrence form. Six
fields of live code no surface could call — built and dark, which this
repository treats as a defect with a deadline rather than a spare part.

**So the question a person is actually asking gets asked back.** Rent went up:
is that August, or is that rent? Both are real and the answers differ, and until
now the product could only record the first — you corrected September, and
October arrived at the old figure.

**The vocabulary is the delete path's, deliberately.**
`DELETE /money/bills/entry/{id}?whole_series=true` already draws exactly this
line — *"removing August's rent is not the same act as stopping rent"* — so the
edit says `whole_series` too rather than inventing a second word for one
distinction.

**Three rules this holds, each of which could reasonably have gone the other
way and did not:**

- **What was already paid never changes.** §4 rule 3 is that occurrences
  snapshot rather than read through, and a settled bill is a record of money
  that moved. Renaming a payee in March leaves January saying what January said.
- **Later unpaid occurrences do change**, because *this and future* has to mean
  it. `catch_up` and `spawn_next` both create rows ahead of time, so a promise
  that only touched the series would be silently false for every occurrence that
  already existed.
- **A due date is never a series edit.** When a bill falls is the cadence's
  answer, not a field to broadcast; moving one occurrence's date moves that
  occurrence.
"""
import datetime
from decimal import Decimal

from django.test import Client, TestCase

from accounts.models import User
from clarice.recurrence import Recurrence
from money import services as bills
from money.models import Account, AccountKind, Bill, MoneyCategory

JUNE = datetime.date(2026, 6, 1)
PASSWORD = "a secure password"


class ReviseFromTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("alice", "alice@example.com", PASSWORD)

    def rent(self, due=JUNE):
        return bills.record(
            self.user, payee="Landlord", amount=Decimal("1200.00"),
            due_date=due, recurrence=Recurrence.MONTHLY,
        )

    def owed(self):
        return list(
            Bill.objects.filter(owner=self.user, paid_at__isnull=True)
            .order_by("due_date")
        )

    def test_it_changes_the_standing_rule(self):
        rent = self.rent()

        bills.revise_from(rent, amount=Decimal("1300.00"))

        rent.series.refresh_from_db()
        self.assertEqual(rent.series.amount, Decimal("1300.00"))

    def test_it_changes_this_occurrence_too(self):
        """*This* and future. A rule that took effect only next month would be
        the thing somebody was already able to do."""
        rent = self.rent()

        bills.revise_from(rent, amount=Decimal("1300.00"))

        rent.refresh_from_db()
        self.assertEqual(rent.amount, Decimal("1300.00"))

    def test_it_reaches_later_occurrences_that_already_exist(self):
        """`catch_up` and `spawn_next` create rows ahead of time, so a promise
        that only revised the template would be false for every occurrence
        already sitting there."""
        rent = self.rent()
        bills.catch_up(self.user, today=datetime.date(2026, 8, 1))
        self.assertEqual(len(self.owed()), 3)

        bills.revise_from(rent, payee="New Landlord")

        self.assertEqual({b.payee for b in self.owed()}, {"New Landlord"})

    def test_it_leaves_earlier_occurrences_alone(self):
        """Rent went up in September; August was still what August was."""
        june = self.rent()
        bills.catch_up(self.user, today=datetime.date(2026, 8, 1))
        august = self.owed()[-1]

        bills.revise_from(august, amount=Decimal("1300.00"))

        june.refresh_from_db()
        self.assertEqual(june.amount, Decimal("1200.00"))

    def test_it_never_rewrites_what_was_paid(self):
        """§4 rule 3, and the reason occurrences snapshot at all: a settled bill
        is a record of money that actually moved."""
        june = self.rent()
        bills.settle(june, amount=Decimal("1200.00"), today=JUNE)
        july = self.owed()[0]

        bills.revise_from(july, payee="New Landlord", amount=Decimal("1300.00"))

        june.refresh_from_db()
        self.assertEqual(june.payee, "Landlord")
        self.assertEqual(june.paid_amount, Decimal("1200.00"))

    def test_it_moves_the_account_and_the_category(self):
        card = bills.create_account(self.user, name="Amex", kind=AccountKind.CARD)
        housing = bills.add_category(self.user, name="Housing")
        rent = self.rent()

        bills.revise_from(rent, account=card, category=housing)

        rent.refresh_from_db()
        rent.series.refresh_from_db()
        self.assertEqual(rent.account, card)
        self.assertEqual(rent.series.account, card)
        self.assertEqual(rent.series.category, housing)

    def test_it_moves_the_lead_time(self):
        rent = self.rent()

        bills.revise_from(rent, lead_days=30)

        rent.refresh_from_db()
        rent.series.refresh_from_db()
        self.assertEqual(rent.lead_days, 30)
        self.assertEqual(rent.series.lead_days, 30)

    def test_a_one_off_has_no_series_and_is_simply_edited(self):
        """Asking *this or all* about a bill that happens once is a question
        with one answer, so the caller is not made to care."""
        plumber = bills.record(
            self.user, payee="Plumber", amount=Decimal("90.00"),
            due_date=JUNE, repeats=False,
        )

        bills.revise_from(plumber, amount=Decimal("110.00"))

        plumber.refresh_from_db()
        self.assertEqual(plumber.amount, Decimal("110.00"))
        self.assertIsNone(plumber.series)

    def test_an_empty_payee_is_refused_as_it_is_on_one_occurrence(self):
        rent = self.rent()

        with self.assertRaises(bills.BillConflict):
            bills.revise_from(rent, payee="   ")

    def test_clearing_an_amount_carries_forward_too(self):
        """*"The water bill, whatever it comes to"* is a standing arrangement
        somebody can choose, not only a fact about one month."""
        water = bills.record(
            self.user, payee="Water", amount=Decimal("60.00"),
            due_date=JUNE, recurrence=Recurrence.MONTHLY,
        )

        bills.revise_from(water, clear_amount=True)

        water.refresh_from_db()
        water.series.refresh_from_db()
        self.assertIsNone(water.amount)
        self.assertIsNone(water.series.amount)


class TheEditEndpointAsksWhichTest(TestCase):
    """`PATCH /money/bills/entry/{id}` with `whole_series`, mirroring the delete
    path's query parameter rather than inventing a second word."""

    def setUp(self):
        self.user = User.objects.create_user("alice", "alice@example.com", PASSWORD)
        self.client = Client()
        self.client.force_login(self.user)
        self.rent = bills.record(
            self.user, payee="Landlord", amount=Decimal("1200.00"),
            due_date=JUNE, recurrence=Recurrence.MONTHLY,
        )

    def patch(self, **body):
        return self.client.patch(
            f"/api/v1/money/bills/entry/{self.rent.id}",
            data=body, content_type="application/json",
        )

    def test_by_default_it_edits_this_one_only(self):
        """Absent is the narrow act, which is the delete path's default and for
        its reason: the wider answer is the one that cannot be undone by
        editing something back."""
        response = self.patch(amount="1300.00")

        self.assertEqual(response.status_code, 200)
        self.rent.series.refresh_from_db()
        self.assertEqual(self.rent.series.amount, Decimal("1200.00"))

    def test_whole_series_reaches_the_standing_rule(self):
        response = self.patch(amount="1300.00", whole_series=True)

        self.assertEqual(response.status_code, 200)
        self.rent.series.refresh_from_db()
        self.assertEqual(self.rent.series.amount, Decimal("1300.00"))

    def test_it_answers_with_the_occurrence_either_way(self):
        body = self.patch(payee="New Landlord", whole_series=True).json()

        self.assertEqual(body["payee"], "New Landlord")
        self.assertEqual(body["id"], self.rent.id)

    def test_a_due_date_is_never_a_series_edit(self):
        """When a bill falls is the cadence's answer. Moving one occurrence's
        date moves that occurrence, `whole_series` or not -- there is no field
        on the rule for it to reach."""
        self.patch(due_date="2026-06-05", whole_series=True)

        self.rent.refresh_from_db()
        self.assertEqual(self.rent.due_date, datetime.date(2026, 6, 5))

    def test_the_cadence_is_series_level_whichever_is_asked(self):
        """It always was: a cadence on one occurrence is not a thing, so
        `set_cadence` has changed the rule since the day it was written."""
        self.patch(recurrence=Recurrence.ANNUAL)

        self.rent.refresh_from_db()
        self.assertEqual(self.rent.series.cadence, Recurrence.ANNUAL)
