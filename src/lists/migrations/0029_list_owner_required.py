"""Make List.owner non-null.

Hand-written rather than generated. `makemigrations` insists on a one-off
default for any nullable-to-required change, because it cannot know whether
NULL rows exist -- 0028 has already deleted every one of them, so a default
would be dead weight standing in for a case that can no longer happen.

Separate from 0028 on purpose: a data migration that removes rows and a
schema change that depends on their absence are two things to be able to
read, review and roll back independently, per principles.md's
"prefer small, verifiable changes". They ship together and 0029 will fail
loudly if 0028 somehow left a NULL behind, which is the right failure.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
        ("lists", "0028_delete_ownerless_lists"),
    ]

    operations = [
        migrations.AlterField(
            model_name="list",
            name="owner",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="lists",
                to="accounts.user",
            ),
        ),
    ]
