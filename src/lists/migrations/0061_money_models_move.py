"""`lists` gives up the five money models. **No table moves and no row moves.**

The mirror of `money.0001_money_models_move`, and the second half of step 4.
Everything is inside `SeparateDatabaseAndState`: Django's state stops believing
`lists` owns these models, and the database is not touched — the tables are
still called `lists_bill`, `lists_account` and so on, because `money.models`
pins `db_table` to exactly those names.

**Depends on `money.0001`**, so the models exist in `money`'s state before they
leave this one. The other order would leave the foreign keys between them
dangling at a point in the graph, which `makemigrations` would not notice and a
fresh `migrate` would.

**The tables outlive the app label, deliberately.** See `money/models.py` for
why renaming them was declined rather than forgotten.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('lists', '0060_bill_amount_not_negative'),
        # Created there before deleted here, so the keys between these five
        # resolve at every point in the graph.
        ('money', '0001_money_models_move'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
            migrations.RemoveField(
                model_name='account',
                name='owner',
            ),
            migrations.RemoveField(
                model_name='bill',
                name='account',
            ),
            migrations.RemoveField(
                model_name='billseries',
                name='account',
            ),
            migrations.RemoveField(
                model_name='bill',
                name='category',
            ),
            migrations.RemoveField(
                model_name='bill',
                name='owner',
            ),
            migrations.RemoveField(
                model_name='bill',
                name='series',
            ),
            migrations.RemoveField(
                model_name='billseries',
                name='category',
            ),
            migrations.RemoveField(
                model_name='billseries',
                name='owner',
            ),
            migrations.RemoveField(
                model_name='moneycategory',
                name='owner',
            ),
            migrations.DeleteModel(
                name='BalanceReading',
            ),
            migrations.DeleteModel(
                name='Account',
            ),
            migrations.DeleteModel(
                name='Bill',
            ),
            migrations.DeleteModel(
                name='BillSeries',
            ),
            migrations.DeleteModel(
                name='MoneyCategory',
            ),
            ],
            database_operations=[],
        ),
    ]
