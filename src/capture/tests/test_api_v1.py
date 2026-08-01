"""POST /api/v1/capture -- the one endpoint a non-browser client gets.

Isolation gets two tests rather than a suite: nothing here takes an id, in
a path or a body, so there is no way to address another user's data through
it at all. A capture is created for whoever the credential resolves to, and
that's the whole attack surface -- materially smaller than `parent` was in
lists/tests/test_isolation.py.
"""
import json

from django.test import Client, TestCase

from accounts.models import PersonalAccessToken, User
from capture.models import Capture
from capture.services import EMPTY_CAPTURE_ERROR


PASSWORD = "correct horse battery staple 47!"
URL = "/api/v1/capture"


class CaptureEndpointTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", PASSWORD
        )
        _, self.raw = PersonalAccessToken.generate(self.user, label="Phone")
        # enforce_csrf_checks, because the default client silently disables
        # CSRF and that is precisely what hid a real bug here: a bad token
        # used to fall through to session auth and answer "403 CSRF check
        # Failed" instead of 401. Only curl could see it.
        self.client = Client(enforce_csrf_checks=True)

    def post(self, payload, token=None, **extra):
        if token is not None:
            extra["HTTP_AUTHORIZATION"] = f"Bearer {token}"
        return self.client.post(
            URL,
            data=json.dumps(payload),
            content_type="application/json",
            **extra,
        )

    def test_a_valid_token_creates_a_capture_for_its_owner(self):
        response = self.post({"text": "Call the vet"}, token=self.raw)

        self.assertEqual(response.status_code, 201)
        capture = Capture.objects.get()
        self.assertEqual(capture.owner, self.user)
        self.assertEqual(capture.text, "Call the vet")
        self.assertEqual(response.json()["id"], capture.id)

    def test_the_capture_lands_in_the_owners_inbox(self):
        self.post({"text": "Call the vet"}, token=self.raw)

        self.client.force_login(self.user)
        inbox = self.client.get("/capture/")

        self.assertContains(inbox, "Call the vet")

    def test_no_credential_at_all_is_401(self):
        response = self.post({"text": "Call the vet"})

        self.assertEqual(response.status_code, 401)
        self.assertFalse(Capture.objects.exists())

    def test_a_made_up_token_is_401(self):
        response = self.post({"text": "Call the vet"}, token="not-a-real-token")

        self.assertEqual(response.status_code, 401)
        self.assertFalse(Capture.objects.exists())

    def test_a_deleted_token_is_401(self):
        # Deleting the row is the whole of revocation, so this is the test
        # that revocation works.
        PersonalAccessToken.objects.all().delete()

        response = self.post({"text": "Call the vet"}, token=self.raw)

        self.assertEqual(response.status_code, 401)
        self.assertFalse(Capture.objects.exists())

    def test_a_token_belonging_to_a_deactivated_account_is_401(self):
        self.user.is_active = False
        self.user.save()

        response = self.post({"text": "Call the vet"}, token=self.raw)

        self.assertEqual(response.status_code, 401)

    def test_using_a_token_stamps_last_used_at(self):
        self.post({"text": "Call the vet"}, token=self.raw)

        self.assertIsNotNone(
            PersonalAccessToken.objects.get(owner=self.user).last_used_at
        )

    def test_a_capture_belongs_to_the_token_holder_not_whoever_asks(self):
        other = User.objects.create_user("bob", "bob@example.com", PASSWORD)
        _, other_raw = PersonalAccessToken.generate(other)

        self.post({"text": "Bob's thought"}, token=other_raw)

        self.assertEqual(Capture.objects.get().owner, other)

    def test_empty_text_is_rejected_with_the_same_message_the_form_shows(self):
        response = self.post({"text": "   "}, token=self.raw)

        self.assertEqual(response.status_code, 400)
        self.assertIn(EMPTY_CAPTURE_ERROR, response.json()["detail"])
        self.assertFalse(Capture.objects.exists())

    def test_a_logged_in_browser_can_still_use_it(self):
        # Session auth stays on the same endpoint rather than getting its
        # own -- two code paths for one action is how they drift.
        self.client.force_login(self.user)
        csrf_token = self.client.get(
            "/accounts/password/change/"
        ).cookies["csrftoken"].value

        response = self.client.post(
            URL,
            data=json.dumps({"text": "From the browser"}),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=csrf_token,
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Capture.objects.get().owner, self.user)

    def test_a_logged_in_browser_still_needs_its_csrf_token(self):
        # The other half of the fix: declining to CSRF-check a caller with
        # no session must not stop checking one that has a session, which
        # is the only request the check ever protected.
        self.client.force_login(self.user)

        response = self.client.post(
            URL,
            data=json.dumps({"text": "Forged"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Capture.objects.exists())
