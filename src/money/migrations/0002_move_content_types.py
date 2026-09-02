"""Move the content types with the models, so permissions survive the app change.

`0001` moved five models from `lists` to `money` in state only. Django's
`post_migrate` hook then creates a content type per model per app label — so
without this, `django_content_type` ends up holding **both** `lists | bill` and
`money | bill`, and `auth_permission` holds two of each of their four
permissions. Twenty orphan rows, and every money permission listed twice in the
admin.

**Repointed rather than deleted, where repointing is possible.** A content type
is what a granted permission hangs off; deleting `lists | bill` would cascade
away *"this user may add bills"* if anybody had ever granted it. Nothing has
here — checked, on both databases — but the destructive version is only correct
because of a fact about today's data, and the non-destructive one is correct
regardless.

**Two cases, because the ordering differs by database.** On a database that has
not yet run `0001`'s `post_migrate`, only the `lists` rows exist and this simply
renames their `app_label`. On one where both already exist — this checkout,
which applied `0001` before this migration was written — the `money` row is
already the live one, so references are moved onto it and the `lists` row is
removed. Either way the end state is one content type per model and no orphan
permissions.

**It refuses rather than guessing** if an admin log entry points at a row it
cannot move, which is the same shape `0057` uses: `LogEntry.content_type` is
`PROTECT`-like in effect, and silently dropping somebody's audit trail to tidy a
table is not a trade a migration gets to make.
"""
from django.db import migrations

#: The five that moved. Written out rather than derived: a migration that asks
#: the live app registry describes whatever the code says today, not what this
#: migration was written to do.
MOVED = ("account", "balancereading", "moneycategory", "billseries", "bill")


def move_content_types(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    Permission = apps.get_model("auth", "Permission")
    LogEntry = apps.get_model("admin", "LogEntry")

    for model in MOVED:
        stale = ContentType.objects.filter(app_label="lists", model=model).first()
        if stale is None:
            continue

        live = ContentType.objects.filter(app_label="money", model=model).first()
        if live is None:
            # Nothing has claimed the new label yet: the row itself moves, and
            # every permission and log entry hanging off it comes along for
            # free because they point at its id.
            stale.app_label = "money"
            stale.save(update_fields=["app_label"])
            continue

        # Both exist. The `money` one is what the application now resolves to,
        # so references move onto it and the old row goes.
        LogEntry.objects.filter(content_type=stale).update(content_type=live)
        for permission in Permission.objects.filter(content_type=stale):
            twin = Permission.objects.filter(
                content_type=live, codename=permission.codename
            ).first()
            if twin is None:
                permission.content_type = live
                permission.save(update_fields=["content_type"])
            else:
                permission.delete()
        stale.delete()


def leave_them_alone(apps, schema_editor):
    """Reversing changes nothing, and that is correct rather than lazy.

    `post_migrate` recreates whatever content type the models' current app label
    calls for, so a reverse that moved these back would be undone by the same
    `migrate` command that ran it. What this migration really removes is
    duplication, and duplication is not a state worth restoring.
    """


class Migration(migrations.Migration):
    dependencies = [
        ("money", "0001_money_models_move"),
        ("contenttypes", "0002_remove_content_type_name"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("admin", "0003_logentry_add_action_flag_choices"),
    ]

    operations = [
        migrations.RunPython(move_content_types, leave_them_alone),
    ]
