"""RecurringCommitment stops being only an identity anchor.

recurring-commitment-vocabulary-plan.md slice 1 -- the expand step. The
template gains the fields that will decide what the next occurrence starts
as; nothing reads them yet, and no behaviour changes. `_spawn_next_occurrence`
still copies from the completed item, which slice 2 changes.

The pairing this creates is deliberate and is not the two-sources-of-truth
drift crane-plan.md 3 warned about: the template answers "what will the next
one be", each occurrence answers "what was this one". Routine and
RoutineOccurrence already ship exactly this pair for target_quantity.
"""
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from accounts.models import User
from lists.models import Item, List, RecurringCommitment


class CommitmentTemplateFieldsTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        cls.area = List.objects.create(owner=cls.owner, title="Home")

    def test_a_new_commitment_carries_an_empty_template(self):
        """Additive and inert. A commitment created by today's code paths
        gets no template values, because nothing writes them yet.
        """
        commitment = RecurringCommitment.objects.create(owner=self.owner)

        self.assertEqual(commitment.text, "")
        self.assertIsNone(commitment.list_id)
        self.assertEqual(commitment.cadence, Item.Recurrence.NONE)
        self.assertEqual(commitment.notes, "")
        self.assertEqual(list(commitment.tags.all()), [])

    def test_a_template_holds_what_the_next_occurrence_starts_as(self):
        commitment = RecurringCommitment.objects.create(
            owner=self.owner,
            text="Pay rent",
            list=self.area,
            cadence=Item.Recurrence.MONTHLY,
            notes="Bank transfer, not cash",
        )

        commitment.refresh_from_db()
        self.assertEqual(commitment.text, "Pay rent")
        self.assertEqual(commitment.list, self.area)
        self.assertEqual(commitment.cadence, Item.Recurrence.MONTHLY)
        self.assertEqual(commitment.notes, "Bank transfer, not cash")



class CommitmentWriteThroughTest(TestCase):
    """Editing a linked occurrence edits the commitment: this and future.

    Decided by Vince on August 3, 2026 from the two options in
    recurring-commitment-vocabulary-plan.md 4. Renaming a recurring task means
    renaming the commitment; the occurrences already completed keep what they
    were called, because they hold their own snapshot.

    Deliberately no prompt. Adding one later is additive; teaching people that
    edits are per-occurrence and then reversing it is not.
    """

    def setUp(self):
        self.owner = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.area = List.objects.create(owner=self.owner, title="Home")

    def recurring(self, text="Pay rent"):
        from lists import services

        return services.create_item(
            self.area, text, recurrence=Item.Recurrence.MONTHLY,
        )

    def test_creating_a_recurring_task_seeds_its_template(self):
        task = self.recurring()

        commitment = task.commitment
        self.assertEqual(commitment.text, "Pay rent")
        self.assertEqual(commitment.list_id, self.area.id)
        self.assertEqual(commitment.cadence, Item.Recurrence.MONTHLY)

    def test_renaming_a_linked_task_renames_the_commitment(self):
        from lists import services

        task = self.recurring()

        services.edit_item(task, "Pay rent - new landlord")

        task.commitment.refresh_from_db()
        self.assertEqual(task.commitment.text, "Pay rent - new landlord")

    def test_notes_and_tags_write_through_too(self):
        from lists import services

        task = self.recurring()

        services.set_item_notes(task, "Bank transfer, not cash")
        services.set_item_tags(task, ["money"])

        commitment = task.commitment
        commitment.refresh_from_db()
        self.assertEqual(commitment.notes, "Bank transfer, not cash")
        self.assertEqual([t.name for t in commitment.tags.all()], ["money"])

    def test_an_unlinked_task_has_nothing_to_write_through_to(self):
        """Most tasks. The write-through must not invent a commitment for a
        one-off, which would turn every edited task into a series.
        """
        from lists import services

        task = services.create_item(self.area, "One-off")

        services.edit_item(task, "Renamed")
        services.set_item_notes(task, "A note")

        task.refresh_from_db()
        self.assertIsNone(task.commitment_id)
        self.assertEqual(RecurringCommitment.objects.count(), 0)


