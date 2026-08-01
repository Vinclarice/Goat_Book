"""POST /api/v1/capture -- the one endpoint a non-browser client gets.

Isolation gets two tests rather than a suite: nothing here takes an id, in
a path or a body, so there is no way to address another user's data through
it at all. A capture is created for whoever the credential resolves to, and
that's the whole attack surface -- materially smaller than `parent` was in
lists/tests/test_isolation.py.
"""
import json
import uuid

from django.test import Client, TestCase

from accounts.models import PersonalAccessToken, User
from capture.models import Capture
from capture.services import EMPTY_CAPTURE_ERROR, create_capture_idempotent


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


class CaptureIdempotencyKeyTest(CaptureEndpointTest):
    """Bittern M1: POST /api/v1/capture's Idempotency-Key header.

    Inherits CaptureEndpointTest's setUp (an owner with a valid token and
    a CSRF-enforcing client) rather than duplicating it -- this is the
    same endpoint, one more optional header.
    """

    def post(self, payload, token=None, idempotency_key=None, **extra):
        if idempotency_key is not None:
            extra["HTTP_IDEMPOTENCY_KEY"] = str(idempotency_key)
        return super().post(payload, token=token, **extra)

    def test_a_keyed_request_creates_one_capture(self):
        key = uuid.uuid4()

        response = self.post(
            {"text": "Call the vet"}, token=self.raw, idempotency_key=key
        )

        self.assertEqual(response.status_code, 201)
        capture = Capture.objects.get()
        self.assertEqual(capture.idempotency_key, key)

    def test_repeating_the_same_key_returns_the_original_capture_not_a_new_one(self):
        key = uuid.uuid4()
        first = self.post(
            {"text": "Call the vet"}, token=self.raw, idempotency_key=key
        )

        retry = self.post(
            # Different text on purpose: a lost-response retry sends the
            # same request, but even if it didn't, the first successful
            # write is the one of record -- see create_capture_idempotent.
            {"text": "Call the vet (retry)"}, token=self.raw, idempotency_key=key
        )

        self.assertEqual(retry.status_code, 200)
        self.assertEqual(retry.json()["id"], first.json()["id"])
        self.assertEqual(Capture.objects.count(), 1)
        self.assertEqual(Capture.objects.get().text, "Call the vet")

    def test_a_lost_race_returns_the_row_the_winner_created(self):
        # Simulates the case a real concurrent retry hits: another request
        # already committed a row for this (owner, key) by the time this
        # one reaches the constraint. create_capture_idempotent must catch
        # that IntegrityError and return the existing row rather than
        # raising it up through the view.
        key = uuid.uuid4()
        winner = Capture.objects.create(
            owner=self.user, text="Already there", idempotency_key=key
        )

        capture, created = create_capture_idempotent(self.user, "Also mine", key)

        self.assertFalse(created)
        self.assertEqual(capture, winner)
        self.assertEqual(Capture.objects.count(), 1)

    def test_different_owners_may_reuse_the_same_key(self):
        other = User.objects.create_user("bob", "bob@example.com", PASSWORD)
        _, other_raw = PersonalAccessToken.generate(other)
        key = uuid.uuid4()

        self.post({"text": "Mine"}, token=self.raw, idempotency_key=key)
        response = self.post({"text": "Theirs"}, token=other_raw, idempotency_key=key)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Capture.objects.count(), 2)
        self.assertEqual(
            {c.owner for c in Capture.objects.all()}, {self.user, other}
        )

    def test_a_malformed_key_is_rejected_and_creates_nothing(self):
        response = self.post(
            {"text": "Call the vet"}, token=self.raw, idempotency_key="not-a-uuid"
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Capture.objects.exists())

    def test_omitting_the_header_still_works_exactly_as_before(self):
        response = self.post({"text": "Call the vet"}, token=self.raw)

        self.assertEqual(response.status_code, 201)
        capture = Capture.objects.get()
        self.assertIsNone(capture.idempotency_key)

    def test_two_keyless_requests_never_collide_with_each_other(self):
        self.post({"text": "One"}, token=self.raw)
        response = self.post({"text": "Two"}, token=self.raw)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Capture.objects.count(), 2)
