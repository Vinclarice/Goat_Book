"""A database built from scratch ends up where the migrated one did.

**Every test database is a fresh build**, so this is the path CI takes and the
path a restore drill takes -- and it is a different path from the one a deploy
takes. A migration pair that is correct forwards over existing data can still be
wrong from empty, and nothing else here would notice.

Written for step 4 of the Money extraction, where the risk is concrete:
`money.0001` adopts tables that `lists.0053` created under `lists_` names
earlier in the same graph. If `db_table` were ever lost, a fresh build would
quietly create `money_bill` alongside `lists_bill` and every test would pass
against the empty one.
"""
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.test import TestCase

MODELS = ("account", "balancereading", "moneycategory", "billseries", "bill")


class AFreshDatabaseLandsWhereThisOneDidTest(TestCase):
    """This test class runs against a database Django has just built by running
    every migration from empty, which is what makes it the fresh-build check."""

    def test_the_money_tables_are_the_lists_ones(self):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' AND "
                "(table_name LIKE 'money%%' OR table_name LIKE 'lists_bill%%')"
            )
            names = sorted(row[0] for row in cursor.fetchall())

        self.assertIn("lists_bill", names)
        self.assertIn("lists_billseries", names)
        self.assertEqual(
            [n for n in names if n.startswith("money")],
            [],
            "a fresh build created tables under the money prefix. On a deploy "
            "the rows are in the lists_ ones, so the two paths have diverged "
            "and only one of them is being tested.",
        )

    def test_content_types_are_not_duplicated(self):
        for model in MODELS:
            with self.subTest(model=model):
                labels = sorted(
                    ContentType.objects.filter(model=model)
                    .values_list("app_label", flat=True)
                )
                self.assertEqual(
                    labels,
                    ["money"],
                    f"{model} has content types under {labels}. Two means every "
                    "permission on it is listed twice and one of them grants "
                    "nothing.",
                )

    def test_each_money_model_has_its_four_permissions_once(self):
        for model in MODELS:
            with self.subTest(model=model):
                self.assertEqual(
                    Permission.objects.filter(content_type__model=model).count(),
                    4,
                    "add, change, delete and view -- once each",
                )
