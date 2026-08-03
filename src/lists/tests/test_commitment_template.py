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

    def test_spawning_still_copies_from_the_completed_item(self):
        """The expand step changes nothing about behaviour, stated as a test
        rather than as a claim. Slice 2 is what makes the spawn read the
        template; until then an empty template must not empty a task.
        """
        from lists import services

        task = services.create_item(
            self.area, "Pay rent", recurrence=Item.Recurrence.MONTHLY,
        )
        services.set_item_notes(task, "Bank transfer, not cash")

        completed = services.complete_item(task)
        spawned = completed._spawned

        self.assertEqual(spawned.text, "Pay rent")
        self.assertEqual(spawned.notes, "Bank transfer, not cash")
        self.assertEqual(spawned.recurrence, Item.Recurrence.MONTHLY)
        # And the commitment it points at is still the empty template.
        self.assertEqual(spawned.commitment.text, "")


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
        self.migrate(AFTER)

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
