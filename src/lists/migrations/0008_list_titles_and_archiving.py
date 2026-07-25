from django.db import migrations, models


def populate_list_titles(apps, schema_editor):
    List = apps.get_model("lists", "List")
    Item = apps.get_model("lists", "Item")

    for list_ in List.objects.all().iterator():
        first_item = Item.objects.filter(list=list_).order_by("id").first()
        if first_item:
            list_.title = first_item.text[:100]
            list_.save(update_fields=("title",))


class Migration(migrations.Migration):
    dependencies = [
        ("lists", "0007_list_owner"),
    ]

    operations = [
        migrations.AddField(
            model_name="list",
            name="archived_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="list",
            name="is_archived",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="list",
            name="title",
            field=models.CharField(default="Untitled list", max_length=100),
        ),
        migrations.RunPython(
            populate_list_titles,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.AddIndex(
            model_name="list",
            index=models.Index(
                fields=("owner", "is_archived"),
                name="list_owner_status_idx",
            ),
        ),
    ]
