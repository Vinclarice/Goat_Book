from django.db import migrations, models


class Migration(migrations.Migration):
    # Additive, with a default, so existing rows fill in as "" without a data
    # migration -- and on Postgres 11+ adding a defaulted column doesn't
    # rewrite the table, so this is cheap even once there's real data.
    dependencies = [
        ("lists", "0018_archived_status_timestamps"),
    ]

    operations = [
        migrations.AddField(
            model_name="item",
            name="notes",
            field=models.TextField(blank=True, default=""),
        ),
    ]
