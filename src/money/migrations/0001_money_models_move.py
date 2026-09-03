"""Money takes ownership of its five models. **No table moves and no row moves.**

Step 4 of `design/roadmap.md`'s Money-app extraction. Everything here is inside
`SeparateDatabaseAndState`, so Django's migration state learns that these models
belong to `money` and **the database is not touched at all** — `sqlmigrate` on
this migration emits nothing but the transaction wrapper, which is the whole
point and is asserted by
`clarice/tests/test_the_money_move_touched_no_table.py`.

**The tables keep their `lists_` names**, pinned by `db_table` on each model.
They hold somebody's financial history and renaming them buys tidiness in
`psql` and nothing else; `0057` deleted rows and `0059` dropped a table in the
same week, and a third physical migration for a cosmetic gain is not that
trade. If it is ever worth doing it is its own decision — declined here rather
than overlooked.

**Runs before `lists.0061`, which is the mirror of this.** That one deletes the
same models from `lists`' state, also without touching the database. Creating
before deleting keeps the foreign keys between these five resolvable at every
point in the graph.

**Safe on a fresh database as well as an existing one.** On an existing one the
tables are already there and this changes only who Django thinks owns them. On
a fresh one — CI builds every test database this way — `lists.0053` still
creates the physical tables under their `lists_` names earlier in the graph,
and this adopts them.
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        # **After the migrations that physically create these tables.** This one
        # creates nothing -- it is state-only -- so without saying so, Django is
        # free to order it before `lists.0053`, and money's state would then
        # claim models whose tables do not exist yet.
        #
        # Added September 3, 2026 after `accounts.tests.test_migrations` failed
        # with *relation "lists_account" does not exist*: it rewinds the whole
        # graph, which is the one path that exercises the ordering. A
        # forward-only build happened to be fine and proved nothing.
        ("lists", "0060_bill_amount_not_negative"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
            migrations.CreateModel(
                name='Account',
                fields=[
                    ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                    ('name', models.CharField(max_length=120)),
                    ('kind', models.CharField(choices=[('card', 'Credit card'), ('loan', 'Loan'), ('savings', 'Savings'), ('investment', 'Investment')], default='card', max_length=12)),
                    ('currency', models.CharField(default='USD', max_length=3)),
                    ('owes', models.BooleanField(default=True)),
                    ('created_at', models.DateTimeField(auto_now_add=True)),
                    ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='accounts', to=settings.AUTH_USER_MODEL)),
                ],
                options={
                    'db_table': 'lists_account',
                    'ordering': ('name',),
                },
            ),
            migrations.CreateModel(
                name='BalanceReading',
                fields=[
                    ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                    ('on_date', models.DateField()),
                    ('amount', models.DecimalField(decimal_places=2, max_digits=12)),
                    ('recorded_at', models.DateTimeField(auto_now=True)),
                    ('account', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='readings', to='money.account')),
                ],
                options={
                    'db_table': 'lists_balancereading',
                    'ordering': ('-on_date',),
                },
            ),
            migrations.CreateModel(
                name='MoneyCategory',
                fields=[
                    ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                    ('name', models.CharField(max_length=60)),
                    ('position', models.PositiveIntegerField(default=0)),
                    ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='money_categories', to=settings.AUTH_USER_MODEL)),
                ],
                options={
                    'db_table': 'lists_moneycategory',
                    'ordering': ('position', 'name'),
                },
            ),
            migrations.CreateModel(
                name='BillSeries',
                fields=[
                    ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                    ('payee', models.CharField(max_length=200)),
                    ('amount', models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                    ('currency', models.CharField(default='USD', max_length=3)),
                    ('direction', models.CharField(choices=[('out', 'Money out'), ('in', 'Money in')], default='out', max_length=3)),
                    ('cadence', models.CharField(choices=[('none', "Doesn't repeat"), ('daily', 'Daily'), ('weekly', 'Weekly'), ('fortnightly', 'Every two weeks'), ('monthly', 'Monthly'), ('quarterly', 'Quarterly'), ('annual', 'Annually')], default='monthly', max_length=20)),
                    ('cadence_mode', models.CharField(choices=[('anchored', 'On a fixed schedule'), ('floating', 'A set time after it is done')], default='anchored', max_length=20)),
                    ('lead_days', models.PositiveSmallIntegerField(default=0)),
                    ('created_at', models.DateTimeField(auto_now_add=True)),
                    ('ended_at', models.DateTimeField(blank=True, null=True)),
                    ('account', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='bill_series', to='money.account')),
                    ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='bill_series', to=settings.AUTH_USER_MODEL)),
                    ('category', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='bill_series', to='money.moneycategory')),
                ],
                options={
                    'verbose_name_plural': 'bill series',
                    'db_table': 'lists_billseries',
                },
            ),
            migrations.CreateModel(
                name='Bill',
                fields=[
                    ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                    ('due_date', models.DateField()),
                    ('payee', models.CharField(max_length=200)),
                    ('amount', models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                    ('currency', models.CharField(default='USD', max_length=3)),
                    ('direction', models.CharField(choices=[('out', 'Money out'), ('in', 'Money in')], default='out', max_length=3)),
                    ('paid_amount', models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                    ('paid_at', models.DateTimeField(blank=True, null=True)),
                    ('lead_days', models.PositiveSmallIntegerField(default=0)),
                    ('notes', models.TextField(blank=True, default='')),
                    ('created_at', models.DateTimeField(auto_now_add=True)),
                    ('updated_at', models.DateTimeField(auto_now=True)),
                    ('account', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='bills', to='money.account')),
                    ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='bills', to=settings.AUTH_USER_MODEL)),
                    ('series', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='occurrences', to='money.billseries')),
                    ('category', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='bills', to='money.moneycategory')),
                ],
                options={
                    'db_table': 'lists_bill',
                },
            ),
            migrations.AddConstraint(
                model_name='account',
                constraint=models.UniqueConstraint(fields=('owner', 'name'), name='unique_account_name_per_owner'),
            ),
            migrations.AddConstraint(
                model_name='balancereading',
                constraint=models.UniqueConstraint(fields=('account', 'on_date'), name='one_reading_per_account_per_month'),
            ),
            migrations.AddConstraint(
                model_name='moneycategory',
                constraint=models.UniqueConstraint(fields=('owner', 'name'), name='unique_money_category_per_owner'),
            ),
            migrations.AddIndex(
                model_name='billseries',
                index=models.Index(fields=['owner', '-created_at'], name='bill_series_owner'),
            ),
            migrations.AddIndex(
                model_name='bill',
                index=models.Index(fields=['owner', 'due_date'], name='bill_owner_due'),
            ),
            migrations.AddIndex(
                model_name='bill',
                index=models.Index(fields=['owner', 'paid_at'], name='bill_owner_paid_at'),
            ),
            migrations.AddIndex(
                model_name='bill',
                index=models.Index(fields=['series', 'due_date'], name='bill_series_due'),
            ),
            migrations.AddConstraint(
                model_name='bill',
                constraint=models.CheckConstraint(condition=models.Q(('paid_amount__isnull', True), ('paid_at__isnull', False), _connector='OR'), name='bill_paid_at_and_amount_agree'),
            ),
            migrations.AddConstraint(
                model_name='bill',
                constraint=models.UniqueConstraint(fields=('series', 'due_date'), name='bill_one_occurrence_per_period'),
            ),
            migrations.AddConstraint(
                model_name='bill',
                constraint=models.CheckConstraint(condition=models.Q(models.Q(('amount__isnull', True), ('amount__gte', 0), _connector='OR'), models.Q(('paid_amount__isnull', True), ('paid_amount__gte', 0), _connector='OR')), name='bill_amount_not_negative'),
            ),
            ],
            database_operations=[],
        ),
    ]
