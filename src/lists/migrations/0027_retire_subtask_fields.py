"""Contract: retire the self-FK subtask fields -- release-d-plan.md 2, 5.

Drops Item.parent, Item.always_recurs and Item.archive_group. Safe by this
point in the sequence: 0026 converted or promoted every subtask it could
reach, and nothing has created a new one since (the only UI paths that could
were removed from the frontend in slice 3).

The one bounded, already-accepted gap: 0026 skips subtasks under an
owner-less List, because a ChecklistStep requires an owner and List.owner is
still nullable for anonymous-era reasons. Any such row -- there are none in
this database, and there is no path that creates one anymore -- loses its
parent link outright when this migration runs, the same kind of gap Crane
0a accepted for pre-existing recurring series it could not retroactively
link. Not reversible in the sense that matters: the columns can be
recreated, but no migration can repopulate what they held.

The unique_active_item and unique_open_checklist_step_text constraints are
also simplified here, dropping nulls_distinct=False from both. That flag
existed only because Item.parent was nullable and appeared in the
constraint's fields; text and its remaining sibling fields on both models
are never null, so the flag was doing nothing once parent left. Concretely:
both constraints are now enforced on SQLite too, which they were not before
-- see the constraint tests un-skipped in the same commit.
"""
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('lists', '0026_convert_subtasks_to_checklist_steps'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='checkliststep',
            name='unique_open_checklist_step_text',
        ),
        migrations.RemoveConstraint(
            model_name='item',
            name='unique_active_item',
        ),
        migrations.RemoveIndex(
            model_name='item',
            name='item_parent_state_idx',
        ),
        migrations.RemoveField(
            model_name='item',
            name='always_recurs',
        ),
        migrations.RemoveField(
            model_name='item',
            name='archive_group',
        ),
        migrations.RemoveField(
            model_name='item',
            name='parent',
        ),
        migrations.AddConstraint(
            model_name='checkliststep',
            constraint=models.UniqueConstraint(condition=models.Q(('is_done', False)), fields=('task', 'text'), name='unique_open_checklist_step_text'),
        ),
        migrations.AddConstraint(
            model_name='item',
            constraint=models.UniqueConstraint(condition=models.Q(('status', 'archived'), _negated=True), fields=('list', 'text'), name='unique_active_item'),
        ),
    ]
