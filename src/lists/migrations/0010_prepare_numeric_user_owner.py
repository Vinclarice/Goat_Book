from django.db import migrations, models


def preserve_owner_emails(apps, schema_editor):
    List = apps.get_model("lists", "List")
    for list_ in List.objects.exclude(owner_id=None).iterator():
        list_.owner_email_backup = list_.owner_id
        list_.save(update_fields=("owner_email_backup",))


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0003_username_password_auth"),
        ("lists", "0009_task_completion_and_archive"),
    ]

    operations = [
        migrations.AddField(
            model_name="list",
            name="owner_email_backup",
            field=models.EmailField(blank=True, max_length=254, null=True),
        ),
        migrations.RunPython(
            preserve_owner_emails,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.RemoveField(
            model_name="list",
            name="owner",
        ),
    ]
