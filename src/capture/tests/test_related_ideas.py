"""Manually linking two ideas -- design/second-mind-discovery-plan.md 4.3.

Service-level coverage for link_ideas/unlink_ideas, including the
cross-owner guard the model's plain ManyToManyField("self") can't enforce
on its own. View-level rendering and isolation live in test_ideas.py and
here respectively.
"""
from django.test import TestCase

from accounts.models import User
from capture.models import Idea
from capture.services import (
    SELF_LINK_ERROR,
    UNRELATED_OWNERS_ERROR,
    CaptureConflict,
    link_ideas,
    unlink_ideas,
)


PASSWORD = "correct horse battery staple 47!"


class LinkIdeasTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", PASSWORD
        )
        self.a = Idea.objects.create(owner=self.user, text="Write a roguelike")
        self.b = Idea.objects.create(owner=self.user, text="Learn procgen")

    def test_linking_is_visible_from_both_sides_after_one_write(self):
        link_ideas(self.a, self.b)

        self.assertEqual(list(self.a.related_ideas.all()), [self.b])
        self.assertEqual(list(self.b.related_ideas.all()), [self.a])

    def test_linking_twice_is_harmless(self):
        link_ideas(self.a, self.b)
        link_ideas(self.a, self.b)

        self.assertEqual(list(self.a.related_ideas.all()), [self.b])

    def test_cannot_link_an_idea_to_itself(self):
        with self.assertRaises(CaptureConflict) as raised:
            link_ideas(self.a, self.a)

        self.assertEqual(str(raised.exception), SELF_LINK_ERROR)
        self.assertEqual(list(self.a.related_ideas.all()), [])

    def test_cannot_link_two_ideas_with_different_owners(self):
        bob = User.objects.create_user("bob", "bob@example.com", PASSWORD)
        theirs = Idea.objects.create(owner=bob, text="Bob's idea")

        with self.assertRaises(CaptureConflict) as raised:
            link_ideas(self.a, theirs)

        self.assertEqual(str(raised.exception), UNRELATED_OWNERS_ERROR)
        self.assertEqual(list(self.a.related_ideas.all()), [])
        self.assertEqual(list(theirs.related_ideas.all()), [])


class UnlinkIdeasTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", PASSWORD
        )
        self.a = Idea.objects.create(owner=self.user, text="Write a roguelike")
        self.b = Idea.objects.create(owner=self.user, text="Learn procgen")
        link_ideas(self.a, self.b)

    def test_unlinking_removes_the_relation_from_both_sides(self):
        unlink_ideas(self.a, self.b)

        self.assertEqual(list(self.a.related_ideas.all()), [])
        self.assertEqual(list(self.b.related_ideas.all()), [])

    def test_unlinking_something_never_linked_is_harmless(self):
        c = Idea.objects.create(owner=self.user, text="Unrelated")

        unlink_ideas(self.a, c)

        self.assertEqual(list(self.a.related_ideas.all()), [self.b])


class LinkIdeaViewTest(TestCase):
    """The HTTP surface: both ids arrive owner-scoped, so a cross-owner pair
    404s before it ever reaches link_ideas's own guard above.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", PASSWORD
        )
        self.client.force_login(self.user)
        self.a = Idea.objects.create(owner=self.user, text="Write a roguelike")
        self.b = Idea.objects.create(owner=self.user, text="Learn procgen")

    def link(self, idea, other):
        return self.client.post(
            f"/capture/ideas/{idea.id}/related/", data={"related": other.id}
        )

    def test_links_two_of_the_users_own_ideas(self):
        self.link(self.a, self.b)

        self.assertEqual(list(self.a.related_ideas.all()), [self.b])

    def test_cannot_link_to_someone_elses_idea(self):
        bob = User.objects.create_user("bob", "bob@example.com", PASSWORD)
        theirs = Idea.objects.create(owner=bob, text="Bob's idea")

        response = self.link(self.a, theirs)

        self.assertEqual(response.status_code, 404)
        self.assertEqual(list(self.a.related_ideas.all()), [])

    def test_cannot_link_someone_elses_idea_to_ones_own(self):
        bob = User.objects.create_user("bob", "bob@example.com", PASSWORD)
        theirs = Idea.objects.create(owner=bob, text="Bob's idea")

        response = self.link(theirs, self.a)

        self.assertEqual(response.status_code, 404)
        self.assertEqual(list(self.a.related_ideas.all()), [])


class UnlinkIdeaViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", PASSWORD
        )
        self.client.force_login(self.user)
        self.a = Idea.objects.create(owner=self.user, text="Write a roguelike")
        self.b = Idea.objects.create(owner=self.user, text="Learn procgen")
        link_ideas(self.a, self.b)

    def unlink(self, idea, other):
        return self.client.post(
            f"/capture/ideas/{idea.id}/related/{other.id}/unlink/"
        )

    def test_removes_the_relation(self):
        self.unlink(self.a, self.b)

        self.assertEqual(list(self.a.related_ideas.all()), [])

    def test_cannot_unlink_someone_elses_idea(self):
        bob = User.objects.create_user("bob", "bob@example.com", PASSWORD)
        theirs = Idea.objects.create(owner=bob, text="Bob's idea")

        response = self.unlink(self.a, theirs)

        self.assertEqual(response.status_code, 404)
