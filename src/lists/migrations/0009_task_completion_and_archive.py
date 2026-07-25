import django.utils.timezone
from django.db import migrations, models


def migrate_archived_lists_to_tasks(apps, schema_editor):
    List = apps.get_model("lists", "List")
    Item = apps.get_model("lists", "Item")
    now = django.utils.timezone.now()

    for list_ in List.objects.filter(is_archived=True).iterator():
        archived_at = list_.archived_at or now
        Item.objects.filter(list=list_).update(
            is_completed=True,
            completed_at=archived_at,
            is_archived=True,
            archived_at=archived_at,
        )


class Migration(migrations.Migration):
    dependencies = [
        ("lists", "0008_list_titles_and_archiving"),
    ]

    operations = [
        migrations.AddField(
            model_name="item",
            name="archived_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="item",
            name="completed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="item",
            name="created_at",
            field=models.DateTimeField(
                auto_now_add=True,
                default=django.utils.timezone.now,
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="item",
            name="is_archived",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="item",
            name="is_completed",
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(
            migrate_archived_lists_to_tasks,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.RemoveIndex(
            model_name="list",
            name="list_owner_status_idx",
        ),
        migrations.RemoveField(
            model_name="list",
            name="archived_at",
        ),
        migrations.RemoveField(
            model_name="list",
            name="is_archived",
        ),
        migrations.AlterUniqueTogether(
            name="item",
            unique_together=set(),
        ),
        migrations.AddConstraint(
            model_name="item",
            constraint=models.UniqueConstraint(
                condition=models.Q(("is_archived", False)),
                fields=("list", "text"),
                name="unique_active_list_item",
            ),
        ),
        migrations.AddIndex(
            model_name="item",
            index=models.Index(
                fields=("list", "is_archived", "is_completed"),
                name="item_list_state_idx",
            ),
        ),
    ]
