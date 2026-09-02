"""Drop `MoneyLine` — increment 8 of `design/bill-as-a-model-plan.md`.

**The plan's two conditions, both met before this was written.** *Not before
every read and write has moved*: increment 4 moved them on September 1, 2026
and this file's own suite would fail loudly if anything still wrote here. *And
a backup has been taken*: DigitalOcean's daily backup of the production cluster
is checked by `.github/workflows/backup-freshness.yml`, which has passed every
morning.

**The table is already empty when this runs**, and not by luck.
`0057_retire_the_tasks_that_were_bills` deletes every task that had one, and
`MoneyLine.item` is a cascade — so the rows go with their tasks two migrations
earlier, in the same deploy. `0057` asserts the table is empty afterwards for
exactly this reason.

**Measured against production before this was written**, September 1, 2026: one
`MoneyLine`, one task carrying it, no undated bill and no figure without a
completion — so neither `0055`'s refusal nor `0057`'s can fire there, and this
drops a table with nothing in it.

**Irreversible in the way that matters.** Django can recreate the table on
reverse; it cannot recreate the rows, and the reverse of `0057` explicitly does
not bring back the tasks they hung off. Going back is `MIGRATION.md`'s restore
drill, which is what `CLAUDE.md` says about rolling back code and not the
database.

**What went with it.** `money_line_amount_not_negative`, a CHECK the restore
drill exercised by name; `accounts/export.py`'s `bills` key, whose data now
lives in `bill_occurrences` and `bill_series`, owned directly rather than
reached through a task's owner; and the relation
`test_a_spawn_accounts_for_everything_on_a_task.py` used to require an answer
about — the defect that test was written for was a *paid recurring bill
silently stopping being a bill*, and there is no sidecar left to forget.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('lists', '0058_bill_one_occurrence_per_period'),
    ]

    operations = [
        migrations.DeleteModel(
            name='MoneyLine',
        ),
    ]