class SpawnReadsTheTemplateTest(TestCase):
    """The next occurrence is built from the commitment, not copied forward."""

    def setUp(self):
        self.owner = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.area = List.objects.create(owner=self.owner, title="Home")

    def test_the_crane_plan_acceptance_example(self):
        """crane-plan.md 3, executed rather than described.

        Completed twice under one name, renamed, completed again. The series
        returns four occurrences, the later ones carrying the new text and the
        earlier ones the old.

        **This passes under plain copy-forward too**, because the completed
        item already carries the new text, so on its own it proves nothing
        about where the spawn read from. The next test is the one that does.
        """
        from lists import services

        task = services.create_item(
            self.area, "Pay rent", recurrence=Item.Recurrence.MONTHLY,
        )
        commitment = task.commitment

        task = services.complete_item(task)._spawned
        task = services.complete_item(task)._spawned

        services.edit_item(task, "Pay rent - new landlord")
        task.refresh_from_db()
        spawned = services.complete_item(task)._spawned

        series = list(Item.objects.filter(commitment=commitment).order_by("id"))
        self.assertEqual(
            [each.text for each in series],
            [
                "Pay rent",
                "Pay rent",
                "Pay rent - new landlord",
                "Pay rent - new landlord",
            ],
        )
        self.assertEqual(spawned.text, "Pay rent - new landlord")

    def test_the_template_wins_when_it_disagrees_with_the_occurrence(self):
        """The test that actually distinguishes reading from copying.

        The template and the completed occurrence deliberately disagree, so
        only a spawn that reads the template can pass.
        """
        from lists import services

        task = services.create_item(
            self.area, "Pay rent", recurrence=Item.Recurrence.MONTHLY,
        )
        commitment = task.commitment
        # Straight to the template, bypassing the write-through, so the
        # occurrence still says "Pay rent".
        RecurringCommitment.objects.filter(pk=commitment.pk).update(
            text="Pay the new landlord",
        )
        task.refresh_from_db()
        self.assertEqual(task.text, "Pay rent")

        spawned = services.complete_item(task)._spawned

        self.assertEqual(spawned.text, "Pay the new landlord")

    def test_the_spawn_takes_notes_and_tags_from_the_template(self):
        from lists import services

        task = services.create_item(
            self.area, "Pay rent", recurrence=Item.Recurrence.MONTHLY,
        )
        services.set_item_notes(task, "Bank transfer")
        services.set_item_tags(task, ["money"])
        task.refresh_from_db()

        spawned = services.complete_item(task)._spawned

        self.assertEqual(spawned.notes, "Bank transfer")
        self.assertEqual([t.name for t in spawned.tags.all()], ["money"])

    def test_a_legacy_commitment_created_at_completion_is_seeded_first(self):
        """Rows predating the key reach completion without a commitment.

        `_anchor_commitment` adopts them there and must seed the template at
        the same moment, or the first spawn after adoption reads an empty
        template and produces a blank task.
        """
        from lists import services

        task = services.create_item(
            self.area, "Legacy", recurrence=Item.Recurrence.WEEKLY,
        )
        Item.objects.filter(pk=task.pk).update(commitment=None)
        RecurringCommitment.objects.all().delete()
        task.refresh_from_db()

        spawned = services.complete_item(task)._spawned

        self.assertEqual(spawned.text, "Legacy")
        self.assertEqual(spawned.commitment.text, "Legacy")


