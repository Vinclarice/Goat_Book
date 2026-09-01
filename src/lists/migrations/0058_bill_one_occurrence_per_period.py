"""One occurrence per period — increment 6 of `design/bill-as-a-model-plan.md`.

`bills.catch_up` replays the periods a live series has come to owe, and it runs
on a schedule. It is idempotent by construction — it reads the latest occurrence
and builds forward from it — but `principles.md` is explicit that retry-safety
is bought with a database constraint rather than with care, and two overlapping
passes would otherwise double somebody's rent.

**Safe to apply.** Development and production both held zero colliding pairs
when this was written, checked by query rather than assumed: nothing before this
increment could create two occurrences of one series on one date, because the
only producer was `spawn_next` and it runs once per settlement.

**One-offs are unaffected**, and that is the point of scoping it to the series
rather than to the owner and payee: a one-off carries no series, nulls do not
collide in Postgres, and two invoices from one supplier on one day are two real
records. What cannot happen is one *schedule* claiming a period twice.
"""
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('lists', '0057_retire_the_tasks_that_were_bills'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='bill',
            constraint=models.UniqueConstraint(fields=('series', 'due_date'), name='bill_one_occurrence_per_period'),
        ),
    ]
