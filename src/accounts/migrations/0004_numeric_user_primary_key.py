import django.contrib.auth.models
import django.db.models.deletion
from django.db import migrations, models


def preserve_auth_relationships(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    GroupBackup = apps.get_model("accounts", "UserGroupBackup")
    PermissionBackup = apps.get_model("accounts", "UserPermissionBackup")

    GroupBackup.objects.bulk_create(
        GroupBackup(user_email=user_id, target_id=group_id)
        for user_id, group_id in User.groups.through.objects.values_list(
            "user_id",
            "group_id",
        )
    )
    PermissionBackup.objects.bulk_create(
        PermissionBackup(user_email=user_id, target_id=permission_id)
        for user_id, permission_id in User.user_permissions.through.objects.values_list(
            "user_id",
            "permission_id",
        )
    )


def restore_auth_relationships(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    GroupBackup = apps.get_model("accounts", "UserGroupBackup")
    PermissionBackup = apps.get_model("accounts", "UserPermissionBackup")

    user_ids = dict(User.objects.values_list("email", "id"))
    User.groups.through.objects.bulk_create(
        User.groups.through(
            user_id=user_ids[backup.user_email],
            group_id=backup.target_id,
        )
        for backup in GroupBackup.objects.all()
    )
    User.user_permissions.through.objects.bulk_create(
        User.user_permissions.through(
            user_id=user_ids[backup.user_email],
            permission_id=backup.target_id,
        )
        for backup in PermissionBackup.objects.all()
    )


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0003_username_password_auth"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("lists", "0010_prepare_numeric_user_owner"),
    ]

    operations = [
        migrations.CreateModel(
            name="UserGroupBackup",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("user_email", models.EmailField(max_length=254)),
                ("target_id", models.BigIntegerField()),
            ],
        ),
        migrations.CreateModel(
            name="UserPermissionBackup",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("user_email", models.EmailField(max_length=254)),
                ("target_id", models.BigIntegerField()),
            ],
        ),
        migrations.RunPython(
            preserve_auth_relationships,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.RemoveField(
            model_name="user",
            name="groups",
        ),
        migrations.RemoveField(
            model_name="user",
            name="user_permissions",
        ),
        migrations.AlterField(
            model_name="user",
            name="email",
            field=models.EmailField(max_length=254, unique=True),
        ),
        migrations.AddField(
            model_name="user",
            name="id",
            field=models.BigAutoField(
                auto_created=True,
                primary_key=True,
                serialize=False,
                verbose_name="ID",
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="groups",
            field=models.ManyToManyField(
                blank=True,
                help_text=(
                    "The groups this user belongs to. A user will get all "
                    "permissions granted to each of their groups."
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
        migrations.RunPython(
            restore_auth_relationships,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.AlterModelManagers(
            name="user",
            managers=[
                ("objects", django.contrib.auth.models.UserManager()),
            ],
        ),
        migrations.DeleteModel(
            name="UserGroupBackup",
        ),
        migrations.DeleteModel(
            name="UserPermissionBackup",
        ),
    ]
