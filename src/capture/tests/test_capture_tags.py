"""Optional tags at capture time -- design/capture-tags-plan.md.

Service-level coverage for create_capture and create_capture_idempotent.

**Only the Inbox form reaches these now.** `/api/v1/capture` writes a node since
Heron 4a, so tagging on the route a phone actually uses is
mind/tests/test_the_one_capture_endpoint.py, where a typed tag becomes a
confirmed concept. This file and the services under it retire with `Capture`
in 4b.
"""
import uuid

from django.test import TestCase

from accounts.models import User
from capture.services import create_capture, create_capture_idempotent
from lists.models import Tag


PASSWORD = "correct horse battery staple 47!"


class CreateCaptureTagsTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", PASSWORD
        )

    def test_tags_are_optional(self):
        capture = create_capture(self.user, "Ring the vet")

        self.assertEqual(list(capture.tags.all()), [])

    def test_tag_names_resolve_against_the_shared_vocabulary(self):
        existing = Tag.objects.create(owner=self.user, name="movies")

        capture = create_capture(self.user, "Watch that trailer", tags=["movies"])

        self.assertEqual(list(capture.tags.all()), [existing])
        self.assertEqual(Tag.objects.filter(owner=self.user).count(), 1)

    def test_a_new_tag_name_is_created(self):
        capture = create_capture(self.user, "Design a boss fight", tags=["game-dev"])

        self.assertEqual([t.name for t in capture.tags.all()], ["game-dev"])

    def test_tags_are_scoped_to_the_owner(self):
        bob = User.objects.create_user("bob", "bob@example.com", PASSWORD)
        Tag.objects.create(owner=bob, name="movies")

        capture = create_capture(self.user, "Watch that trailer", tags=["movies"])

        tag = capture.tags.get()
        self.assertEqual(tag.owner, self.user)
        self.assertEqual(Tag.objects.filter(name="movies").count(), 2)


class CreateCaptureIdempotentTagsTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", PASSWORD
        )

    def test_a_keyed_capture_can_carry_tags(self):
        key = uuid.uuid4()

        capture, created = create_capture_idempotent(
            self.user, "Design a boss fight", key, tags=["game-dev"]
        )

        self.assertTrue(created)
        self.assertEqual([t.name for t in capture.tags.all()], ["game-dev"])

    def test_a_replay_does_not_touch_the_existing_rows_tags(self):
        """The same rule the docstring already states for text: the first
        successful write is the one of record. A retry that shows up with
        different tags (a client bug, or two different capture screens
        racing) must not silently rewrite what the original row said.
        """
        key = uuid.uuid4()
        first, _ = create_capture_idempotent(
            self.user, "Design a boss fight", key, tags=["game-dev"]
        )

        replay, created = create_capture_idempotent(
            self.user, "Design a boss fight", key, tags=["something-else"]
        )

        self.assertFalse(created)
        self.assertEqual(replay.id, first.id)
        self.assertEqual([t.name for t in replay.tags.all()], ["game-dev"])

    def test_omitting_tags_still_works_exactly_as_before(self):
        key = uuid.uuid4()

        capture, created = create_capture_idempotent(self.user, "Call the vet", key)

        self.assertTrue(created)
        self.assertEqual(list(capture.tags.all()), [])
