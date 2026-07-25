from django.contrib.auth import SESSION_KEY
from django.contrib.sessions.backends.db import SessionStore
from django.db import migrations


def _rewrite_session_user_ids(apps, schema_editor, user_id_map):
    Session = apps.get_model("sessions", "Session")
    database = schema_editor.connection.alias

    for session in Session.objects.using(database).all().iterator():
        store = SessionStore(session_key=session.session_key)
        data = store.decode(session.session_data)
        old_user_id = data.get(SESSION_KEY)
        new_user_id = user_id_map.get(str(old_user_id))
        if new_user_id is None:
            continue

        data[SESSION_KEY] = str(new_user_id)
        session.session_data = store.encode(data)
        session.save(using=database, update_fields=("session_data",))


def migrate_email_session_ids(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    database = schema_editor.connection.alias
    user_id_map = {
        email: user_id
        for email, user_id in User.objects.using(database).values_list(
            "email",
            "id",
        )
    }
    _rewrite_session_user_ids(apps, schema_editor, user_id_map)


def restore_email_session_ids(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    database = schema_editor.connection.alias
    user_id_map = {
        str(user_id): email
        for user_id, email in User.objects.using(database).values_list(
            "id",
            "email",
        )
    }
    _rewrite_session_user_ids(apps, schema_editor, user_id_map)


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0004_numeric_user_primary_key"),
        ("sessions", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            migrate_email_session_ids,
            reverse_code=restore_email_session_ids,
        ),
    ]