class CadenceBelongsToTheCommitmentTest(TestCase):
    """The rule lives on the template; the occurrence keeps a snapshot.

    recurring-commitment-vocabulary-plan.md 3: a commitment is weekly; an
    occurrence is not weekly, it is one instance of a weekly thing. This is
    what closes crane-plan.md 3's complaint that "change its cadence and
    nothing records that it was ever weekly".
    """

    def setUp(self):
        self.owner = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.area = List.objects.create(owner=self.owner, title="Home")

    def recurring(self, cadence=Item.Recurrence.WEEKLY):
        from lists import services

        return services.create_item(self.area, "Pay rent", recurrence=cadence)

    def test_changing_a_task_s_repeat_changes_the_commitment_s_cadence(self):
        from lists import services

        task = self.recurring(Item.Recurrence.WEEKLY)

        services.set_recurrence(task, Item.Recurrence.MONTHLY)

        task.commitment.refresh_from_db()
        self.assertEqual(task.commitment.cadence, Item.Recurrence.MONTHLY)

    def test_the_spawn_takes_its_cadence_from_the_commitment(self):
        """Discriminating, like the text one: the template and the occurrence
        deliberately disagree, so only a spawn reading the template passes.
        """
        from lists import services

        task = self.recurring(Item.Recurrence.WEEKLY)
        RecurringCommitment.objects.filter(pk=task.commitment_id).update(
            cadence=Item.Recurrence.MONTHLY,
        )
        task.refresh_from_db()
        self.assertEqual(task.recurrence, Item.Recurrence.WEEKLY)

        spawned = services.complete_item(task)._spawned

        self.assertEqual(spawned.recurrence, Item.Recurrence.MONTHLY)

    def test_the_due_date_advances_by_the_commitment_s_cadence(self):
        """The cadence decides the next due date, so reading the wrong one is
        not merely a label being stale.
        """
        from datetime import date

        from lists import services

        task = services.create_item(
            self.area,
            "Pay rent",
            recurrence=Item.Recurrence.WEEKLY,
            due_date=date(2026, 8, 3),
        )
        RecurringCommitment.objects.filter(pk=task.commitment_id).update(
            cadence=Item.Recurrence.MONTHLY,
        )
        task.refresh_from_db()

        spawned = services.complete_item(task)._spawned

        # A month on, not a week.
        self.assertEqual(spawned.due_date, date(2026, 9, 3))

    def test_a_completed_occurrence_keeps_the_cadence_it_ran_under(self):
        """Charter rule 3. The series changing to monthly must not rewrite
        the record of a week that actually was weekly.
        """
        from lists import services

        task = self.recurring(Item.Recurrence.WEEKLY)
        completed = services.complete_item(task)
        follow_on = completed._spawned

        services.set_recurrence(follow_on, Item.Recurrence.MONTHLY)

        completed.refresh_from_db()
        self.assertEqual(completed.recurrence, Item.Recurrence.WEEKLY)
        # Re-read rather than trusting follow_on.commitment: set_recurrence
        # re-fetches the item internally and writes through on that instance,
        # so the copy held here predates the change.
        commitment = RecurringCommitment.objects.get(pk=follow_on.commitment_id)
        self.assertEqual(commitment.cadence, Item.Recurrence.MONTHLY)

    def test_stopping_a_repeat_records_none_on_the_commitment_and_ends_it(self):
        from lists import services

        task = self.recurring(Item.Recurrence.WEEKLY)

        services.set_recurrence(task, Item.Recurrence.NONE)

        commitment = task.commitment
        commitment.refresh_from_db()
        self.assertEqual(commitment.cadence, Item.Recurrence.NONE)
        # The link stays and the series is closed rather than deleted.
        self.assertIsNotNone(commitment.ended_at)
        task.refresh_from_db()
        self.assertEqual(task.commitment_id, commitment.pk)


class TheTemplateIsTheOnlySourceTest(TestCase):
    """What replaced TemplateFallbackWindowTest when the window closed.

    That test pinned three `or` fallbacks to the completed occurrence, which
    existed for exactly one deploy so that a row 0031's backfill might have
    missed could not produce a blank task. The migration reported empty=0
    against production on August 3, 2026, so there was nothing left to cover
    and the fallbacks came out.

    This asserts the invariant that holds now: the spawn reads the template
    and nothing else, so a defect in the template shows up as a defect rather
    than being silently papered over by the occurrence it came from.
    """

    def setUp(self):
        self.owner = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.area = List.objects.create(owner=self.owner, title="Home")

    def test_every_field_of_the_next_occurrence_comes_from_the_template(self):
        from lists import services

        elsewhere = List.objects.create(owner=self.owner, title="Work")
        task = services.create_item(
            self.area, "Pay rent", recurrence=Item.Recurrence.WEEKLY,
        )
        # The template and the occurrence disagree about every seeded field.
        RecurringCommitment.objects.filter(pk=task.commitment_id).update(
            text="Pay the new landlord",
            list=elsewhere,
            cadence=Item.Recurrence.MONTHLY,
            notes="Moved and rescheduled",
        )
        task.refresh_from_db()

        spawned = services.complete_item(task)._spawned

        self.assertEqual(spawned.text, "Pay the new landlord")
        self.assertEqual(spawned.list_id, elsewhere.id)
        self.assertEqual(spawned.recurrence, Item.Recurrence.MONTHLY)
        self.assertEqual(spawned.notes, "Moved and rescheduled")


