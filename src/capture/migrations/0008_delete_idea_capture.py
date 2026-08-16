"""The Inbox's tables, dropped. Heron step 4b.

**This is irreversible and is meant to be.** There is no reverse operation that
brings the rows back, so the safety is entirely in what ran before it:
`migrate_inbox` moved every `Capture` and every `Idea` into the graph as a
`Node`, keeping its original `captured_at`, its tags as confirmed concepts, its
archived state where it had been discarded, and its link to whatever task it
became. That command was idempotent on `import_key` and was run a final time on
production on August 15, 2026, catching the one capture that had arrived since
the previous run.

Verify before applying anywhere the migration has not already run. The question
is not "does the graph have nodes" but "does it have one per capture":

    Capture.objects.count() + Idea.objects.count()
    == Node.objects.filter(import_key__startswith="inbox:").count()

`lists.Tag` is untouched. It was always the shared vocabulary rather than
capture's own, and `Item` still uses it — only the two join tables go.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("capture", "0007_idea_related_ideas"),
    ]

    operations = [
        # The index goes before the fields it covers, and this is not tidiness.
        # `idea_owner_status_idx` is on ("owner", "status", "-created_at"), and
        # the autodetector wrote the field removals without it -- which applies
        # fine and *reverses* into a broken state: unapplying `DeleteModel` runs
        # before unapplying `RemoveField`, so Django rebuilds the table and then
        # tries to index a column it has not re-added yet.
        #
        # `FieldDoesNotExist: Idea has no field named 'owner'`, and it is the
        # migration-rewind tests in `lists` that see it, not anything here.
        # Nothing in production would ever have hit it. It is fixed rather than
        # waived because a migration that cannot be unapplied is one nobody can
        # back out of at the moment they most want to.
        migrations.RemoveIndex(
            model_name="idea",
            name="idea_owner_status_idx",
        ),
        # The fields come off Idea next because Capture.promoted_idea points at
        # it; dropping them in this order is what lets both models go without a
        # circular dependency between the two DeleteModels.
        migrations.RemoveField(
            model_name="idea",
            name="owner",
        ),
        migrations.RemoveField(
            model_name="idea",
            name="promoted_task",
        ),
        migrations.RemoveField(
            model_name="idea",
            name="related_ideas",
        ),
        migrations.RemoveField(
            model_name="idea",
            name="tags",
        ),
        migrations.DeleteModel(
            name="Capture",
        ),
        migrations.DeleteModel(
            name="Idea",
        ),
    ]
