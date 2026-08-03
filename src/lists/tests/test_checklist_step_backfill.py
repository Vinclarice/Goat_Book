"""The 0026 subtask-to-checklist-step conversion, exercised as a migration
rather than described -- release-d-plan.md 2, "Migrate."

Driven through the real MigrationExecutor against the real migration file,
same as test_commitment_backfill.py: reimplementing the query here would
assert the test back at itself.
"""
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

from accounts.models import User


BEFORE = [("lists", "0025_checklist_step")]
AFTER = [("lists", "0026_convert_subtasks_to_checklist_steps")]


class ChecklistStepBackfillTest(TransactionTestCase):
    def migrate(self, target):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(target)
        return executor.loader.project_state(target).apps

    def tearDown(self):
        # Leave the test database where the rest of the suite expects it.
        self.migrate(AFTER)

    def test_a_plain_subtask_becomes_a_checklist_step(self):
        old_apps = self.migrate(BEFORE)
        List = old_apps.get_model("lists", "List")
        Item = old_apps.get_model("lists", "Item")

        alice = User.objects.create_user("alice", "alice@example.com", "a password")
        alice_list = List.objects.create(owner_id=alice.pk, title="Home")
        parent = Item.objects.create(list=alice_list, text="Get the dog ready")
        child = Item.objects.create(
            list=alice_list,
            text="Refill medication",
            parent=parent,
            position=3,
            always_recurs=False,
        )

        new_apps = self.migrate(AFTER)
        Item = new_apps.get_model("lists", "Item")
        ChecklistStep = new_apps.get_model("lists", "ChecklistStep")

        self.assertFalse(Item.objects.filter(pk=child.pk).exists())
        step = ChecklistStep.objects.get(task_id=parent.pk)
        self.assertEqual(step.text, "Refill medication")
        self.assertEqual(step.position, 3)
        self.assertFalse(step.is_done)
        self.assertIsNone(step.completed_at)
        self.assertFalse(step.carries_forward)
        self.assertEqual(step.owner_id, alice.pk)

    def test_a_completed_subtask_becomes_a_done_step(self):
        old_apps = self.migrate(BEFORE)
        List = old_apps.get_model("lists", "List")
        Item = old_apps.get_model("lists", "Item")

        alice = User.objects.create_user("alice", "alice@example.com", "a password")
        alice_list = List.objects.create(owner_id=alice.pk, title="Home")
        parent = Item.objects.create(list=alice_list, text="Get the dog ready")
        Item.objects.create(
            list=alice_list,
            text="Book the kennel",
            parent=parent,
            status="completed",
            completed_at="2026-07-20T12:00:00Z",
        )

        new_apps = self.migrate(AFTER)
        ChecklistStep = new_apps.get_model("lists", "ChecklistStep")

        step = ChecklistStep.objects.get(text="Book the kennel")
        self.assertTrue(step.is_done)
        self.assertIsNotNone(step.completed_at)

    def test_a_due_dated_subtask_is_promoted_instead_of_converted(self):
        old_apps = self.migrate(BEFORE)
        List = old_apps.get_model("lists", "List")
        Item = old_apps.get_model("lists", "Item")

        alice = User.objects.create_user("alice", "alice@example.com", "a password")
        alice_list = List.objects.create(owner_id=alice.pk, title="Home")
        parent = Item.objects.create(list=alice_list, text="Get the dog ready")
        Item.objects.create(list=alice_list, text="Book flights", position=0)
        child = Item.objects.create(
            list=alice_list,
            text="Renew passport",
            parent=parent,
            due_date="2026-09-01",
        )

        new_apps = self.migrate(AFTER)
        Item = new_apps.get_model("lists", "Item")
        ChecklistStep = new_apps.get_model("lists", "ChecklistStep")

        promoted = Item.objects.get(pk=child.pk)
        self.assertIsNone(promoted.parent_id)
        self.assertEqual(str(promoted.due_date), "2026-09-01")
        self.assertEqual(promoted.position, 1)  # after the existing root task
        self.assertFalse(ChecklistStep.objects.filter(text="Renew passport").exists())

    def test_a_tagged_subtask_is_promoted(self):
        old_apps = self.migrate(BEFORE)
        List = old_apps.get_model("lists", "List")
        Item = old_apps.get_model("lists", "Item")
        Tag = old_apps.get_model("lists", "Tag")

        alice = User.objects.create_user("alice", "alice@example.com", "a password")
        alice_list = List.objects.create(owner_id=alice.pk, title="Home")
        parent = Item.objects.create(list=alice_list, text="Get the dog ready")
        child = Item.objects.create(
            list=alice_list, text="Book the kennel", parent=parent,
        )
        tag = Tag.objects.create(owner_id=alice.pk, name="Travel")
        child.tags.add(tag)

        new_apps = self.migrate(AFTER)
        Item = new_apps.get_model("lists", "Item")

        promoted = Item.objects.get(pk=child.pk)
        self.assertIsNone(promoted.parent_id)

    def test_a_recurring_subtask_is_promoted(self):
        """A subtask can't have a non-none recurrence in practice --
        set_recurrence rejects it -- but the migration guards it anyway
        rather than trusting an invariant a hand-edited or pre-guard row
        might violate.
        """
        old_apps = self.migrate(BEFORE)
        List = old_apps.get_model("lists", "List")
        Item = old_apps.get_model("lists", "Item")

        alice = User.objects.create_user("alice", "alice@example.com", "a password")
        alice_list = List.objects.create(owner_id=alice.pk, title="Home")
        parent = Item.objects.create(list=alice_list, text="Get the dog ready")
        child = Item.objects.create(
            list=alice_list,
            text="Weekly vet check",
            parent=parent,
            recurrence="weekly",
        )

        new_apps = self.migrate(AFTER)
        Item = new_apps.get_model("lists", "Item")

        promoted = Item.objects.get(pk=child.pk)
        self.assertIsNone(promoted.parent_id)

    def test_a_noted_subtask_is_promoted_rather_than_losing_its_notes(self):
        """The gap release-d-plan.md 2 records finding while writing this
        migration: ChecklistStep has no notes field, so a child carrying
        notes has to be promoted rather than converted, or the notes are
        silently gone.
        """
        old_apps = self.migrate(BEFORE)
        List = old_apps.get_model("lists", "List")
        Item = old_apps.get_model("lists", "Item")

        alice = User.objects.create_user("alice", "alice@example.com", "a password")
        alice_list = List.objects.create(owner_id=alice.pk, title="Home")
        parent = Item.objects.create(list=alice_list, text="Get the dog ready")
        child = Item.objects.create(
            list=alice_list,
            text="Book the kennel",
            parent=parent,
            notes="Ask for the one near the vet",
        )

        new_apps = self.migrate(AFTER)
        Item = new_apps.get_model("lists", "Item")

        promoted = Item.objects.get(pk=child.pk)
        self.assertIsNone(promoted.parent_id)
        self.assertEqual(promoted.notes, "Ask for the one near the vet")

    def test_multiple_promotions_in_one_list_do_not_collide_on_position(self):
        old_apps = self.migrate(BEFORE)
        List = old_apps.get_model("lists", "List")
        Item = old_apps.get_model("lists", "Item")

        alice = User.objects.create_user("alice", "alice@example.com", "a password")
        alice_list = List.objects.create(owner_id=alice.pk, title="Home")
        parent = Item.objects.create(list=alice_list, text="Get the dog ready")
        first = Item.objects.create(
            list=alice_list, text="Renew passport", parent=parent, due_date="2026-09-01",
        )
        second = Item.objects.create(
            list=alice_list, text="Buy a crate", parent=parent, due_date="2026-09-05",
        )

        new_apps = self.migrate(AFTER)
        Item = new_apps.get_model("lists", "Item")

        positions = {
            Item.objects.get(pk=first.pk).position,
            Item.objects.get(pk=second.pk).position,
        }
        self.assertEqual(len(positions), 2)

    def test_an_ownerless_lists_subtasks_are_left_untouched(self):
        """At 0026, List.owner is still nullable and ChecklistStep.owner is not.

        Reads as history now: 0028 deletes these rows and 0029 makes the
        column required, so no database reaching 0029 still has one. The
        skip-clause 0026 had to write for them is exactly what release D
        slice 6 removed the need for -- but 0026 still has to behave this way
        when replayed from an old database, which is what this asserts.
        """
        old_apps = self.migrate(BEFORE)
        List = old_apps.get_model("lists", "List")
        Item = old_apps.get_model("lists", "Item")

        orphan_list = List.objects.create(owner=None, title="Anonymous era")
        parent = Item.objects.create(list=orphan_list, text="Get the dog ready")
        child = Item.objects.create(
            list=orphan_list, text="Refill medication", parent=parent,
        )

        new_apps = self.migrate(AFTER)
        Item = new_apps.get_model("lists", "Item")
        ChecklistStep = new_apps.get_model("lists", "ChecklistStep")

        self.assertTrue(Item.objects.filter(pk=child.pk).exists())
        self.assertEqual(ChecklistStep.objects.count(), 0)

    def test_a_root_task_is_never_touched(self):
        old_apps = self.migrate(BEFORE)
        List = old_apps.get_model("lists", "List")
        Item = old_apps.get_model("lists", "Item")

        alice = User.objects.create_user("alice", "alice@example.com", "a password")
        alice_list = List.objects.create(owner_id=alice.pk, title="Home")
        root = Item.objects.create(list=alice_list, text="Book flights", position=0)

        new_apps = self.migrate(AFTER)
        Item = new_apps.get_model("lists", "Item")

        unchanged = Item.objects.get(pk=root.pk)
        self.assertIsNone(unchanged.parent_id)
        self.assertEqual(unchanged.position, 0)
