"""M2 Connect: letting a bearer token ask who it belongs to.

The Connect screen pastes a personal access token and has to say whether it
works before saving it. Until now the only endpoint accepting a bearer token
was POST /api/v1/capture, so the only way to check a token was to write a
capture -- which would put a junk row in the owner's Inbox every time
somebody typed the token wrong.

GET /api/v1/me now accepts either auth. The same response also gives the
Settings screen the connected-account identity M2 asks it to show.

No escalation: a token already authorises writing captures to this account,
so telling its holder which account that is reveals nothing they could not
already infer.
"""
from django.test import Client, TestCase

from accounts.models import PersonalAccessToken, User


PASSWORD = "correct horse battery staple 47!"


class MeWithBearerTokenTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", PASSWORD
        )
        self.token_row, self.raw = PersonalAccessToken.generate(
            self.user, label="Phone"
        )
        self.client = Client(enforce_csrf_checks=True)

    def get_me(self, token=None):
        extra = {}
        if token is not None:
            extra["HTTP_AUTHORIZATION"] = f"Bearer {token}"
        return self.client.get("/api/v1/me", **extra)

    def test_a_valid_token_identifies_its_owner(self):
        response = self.get_me(self.raw)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"username": "alice", "email": "alice@example.com"},
        )

    def test_an_unknown_token_is_refused(self):
        response = self.get_me("not-a-real-token")

        self.assertEqual(response.status_code, 401)

    def test_a_revoked_token_stops_working(self):
        # Deleting the row is the whole of revocation, so this is what the
        # Connect screen sees after someone revokes a phone on the web.
        self.token_row.delete()

        response = self.get_me(self.raw)

        self.assertEqual(response.status_code, 401)

    def test_a_token_belonging_to_a_deactivated_account_is_refused(self):
        self.user.is_active = False
        self.user.save()

        response = self.get_me(self.raw)

        self.assertEqual(response.status_code, 401)

    def test_no_credentials_at_all_is_still_refused(self):
        self.assertEqual(self.get_me().status_code, 401)

    def test_one_users_token_never_answers_as_another(self):
        bob = User.objects.create_user("bob", "bob@example.com", PASSWORD)
        _, bobs_raw = PersonalAccessToken.generate(bob)

        response = self.get_me(bobs_raw)

        self.assertEqual(response.json()["username"], "bob")

    def test_using_a_token_records_that_it_was_used(self):
        # Connect is the first thing to touch a fresh token, so this is
        # where last_used_at starts being meaningful on the web token page.
        self.assertIsNone(self.token_row.last_used_at)

        self.get_me(self.raw)

        self.token_row.refresh_from_db()
        self.assertIsNotNone(self.token_row.last_used_at)


class MeWithSessionStillWorksTest(TestCase):
    """The SPA reads this endpoint too; adding token auth must not cost it."""

    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", PASSWORD
        )

    def test_a_logged_in_session_still_identifies_itself(self):
        self.client.force_login(self.user)

        response = self.client.get("/api/v1/me")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["username"], "alice")
