"""`0055_copy_money_lines_into_bills` — increment 2 of
`design/bill-as-a-model-plan.md`.

**A data migration is the one kind of code that runs once, against data nobody
can reproduce afterwards.** Production holds a handful of rows today, which is
the argument for doing this now; it is also the reason the conversion is tested
rather than eyeballed, since the second run is a restore drill rather than a
retry.

Same shape as `test_checklist_step_backfill.py`, which is the precedent for
migration tests here.
"""
import datetime
from decimal import Decimal

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone

from accounts.models import User


BEFORE = [("lists", "0054_bill_settlement_constraint")]
AFTER = [("lists", "0055_copy_money_lines_into_bills")]
RETIRED = [("lists", "0057_retire_the_tasks_that_were_bills")]


class BillConversionTest(TransactionTestCase):
    def migrate(self, target):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(target)
        return executor.loader.project_state(target).apps

    def tearDown(self):
        # Every app forward, not just this one's target -- see
        # test_checklist_step_backfill.py, which carries the full reason.
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(executor.loader.graph.leaf_nodes())

    def seed(self, apps, **line_fields):
        """One money line and its task, in the old shape.

        Defaults are merged rather than passed alongside overrides -- a test
        that wants `amount=None` is saying something, and `create()` would
        otherwise refuse it as a duplicate keyword.
        """
        List = apps.get_model("lists", "List")
        Item = apps.get_model("lists", "Item")
        MoneyLine = apps.get_model("lists", "MoneyLine")
        n = User.objects.count()
        user = User.objects.create_user(f"u{n}", f"u{n}@example.com", "pw")
        area = List.objects.create(owner_id=user.pk, title="Home")
        item_fields = {
            "text": "Pay Landlord",
            "due_date": datetime.date(2026, 8, 1),
            **line_fields.pop("item_fields", {}),
        }
        item = Item.objects.create(list=area, owner_id=user.pk, **item_fields)
        MoneyLine.objects.create(
            item=item,
            **{
                "payee": "Landlord",
                "amount": Decimal("1200.00"),
                "currency": "USD",
                "direction": "out",
                **line_fields,
            },
        )
        return user, item

    def test_an_outstanding_bill_arrives_whole(self):
        old = self.migrate(BEFORE)
        user, item = self.seed(old)

        new = self.migrate(AFTER)
        bill = new.get_model("lists", "Bill").objects.get()

        self.assertEqual(bill.owner_id, user.pk)
        self.assertEqual(bill.payee, "Landlord")
        self.assertEqual(bill.amount, Decimal("1200.00"))
        self.assertEqual(bill.currency, "USD")
        self.assertEqual(bill.direction, "out")
        self.assertEqual(bill.due_date, datetime.date(2026, 8, 1))
        self.assertIsNone(bill.paid_at, "Nothing settled it, so it is still owed.")
        self.assertIsNone(bill.paid_amount)
        self.assertIsNone(bill.series_id, "A one-off needs no template.")

    def test_a_settled_bill_keeps_both_numbers_and_the_date(self):
        """The two-amount discipline is the thing most easily lost in a
        conversion, and it is the reason *"this has been creeping up"* is
        answerable at all."""
        old = self.migrate(BEFORE)
        settled = timezone.now()
        self.seed(
            old,
            paid_amount=Decimal("1275.40"),
            item_fields={"status": "completed", "completed_at": settled},
        )

        new = self.migrate(AFTER)
        bill = new.get_model("lists", "Bill").objects.get()

        self.assertEqual(bill.amount, Decimal("1200.00"))
        self.assertEqual(bill.paid_amount, Decimal("1275.40"))
        self.assertEqual(bill.paid_at, settled)

    def test_an_unpriced_bill_paid_without_a_figure_survives(self):
        """The row that would have failed the constraint as first written --
        one of five in development. *Paid, amount unrecorded* is a real
        answer and it comes through as one."""
        old = self.migrate(BEFORE)
        settled = timezone.now()
        self.seed(
            old,
            amount=None,
            paid_amount=None,
            item_fields={"status": "completed", "completed_at": settled},
        )

        new = self.migrate(AFTER)
        bill = new.get_model("lists", "Bill").objects.get()

        self.assertEqual(bill.paid_at, settled)
        self.assertIsNone(bill.paid_amount)
        self.assertIsNone(bill.amount)

    def test_a_repeating_bill_gets_a_series_and_points_at_it(self):
        old = self.migrate(BEFORE)
        Commitment = old.get_model("lists", "RecurringCommitment")
        user, item = self.seed(old)
        commitment = Commitment.objects.create(
            owner_id=user.pk, cadence="monthly", cadence_mode="anchored"
        )
        item.commitment = commitment
        item.lead_days = 5
        item.save()

        new = self.migrate(AFTER)
        bill = new.get_model("lists", "Bill").objects.get()
        series = new.get_model("lists", "BillSeries").objects.get()

        self.assertEqual(bill.series_id, series.pk)
        self.assertEqual(series.owner_id, user.pk)
        self.assertEqual(series.cadence, "monthly")
        self.assertEqual(series.cadence_mode, "anchored")
        self.assertEqual(series.lead_days, 5)
        self.assertEqual(series.payee, "Landlord")

    def test_two_occurrences_of_one_commitment_share_a_single_series(self):
        """§4 rule 8's whole point: the history exists *and* can be assembled.
        A series per occurrence would be the chain-of-rows shape the charter
        names as the counter-example that was in production."""
        old = self.migrate(BEFORE)
        Commitment = old.get_model("lists", "RecurringCommitment")
        Item = old.get_model("lists", "Item")
        MoneyLine = old.get_model("lists", "MoneyLine")
        user, july = self.seed(old)
        commitment = Commitment.objects.create(
            owner_id=user.pk, cadence="monthly", cadence_mode="anchored"
        )
        july.commitment = commitment
        july.save()
        august = Item.objects.create(
            list=july.list,
            owner_id=user.pk,
            # Not the same text as July's: `unique_active_item` refuses two
            # open tasks with one name in one area, which is a real rule about
            # tasks and one more thing a bill will stop inheriting.
            text="Pay Landlord (September)",
            due_date=datetime.date(2026, 9, 1),
            commitment=commitment,
        )
        MoneyLine.objects.create(
            item=august, payee="Landlord", amount=Decimal("1200.00")
        )

        new = self.migrate(AFTER)

        self.assertEqual(new.get_model("lists", "BillSeries").objects.count(), 1)
        self.assertEqual(new.get_model("lists", "Bill").objects.count(), 2)

    def test_it_leaves_the_old_rows_exactly_where_they_were(self):
        """Additive. Increment 3 compares the two, which is only possible while
        both exist -- and `MoneyLine` is not dropped until increment 8."""
        old = self.migrate(BEFORE)
        self.seed(old)

        new = self.migrate(AFTER)

        self.assertEqual(new.get_model("lists", "MoneyLine").objects.count(), 1)
        self.assertEqual(new.get_model("lists", "Item").objects.count(), 1)

    def test_reversing_empties_the_new_tables_and_touches_nothing_else(self):
        old = self.migrate(BEFORE)
        self.seed(old)
        self.migrate(AFTER)

        back = self.migrate(BEFORE)

        self.assertEqual(back.get_model("lists", "MoneyLine").objects.count(), 1)
        self.assertEqual(back.get_model("lists", "Item").objects.count(), 1)

    def test_it_refuses_a_bill_with_no_due_date_rather_than_dropping_it(self):
        """`set_bill` can mark an undated task as a bill, and `Bill.due_date`
        is not nullable. Skipping the row would be silent data loss; failing at
        `migrate` puts the decision in front of a person."""
        old = self.migrate(BEFORE)
        self.seed(old, item_fields={"due_date": None})

        with self.assertRaises(RuntimeError) as caught:
            self.migrate(AFTER)

        self.assertIn("no due date", str(caught.exception))
        # tearDown migrates every app forward, which would run this migration
        # again and fail the same way -- so the row it refuses is removed once
        # the refusal has been proven.
        old.get_model("lists", "MoneyLine").objects.all().delete()

    def test_it_refuses_a_figure_with_no_settlement(self):
        """Paying then reopening leaves the amount with no completion, which
        the constraint refuses on purpose."""
        old = self.migrate(BEFORE)
        self.seed(old, paid_amount=Decimal("1200.00"))

        with self.assertRaises(RuntimeError) as caught:
            self.migrate(AFTER)

        self.assertIn("no completion", str(caught.exception))
        old.get_model("lists", "MoneyLine").objects.all().delete()


