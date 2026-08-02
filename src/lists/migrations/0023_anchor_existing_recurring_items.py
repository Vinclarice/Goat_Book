"""Give every existing repeating task a commitment, so series start today.

Crane 0a adds the identity key, but rows created before it have none. Without
this, an existing recurring task stays unlinked until its next completion --
which for a monthly commitment is up to a month of history still accruing
unlinkable. One commitment per existing repeating root closes that window.

**What this deliberately does not do** is reconstruct past series by matching
on (list, text, recurrence). At today's row counts that would mostly work,
which is exactly what makes it tempting. It would also silently merge two
genuinely distinct tasks that happen to share a title, and silently split any
series whose text was ever edited -- inventing history indistinguishable from
the real thing. Already-archived occurrences therefore stay unlinked, and the
gap stays visible. See design/crane-plan.md 3, "Legacy rows, and the honest
limit."
"""
from django.db import migrations


def anchor_existing(apps, schema_editor):
    Item = apps.get_model("lists", "Item")
    RecurringCommitment = apps.get_model("lists", "RecurringCommitment")

    repeating = (
        Item.objects.filter(parent__isnull=True, commitment__isnull=True)
        .exclude(recurrence="none")
        # An owner is required, and List.owner is still nullable for
        # anonymous-era reasons. Such a row can't be anchored; skip it rather
        # than fail the migration.
        .exclude(list__owner__isnull=True)
        .select_related("list")
    )
    for item in repeating:
        item.commitment = RecurringCommitment.objects.create(owner_id=item.list.owner_id)
        item.save(update_fields=["commitment"])


def unanchor(apps, schema_editor):
    Item = apps.get_model("lists", "Item")
    RecurringCommitment = apps.get_model("lists", "RecurringCommitment")

    # Unlink before deleting: Item.commitment is PROTECT, so the occupied
    # rows have to let go first.
    Item.objects.filter(commitment__isnull=False).update(commitment=None)
    RecurringCommitment.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("lists", "0022_recurringcommitment_item_commitment_and_more"),
    ]

    operations = [
        migrations.RunPython(anchor_existing, unanchor),
    ]
