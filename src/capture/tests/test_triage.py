"""What a capture becomes, and how to take it back.

Replaces the MVP's single undifferentiated "Clear" -- see
design/capture-triage-and-polish-plan.md. Isolation is covered here rather
than in lists/tests/test_isolation.py because every route is new and
capture-owned, but the discipline is the same one A3 set: an intruder gets
a 404, and a positive control proves the route exists at all.
"""
from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from capture.models import Capture, Idea
from capture.services import ALREADY_RESOLVED_ERROR
from lists import services as list_services
from lists.models import Item, List


PASSWORD = "correct horse battery staple 47!"


class TriageTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", PASSWORD
        )
        self.client.force_login(self.user)
        self.list_ = List.objects.create(owner=self.user, title="Errands")
        self.capture = Capture.objects.create(
            owner=self.user, text="Ring the vet"
        )

    def promote_to_task(self, capture=None, for_list=None):
        capture = capture or self.capture
        return self.client.post(
            f"/capture/{capture.id}/task/",
            data={"list": (for_list or self.list_).id},
        )

    def promote_to_idea(self, status="exploring", capture=None):
        capture = capture or self.capture
        return self.client.post(
            f"/capture/{capture.id}/idea/", data={"status": status}
        )

    def discard(self, capture=None):
        return self.client.post(f"/capture/{(capture or self.capture).id}/discard/")


class PromoteToTaskTest(TriageTest):
    def test_creates_the_task_in_the_named_list(self):
        response = self.promote_to_task()

        task = Item.objects.get()
        self.assertEqual(task.text, "Ring the vet")
        self.assertEqual(task.list, self.list_)
        self.assertRedirects(response, "/capture/")

    def test_records_what_the_capture_became(self):
        self.promote_to_task()

        self.capture.refresh_from_db()
        self.assertEqual(self.capture.resolution, Capture.Resolution.TASK)
        self.assertEqual(self.capture.promoted_task, Item.objects.get())
        self.assertIsNone(self.capture.promoted_idea)
        self.assertIsNotNone(self.capture.resolved_at)

    def test_it_leaves_the_inbox(self):
        self.promote_to_task()

        inbox = self.client.get("/capture/")

        self.assertEqual(list(inbox.context["captures"]), [])

    def test_a_duplicate_title_leaves_the_capture_where_it_is(self):
        # The lists-side rule surfacing through triage. Resolving anyway
        # would quietly drop the thought on the floor.
        Item.objects.create(list=self.list_, text="Ring the vet")

        self.promote_to_task()

        self.capture.refresh_from_db()
        self.assertIsNone(self.capture.resolved_at)
        self.assertEqual(self.capture.resolution, "")

    def test_cannot_promote_into_someone_elses_list(self):
        bob = User.objects.create_user("bob", "bob@example.com", PASSWORD)
        theirs = List.objects.create(owner=bob, title="Bob's list")

        response = self.promote_to_task(for_list=theirs)

        self.assertEqual(response.status_code, 404)
        self.assertFalse(Item.objects.exists())

    def test_cannot_promote_someone_elses_capture(self):
        bob = User.objects.create_user("bob", "bob@example.com", PASSWORD)
        theirs = Capture.objects.create(owner=bob, text="Bob's thought")

        response = self.promote_to_task(capture=theirs)

        self.assertEqual(response.status_code, 404)
        theirs.refresh_from_db()
        self.assertIsNone(theirs.resolved_at)

    def test_carries_the_captures_tags_onto_the_task(self):
        # design/second-mind-discovery-plan.md 4.2 -- a capture's tags used
        # to end at the Inbox. Item.tags already exists; this is a copy, not
        # a schema change.
        self.capture.tags.set(
            list_services.resolve_tags(self.user, ["game-dev"])
        )

        self.promote_to_task()

        task = Item.objects.get()
        self.assertEqual([t.name for t in task.tags.all()], ["game-dev"])

    def test_an_untagged_capture_produces_an_untagged_task(self):
        # The regression that keeps the test above honest: a bug that
        # always attached some default tag would still pass a test that
        # only ever checked the tagged case.
        self.promote_to_task()

        task = Item.objects.get()
        self.assertEqual(list(task.tags.all()), [])


