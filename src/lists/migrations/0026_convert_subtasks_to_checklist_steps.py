"""Convert existing self-FK subtasks into ChecklistStep rows.

Not every existing subtask fits the new model. A child with no due date, no
tags, no notes, and no recurrence becomes a ChecklistStep, copying its
completion state and always_recurs flag across; the original Item row is
deleted once copied, because a step and a subtask are not two
representations of one fact, and leaving both around would be exactly the
two-sources-of-truth drift principles.md forbids.

A child that carries a due date, a tag, notes, or a recurrence value doesn't
fit -- ChecklistStep was deliberately built without those fields -- and is
promoted instead: it stops being a subtask (parent cleared) and keeps
whatever the new model couldn't hold, repositioned after its list's existing
root tasks. Nothing is silently dropped; the migration's own printed counts
are the evidence for what actually existed in this database. See
design/release-d-plan.md 2, "Migrate."

Deleting a converted child is schema-safe even if it was ever pinned to a
day or promoted from a capture/idea: DailyFocus.task, Idea.promoted_task and
Capture.promoted_task are all SET_NULL, the same protection
delete_archived_item already relies on.

Owner-less rows are skipped, same reasoning as
0023_anchor_existing_recurring_items: List.owner is still nullable for
anonymous-era reasons, and ChecklistStep.owner is not. A skipped subtask
keeps its old shape untouched -- there's nowhere to move it to responsibly.
"""
from django.db import migrations
from django.db.models import Max


def convert_subtasks(apps, schema_editor):
    Item = apps.get_model("lists", "Item")
    ChecklistStep = apps.get_model("lists", "ChecklistStep")

    skipped = Item.objects.filter(
        parent__isnull=False, list__owner__isnull=True
    ).count()

    subtasks = (
        Item.objects.filter(parent__isnull=False, list__owner__isnull=False)
        .select_related("list")
        .order_by("parent_id", "position")
    )

    next_root_position = {}
    converted = promoted = 0

    for child in subtasks:
        fits = (
            child.due_date is None
            and child.recurrence == "none"
            and child.commitment_id is None
            and not child.notes
            and not child.tags.exists()
        )
        if fits:
            ChecklistStep.objects.create(
                owner_id=child.list.owner_id,
                task_id=child.parent_id,
                text=child.text,
                position=child.position,
                is_done=(child.status == "completed"),
                completed_at=child.completed_at,
                carries_forward=child.always_recurs,
            )
            child.delete()
            converted += 1
        else:
            list_id = child.list_id
            if list_id not in next_root_position:
                highest = Item.objects.filter(
                    list_id=list_id, parent__isnull=True
                ).aggregate(Max("position"))["position__max"]
                next_root_position[list_id] = 0 if highest is None else highest + 1
            child.parent = None
            child.position = next_root_position[list_id]
            child.save(update_fields=["parent", "position"])
            next_root_position[list_id] += 1
            promoted += 1

    print(
        f"checklist step conversion: converted={converted} "
        f"promoted={promoted} skipped(no owner)={skipped}"
    )


def revert(apps, schema_editor):
    """Best-effort only, like 0023's unanchor: which Items were promoted, and
    which ChecklistSteps came from which converted child, isn't recoverable
    after the fact. Kept so reversing doesn't fail outright; not a real undo,
    and a promoted child's parent link is not restored.
    """
    ChecklistStep = apps.get_model("lists", "ChecklistStep")
    ChecklistStep.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("lists", "0025_checklist_step"),
    ]

    operations = [
        migrations.RunPython(convert_subtasks, revert),
    ]
