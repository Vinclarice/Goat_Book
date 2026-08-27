"""Rename `Bill` to `MoneyLine` and give it a direction.

**Hand-written, and the reason matters.** `makemigrations` produced a
`CreateModel` plus a `DeleteModel` for this, because Django cannot detect a
model rename without asking and asking needs a terminal it did not have.
Applying that would have **dropped the table and every bill in it**, under a
migration whose auto-generated name reads like a rename.

So: `RenameModel`, which keeps the rows. Then the reverse accessor, the new
column, and the constraint renamed to follow the model -- as a remove and an add,
because Django has `RenameIndex` and no `RenameConstraint`.

`direction` defaults to `out`, so every existing row is a bill, which is what
every existing row is.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("lists", "0047_bill_paid_amount"),
    ]

    operations = [
        migrations.RenameModel(old_name="Bill", new_name="MoneyLine"),
        migrations.AlterField(
            model_name="moneyline",
            name="item",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="money_line",
                to="lists.item",
            ),
        ),
        migrations.AddField(
            model_name="moneyline",
            name="direction",
            field=models.CharField(
                choices=[("out", "Money out"), ("in", "Money in")],
                default="out",
                max_length=3,
            ),
        ),
        migrations.RemoveConstraint(
            model_name="moneyline",
            name="bill_amount_not_negative",
        ),
        migrations.AddConstraint(
            model_name="moneyline",
            constraint=models.CheckConstraint(
                condition=models.Q(("amount__isnull", True), ("amount__gte", 0), _connector="OR"),
                name="money_line_amount_not_negative",
            ),
        ),
    ]
