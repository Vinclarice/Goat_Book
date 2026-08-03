"""0028 removes anonymous-era Lists so 0029 can make the owner required.

release-d-plan.md 5 slice 6, closing the last item
architecture-trajectory.md 6 calls "the last anonymous-era hole". That
document offers two branches -- backfill or remove orphans -- and removal is
the one chosen: an ownerless List is unreachable, because every query in the
application is owner-scoped, so nothing that any user can see is being
destroyed.

Driven through the real MigrationExecutor against the real migration files,
same as test_checklist_step_backfill.py: reimplementing the query here would
assert the test back at itself.
"""
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

from accounts.models import User


# capture is named alongside lists so Idea is present in the historical
# state -- project_state only carries the apps the target actually reaches,
# and the SET_NULL case below needs both.
BEFORE = [("lists", "0027_retire_subtask_fields"), ("capture", "0004_idea_idea_owner_status_idx")]
AFTER = [("lists", "0029_list_owner_required"), ("capture", "0004_idea_idea_owner_status_idx")]


class OwnerlessListRemovalTest(TransactionTestCase):
    def migrate(self, target):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(target)
        return executor.loader.project_state(target).apps

    def tearDown(self):
        # Leave the test database where the rest of the suite expects it.
        self.migrate(AFTER)

    def test_an_ownerless_list_and_its_tasks_are_removed(self):
        old_apps = self.migrate(BEFORE)
        List = old_apps.get_model("lists", "List")
        Item = old_apps.get_model("lists", "Item")

        orphan = List.objects.create(owner=None, title="Anonymous era")
        stranded = Item.objects.create(list=orphan, text="Nobody can see me")

        new_apps = self.migrate(AFTER)
        List = new_apps.get_model("lists", "List")
        Item = new_apps.get_model("lists", "Item")

        self.assertFalse(List.objects.filter(pk=orphan.pk).exists())
        self.assertFalse(Item.objects.filter(pk=stranded.pk).exists())

    def test_an_owned_list_is_never_touched(self):
        old_apps = self.migrate(BEFORE)
        List = old_apps.get_model("lists", "List")
        Item = old_apps.get_model("lists", "Item")

        alice = User.objects.create_user("alice", "alice@example.com", "a password")
        kept = List.objects.create(owner_id=alice.pk, title="Home")
        task = Item.objects.create(list=kept, text="Still mine")

        new_apps = self.migrate(AFTER)
        List = new_apps.get_model("lists", "List")
        Item = new_apps.get_model("lists", "Item")

        self.assertTrue(List.objects.filter(pk=kept.pk).exists())
        self.assertTrue(Item.objects.filter(pk=task.pk).exists())

    def test_a_real_user_s_idea_survives_losing_the_task_it_pointed_at(self):
        """The one way this deletion is visible to somebody who still exists.

        An Idea belongs to a real owner but can point at a promoted task,
        and that task could have been sitting in an ownerless List. The FK
        is SET_NULL -- the same protection delete_archived_item relies on --
        so the Idea survives and reads "Became a task, since deleted."
        rather than being cascaded away with the orphan.
        """
        old_apps = self.migrate(BEFORE)
        List = old_apps.get_model("lists", "List")
        Item = old_apps.get_model("lists", "Item")
        Idea = old_apps.get_model("capture", "Idea")

        alice = User.objects.create_user("alice", "alice@example.com", "a password")
        orphan = List.objects.create(owner=None, title="Anonymous era")
        stranded = Item.objects.create(list=orphan, text="Promoted long ago")
        idea = Idea.objects.create(
            owner_id=alice.pk, text="An old thought", promoted_task=stranded,
        )

        new_apps = self.migrate(AFTER)
        Idea = new_apps.get_model("capture", "Idea")

        survivor = Idea.objects.get(pk=idea.pk)
        self.assertIsNone(survivor.promoted_task_id)
