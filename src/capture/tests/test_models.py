from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from capture.models import Capture, Idea
from lists.models import Tag


PASSWORD = "correct horse battery staple 47!"


class CaptureModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "alice",
            "alice@example.com",
            PASSWORD,
        )

    def test_a_new_capture_is_unresolved_and_stamped(self):
        capture = Capture.objects.create(owner=self.user, text="Ring the vet")

        self.assertIsNone(capture.resolved_at)
        self.assertIsNotNone(capture.created_at)

    def test_string_representation_is_the_text(self):
        capture = Capture.objects.create(owner=self.user, text="Ring the vet")

        self.assertEqual(str(capture), "Ring the vet")

    def test_captures_are_ordered_newest_first(self):
        first = Capture.objects.create(owner=self.user, text="First")
        second = Capture.objects.create(owner=self.user, text="Second")

        self.assertEqual(list(Capture.objects.all()), [second, first])

    def test_captures_belong_to_their_owner(self):
        bob = User.objects.create_user("bob", "bob@example.com", PASSWORD)
        mine = Capture.objects.create(owner=self.user, text="Mine")
        Capture.objects.create(owner=bob, text="Theirs")

        self.assertEqual(list(self.user.captures.all()), [mine])

    def test_resolving_takes_a_capture_out_of_the_unresolved_set(self):
        capture = Capture.objects.create(owner=self.user, text="Ring the vet")

        capture.resolved_at = timezone.now()
        capture.save()

        self.assertEqual(
            Capture.objects.filter(resolved_at__isnull=True).count(), 0,
        )

    def test_a_capture_can_carry_tags_from_the_shared_tag_vocabulary(self):
        """capture.tags reuses lists.Tag rather than a parallel model --
        the same owner-scoped tag typed on a task and on a capture should
        be one row, not two that happen to share a name.
        """
        capture = Capture.objects.create(owner=self.user, text="Buy the game")
        game = Tag.objects.create(owner=self.user, name="game-dev")

        capture.tags.add(game)

        self.assertEqual(list(capture.tags.all()), [game])
        self.assertEqual(list(game.captures.all()), [capture])

    def test_a_capture_has_no_tags_by_default(self):
        capture = Capture.objects.create(owner=self.user, text="Ring the vet")

        self.assertEqual(list(capture.tags.all()), [])


class IdeaModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "alice",
            "alice@example.com",
            PASSWORD,
        )

    def test_an_idea_can_carry_tags_from_the_shared_tag_vocabulary(self):
        # design/second-mind-discovery-plan.md 4.1 -- the same field
        # Capture.tags already is, same shared lists.Tag vocabulary.
        idea = Idea.objects.create(owner=self.user, text="Write a roguelike")
        game = Tag.objects.create(owner=self.user, name="game-dev")

        idea.tags.add(game)

        self.assertEqual(list(idea.tags.all()), [game])
        self.assertEqual(list(game.ideas.all()), [idea])

    def test_an_idea_has_no_tags_by_default(self):
        idea = Idea.objects.create(owner=self.user, text="Write a roguelike")

        self.assertEqual(list(idea.tags.all()), [])

    def test_related_ideas_are_visible_from_either_side_after_one_write(self):
        # design/second-mind-discovery-plan.md 4.3 -- symmetrical, so a
        # single add() is a two-way link, not two writes that could drift.
        a = Idea.objects.create(owner=self.user, text="Write a roguelike")
        b = Idea.objects.create(owner=self.user, text="Learn procgen")

        a.related_ideas.add(b)

        self.assertEqual(list(a.related_ideas.all()), [b])
        self.assertEqual(list(b.related_ideas.all()), [a])

    def test_an_idea_has_no_related_ideas_by_default(self):
        idea = Idea.objects.create(owner=self.user, text="Write a roguelike")

        self.assertEqual(list(idea.related_ideas.all()), [])
