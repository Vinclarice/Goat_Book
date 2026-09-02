"""Increment 6 of `design/bill-as-a-model-plan.md` — the life-cycle difference
that justified the model, made real.

**This is the argument the split was made on.** `architecture-trajectory.md` §4
grants a model when a concept has a different life cycle, and §2 of the plan
names it: the same event — a period elapsing unfinished — must produce opposite
outcomes. Five missed bin rounds are five things that did not happen, and
`principles.md` refuses to invent them. **A payment you did not make is still
owed**, whether or not any row says so.

**Measured before it was built**, September 1, 2026, which is what
`roadmap.md`'s entry asked for. In this checkout: *American Express*, monthly,
due August 20, unpaid — and **exactly one occurrence exists**. There is no
September row and there never will be, because the only thing that creates a
successor is settling or deleting the current one. A bill you fall behind on
stops being mentioned at all, which is precisely backwards: the further behind
you are, the less the module tells you.

That is worse than the shape `roadmap.md` predicted (*"paid in August,
schedules September, July is gone"*), and it is the same doctrine underneath.

**Two mechanisms, and both had to move.**

- `spawn_next` skipped. It advanced past *today*, so paying June's rent in
  August produced September's and July's was never owed by anybody.
- Nothing generated occurrences except settlement. So a series nobody touches
  never grows, whatever the calendar does.

**And what it deliberately does not do.** It does not replay a *floating*
series: floating counts from when the work was done, so by construction there
is no missed period to replay — `_advance_due_date` says so and this file
tests it rather than restating it. It asks nobody to confirm anything, because
`modules.md`'s input ratio counts a confirmation prompt as feeding. And it
creates nothing dated after today: a bill not yet due is not owed.
"""
import datetime
from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.db.utils import IntegrityError
from django.test import TestCase

from accounts.models import User
from money import services as bills
from lists.models import CadenceMode, Item
from money.models import Bill, BillSeries

JUNE = datetime.date(2026, 6, 1)
AUGUST = datetime.date(2026, 8, 10)


class ReplayingAMissedPeriodTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )

    def rent(self, due=JUNE, cadence=Item.Recurrence.MONTHLY):
        return bills.record(
            self.user,
            payee="Landlord",
            amount=Decimal("1200.00"),
            due_date=due,
            recurrence=cadence,
        )

    def owed(self):
        return [
            b.due_date
            for b in Bill.objects.filter(owner=self.user, paid_at__isnull=True)
            .order_by("due_date")
        ]

    def test_a_series_nobody_touches_still_grows(self):
        """**The defect measured in this checkout.** Amex, monthly, due August
        20 and unpaid, had one occurrence and would have had one forever."""
        self.rent()

        bills.catch_up(self.user, today=AUGUST)

        self.assertEqual(
            self.owed(),
            [JUNE, datetime.date(2026, 7, 1), datetime.date(2026, 8, 1)],
            "June was owed, July came and went, August came and went.",
        )

    def test_nothing_is_created_beyond_today(self):
        """A bill not yet due is not owed. September's rent on August 10 would
        be a forecast wearing the same clothes as a debt."""
        self.rent()

        bills.catch_up(self.user, today=AUGUST)

        self.assertNotIn(datetime.date(2026, 9, 1), self.owed())

    def test_an_occurrence_falling_exactly_on_today_is_owed(self):
        """The boundary, said out loud. Rent due today is due today -- unlike
        `_advance_due_date`'s `>`, which drops the slot the *completion* lands
        on because that slot was just satisfied. Nothing has satisfied this
        one."""
        self.rent()

        bills.catch_up(self.user, today=datetime.date(2026, 7, 1))

        self.assertIn(datetime.date(2026, 7, 1), self.owed())

    def test_running_it_twice_creates_nothing_new(self):
        """Idempotent, because it will run on a schedule and a second pass in
        the same day must not double a person's rent."""
        self.rent()
        bills.catch_up(self.user, today=AUGUST)
        before = self.owed()

        bills.catch_up(self.user, today=AUGUST)

        self.assertEqual(self.owed(), before)

    def test_a_replayed_occurrence_is_unpriced(self):
        """`spawn_next`'s rule, and for its reason: what a bill comes to is a
        fact about *this* occurrence. Carrying June's figure into August would
        state something nobody has been told."""
        self.rent()

        bills.catch_up(self.user, today=AUGUST)

        august = Bill.objects.get(owner=self.user, due_date=datetime.date(2026, 8, 1))
        self.assertIsNone(august.amount)
        self.assertEqual(august.payee, "Landlord")

    def test_a_replayed_occurrence_belongs_to_the_series(self):
        self.rent()

        bills.catch_up(self.user, today=AUGUST)

        series = BillSeries.objects.get()
        self.assertEqual(Bill.objects.filter(series=series).count(), 3)

    def test_a_one_off_is_never_replayed(self):
        """It happens once. That is the whole of what one-off means."""
        bills.record(
            self.user, payee="Plumber", amount=Decimal("90.00"),
            due_date=JUNE, repeats=False,
        )

        bills.catch_up(self.user, today=AUGUST)

        self.assertEqual(self.owed(), [JUNE])

    def test_an_ended_series_is_not_replayed(self):
        """Stopping a bill means stopping it. A series that ends in June does
        not owe you July."""
        rent = self.rent()
        bills.remove(rent, whole_series=True, today=JUNE)

        bills.catch_up(self.user, today=AUGUST)

        self.assertEqual(self.owed(), [])

    def test_a_floating_series_is_not_replayed(self):
        """**By construction, not by exception.** Floating counts from when the
        work was done, so there is no period that elapsed unnoticed --
        `_advance_due_date` makes that argument for tasks and it survives
        unchanged here."""
        rent = self.rent()
        rent.series.cadence_mode = CadenceMode.FLOATING
        rent.series.save(update_fields=["cadence_mode"])

        bills.catch_up(self.user, today=AUGUST)

        self.assertEqual(self.owed(), [JUNE])

    def test_a_settled_occurrence_does_not_stop_the_replay(self):
        """Paying June in August is the case `roadmap.md` named. July is still
        owed, and used to vanish."""
        rent = self.rent()
        bills.settle(rent, today=AUGUST)

        bills.catch_up(self.user, today=AUGUST)

        self.assertEqual(self.owed(), [datetime.date(2026, 7, 1), datetime.date(2026, 8, 1)])

    def test_one_person_s_bills_are_replayed_and_not_anothers(self):
        other = User.objects.create_user("bob", "bob@example.com", "a password")
        bills.record(
            other, payee="Theirs", amount=Decimal("10.00"),
            due_date=JUNE, recurrence=Item.Recurrence.MONTHLY,
        )

        bills.catch_up(self.user, today=AUGUST)

        self.assertEqual(Bill.objects.filter(owner=other).count(), 1)

    def test_with_no_owner_it_covers_everybody(self):
        """How the scheduled pass runs: an account created tomorrow is caught
        up without anybody remembering to add it, which is the reason
        `run_mind_maintenance` takes no owner either."""
        other = User.objects.create_user("bob", "bob@example.com", "a password")
        self.rent()
        bills.record(
            other, payee="Theirs", amount=Decimal("10.00"),
            due_date=JUNE, recurrence=Item.Recurrence.MONTHLY,
        )

        bills.catch_up(today=AUGUST)

        self.assertEqual(Bill.objects.filter(owner=self.user).count(), 3)
        self.assertEqual(Bill.objects.filter(owner=other).count(), 3)

    def test_it_reports_what_it_created(self):
        """The scheduled pass prints this, and a number nobody can see is a
        job nobody can tell has stopped working."""
        self.rent()

        self.assertEqual(bills.catch_up(self.user, today=AUGUST), 2)


