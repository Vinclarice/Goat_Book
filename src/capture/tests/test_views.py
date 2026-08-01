from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from capture.forms import EMPTY_CAPTURE_ERROR
from capture.models import Capture


PASSWORD = "correct horse battery staple 47!"


class CaptureInboxViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "alice",
            "alice@example.com",
            PASSWORD,
        )
        self.client.force_login(self.user)

    def test_requires_login(self):
        self.client.logout()

        response = self.client.get("/capture/")

        self.assertRedirects(response, "/accounts/login/?next=/capture/")

    def test_renders_the_inbox_with_a_capture_box(self):
        response = self.client.get("/capture/")

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "capture/inbox.html")
        self.assertTemplateUsed(response, "base.html")
        self.assertContains(response, 'name="text"')

    def test_shows_unresolved_captures_newest_first(self):
        Capture.objects.create(owner=self.user, text="Older thought")
        Capture.objects.create(owner=self.user, text="Newer thought")

        response = self.client.get("/capture/")

        self.assertEqual(
            [capture.text for capture in response.context["captures"]],
            ["Newer thought", "Older thought"],
        )

    def test_hides_resolved_captures(self):
        Capture.objects.create(
            owner=self.user,
            text="Already dealt with",
            resolved_at=timezone.now(),
        )

        response = self.client.get("/capture/")

        self.assertEqual(list(response.context["captures"]), [])
        self.assertNotContains(response, "Already dealt with")

    def test_hides_other_peoples_captures(self):
        bob = User.objects.create_user("bob", "bob@example.com", PASSWORD)
        Capture.objects.create(owner=bob, text="Bob's private thought")

        response = self.client.get("/capture/")

        self.assertEqual(list(response.context["captures"]), [])
        self.assertNotContains(response, "Bob&#x27;s private thought")


class NewCaptureViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "alice",
            "alice@example.com",
            PASSWORD,
        )
        self.client.force_login(self.user)

    def test_requires_login(self):
        self.client.logout()

        response = self.client.post("/capture/new/", data={"text": "Private thought"})

        self.assertRedirects(response, "/accounts/login/?next=/capture/new/")
        self.assertEqual(Capture.objects.count(), 0)

    def test_rejects_get(self):
        response = self.client.get("/capture/new/")

        self.assertEqual(response.status_code, 405)

    def test_saves_the_capture_for_the_owner_then_redirects_to_the_inbox(self):
        response = self.client.post("/capture/new/", data={"text": "Ring the vet"})

        capture = Capture.objects.get()
        self.assertEqual(capture.text, "Ring the vet")
        self.assertEqual(capture.owner, self.user)
        self.assertIsNone(capture.resolved_at)
        self.assertRedirects(response, "/capture/")

    def test_blank_capture_re_renders_the_inbox_without_saving(self):
        response = self.client.post("/capture/new/", data={"text": ""})

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "capture/inbox.html")
        self.assertContains(response, EMPTY_CAPTURE_ERROR)
        self.assertEqual(Capture.objects.count(), 0)
