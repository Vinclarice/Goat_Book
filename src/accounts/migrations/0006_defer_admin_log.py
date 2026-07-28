from django.db import migrations


class Migration(migrations.Migration):
    """No-op migration that only exists to fix migration ordering.

    django.contrib.admin's own initial migration creates admin.LogEntry,
    which has a ForeignKey to AUTH_USER_MODEL. Its dependency on this app
    resolves to accounts' *first* migration, so without this, a fresh
    migrate would create that table right after 0001_initial -- before
    0004_numeric_user_primary_key rebuilds the User table to switch its
    primary key from email to a numeric id. On SQLite that table rebuild
    then trips a "foreign key mismatch" against the already-created
    LogEntry table.

    Forcing admin's initial migration to run after our own primary key
    migration avoids the problem entirely: LogEntry ends up referencing
    the User table's final shape.
    """

    dependencies = [
        ("accounts", "0005_migrate_session_user_ids"),
    ]

    run_before = [
        ("admin", "0001_initial"),
    ]

    operations = []