class RetiringTheTasksThatWereBillsTest(TransactionTestCase):
    """`0057_retire_the_tasks_that_were_bills` — the other half of the
    conversion, and the point of no return.

    `0055` copied rather than moved, so every converted bill existed twice. That
    was the point while both reads were live; the moment the writes moved, the
    task copy became a duplicate that the digest, the calendar, search and the
    archive would all go on showing, with a *Complete* button that would spawn a
    shadow of next month's bill.
    """

    def migrate(self, target):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(target)
        return executor.loader.project_state(target).apps

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(executor.loader.graph.leaf_nodes())

    def seed_bill_task(self, apps, *, repeats=False):
        List = apps.get_model("lists", "List")
        Item = apps.get_model("lists", "Item")
        MoneyLine = apps.get_model("lists", "MoneyLine")
        RecurringCommitment = apps.get_model("lists", "RecurringCommitment")
        n = User.objects.count()
        user = User.objects.create_user(f"u{n}", f"u{n}@example.com", "pw")
        area = List.objects.create(owner_id=user.pk, title="Home")
        commitment = None
        if repeats:
            commitment = RecurringCommitment.objects.create(
                owner_id=user.pk, text="Pay Landlord", cadence="monthly"
            )
        item = Item.objects.create(
            list=area,
            owner_id=user.pk,
            text="Pay Landlord",
            due_date=datetime.date(2026, 8, 1),
            commitment=commitment,
            recurrence="monthly" if repeats else "none",
        )
        MoneyLine.objects.create(
            item=item, payee="Landlord", amount=Decimal("1200.00"), currency="USD"
        )
        return user, item, commitment

    def test_the_task_and_its_sidecar_go_and_the_bill_stays(self):
        old = self.migrate(BEFORE)
        self.seed_bill_task(old)

        new = self.migrate(RETIRED)

        self.assertEqual(new.get_model("lists", "Item").objects.count(), 0)
        self.assertEqual(new.get_model("lists", "MoneyLine").objects.count(), 0)
        self.assertEqual(new.get_model("lists", "Bill").objects.count(), 1)

    def test_an_ordinary_task_is_untouched(self):
        """The filter is `money_line__isnull=False`, and this is the test that
        says so out loud rather than trusting the query."""
        old = self.migrate(BEFORE)
        user, _, _ = self.seed_bill_task(old)
        List = old.get_model("lists", "List")
        area = List.objects.filter(owner_id=user.pk).first()
        old.get_model("lists", "Item").objects.create(
            list=area, owner_id=user.pk, text="Call the plumber"
        )

        new = self.migrate(RETIRED)

        self.assertEqual(
            [item.text for item in new.get_model("lists", "Item").objects.all()],
            ["Call the plumber"],
        )

    def test_a_commitment_whose_occurrences_were_all_bills_goes_with_them(self):
        """`BillSeries` plays that role now, built by 0055 from this very
        commitment. Leaving it would be a template for nothing."""
        old = self.migrate(BEFORE)
        self.seed_bill_task(old, repeats=True)

        new = self.migrate(RETIRED)

        self.assertEqual(
            new.get_model("lists", "RecurringCommitment").objects.count(), 0
        )
        self.assertEqual(new.get_model("lists", "BillSeries").objects.count(), 1)

    def test_a_commitment_that_also_made_ordinary_tasks_survives(self):
        """It is still a template for those. Measured by query rather than
        assumed from how the rows were made."""
        old = self.migrate(BEFORE)
        user, item, commitment = self.seed_bill_task(old, repeats=True)
        old.get_model("lists", "Item").objects.create(
            list=item.list,
            owner_id=user.pk,
            text="Take the bins out",
            commitment=commitment,
            recurrence="monthly",
        )

        new = self.migrate(RETIRED)

        self.assertEqual(
            new.get_model("lists", "RecurringCommitment").objects.count(), 1
        )

    def test_reversing_it_restores_nothing_and_says_so(self):
        """**The guard the no-op reverse promises.** A reverse that silently
        does nothing is exactly the kind of thing somebody later reads as
        *undone*; this is the test that makes it a decision instead."""
        old = self.migrate(BEFORE)
        self.seed_bill_task(old)
        self.migrate(RETIRED)

        back = self.migrate(AFTER)

        self.assertEqual(back.get_model("lists", "Item").objects.count(), 0)
        self.assertEqual(back.get_model("lists", "MoneyLine").objects.count(), 0)
        self.assertEqual(
            back.get_model("lists", "Bill").objects.count(),
            1,
            "And the Bill rows -- the record now -- are still standing.",
        )

    def test_it_refuses_rather_than_losing_a_bill_written_after_the_copy(self):
        """More bill tasks than `Bill` rows means something used the old write
        path after 0055, and deleting the tasks would lose whichever side has
        the extra row. Which side that is depends on facts a migration cannot
        see, so it stops and names the counts."""
        old = self.migrate(BEFORE)
        self.seed_bill_task(old)
        after = self.migrate(AFTER)
        after.get_model("lists", "Bill").objects.all().delete()

        with self.assertRaises(RuntimeError):
            self.migrate(RETIRED)

        # Cleared so `tearDown`'s migrate-to-leaf does not hit the same
        # refusal and report it as a second failure -- the trap this file's
        # sibling tests already found once.
        after.get_model("lists", "Item").objects.all().delete()