class PromoteToIdeaTest(TriageTest):
    def test_creates_an_exploring_idea(self):
        self.promote_to_idea("exploring")

        idea = Idea.objects.get()
        self.assertEqual(idea.text, "Ring the vet")
        self.assertEqual(idea.owner, self.user)
        self.assertEqual(idea.status, Idea.Status.EXPLORING)

    def test_creates_a_reference_idea(self):
        self.promote_to_idea("reference")

        self.assertEqual(Idea.objects.get().status, Idea.Status.REFERENCE)

    def test_records_what_the_capture_became(self):
        self.promote_to_idea()

        self.capture.refresh_from_db()
        self.assertEqual(self.capture.resolution, Capture.Resolution.IDEA)
        self.assertEqual(self.capture.promoted_idea, Idea.objects.get())
        # Never a task directly -- that hop belongs to Idea.promoted_task.
        self.assertIsNone(self.capture.promoted_task)

    def test_promoted_is_not_a_status_an_idea_can_be_born_in(self):
        self.promote_to_idea("promoted")

        self.assertFalse(Idea.objects.exists())
        self.capture.refresh_from_db()
        self.assertIsNone(self.capture.resolved_at)

    def test_cannot_promote_someone_elses_capture(self):
        bob = User.objects.create_user("bob", "bob@example.com", PASSWORD)
        theirs = Capture.objects.create(owner=bob, text="Bob's thought")

        response = self.promote_to_idea(capture=theirs)

        self.assertEqual(response.status_code, 404)
        self.assertFalse(Idea.objects.exists())

    def test_carries_the_captures_tags_onto_the_idea(self):
        # design/second-mind-discovery-plan.md 4.2 -- the Idea-side half of
        # the same carry promote_to_task already does.
        self.capture.tags.set(
            list_services.resolve_tags(self.user, ["game-dev"])
        )

        self.promote_to_idea()

        idea = Idea.objects.get()
        self.assertEqual([t.name for t in idea.tags.all()], ["game-dev"])

    def test_an_untagged_capture_produces_an_untagged_idea(self):
        self.promote_to_idea()

        idea = Idea.objects.get()
        self.assertEqual(list(idea.tags.all()), [])


class DiscardTest(TriageTest):
    def test_marks_it_discarded_and_creates_nothing(self):
        self.discard()

        self.capture.refresh_from_db()
        self.assertEqual(self.capture.resolution, Capture.Resolution.DISCARDED)
        self.assertIsNotNone(self.capture.resolved_at)
        self.assertFalse(Item.objects.exists())
        self.assertFalse(Idea.objects.exists())

    def test_the_row_survives(self):
        # Soft, not hard: every capture keeps saying what happened to it,
        # and that's also what makes discard undoable.
        self.discard()

        self.assertTrue(Capture.objects.filter(pk=self.capture.pk).exists())

    def test_cannot_discard_someone_elses_capture(self):
        bob = User.objects.create_user("bob", "bob@example.com", PASSWORD)
        theirs = Capture.objects.create(owner=bob, text="Bob's thought")

        response = self.discard(capture=theirs)

        self.assertEqual(response.status_code, 404)
        theirs.refresh_from_db()
        self.assertIsNone(theirs.resolved_at)


class SecondAttemptTest(TriageTest):
    """A double-click, a stale tab, a back button -- all reach these views
    with a capture that has already moved on.
    """

    def test_a_second_triage_is_refused_rather_than_silently_reapplied(self):
        self.discard()
        self.capture.refresh_from_db()
        first_time = self.capture.resolved_at

        response = self.promote_to_task(), self.promote_to_idea(), self.discard()

        self.capture.refresh_from_db()
        self.assertEqual(self.capture.resolved_at, first_time)
        self.assertEqual(self.capture.resolution, Capture.Resolution.DISCARDED)
        self.assertFalse(Item.objects.exists())
        self.assertFalse(Idea.objects.exists())
        self.assertContains(
            self.client.get("/capture/"), ALREADY_RESOLVED_ERROR
        )
        self.assertEqual({each.status_code for each in response}, {302})