class SettlingNoLongerSkipsTest(TestCase):
    """`spawn_next` advanced past *today*, which is right for a task and wrong
    for a bill — the asymmetry §2 is built on, in the one function both used.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )

    def test_the_successor_is_the_next_period_not_the_next_future_one(self):
        rent = bills.record(
            self.user, payee="Landlord", amount=Decimal("1200.00"),
            due_date=JUNE, recurrence=Item.Recurrence.MONTHLY,
        )

        bills.settle(rent, today=AUGUST)

        successor = Bill.objects.get(owner=self.user, paid_at__isnull=True)
        self.assertEqual(
            successor.due_date,
            datetime.date(2026, 7, 1),
            "July was owed. It used to be skipped to September.",
        )

    def test_deleting_one_month_leaves_the_next_month_not_a_later_one(self):
        """The instance found on September 1, 2026 by a test that started
        failing for no reason but the date: deleting August's rent that day
        produced *October's*."""
        rent = bills.record(
            self.user, payee="Landlord", amount=Decimal("1200.00"),
            due_date=JUNE, recurrence=Item.Recurrence.MONTHLY,
        )

        bills.remove(rent, today=AUGUST)

        successor = Bill.objects.get(owner=self.user)
        self.assertEqual(successor.due_date, datetime.date(2026, 7, 1))

    def test_a_task_still_skips(self):
        """**The asymmetry, asserted from the other side.** If this ever fails,
        the fix for bills has leaked into the doctrine that is correct for
        tasks -- five missed bin rounds are still five things that did not
        happen."""
        from lists import services
        from lists.models import List

        area = List.objects.create(owner=self.user, title="Home")
        bins = services.create_item(area, "Take the bins out", due_date=JUNE)
        services.set_recurrence(bins, Item.Recurrence.MONTHLY)
        bins.refresh_from_db()

        services.complete_item(bins, today=AUGUST)

        successor = Item.objects.get(owner=self.user, status=Item.Status.ACTIVE)
        self.assertEqual(
            successor.due_date,
            datetime.date(2026, 9, 1),
            "A missed bin round is not owed, and inventing it is fabricated "
            "history.",
        )


class OneOccurrencePerPeriodTest(TestCase):
    """The constraint that makes `catch_up`'s idempotence a promise.

    `principles.md`: *"Use a client-generated identity, an explicit API
    contract, and a database constraint for the guarantee."* The scheduled pass
    is the retry-sensitive writer here, and reasoning about its query is not the
    same as being unable to write the row twice.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )

    def test_a_series_cannot_claim_one_date_twice(self):
        rent = bills.record(
            self.user, payee="Landlord", amount=Decimal("1200.00"),
            due_date=JUNE, recurrence=Item.Recurrence.MONTHLY,
        )

        with self.assertRaises(IntegrityError):
            Bill.objects.create(
                owner=self.user, series=rent.series, due_date=JUNE,
                payee="Landlord", currency="USD",
            )

    def test_two_one_offs_on_one_day_are_still_two_records(self):
        """Scoped to the series on purpose. Two invoices from one supplier on
        one day is ordinary, and the refusal that used to prevent it was the
        task core's uniqueness rule leaking through a derived title."""
        for amount in ("7.99", "4.99"):
            bills.record(
                self.user, payee="Amazon", amount=Decimal(amount),
                due_date=JUNE, repeats=False,
            )

        self.assertEqual(Bill.objects.filter(payee="Amazon").count(), 2)


class TheScheduledPassTest(TestCase):
    """`catch_up_bills`, which is what actually makes this increment reach
    anybody.

    **A seam that is not switched on is not a seam** — `CLAUDE.md` records
    three of those, and the digest is one: the command existed and worked and
    nothing invoked it, so it reached nobody. The cron entry ships in the same
    commit as this command, and these tests cover the command rather than the
    schedule, which only a deploy can prove.
    """

    def setUp(self):
        self.alice = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.bob = User.objects.create_user("bob", "bob@example.com", "a password")

    def rent(self, owner, payee="Landlord"):
        return bills.record(
            owner, payee=payee, amount=Decimal("1200.00"),
            due_date=JUNE, recurrence=Item.Recurrence.MONTHLY,
        )

    def run_command(self, **options):
        out = StringIO()
        call_command("catch_up_bills", stdout=out, **options)
        return out.getvalue()

    def test_it_covers_everybody_by_default(self):
        self.rent(self.alice)
        self.rent(self.bob)

        self.run_command()

        self.assertGreater(Bill.objects.filter(owner=self.alice).count(), 1)
        self.assertGreater(Bill.objects.filter(owner=self.bob).count(), 1)

    def test_one_owner_can_be_named(self):
        self.rent(self.alice)
        self.rent(self.bob)

        self.run_command(owner="alice")

        self.assertEqual(Bill.objects.filter(owner=self.bob).count(), 1)

    def test_a_dry_run_says_what_it_would_do_and_does_nothing(self):
        """Counted by doing it and rolling back rather than by a second
        implementation of the same arithmetic."""
        self.rent(self.alice)

        output = self.run_command(dry_run=True)

        self.assertIn("would create", output)
        self.assertEqual(Bill.objects.filter(owner=self.alice).count(), 1)

    def test_it_says_so_even_when_it_created_nothing(self):
        """A quiet run and a run that never happened look identical otherwise,
        which is how three seams here turned out never to have been switched
        on."""
        output = self.run_command()

        self.assertIn("created 0", output)
