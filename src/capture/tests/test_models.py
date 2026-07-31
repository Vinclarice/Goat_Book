from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from capture.models import Capture


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
