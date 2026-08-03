"""Remove anonymous-era Lists so 0029 can make the owner required.

architecture-trajectory.md 6 offers two branches for this -- "backfill or
remove orphans" -- and removal is the one taken, on the argument that an
ownerless List is already invisible: every read in the application is
owner-scoped, so no user can reach one. Two earlier migrations
(0023_anchor_existing_recurring_items, 0026_convert_subtasks_to_checklist_steps)
each had to write an explicit skip-clause for these rows, which is the
clearest evidence that the exception was costing more than the data was
worth.

**This deletes rows and cannot be reversed.** The reverse is a deliberate
no-op rather than a lie: nothing here can reconstruct which List a deleted
Item belonged to, and pretending otherwise would be worse than admitting it.
Rolling 0029 back restores the nullable column, not the data.

The counts are printed rather than assumed. Local development had zero
ownerless rows, but that is a two-user SQLite database, and principles.md's
"production truth beats local confidence" says this migration's own output
against production is the first real evidence of how many there were.

Deleting is schema-safe even for a task somebody had pinned or promoted:
DailyFocus.task, Idea.promoted_task and Capture.promoted_task are all
SET_NULL, the same protection delete_archived_item relies on. An Idea owned
by a real user therefore survives its promoted task being removed, and reads
"Became a task, since deleted." -- which is the one way this deletion is
visible to anybody who still exists.
"""
from django.db import migrations


def delete_ownerless_lists(apps, schema_editor):
    List = apps.get_model("lists", "List")
    Item = apps.get_model("lists", "Item")

    orphans = List.objects.filter(owner__isnull=True)
    stranded_tasks = Item.objects.filter(list__owner__isnull=True).count()
    orphan_count = orphans.count()

    orphans.delete()

    print(
        f"ownerless area removal: areas={orphan_count} "
        f"tasks={stranded_tasks}"
    )


def irreversible(apps, schema_editor):
    """Deliberately a no-op -- see the module docstring."""


class Migration(migrations.Migration):
    dependencies = [
        ("lists", "0027_retire_subtask_fields"),
    ]

    operations = [
        migrations.RunPython(delete_ownerless_lists, irreversible),
    ]
