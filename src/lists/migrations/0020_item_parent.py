import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    # Adds the self-FK and swaps the unique constraint for one that covers
    # root tasks and subtasks together. No data migration: every existing row
    # gets parent = NULL, which the new constraint treats exactly as the old
    # one treated (list, text) -- provided nulls_distinct=False, which is
    # Postgres 15+ only. On SQLite this constraint is silently not created,
    # so the suite has to run on Postgres for it to mean anything (CI does).
    #
    # Not reversible in practice once subtasks exist: reversing restores a
    # (list, text) unique constraint that a parent and its subtask sharing a
    # text would violate.
    dependencies = [
        ("lists", "0019_item_notes"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="item",
            name="unique_active_list_item",
        ),
        migrations.AddField(
            model_name="item",
            name="archive_group",
            field=models.UUIDField(blank=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name="item",
            name="parent",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="subtasks",
                to="lists.item",
            ),
        ),
        migrations.AddIndex(
            model_name="item",
            index=models.Index(
                fields=["parent", "status"],
                name="item_parent_state_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="item",
            constraint=models.UniqueConstraint(
                condition=models.Q(("status", "archived"), _negated=True),
                fields=("list", "parent", "text"),
                name="unique_active_item",
                nulls_distinct=False,
            ),
        ),
    ]