class UndoTest(TriageTest):
    def undo(self, capture=None):
        return self.client.post(f"/capture/{(capture or self.capture).id}/undo/")

    def test_the_inbox_offers_undo_for_one_page_load(self):
        self.discard()

        first = self.client.get("/capture/")
        second = self.client.get("/capture/")

        self.assertEqual(first.context["undo_capture"], self.capture)
        self.assertIsNone(second.context["undo_capture"])

    def test_undoing_a_discard_puts_it_back(self):
        self.discard()

        self.undo()

        self.capture.refresh_from_db()
        self.assertIsNone(self.capture.resolved_at)
        self.assertEqual(self.capture.resolution, "")
        self.assertEqual(
            list(self.client.get("/capture/").context["captures"]), [self.capture]
        )

    def test_undoing_a_task_deletes_the_task(self):
        self.promote_to_task()

        self.undo()

        self.assertFalse(Item.objects.exists())
        self.capture.refresh_from_db()
        self.assertIsNone(self.capture.promoted_task)
        self.assertIsNone(self.capture.resolved_at)

    def test_undoing_an_idea_deletes_the_idea(self):
        self.promote_to_idea()

        self.undo()

        self.assertFalse(Idea.objects.exists())
        self.capture.refresh_from_db()
        self.assertIsNone(self.capture.promoted_idea)
        self.assertIsNone(self.capture.resolved_at)

    def test_undoing_something_still_in_the_inbox_is_refused(self):
        response = self.undo()

        self.assertRedirects(response, "/capture/")
        self.capture.refresh_from_db()
        self.assertIsNone(self.capture.resolved_at)

    def test_cannot_undo_someone_elses_capture(self):
        bob = User.objects.create_user("bob", "bob@example.com", PASSWORD)
        theirs = Capture.objects.create(
            owner=bob,
            text="Bob's thought",
            resolved_at=timezone.now(),
            resolution=Capture.Resolution.DISCARDED,
        )

        response = self.undo(capture=theirs)

        self.assertEqual(response.status_code, 404)
        theirs.refresh_from_db()
        self.assertIsNotNone(theirs.resolved_at)


class EditCaptureTest(TriageTest):
    def test_fixes_a_typo_while_it_is_still_unresolved(self):
        response = self.client.post(
            f"/capture/{self.capture.id}/edit/", data={"text": "Ring the vet back"}
        )

        self.capture.refresh_from_db()
        self.assertEqual(self.capture.text, "Ring the vet back")
        self.assertRedirects(response, "/capture/")

    def test_a_resolved_capture_is_locked(self):
        # The downstream task or idea is the live record from then on, and
        # two records disagreeing about what was captured helps nobody.
        self.discard()

        response = self.client.post(
            f"/capture/{self.capture.id}/edit/", data={"text": "Too late"}
        )

        self.capture.refresh_from_db()
        self.assertEqual(self.capture.text, "Ring the vet")
        self.assertContains(response, ALREADY_RESOLVED_ERROR)

    def test_blank_text_is_refused(self):
        response = self.client.post(
            f"/capture/{self.capture.id}/edit/", data={"text": "   "}
        )

        self.capture.refresh_from_db()
        self.assertEqual(self.capture.text, "Ring the vet")
        self.assertEqual(response.status_code, 200)

    def test_cannot_edit_someone_elses_capture(self):
        bob = User.objects.create_user("bob", "bob@example.com", PASSWORD)
        theirs = Capture.objects.create(owner=bob, text="Bob's thought")

        response = self.client.post(
            f"/capture/{theirs.id}/edit/", data={"text": "Mine now"}
        )

        self.assertEqual(response.status_code, 404)
        theirs.refresh_from_db()
        self.assertEqual(theirs.text, "Bob's thought")


class InboxPolishTest(TriageTest):
    def test_search_filters_the_inbox(self):
        Capture.objects.create(owner=self.user, text="Buy stamps")

        response = self.client.get("/capture/", {"q": "vet"})

        self.assertEqual(
            [each.text for each in response.context["captures"]], ["Ring the vet"]
        )

    def test_search_does_not_reach_another_users_captures(self):
        bob = User.objects.create_user("bob", "bob@example.com", PASSWORD)
        Capture.objects.create(owner=bob, text="Bob's vet appointment")

        response = self.client.get("/capture/", {"q": "vet"})

        self.assertEqual(
            [each.text for each in response.context["captures"]], ["Ring the vet"]
        )

    def test_the_inbox_says_how_long_the_oldest_has_been_waiting(self):
        response = self.client.get("/capture/")

        self.assertEqual(response.context["oldest"], self.capture.created_at)

    def test_an_empty_inbox_has_no_staleness_signal(self):
        self.discard()

        response = self.client.get("/capture/")

        self.assertIsNone(response.context["oldest"])
