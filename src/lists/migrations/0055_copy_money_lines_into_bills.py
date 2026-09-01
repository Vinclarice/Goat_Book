"""Copy every `MoneyLine` + its `Item` into a `Bill` — increment 2 of
`design/bill-as-a-model-plan.md`.

**Additive and reversible.** Nothing is deleted and nothing existing is altered:
`MoneyLine` and its `Item` are read, never written. Increment 3 reads the new
tables while the old ones still exist, so the two can be compared before
increment 4 makes the new ones authoritative. `MoneyLine` is not dropped until
increment 8.

**It refuses rather than guesses.** Two states are reachable in the old model
and cannot be represented in the new one, and both would otherwise be silent
data loss:

- **A bill with no due date.** `set_bill` can mark any task as a bill, and a
  task's due date is nullable where `Bill.due_date` is not. Such a bill is
  already invisible in every Money read, since all of them are keyed to a
  month — but skipping it here would delete a record rather than fail to show
  one.
- **A figure with no settlement.** Paying then reopening leaves `paid_amount`
  set with `completed_at` cleared, which the new constraint refuses on purpose:
  a number against a bill nobody settled is a claim about money that did not
  move.

Neither exists in development or production as of August 31, 2026 — both were
counted before this was written, which is why the migration asserts instead of
inventing a policy nobody needs yet. If one appears, this fails at `migrate`
with the rows named, which is where a person can decide.

**One `BillSeries` per `RecurringCommitment`**, and none for a one-off. §4 rule
8's template, populated from the commitment that already plays that role for
tasks.
"""
from django.db import migrations


def copy_money_lines(apps, schema_editor):
    MoneyLine = apps.get_model("lists", "MoneyLine")
    Bill = apps.get_model("lists", "Bill")
    BillSeries = apps.get_model("lists", "BillSeries")

    lines = MoneyLine.objects.select_related("item", "item__commitment").all()

    undated = [line.pk for line in lines if line.item.due_date is None]
    unsettled = [
        line.pk
        for line in lines
        if line.paid_amount is not None and line.item.completed_at is None
    ]
    if undated or unsettled:
        raise RuntimeError(
            "Cannot convert every MoneyLine without losing or inventing "
            f"something. MoneyLine ids with no due date: {undated or 'none'}; "
            f"with a paid amount but no completion: {unsettled or 'none'}. "
            "See this migration's docstring: both are reachable, neither had "
            "occurred when it was written, and both want a decision rather "
            "than a default."
        )

    # One series per commitment, built as they are met. `Item.commitment` is
    # already the template for a repeating task, so the mapping is a copy
    # rather than a judgement.
    series_for_commitment = {}
    for line in lines:
        item = line.item
        commitment = item.commitment
        series = None
        if commitment is not None:
            series = series_for_commitment.get(commitment.pk)
            if series is None:
                series = BillSeries.objects.create(
                    owner_id=item.owner_id,
                    payee=line.payee,
                    amount=line.amount,
                    currency=line.currency,
                    direction=line.direction,
                    category_id=line.category_id,
                    cadence=commitment.cadence,
                    cadence_mode=commitment.cadence_mode,
                    lead_days=item.lead_days,
                    # A commitment that has ended produced its last occurrence
                    # already; carrying the date keeps that fact rather than
                    # resurrecting the series.
                    ended_at=commitment.ended_at,
                )
                series_for_commitment[commitment.pk] = series

        Bill.objects.create(
            owner_id=item.owner_id,
            series=series,
            due_date=item.due_date,
            # Snapshots, §4 rule 3 -- copied from the line rather than read
            # through the series, which is the whole point of them.
            payee=line.payee,
            amount=line.amount,
            currency=line.currency,
            direction=line.direction,
            category_id=line.category_id,
            paid_amount=line.paid_amount,
            # **`completed_at`, not a status.** A settled bill is one that was
            # completed, and the date it happened is the fact worth keeping.
            # Null for anything still owed, including a period long past --
            # which is the asymmetry this whole model exists for.
            paid_at=item.completed_at,
            notes=item.notes,
        )


def drop_copied_bills(apps, schema_editor):
    """Reverse by emptying both tables, which is safe **only while they are
    dark**.

    Nothing wrote them until increment 4, so on a database where that has not
    run, everything in them came from the forward function and deleting it
    loses nothing.

    **Increment 4 shipped on August 31, 2026 and this reverse became
    destructive.** From then on the `Bill` rows are the record and the tasks
    are gone -- `0057_retire_the_tasks_that_were_bills` deleted them -- so
    reversing this on a live database deletes somebody's financial history and
    reversing `0057` first does not bring the tasks back to replace it.

    It is left runnable rather than made to raise, because the alternative is
    an un-rewindable graph and every other app's migration tests rewind the
    whole of it. What protects production is not this function: it is that
    rolling a data migration back there is `MIGRATION.md`'s restore drill and
    never a `migrate` command -- the caveat `CLAUDE.md` records about rolling
    back code but not the database.
    """
    apps.get_model("lists", "Bill").objects.all().delete()
    apps.get_model("lists", "BillSeries").objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ("lists", "0054_bill_settlement_constraint"),
    ]

    operations = [
        migrations.RunPython(copy_money_lines, drop_copied_bills),
    ]
