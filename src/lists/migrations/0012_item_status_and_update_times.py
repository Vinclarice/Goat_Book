import django.utils.timezone
from django.db import migrations, models


def normalize_item_states(apps, schema_editor):
    Item = apps.get_model("lists", "Item")
    now = django.utils.timezone.now()

    for item in Item.objects.all().iterator():
        if item.is_archived:
            item.status = "archived"
            item.completed_at = item.completed_at or item.archived_at or now
            item.archived_at = item.archived_at or item.completed_at
        elif item.is_completed:
            item.status = "completed"
            item.completed_at = item.completed_at or now
            item.archived_at = None
        else:
            item.status = "active"
            item.completed_at = None
            item.archived_at = None
        item.save(
            update_fields=(
                "status",
                "completed_at",
                "archived_at",
            ),
        )


class Migration(migrations.Migration):
    dependencies = [
        ("lists", "0011_restore_numeric_user_owner"),
    ]

    operations = [
        migrations.AddField(
            model_name="item",
            name="status",
            field=models.CharField(
                choices=[
                    ("active", "Open"),
                    ("completed", "Completed"),
                    ("archived", "Archived"),
                ],
                default="active",
                max_length=12,
            ),
        ),
        migrations.AddField(
            model_name="item",
            name="updated_at",
            field=models.DateTimeField(
                auto_now=True,
                default=django.utils.timezone.now,
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="list",
            name="updated_at",
            field=models.DateTimeField(
                auto_now=True,
                default=django.utils.timezone.now,
            ),
            preserve_default=False,
        ),
        migrations.RunPython(
            normalize_item_states,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.RemoveConstraint(
            model_name="item",
            name="unique_active_list_item",
        ),
        migrations.RemoveIndex(
            model_name="item",
            name="item_list_state_idx",
        ),
        migrations.RemoveField(
            model_name="item",
            name="is_archived",
        ),
        migrations.RemoveField(
            model_name="item",
            name="is_completed",
        ),
        migrations.AddConstraint(
            model_name="item",
            constraint=models.UniqueConstraint(
                condition=~models.Q(("status", "archived")),
                fields=("list", "text"),
                name="unique_active_list_item",
            ),
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
                        ("completed_at__isnull", False),
                        ("status", "archived"),
                    )
                ),
                name="valid_item_status_timestamps",
            ),
        ),
        migrations.AddIndex(
            model_name="item",
            index=models.Index(
                fields=("list", "status"),
                name="item_list_state_idx",
            ),
        ),
    ]