# capture is named alongside lists for the reason test_ownerless_list_removal
# discovered the hard way: a target that mentions only one app lets the next
# migration test ask for a plan that runs lists backwards and capture
# forwards, which Django refuses outright. Naming both keeps every plan
# single-direction regardless of the order these classes run in.
BEFORE = [("lists", "0030_project"), ("capture", "0004_idea_idea_owner_status_idx")]
AFTER = [
    ("lists", "0031_commitment_template"),
    ("capture", "0004_idea_idea_owner_status_idx"),
]


class CommitmentTemplateBackfillTest(TransactionTestCase):
    """Each existing commitment learns what it is from its own history.

    Driven through the real MigrationExecutor, same as
    test_checklist_step_backfill.py and test_ownerless_list_removal.py.
    """

    def migrate(self, target):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(target)
        return executor.loader.project_state(target).apps

    def tearDown(self):
        # Every app forward -- see the note in test_checklist_step_backfill.py.
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(executor.loader.graph.leaf_nodes())

    def test_a_commitment_is_seeded_from_its_most_recent_occurrence(self):
        old_apps = self.migrate(BEFORE)
        List = old_apps.get_model("lists", "List")
        Item = old_apps.get_model("lists", "Item")
        RecurringCommitment = old_apps.get_model("lists", "RecurringCommitment")
        Tag = old_apps.get_model("lists", "Tag")

        alice = User.objects.create_user("alice", "alice@example.com", "a password")
        area = List.objects.create(owner_id=alice.pk, title="Home")
        commitment = RecurringCommitment.objects.create(owner_id=alice.pk)
        money = Tag.objects.create(owner_id=alice.pk, name="money")

        # Three occurrences. The newest is the one the template should learn
        # from -- it is what the commitment currently is.
        Item.objects.create(
            list=area, text="Pay rent", recurrence="monthly",
            commitment=commitment, status="completed",
            completed_at=timezone.now(),
        )
        newest = Item.objects.create(
            list=area, text="Pay rent — new landlord", recurrence="monthly",
            commitment=commitment, notes="Bank transfer",
        )
        newest.tags.add(money)

        new_apps = self.migrate(AFTER)
        RecurringCommitment = new_apps.get_model("lists", "RecurringCommitment")

        seeded = RecurringCommitment.objects.get(pk=commitment.pk)
        self.assertEqual(seeded.text, "Pay rent — new landlord")
        self.assertEqual(seeded.list_id, area.pk)
        self.assertEqual(seeded.cadence, "monthly")
        self.assertEqual(seeded.notes, "Bank transfer")
        self.assertEqual([tag.name for tag in seeded.tags.all()], ["money"])

    def test_a_commitment_with_no_occurrences_is_left_empty(self):
        """Not reachable through the application -- a commitment is only
        created alongside an item -- but the migration must not assume that
        of production data it has never seen.
        """
        old_apps = self.migrate(BEFORE)
        RecurringCommitment = old_apps.get_model("lists", "RecurringCommitment")

        alice = User.objects.create_user("alice", "alice@example.com", "a password")
        stray = RecurringCommitment.objects.create(owner_id=alice.pk)

        new_apps = self.migrate(AFTER)
        RecurringCommitment = new_apps.get_model("lists", "RecurringCommitment")

        seeded = RecurringCommitment.objects.get(pk=stray.pk)
        self.assertEqual(seeded.text, "")
        self.assertIsNone(seeded.list_id)
        self.assertEqual(seeded.cadence, "none")

    def test_an_unlinked_task_is_not_touched(self):
        old_apps = self.migrate(BEFORE)
        List = old_apps.get_model("lists", "List")
        Item = old_apps.get_model("lists", "Item")

        alice = User.objects.create_user("alice", "alice@example.com", "a password")
        area = List.objects.create(owner_id=alice.pk, title="Home")
        plain = Item.objects.create(list=area, text="One-off", recurrence="none")

        new_apps = self.migrate(AFTER)
        Item = new_apps.get_model("lists", "Item")

        kept = Item.objects.get(pk=plain.pk)
        self.assertEqual(kept.text, "One-off")
        self.assertIsNone(kept.commitment_id)
