"""Taking your data with you.

The other half of `commercial-blueprint.md`'s legal blocker. Deletion without
export is a trap: the only way to leave is to destroy everything.

**Two formats, because they answer different questions.** `clarice.json` is the
complete record — every row of every owned model across both cores, including
the activity log — and is what a machine can read back. `notes.md` and
`tasks.md` are what a person can actually open, which is what "portable" has to
mean if it means anything; nobody reads their own thoughts as JSON.

**Hand-built rather than `dumpdata`.** That format is pk-keyed and
Django-internal, and it serialises every concrete field — including the password
hash and the token hashes. The exclusions here are named explicitly and asserted
below, because "we probably didn't include the password" is not a thing to be
probably right about.
"""

import json
import zipfile
from datetime import timedelta
from io import BytesIO

from django.test import TestCase
from django.utils import timezone

from accounts import export
from accounts.models import SCOPE_CAPTURE_WRITE, PersonalAccessToken, User
from lists.models import Item, List, RecurringCommitment, Tag
from mind import services as mind_services
from mind.models import NodeSource

PASSWORD = "correct horse battery staple 47!"

# Never leaves the database, in any file, in any format.
SECRETS = ("password", "token_hash")


class ExportTest(TestCase):
    def setUp(self):
        self.now = timezone.now()
        self.alice = self.an_account("alice", "the boiler is making that noise")
        self.bob = self.an_account("bob", "bob's private thought")

    def an_account(self, username, thought):
        user = User.objects.create_user(username, f"{username}@example.com", PASSWORD)
        area = List.objects.create(owner=user, title=f"{username}'s home")
        Item.objects.create(
            list=area, owner=user, text=f"{username}'s task",
            due_date=timezone.localdate() + timedelta(days=1),
        )
        PersonalAccessToken.generate(user, label="Phone", scopes=[SCOPE_CAPTURE_WRITE])
        node = mind_services.capture(
            user, content=thought, captured_at=self.now,
            source=NodeSource.WEB, actor=username,
        )
        mind_services.record_typed_tags(
            node, ["boiler"], now=self.now, actor=username
        )
        return user

    def archive(self, user):
        return zipfile.ZipFile(BytesIO(export.build_archive(user, now=self.now)))

    def read(self, user, name):
        return self.archive(user).read(name).decode("utf-8")

    # -- what is in it -----------------------------------------------------

    def test_it_holds_all_three_files(self):
        self.assertEqual(
            sorted(self.archive(self.alice).namelist()),
            ["clarice.json", "notes.md", "tasks.md"],
        )

    def test_the_json_carries_the_account_and_both_cores(self):
        data = json.loads(self.read(self.alice, "clarice.json"))

        self.assertEqual(data["account"]["username"], "alice")
        self.assertTrue(data["tasks"]["items"])
        self.assertTrue(data["knowledge"]["nodes"])
        self.assertTrue(data["knowledge"]["events"])

    def test_a_thought_survives_into_both_formats(self):
        """The point of the whole exercise. A file that proves the export ran
        but does not contain what somebody wrote is worse than none."""
        self.assertIn(
            "the boiler is making that noise", self.read(self.alice, "clarice.json")
        )
        self.assertIn(
            "the boiler is making that noise", self.read(self.alice, "notes.md")
        )

    def test_a_confirmed_concept_travels_with_its_note(self):
        self.assertIn("boiler", self.read(self.alice, "notes.md"))

    def test_a_task_carries_its_area_and_due_date(self):
        tasks = self.read(self.alice, "tasks.md")

        self.assertIn("alice's task", tasks)
        self.assertIn("alice's home", tasks)
        self.assertIn(
            (timezone.localdate() + timedelta(days=1)).isoformat(), tasks
        )

    # -- what is not ------------------------------------------------------

    def test_a_tagged_task_records_which_tags_were_on_it(self):
        """`_rows` iterates `_meta.concrete_fields`, which by definition
        excludes many-to-many -- so tags exported as a list of names with
        nothing saying which task carried which. The export is the only thing
        standing before irreversible erasure, so an association lost here is
        lost permanently."""
        task = Item.objects.get(owner=self.alice)
        errand = Tag.objects.create(owner=self.alice, name="errand")
        urgent = Tag.objects.create(owner=self.alice, name="urgent")
        task.tags.set([errand, urgent])

        payload = json.loads(self.read(self.alice, "clarice.json"))

        [exported] = payload["tasks"]["items"]
        self.assertEqual(sorted(exported["tag_ids"]), sorted([errand.id, urgent.id]))

    def test_a_commitments_tags_travel_too(self):
        """The other many-to-many on the same model family."""
        commitment = RecurringCommitment.objects.create(owner=self.alice)
        weekly = Tag.objects.create(owner=self.alice, name="weekly")
        commitment.tags.set([weekly])

        payload = json.loads(self.read(self.alice, "clarice.json"))

        [exported] = payload["tasks"]["commitments"]
        self.assertEqual(exported["tag_ids"], [weekly.id])

    def test_the_evidence_behind_a_hypothesis_travels_with_it(self):
        """`HypothesisMember` carries the span citations, which are a
        hypothesis's entire evidence: without them a proposal exports as a
        confidence score and a label with nothing behind it."""
        payload = json.loads(self.read(self.alice, "clarice.json"))

        self.assertIn("hypothesis_members", payload["knowledge"])

    def test_attachments_and_embeddings_are_not_left_behind(self):
        """Both hang off Node and neither was queried. The module docstring
        claims every row of every owned model across both cores."""
        payload = json.loads(self.read(self.alice, "clarice.json"))

        self.assertIn("attachments", payload["knowledge"])
        self.assertIn("sentence_embeddings", payload["knowledge"])

    def test_every_owned_model_is_named_somewhere_in_the_export(self):
        """The guard for the class rather than for these four.

        The docstring's claim is checkable: walk every model in the apps this
        account owns data in, and assert each one is reachable from the
        payload. A model added later without an export line fails here rather
        than being discovered by somebody who has already deleted their
        account.
        """
        payload = json.loads(self.read(self.alice, "clarice.json"))

        # The payload's own two levels, and deliberately no deeper. Recursing
        # into the rows made this pass by coincidence: ActivityEvent carries a
        # JSON payload, `walk` descended into it, and a key that happened to
        # appear in somebody's activity data counted as proof that a model was
        # exported. It reported the export complete with `attachments` removed.
        exported_keys = set(payload)
        for value in payload.values():
            if isinstance(value, dict):
                exported_keys.update(value)

        for model in export.owned_models():
            self.assertIn(
                export.export_key(model),
                exported_keys,
                f"{model.__name__} is owned but never exported",
            )

    def test_no_secret_is_anywhere_in_the_archive(self):
        """Named field by field rather than eyeballed. `dumpdata` would have
        included both of these without comment."""
        alice = User.objects.get(username="alice")
        token = PersonalAccessToken.objects.get(owner=alice)
        whole = b"".join(
            self.archive(alice).read(name)
            for name in self.archive(alice).namelist()
        ).decode("utf-8")

        self.assertNotIn(alice.password, whole)
        self.assertNotIn(token.token_hash, whole)
        for key in SECRETS:
            self.assertNotIn(f'"{key}"', whole)

    def test_the_token_still_appears_so_they_know_it_exists(self):
        """Its label and dates, never its hash. A device connected to the
        account is a fact about the account."""
        data = json.loads(self.read(self.alice, "clarice.json"))

        self.assertEqual(data["account"]["tokens"][0]["label"], "Phone")

    def test_one_persons_export_holds_nothing_of_anothers(self):
        whole = self.read(self.alice, "clarice.json")

        self.assertNotIn("bob", whole)
        self.assertNotIn("bob's private thought", whole)

    def test_an_empty_account_still_says_so_in_words(self):
        """Found by opening a real export, not by an assertion: an account with
        no areas produced a `tasks.md` containing the word "Tasks" and nothing
        else. A reader cannot tell that from a broken export, and the moment
        somebody most needs to trust this file is the moment they are leaving.
        """
        empty = User.objects.create_user("carol", "carol@example.com", PASSWORD)

        archive = zipfile.ZipFile(BytesIO(export.build_archive(empty, now=self.now)))

        self.assertIn("No tasks", archive.read("tasks.md").decode("utf-8"))
        self.assertIn("Nothing captured", archive.read("notes.md").decode("utf-8"))

    def test_it_says_when_it_was_made(self):
        data = json.loads(self.read(self.alice, "clarice.json"))

        self.assertEqual(data["exported_at"], self.now.isoformat())
