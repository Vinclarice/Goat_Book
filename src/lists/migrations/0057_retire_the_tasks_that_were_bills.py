"""Delete the tasks that increment 2 copied into `Bill` — increment 4 of
`design/bill-as-a-model-plan.md`, and the point of no return.

**Why this exists at all**, since the plan did not anticipate it. `0055` was
deliberately additive: it *copied* every `MoneyLine` and its `Item` into a
`Bill` and altered nothing, so the two reads could be compared before either
became authoritative. That leaves every converted bill existing twice. While
both reads were live that was the point; the moment the writes move, it is a
duplicate — the same rent showing in Money as a `Bill` and in the digest, the
calendar, search, the archive and the export as a task, with a *Complete*
button that would spawn a second shadow next month.

**So this is not tidying, it is the other half of the conversion.** It is in
the same commit as the flip because between the two the product is incoherent.

**What goes with them.** `MoneyLine` cascades, which is the deletion this is
really about — the sidecar has no owner of its own and no meaning without its
task. `ChecklistStep` cascades too and there are none: a bill has no checklist,
which is one of the arguments the split is made of. `mind.Facet.task` and
`daily.DailyFocus.task` are `SET_NULL`, and both callers already handle a null
task, because a task has always been deletable. `mind.ActivityEvent.task` is
`DO_NOTHING` with `db_constraint=False` on purpose: the log is append-only by
database trigger, so the event stays and its `task_id` dangles, which is the
behaviour that table was designed for.

**And the commitment.** A repeating bill had a `RecurringCommitment` playing
the template role `BillSeries` now plays, and `0055` built one series per
commitment. A commitment whose every occurrence was a bill is dead with them,
so it goes; one that also produced ordinary tasks is left alone, because it is
still a template for those. Measured rather than assumed -- the check is by
query, not by an assumption about how they were made.

**Its reverse does nothing, and says so rather than pretending.** The tasks
cannot be recreated: their `Bill` rows are the record now, and by the time
anybody reverses this they carry edits the tasks never saw. Three answers were
possible and two are worse. Raising makes the migration graph un-rewindable,
which breaks every *other* app's migration tests as collateral -- they rewind
the whole graph, not this app's slice. Reconstructing tasks from `Bill` rows
would fabricate records: the text, area, tags and position are gone and only
the payee could be guessed back.

So: a no-op, an explicit docstring, and a test in
`test_bill_conversion.py` asserting that reversing does **not** resurrect
anything -- because a silent no-op is exactly the kind of thing somebody later
reads as "undone". Undoing this for real is `MIGRATION.md`'s restore drill,
which is the same caveat `CLAUDE.md` records about rolling back code and not
the database.
"""
from django.db import migrations


def delete_converted_bill_tasks(apps, schema_editor):
    Item = apps.get_model("lists", "Item")
    MoneyLine = apps.get_model("lists", "MoneyLine")
    Bill = apps.get_model("lists", "Bill")
    RecurringCommitment = apps.get_model("lists", "RecurringCommitment")

    # **A refusal, not a guess.** If the tables do not line up, something ran
    # between the copy and this -- a bill made through the old write path after
    # `0055`, or a `Bill` deleted by hand. Deleting the tasks anyway would lose
    # whichever side has the extra row, and which side that is depends on facts
    # this migration cannot see.
    task_count = Item.objects.filter(money_line__isnull=False).count()
    bill_count = Bill.objects.count()
    if task_count > bill_count:
        raise RuntimeError(
            f"{task_count} tasks are bills but only {bill_count} Bill rows "
            "exist, so deleting the tasks would lose the difference. 0055 "
            "copied them one for one; something has written a bill through "
            "the old path since. Re-run 0055's copy for the missing rows, or "
            "decide by hand -- see this migration's docstring."
        )

    commitments = set(
        Item.objects.filter(money_line__isnull=False, commitment__isnull=False)
        .values_list("commitment_id", flat=True)
    )
    Item.objects.filter(money_line__isnull=False).delete()
    # After the tasks are gone, a commitment with no items left is one whose
    # occurrences were all bills. One that still has tasks is still a template.
    RecurringCommitment.objects.filter(pk__in=commitments, occurrences__isnull=True).delete()
    # Nothing should be left; asserted rather than trusted, because the cascade
    # is the mechanism and a changed on_delete would break it silently.
    assert not MoneyLine.objects.exists(), "MoneyLine should cascade with its task."


def do_not_resurrect(apps, schema_editor):
    """Reversing rewinds the schema and restores nothing. See the docstring.

    Deliberately not `noop` from `RunPython`: a named function with this
    docstring is what a person finds when they ask what going back does.
    """


class Migration(migrations.Migration):
    dependencies = [
        ("lists", "0056_bill_lead_days"),
    ]

    operations = [
        migrations.RunPython(delete_converted_bill_tasks, do_not_resurrect),
    ]
