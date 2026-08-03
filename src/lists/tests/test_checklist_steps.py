"""Service-level behaviour for checklist steps -- release-d-plan.md 2.

Kept separate from test_services.py the same way test_subtasks.py is: this
is the bulk of one feature, not a few more cases for the existing ones.
"""
from django.test import TestCase

from accounts.models import User
from lists import services
from lists.models import ChecklistStep, Item, List


class ChecklistStepServiceTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", "a secure password",
        )
        self.list_ = List.objects.create(owner=self.user, title="Travel")
        self.task = services.create_item(self.list_, "Get the dog ready")

    def refresh(self, step):
        return ChecklistStep.objects.get(pk=step.pk)


class AddStepTest(ChecklistStepServiceTest):
    def test_a_step_belongs_to_its_task_and_owner(self):
        step = services.add_checklist_step(self.task, "Refill medication")

        self.assertEqual(step.task_id, self.task.pk)
        self.assertEqual(step.owner_id, self.user.pk)

    def test_defaults_to_not_done_and_carries_forward(self):
        step = services.add_checklist_step(self.task, "Refill medication")

        self.assertFalse(step.is_done)
        self.assertTrue(step.carries_forward)

    def test_carries_forward_can_be_opted_out_at_creation(self):
        step = services.add_checklist_step(
            self.task, "Wash the crate", carries_forward=False,
        )

        self.assertFalse(step.carries_forward)

    def test_positions_run_within_the_task(self):
        first = services.add_checklist_step(self.task, "Refill medication")
        second = services.add_checklist_step(self.task, "Book the kennel")

        self.assertEqual([first.position, second.position], [0, 1])

    def test_duplicate_open_step_text_is_rejected(self):
        services.add_checklist_step(self.task, "Refill medication")

        with self.assertRaises(services.TaskConflict):
            services.add_checklist_step(self.task, "Refill medication")

    def test_the_same_text_is_allowed_under_a_different_task(self):
        other_task = services.create_item(self.list_, "Plan Japan trip")
        services.add_checklist_step(self.task, "Book flights")

        twin = services.add_checklist_step(other_task, "Book flights")

        self.assertEqual(twin.text, "Book flights")

    def test_cannot_add_a_step_to_an_archived_task(self):
        services.archive_item(self.task)

        with self.assertRaises(services.InvalidTaskTransition):
            services.add_checklist_step(self.task, "Refill medication")

    def test_an_empty_step_is_rejected(self):
        with self.assertRaises(services.TaskConflict):
            services.add_checklist_step(self.task, "   ")


class ToggleDoneTest(ChecklistStepServiceTest):
    def setUp(self):
        super().setUp()
        self.step = services.add_checklist_step(self.task, "Refill medication")

    def test_marking_done_stamps_completed_at(self):
        done = services.set_checklist_step_done(self.step, True)

        self.assertTrue(done.is_done)
        self.assertIsNotNone(done.completed_at)

    def test_unmarking_clears_completed_at(self):
        services.set_checklist_step_done(self.step, True)

        reopened = services.set_checklist_step_done(self.refresh(self.step), False)

        self.assertFalse(reopened.is_done)
        self.assertIsNone(reopened.completed_at)

    def test_a_done_step_frees_its_text_for_a_new_one(self):
        services.set_checklist_step_done(self.step, True)

        second = services.add_checklist_step(self.task, "Refill medication")

        self.assertNotEqual(second.pk, self.step.pk)

    def test_cannot_toggle_a_step_on_an_archived_task(self):
        services.archive_item(self.task)

        with self.assertRaises(services.InvalidTaskTransition):
            services.set_checklist_step_done(self.step, True)


class CarriesForwardTest(ChecklistStepServiceTest):
    def test_can_be_turned_off_after_creation(self):
        step = services.add_checklist_step(self.task, "Refill medication")

        updated = services.set_checklist_step_carries_forward(step, False)

        self.assertFalse(updated.carries_forward)


class EditTextTest(ChecklistStepServiceTest):
    def test_renames_the_step(self):
        step = services.add_checklist_step(self.task, "Refil medicaton")

        renamed = services.edit_checklist_step_text(step, "Refill medication")

        self.assertEqual(renamed.text, "Refill medication")

    def test_renaming_onto_an_existing_open_step_is_rejected(self):
        services.add_checklist_step(self.task, "Book the kennel")
        step = services.add_checklist_step(self.task, "Wash the crate")

        with self.assertRaises(services.TaskConflict):
            services.edit_checklist_step_text(step, "Book the kennel")


