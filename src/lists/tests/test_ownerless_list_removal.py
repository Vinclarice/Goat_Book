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


# `capture` used to be named alongside `lists` here, so that `Idea` was present
# in the historical state for the SET_NULL case. That app is deleted and so is
# the case; only `lists` is reached now.
BEFORE = [("lists", "0027_retire_subtask_fields")]
AFTER = [("lists", "0029_list_owner_required")]


class OwnerlessListRemovalTest(TransactionTestCase):
    def migrate(self, target):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(target)
        return executor.loader.project_state(target).apps

    def tearDown(self):
        # Every app forward, not just the one named in AFTER -- see the note in
        # lists/tests/test_checklist_step_backfill.py for what leaving another
        # app behind costs.
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(executor.loader.graph.leaf_nodes())

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

    # A third test stood here: an `Idea` pointing at a task inside an ownerless
    # List survives the deletion, because `Idea.promoted_task` is SET_NULL. It
    # was the one way this migration was visible to somebody who still existed.
    #
    # `Idea` no longer exists -- Heron 4b deleted it and the `capture` app went
    # with it -- so the test cannot be written at all: it needed the model in a
    # historical migration state, and there is no longer a historical state that
    # contains one.
    #
    # Removed rather than replaced, and worth being plain about what that costs.
    # It is not that the risk was re-evaluated; it is that the scenario stopped
    # existing. `0028` has run everywhere it will ever run, and the object it
    # protected is deleted. What remains covered below is the part still true:
    # ownerless Lists and their Items go, real users' Lists and Items stay.
