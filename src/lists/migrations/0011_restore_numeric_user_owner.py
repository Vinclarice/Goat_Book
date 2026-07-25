import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def restore_owners(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    List = apps.get_model("lists", "List")
    user_ids = dict(User.objects.values_list("email", "id"))

    lists_to_update = []
    for list_ in List.objects.exclude(owner_email_backup=None).iterator():
        list_.owner_id = user_ids[list_.owner_email_backup]
        lists_to_update.append(list_)
    List.objects.bulk_update(lists_to_update, ("owner",))


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0004_numeric_user_primary_key"),
        ("lists", "0010_prepare_numeric_user_owner"),
    ]

    operations = [
        migrations.AddField(
            model_name="list",
            name="owner",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="lists",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RunPython(
            restore_owners,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.RemoveField(
            model_name="list",
            name="owner_email_backup",
        ),
    ]
