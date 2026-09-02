"""Moving Money into its own app changed no table and no row.

**The claim step 4 makes, asserted rather than trusted.** `money.0001` and
`lists.0061` move five models between apps with `SeparateDatabaseAndState`, so
Django's idea of who owns them changes and the database does not. That is easy
to write, easy to believe, and would be discovered wrong by a deploy against
production data.

**Two different things are checked here and both matter.**

The migrations must emit no SQL. A `CreateModel` that escaped its
`state_operations` list would build a second set of tables under `money_*`,
leave the real rows behind in `lists_*`, and look like a successful deploy.

And the tables must still be called `lists_*`. `db_table` is the only thing
holding that, one line per model, and losing one is an `ALTER TABLE ... RENAME`
on somebody's financial history — silent in review, because a model without
`db_table` looks like every other model in the codebase.

**Why the names are `lists_` at all** is in `money/models.py`: renaming them
buys consistency in `psql` and costs a physical migration over real data, which
was declined on September 2, 2026 rather than overlooked. This test is what
makes that decision durable — if somebody decides otherwise, they have to come
here and say so.
"""
from django.apps import apps
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

#: Model to the table it has had since it was created, before Money was an app.
TABLES = {
    "Account": "lists_account",
    "BalanceReading": "lists_balancereading",
    "MoneyCategory": "lists_moneycategory",
    "BillSeries": "lists_billseries",
    "Bill": "lists_bill",
}

#: The two halves of the move. Neither may touch the database.
STATE_ONLY = [("money", "0001_money_models_move"), ("lists", "0061_money_models_move")]


class TheMoneyMoveTouchedNoTableTest(TransactionTestCase):
    def test_every_money_model_keeps_the_table_it_was_created_with(self):
        for name, table in TABLES.items():
            with self.subTest(model=name):
                model = apps.get_model("money", name)
                self.assertEqual(
                    model._meta.db_table,
                    table,
                    f"money.{name} would live in {model._meta.db_table}. It was "
                    f"created as {table} and holds real financial history; "
                    "renaming it is a physical migration, not a side effect of "
                    "changing app labels.",
                )

    def test_the_models_belong_to_money_now(self):
        """The other half of the same fact: the label moved even though the
        table did not."""
        for name in TABLES:
            with self.subTest(model=name):
                self.assertEqual(apps.get_model("money", name)._meta.app_label, "money")

    def test_neither_half_of_the_move_emits_any_sql(self):
        """Read out of the migration itself rather than asserted about the
        current schema, so this still fails on a database where somebody has
        already applied a wrong version by hand."""
        loader = MigrationExecutor(connection).loader
        for app_label, name in STATE_ONLY:
            with self.subTest(migration=f"{app_label}.{name}"):
                migration = loader.get_migration(app_label, name)
                for operation in migration.operations:
                    self.assertEqual(
                        type(operation).__name__,
                        "SeparateDatabaseAndState",
                        f"{app_label}.{name} carries a bare "
                        f"{type(operation).__name__}, which will run against the "
                        "database. Every operation in these two must be wrapped.",
                    )
                    self.assertEqual(
                        operation.database_operations,
                        [],
                        f"{app_label}.{name} has database operations. The move "
                        "is state-only; anything real here rewrites tables that "
                        "already hold somebody's money.",
                    )
                    self.assertTrue(
                        operation.state_operations,
                        f"{app_label}.{name} wraps nothing, so it moves no state",
                    )

    def test_the_tables_are_actually_there_under_those_names(self):
        """A positive control against the database rather than the schema
        objects: a mapping that agreed with itself and with nothing real would
        pass the first test and mean nothing."""
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public'"
            )
            present = {row[0] for row in cursor.fetchall()}

        for name, table in TABLES.items():
            with self.subTest(model=name):
                self.assertIn(table, present)

    def test_no_money_prefixed_table_was_created(self):
        """What a `CreateModel` outside `state_operations` would leave behind:
        a second, empty set of tables, with the real rows still in the first."""
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name LIKE 'money_%%'"
            )
            stray = [row[0] for row in cursor.fetchall()]

        self.assertEqual(
            stray,
            [],
            "tables were created under the money_ prefix. The rows are in the "
            "lists_ ones, so these are empty duplicates and the app is reading "
            "the wrong half.",
        )
