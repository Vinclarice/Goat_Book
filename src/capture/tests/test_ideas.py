"""The Ideas page: the half of triage that isn't a task.

An idea has no due date and no done state -- it is either still being
turned over, kept so it can be found again, or promoted into a task, at
which point the task becomes the live record.
"""
from django.test import TestCase

from accounts.models import User
from capture.models import Capture, Idea
from capture.services import PROMOTED_IDEA_LOCKED_ERROR
from lists.models import Item, List, Tag


PASSWORD = "correct horse battery staple 47!"


class IdeasTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", PASSWORD
        )
        self.client.force_login(self.user)
        self.list_ = List.objects.create(owner=self.user, title="Reading")
        self.idea = Idea.objects.create(
            owner=self.user,
            text="Read a book on product design",
            notes="Something about taste, not process",
        )

    def shown(self, response):
        return [idea.text for idea, _form in response.context["ideas"]]


class IdeasPageTest(IdeasTest):
    def test_requires_login(self):
        self.client.logout()

        response = self.client.get("/capture/ideas/")

        self.assertRedirects(response, "/accounts/login/?next=/capture/ideas/")

    def test_shows_exploring_and_reference_by_default(self):
        Idea.objects.create(
            owner=self.user, text="Kept for later", status=Idea.Status.REFERENCE
        )

        response = self.client.get("/capture/ideas/")

        self.assertEqual(
            sorted(self.shown(response)),
            ["Kept for later", "Read a book on product design"],
        )

    def test_hides_promoted_ideas_from_the_default_view(self):
        # The task is the live record once one exists, but the row survives
        # so the Capture -> Idea -> Task lineage stays followable.
        Idea.objects.create(
            owner=self.user, text="Already a task", status=Idea.Status.PROMOTED
        )

        default = self.client.get("/capture/ideas/")
        filtered = self.client.get("/capture/ideas/", {"status": "promoted"})

        self.assertNotIn("Already a task", self.shown(default))
        self.assertEqual(self.shown(filtered), ["Already a task"])

    def test_filters_by_status(self):
        Idea.objects.create(
            owner=self.user, text="Kept for later", status=Idea.Status.REFERENCE
        )

        response = self.client.get("/capture/ideas/", {"status": "reference"})

        self.assertEqual(self.shown(response), ["Kept for later"])

    def test_hides_other_peoples_ideas(self):
        bob = User.objects.create_user("bob", "bob@example.com", PASSWORD)
        Idea.objects.create(owner=bob, text="Bob's private idea")

        response = self.client.get("/capture/ideas/")

        self.assertEqual(self.shown(response), ["Read a book on product design"])
        self.assertNotContains(response, "Bob&#x27;s private idea")

    def test_a_tagged_idea_shows_its_tags(self):
        # design/second-mind-discovery-plan.md 4.1 -- same render pattern as
        # capture.tests.test_views.test_a_tagged_capture_shows_its_tags.
        self.idea.tags.add(Tag.objects.create(owner=self.user, name="game-dev"))

        response = self.client.get("/capture/ideas/")

        self.assertContains(response, "game-dev")

    def test_an_untagged_idea_shows_no_tag_pills(self):
        response = self.client.get("/capture/ideas/")

        self.assertNotContains(response, 'class="idea-tag')


class IdeaSearchTest(IdeasTest):
    def test_searches_the_text(self):
        Idea.objects.create(owner=self.user, text="Learn to sail")

        response = self.client.get("/capture/ideas/", {"q": "product"})

        self.assertEqual(self.shown(response), ["Read a book on product design"])

    def test_searches_the_notes_too(self):
        # A reference archive you can only search by title is barely an
        # archive -- the thinking is in the notes.
        response = self.client.get("/capture/ideas/", {"q": "taste"})

        self.assertEqual(self.shown(response), ["Read a book on product design"])

    def test_search_is_scoped_to_the_current_user(self):
        bob = User.objects.create_user("bob", "bob@example.com", PASSWORD)
        Idea.objects.create(owner=bob, text="Bob's product idea")

        response = self.client.get("/capture/ideas/", {"q": "product"})

        self.assertEqual(self.shown(response), ["Read a book on product design"])


