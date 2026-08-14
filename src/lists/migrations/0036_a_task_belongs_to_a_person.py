"""Give every task an owner of its own.

`0035` made `Item.list` nullable; this is the half that makes that safe. See the
comment on the field for why -- in short, ownership ran through the Area, so a
task without one belonged to nobody and no query returned it.

Three steps in one file, in the order a required column has to arrive: add it
nullable, fill it from the Area every existing row already has, then require it.
Splitting them across files would leave a migration in the sequence at which the
column exists and is empty, which is a state no deploy should be able to stop in.

The backfill is `Item.list.owner` for every row, and there is no other case to
handle: `0028` deleted the ownerless Areas, and until `0035` a task could not
exist without one. So the fill is total by construction rather than by hope --
which the check after it verifies, because "by construction" is an argument and
the count is a fact.
"""

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def fill_owner_from_area(apps, schema_editor):
    Item = apps.get_model("lists", "Item")
    List = apps.get_model("lists", "List")

    # A subquery rather than `F("list__owner")`, which `update()` cannot follow
    # across a join. One statement either way, so the whole table is filled
    # before anything else in this file runs.
    updated = Item.objects.filter(owner__isnull=True).update(
        owner_id=models.Subquery(
            List.objects.filter(pk=models.OuterRef("list_id")).values("owner_id")[:1]
        )
    )
    stranded = Item.objects.filter(owner__isnull=True).count()
    print(f"item owner backfill: filled={updated} stranded={stranded}")
    if stranded:
        # The AlterField below would fail on these anyway; saying which rows and
        # why beats a bare NOT NULL violation partway through a deploy.
        raise RuntimeError(
            f"{stranded} task(s) have no Area to take an owner from. Nothing "
            "should be able to reach that state before this migration -- 0028 "
            "removed the ownerless Areas and 0035 only just allowed a task "
            "without one."
        )


def clear_owner(apps, schema_editor):
    """Reverse of the backfill.

    Only meaningful between the two schema steps, and it drops nothing that
    cannot be recomputed -- which is the test for whether a data migration is
    safely reversible.
    """
    Item = apps.get_model("lists", "Item")
    Item.objects.update(owner=None)


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("lists", "0035_item_without_an_area"),
    ]

    operations = [
        migrations.AddField(
            model_name="item",
            name="owner",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="items",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RunPython(fill_owner_from_area, clear_owner),
        migrations.AlterField(
            model_name="item",
            name="owner",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="items",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddConstraint(
            model_name="item",
            constraint=models.UniqueConstraint(
                condition=models.Q(("list__isnull", True), models.Q(("status", "archived"), _negated=True)),
                fields=("owner", "text"),
                name="unique_active_arealess_item",
            ),
        ),
    ]
