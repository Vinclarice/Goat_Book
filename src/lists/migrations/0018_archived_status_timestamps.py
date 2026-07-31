from django.db import migrations, models


class Migration(migrations.Migration):
    # Archiving used to fabricate a completed_at when a task didn't have one,
    # so restore had no way to tell "was active when archived" from "was
    # completed when archived" and sent everything back to completed. Dropping
    # completed_at__isnull=False from the archived arm lets a null stand for
    # "was active". This only widens the constraint, so no existing row can
    # violate it and there is nothing to backfill — but every row already in
    # the archive carries a completed_at, real or fabricated, and the two are
    # indistinguishable. Those rows keep restoring as completed; only archives
    # created from here on get the corrected behaviour.
    #
    # Forward-safe is not the same as reversible: once a task is archived
    # while active it carries archived_at with completed_at null, which the
    # OLD constraint rejects. Reversing this migration therefore fails on any
    # such row. Delete or complete those rows first if you ever need to.
    dependencies = [
        ("lists", "0017_remove_item_item_list_state_idx_and_more"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="item",
            name="valid_item_status_timestamps",
        ),
        migrations.AddConstraint(
            model_name="item",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(
                        ("archived_at__isnull", True),
                        ("completed_at__isnull", True),
                        ("status", "active"),
                    )
                    | models.Q(
                        ("archived_at__isnull", True),
                        ("completed_at__isnull", False),
                        ("status", "completed"),
                    )
                    | models.Q(
                        ("archived_at__isnull", False),
                        ("status", "archived"),
                    )
                ),
                name="valid_item_status_timestamps",
            ),
        ),
    ]
