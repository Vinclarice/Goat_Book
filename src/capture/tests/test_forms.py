from django.test import TestCase

from accounts.models import User
from capture.forms import EMPTY_CAPTURE_ERROR, CaptureForm
from capture.models import Capture


PASSWORD = "correct horse battery staple 47!"


class CaptureFormTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "alice",
            "alice@example.com",
            PASSWORD,
        )

    def test_text_is_the_only_field(self):
        form = CaptureForm()

        self.assertEqual(list(form.fields), ["text"])

    def test_blank_text_is_rejected(self):
        form = CaptureForm(data={"text": ""})

        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors["text"], [EMPTY_CAPTURE_ERROR])

    def test_whitespace_only_text_is_rejected(self):
        form = CaptureForm(data={"text": "   "})

        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors["text"], [EMPTY_CAPTURE_ERROR])

    def test_saves_a_stripped_capture_for_the_owner(self):
        form = CaptureForm(data={"text": "  Ring the vet  "})
        self.assertTrue(form.is_valid())

        capture = form.save(owner=self.user)

        self.assertEqual(capture, Capture.objects.get())
        self.assertEqual(capture.text, "Ring the vet")
        self.assertEqual(capture.owner, self.user)
        self.assertIsNone(capture.resolved_at)
