import re

from django.contrib.auth import models as auth_models
from django.contrib.auth import validators
from django.db import migrations, models


def populate_legacy_accounts(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    used_usernames = set()

    for user in User.objects.order_by("email"):
        base = user.email.split("@", 1)[0] or "user"
        base = re.sub(r"[^\w.@+-]", "-", base)[:140] or "user"
        username = base
        suffix = 2
        while username.casefold() in used_usernames:
            ending = f"-{suffix}"
            username = f"{base[:150 - len(ending)]}{ending}"
            suffix += 1

        user.username = username
        user.password = "!"
        user.save(update_fields=["username", "password"])
        used_usernames.add(username.casefold())


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_token"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="password",
            field=models.CharField(default="!", max_length=128, verbose_name="password"),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="user",
            name="last_login",
            field=models.DateTimeField(blank=True, null=True, verbose_name="last login"),
        ),
        migrations.AddField(
            model_name="user",
            name="username",
            field=models.CharField(blank=True, max_length=150, null=True),
        ),
        migrations.AddField(
            model_name="user",
            name="is_active",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="user",
            name="is_staff",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="user",
            name="is_superuser",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Designates that this user has all permissions without "
                    "explicitly assigning them."
                ),
                verbose_name="superuser status",
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="groups",
            field=models.ManyToManyField(
                blank=True,
                help_text=(
                    "The groups this user belongs to. A user will get all permissions "
                    "granted to each of their groups."
                ),
                related_name="user_set",
                related_query_name="user",
                to="auth.group",
                verbose_name="groups",
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="user_permissions",
            field=models.ManyToManyField(
                blank=True,
                help_text="Specific permissions for this user.",
                related_name="user_set",
                related_query_name="user",
                to="auth.permission",
                verbose_name="user permissions",
            ),
        ),
        migrations.RunPython(populate_legacy_accounts, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="user",
            name="username",
            field=models.CharField(
                max_length=150,
                unique=True,
                validators=[validators.UnicodeUsernameValidator()],
            ),
        ),
        migrations.AlterModelManagers(
            name="user",
            managers=[
                ("objects", auth_models.UserManager()),
            ],
        ),
        migrations.DeleteModel(name="Token"),
    ]
