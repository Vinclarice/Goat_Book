from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth import BACKEND_SESSION_KEY, HASH_SESSION_KEY, SESSION_KEY
from django.contrib.sessions.backends.db import SessionStore
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone


class UsernamePasswordMigrationTest(TransactionTestCase):
    migrate_from = [
        ("accounts", "0002_token"),
        ("lists", "0006_alter_item_options"),
    ]
    migrate_to = [
        ("accounts", "0003_username_password_auth"),
        ("lists", "0009_task_completion_and_archive"),
    ]

    def setUp(self):
        super().setUp()
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_from)
        old_apps = executor.loader.project_state(self.migrate_from).apps
        LegacyUser = old_apps.get_model("accounts", "User")
        LegacyUser.objects.create(email="edith@example.com")

        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_to)
        self.migrated_apps = executor.loader.project_state(self.migrate_to).apps

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def test_legacy_account_gets_a_username_and_no_guessable_password(self):
        User = self.migrated_apps.get_model("accounts", "User")
        user = User.objects.get(email="edith@example.com")

        self.assertEqual(user.username, "edith")
        self.assertTrue(user.password.startswith("!"))


class NumericUserMigrationTest(TransactionTestCase):
    migrate_from = [
        ("accounts", "0003_username_password_auth"),
        ("lists", "0009_task_completion_and_archive"),
        ("sessions", "0001_initial"),
    ]
    migrate_to = [
        ("accounts", "0005_migrate_session_user_ids"),
        ("lists", "0012_item_status_and_update_times"),
        ("sessions", "0001_initial"),
    ]

    def setUp(self):
        super().setUp()
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_from)
        old_apps = executor.loader.project_state(self.migrate_from).apps
        LegacyUser = old_apps.get_model("accounts", "User")
        LegacyList = old_apps.get_model("lists", "List")
        LegacyItem = old_apps.get_model("lists", "Item")
        LegacySession = old_apps.get_model("sessions", "Session")

        self.password_hash = "pbkdf2_sha256$preserved$password"
        user = LegacyUser.objects.create(
            email="edith@example.com",
            username="edith",
            password=self.password_hash,
        )
        list_ = LegacyList.objects.create(owner=user, title="Programming")
        LegacyItem.objects.create(
            list=list_,
            text="Preserve me",
            is_completed=True,
            completed_at="2026-07-24T12:00:00Z",
        )
        self.session_key = "preserved-session"
        store = SessionStore(session_key=self.session_key)
        LegacySession.objects.create(
            session_key=self.session_key,
            session_data=store.encode(
                {
                    SESSION_KEY: user.pk,
                    BACKEND_SESSION_KEY: (
                        "django.contrib.auth.backends.ModelBackend"
                    ),
                    HASH_SESSION_KEY: "preserved-auth-hash",
                }
            ),
            expire_date=timezone.now() + timedelta(days=1),
        )

        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_to)
        self.migrated_apps = executor.loader.project_state(self.migrate_to).apps

        # test_user_ownership_and_task_state_are_preserved queries through
        # the live (current) User/List/Item models rather than this
        # snapshot, so bring 'lists' the rest of the way to its real head
        # -- otherwise the live Item model's newer fields (due_date,
        # position, tags, recurrence, ...) won't exist in a database only
        # migrated up to this test's fixed migrate_to point.
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes(app="lists"))

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def test_user_ownership_and_task_state_are_preserved(self):
        User = get_user_model()
        user = User.objects.get(email="edith@example.com")
        list_ = user.lists.get(title="Programming")
        item = list_.item_set.get(text="Preserve me")

        self.assertIsInstance(user.pk, int)
        self.assertEqual(user.password, self.password_hash)
        self.assertEqual(item.status, "completed")
        self.assertIsNotNone(item.completed_at)

    def test_existing_login_session_uses_the_new_numeric_user_id(self):
        Session = self.migrated_apps.get_model("sessions", "Session")
        User = self.migrated_apps.get_model("accounts", "User")
        session = Session.objects.get(session_key=self.session_key)
        user = User.objects.get(email="edith@example.com")

        self.assertEqual(
            SessionStore().decode(session.session_data)[SESSION_KEY],
            str(user.pk),
        )