class DeleteStepTest(ChecklistStepServiceTest):
    def test_deletes_the_step(self):
        step = services.add_checklist_step(self.task, "Refill medication")

        services.delete_checklist_step(step)

        self.assertFalse(ChecklistStep.objects.filter(pk=step.pk).exists())

    def test_cannot_delete_a_step_on_an_archived_task(self):
        step = services.add_checklist_step(self.task, "Refill medication")
        services.archive_item(self.task)

        with self.assertRaises(services.InvalidTaskTransition):
            services.delete_checklist_step(step)


class ReorderStepsTest(ChecklistStepServiceTest):
    def test_reorders_the_steps(self):
        first = services.add_checklist_step(self.task, "Refill medication")
        second = services.add_checklist_step(self.task, "Book the kennel")

        services.reorder_checklist_steps(self.task, [second.pk, first.pk])

        self.assertEqual(
            [self.refresh(second).position, self.refresh(first).position], [0, 1],
        )

    def test_a_stale_id_set_is_rejected(self):
        first = services.add_checklist_step(self.task, "Refill medication")

        with self.assertRaises(services.TaskConflict):
            services.reorder_checklist_steps(self.task, [first.pk, 999999])


class PromoteStepTest(ChecklistStepServiceTest):
    def test_promoting_creates_a_root_task_and_removes_the_step(self):
        step = services.add_checklist_step(self.task, "Book the kennel")

        promoted = services.promote_checklist_step(step)

        self.assertEqual(promoted.text, "Book the kennel")
        self.assertEqual(promoted.list_id, self.list_.pk)
        self.assertFalse(ChecklistStep.objects.filter(pk=step.pk).exists())

    def test_promoting_onto_an_existing_task_text_is_rejected(self):
        services.create_item(self.list_, "Book the kennel")
        step = services.add_checklist_step(self.task, "Book the kennel")

        with self.assertRaises(services.TaskConflict):
            services.promote_checklist_step(step)

        # Rejected, not silently dropped -- the step is still there to retry.
        self.assertTrue(ChecklistStep.objects.filter(pk=step.pk).exists())

    def test_a_promoted_step_lands_after_existing_root_tasks(self):
        services.create_item(self.list_, "Book flights")
        step = services.add_checklist_step(self.task, "Book the kennel")

        promoted = services.promote_checklist_step(step)

        self.assertEqual(promoted.position, 2)  # after "Get the dog ready" and "Book flights"

    def test_cannot_promote_a_step_on_an_archived_task(self):
        step = services.add_checklist_step(self.task, "Book the kennel")
        services.archive_item(self.task)

        with self.assertRaises(services.InvalidTaskTransition):
            services.promote_checklist_step(step)


class RecurringCarryForwardTest(ChecklistStepServiceTest):
    def setUp(self):
        super().setUp()
        self.recurring = services.set_recurrence(self.task, Item.Recurrence.WEEKLY)

    def test_a_flagged_step_clones_onto_the_next_occurrence(self):
        services.add_checklist_step(self.recurring, "Refill medication")

        completed = services.complete_item(self.recurring)
        spawned = completed._spawned

        clones = list(spawned.checklist_steps.all())
        self.assertEqual(len(clones), 1)
        self.assertEqual(clones[0].text, "Refill medication")
        self.assertFalse(clones[0].is_done)
        self.assertIsNone(clones[0].completed_at)

    def test_an_opted_out_step_does_not_clone(self):
        services.add_checklist_step(
            self.recurring, "One-time errand", carries_forward=False,
        )

        completed = services.complete_item(self.recurring)
        spawned = completed._spawned

        self.assertEqual(spawned.checklist_steps.count(), 0)

    def test_a_done_flagged_step_still_clones_fresh(self):
        step = services.add_checklist_step(self.recurring, "Refill medication")
        services.set_checklist_step_done(step, True)

        completed = services.complete_item(self.refresh_task(self.recurring))
        spawned = completed._spawned

        clone = spawned.checklist_steps.get()
        self.assertFalse(clone.is_done)

    def refresh_task(self, item):
        return Item.objects.get(pk=item.pk)