class EditIdeaTest(IdeasTest):
    def edit(self, idea=None, text="Read two books", notes="Updated thinking"):
        idea = idea or self.idea
        return self.client.post(
            f"/capture/ideas/{idea.id}/edit/", data={"text": text, "notes": notes}
        )

    def test_edits_text_and_notes(self):
        response = self.edit()

        self.idea.refresh_from_db()
        self.assertEqual(self.idea.text, "Read two books")
        self.assertEqual(self.idea.notes, "Updated thinking")
        self.assertRedirects(response, "/capture/ideas/")

    def test_a_reference_idea_is_editable_too(self):
        self.idea.status = Idea.Status.REFERENCE
        self.idea.save()

        self.edit()

        self.idea.refresh_from_db()
        self.assertEqual(self.idea.text, "Read two books")

    def test_a_promoted_idea_is_locked(self):
        self.idea.status = Idea.Status.PROMOTED
        self.idea.save()

        self.edit()

        self.idea.refresh_from_db()
        self.assertEqual(self.idea.text, "Read a book on product design")
        self.assertContains(
            self.client.get("/capture/ideas/"), PROMOTED_IDEA_LOCKED_ERROR
        )

    def test_blank_text_is_refused(self):
        self.edit(text="   ")

        self.idea.refresh_from_db()
        self.assertEqual(self.idea.text, "Read a book on product design")

    def test_cannot_edit_someone_elses_idea(self):
        bob = User.objects.create_user("bob", "bob@example.com", PASSWORD)
        theirs = Idea.objects.create(owner=bob, text="Bob's idea")

        response = self.edit(idea=theirs)

        self.assertEqual(response.status_code, 404)
        theirs.refresh_from_db()
        self.assertEqual(theirs.text, "Bob's idea")


class PromoteIdeaTest(IdeasTest):
    def promote(self, idea=None, for_list=None):
        idea = idea or self.idea
        return self.client.post(
            f"/capture/ideas/{idea.id}/task/",
            data={"list": (for_list or self.list_).id},
        )

    def test_creates_a_task_carrying_the_text_and_notes(self):
        self.promote()

        task = Item.objects.get()
        self.assertEqual(task.text, "Read a book on product design")
        self.assertEqual(task.list, self.list_)
        # Thinking already recorded shouldn't be stranded on a page you
        # stop visiting once the thing is actionable.
        self.assertEqual(task.notes, "Something about taste, not process")

    def test_records_the_promotion_without_deleting_the_idea(self):
        self.promote()

        self.idea.refresh_from_db()
        self.assertEqual(self.idea.status, Idea.Status.PROMOTED)
        self.assertEqual(self.idea.promoted_task, Item.objects.get())

    def test_a_second_promotion_is_refused(self):
        self.promote()

        self.promote()

        self.assertEqual(Item.objects.count(), 1)

    def test_cannot_promote_into_someone_elses_list(self):
        bob = User.objects.create_user("bob", "bob@example.com", PASSWORD)
        theirs = List.objects.create(owner=bob, title="Bob's list")

        response = self.promote(for_list=theirs)

        self.assertEqual(response.status_code, 404)
        self.assertFalse(Item.objects.exists())

    def test_cannot_promote_someone_elses_idea(self):
        bob = User.objects.create_user("bob", "bob@example.com", PASSWORD)
        theirs = Idea.objects.create(owner=bob, text="Bob's idea")

        response = self.promote(idea=theirs)

        self.assertEqual(response.status_code, 404)
        self.assertFalse(Item.objects.exists())


class DeleteIdeaTest(IdeasTest):
    def delete(self, idea=None):
        return self.client.post(f"/capture/ideas/{(idea or self.idea).id}/delete/")

    def test_deletes_outright(self):
        # Hard, unlike a discarded capture: by the time something is a
        # standalone idea you're managing it, not triaging a queue.
        response = self.delete()

        self.assertFalse(Idea.objects.exists())
        self.assertRedirects(response, "/capture/ideas/")

    def test_the_capture_it_came_from_keeps_its_history(self):
        capture = Capture.objects.create(
            owner=self.user,
            text="Read a book on product design",
            resolution=Capture.Resolution.IDEA,
            promoted_idea=self.idea,
        )

        self.delete()

        capture.refresh_from_db()
        # SET_NULL doing its job: the pointer goes, the fact doesn't.
        self.assertIsNone(capture.promoted_idea)
        self.assertEqual(capture.resolution, Capture.Resolution.IDEA)

    def test_cannot_delete_someone_elses_idea(self):
        bob = User.objects.create_user("bob", "bob@example.com", PASSWORD)
        theirs = Idea.objects.create(owner=bob, text="Bob's idea")

        response = self.delete(idea=theirs)

        self.assertEqual(response.status_code, 404)
        self.assertTrue(Idea.objects.filter(pk=theirs.pk).exists())


class DeletedTaskLineageTest(IdeasTest):
    def test_deleting_the_task_leaves_the_idea_saying_it_was_promoted(self):
        self.client.post(
            f"/capture/ideas/{self.idea.id}/task/", data={"list": self.list_.id}
        )
        Item.objects.get().delete()

        self.idea.refresh_from_db()
        self.assertIsNone(self.idea.promoted_task)
        self.assertEqual(self.idea.status, Idea.Status.PROMOTED)
