from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0006_defer_admin_log"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="daily_digest",
            field=models.BooleanField(
                default=True,
                help_text=(
                    "A morning email listing anything overdue or due today. "
                    "Nothing is sent on days when there's nothing to report."
                ),
                verbose_name="Email me a daily summary",
            ),
        ),
    ]
