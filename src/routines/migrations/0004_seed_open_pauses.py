"""Give every routine that is down right now a pause record to be down in.

The one part of the past that is genuinely recoverable. A pause that began
and ended before `RoutinePause` existed left nothing behind and stays
unrecoverable -- `crane-plan.md` §8's rule for that is that where the record
says nothing, the review says nothing, rather than inferring a pause from an
empty stretch. But a routine that is paused *at this moment* still carries
`Routine.paused_at`, which is exactly the open interval this table wants.

Without this, resuming such a routine after the deploy would close nothing,
and the stretch it had been down for -- possibly weeks of it -- would be
lost at the moment it ended. That is the same shape of loss lists/0023 was
written to stop, and it is why this runs with the schema rather than being
left for later.

Idempotent by construction: it only creates a row where no open one exists.
"""
from django.db import migrations


def seed_open_pauses(apps, schema_editor):
    Routine = apps.get_model("routines", "Routine")
    RoutinePause = apps.get_model("routines", "RoutinePause")
    seeded = 0
    for routine in Routine.objects.filter(
        is_active=False, paused_at__isnull=False
    ).iterator():
        if RoutinePause.objects.filter(
            routine=routine, resumed_at__isnull=True
        ).exists():
            continue
        RoutinePause.objects.create(
            owner_id=routine.owner_id,
            routine=routine,
            paused_at=routine.paused_at,
        )
        seeded += 1
    if seeded:
        print(f"  seeded open pauses: {seeded}")


def drop_seeded_pauses(apps, schema_editor):
    """Reversing drops only the open ones, which is all this created.

    A closed pause was written by somebody resuming a routine after the
    deploy, and rewinding a migration is not a reason to forget that.
    """
    RoutinePause = apps.get_model("routines", "RoutinePause")
    RoutinePause.objects.filter(resumed_at__isnull=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("routines", "0003_routinepause"),
    ]

    operations = [
        migrations.RunPython(seed_open_pauses, drop_seeded_pauses),
    ]
