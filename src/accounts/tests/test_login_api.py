"""POST /api/v1/login -- trading a password for a personal access token.

design/android-login-plan.md: this is how the Android app authenticates
directly instead of requiring someone to paste a token created on the web.
Deliberately unauthenticated (that's the entire point), and deliberately
routed through django.contrib.auth.authenticate() rather than a hand-rolled
check, so axes' five-attempts lockout applies here exactly as it already
does to the web login form -- see accounts/tests/test_lockout.py.
"""
import json

from django.test import Client, TestCase

from accounts.models import PersonalAccessToken, User


PASSWORD = "correct horse battery staple 47!"
URL = "/api/v1/login"


class LoginEndpointTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", PASSWORD
        )
        # enforce_csrf_checks, matching capture's CaptureEndpointTest: this
        # endpoint takes no session cookie at all, so there is nothing for
        # CSRF to protect and nothing it should ever be blocked by.
        self.client = Client(enforce_csrf_checks=True)

    def post(self, payload):
        return self.client.post(
            URL, data=json.dumps(payload), content_type="application/json"
        )

    def test_valid_credentials_return_a_fresh_token(self):
        response = self.post({"username": "alice", "password": PASSWORD})

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["username"], "alice")
        self.assertEqual(body["email"], "alice@example.com")
        self.assertEqual(PersonalAccessToken.objects.count(), 1)

    def test_the_returned_token_actually_authenticates(self):
        token = self.post({"username": "alice", "password": PASSWORD}).json()["token"]

        response = self.client.get(
            "/api/v1/me", HTTP_AUTHORIZATION=f"Bearer {token}"
        )

        self.assertEqual(response.status_code, 200)

    def test_wrong_password_is_401_and_creates_nothing(self):
        response = self.post({"username": "alice", "password": "not it"})

        self.assertEqual(response.status_code, 401)
        self.assertFalse(PersonalAccessToken.objects.exists())

    def test_a_made_up_username_is_401_the_same_shape_as_a_wrong_password(self):
        made_up = self.post({"username": "nobody", "password": "whatever"})
        wrong_password = self.post({"username": "alice", "password": "not it"})

        # No enumeration: a caller cannot tell "wrong password" from
        # "no such account" from the response alone.
        self.assertEqual(made_up.status_code, wrong_password.status_code)
        self.assertEqual(made_up.json(), wrong_password.json())

    def test_a_deactivated_account_is_401(self):
        self.user.is_active = False
        self.user.save()

        response = self.post({"username": "alice", "password": PASSWORD})

        self.assertEqual(response.status_code, 401)
        self.assertFalse(PersonalAccessToken.objects.exists())

    def test_the_label_defaults_to_android(self):
        self.post({"username": "alice", "password": PASSWORD})

        self.assertEqual(PersonalAccessToken.objects.get().label, "Android")

    def test_a_given_label_is_used_instead(self):
        self.post(
            {"username": "alice", "password": PASSWORD, "label": "Vince's phone"}
        )

        self.assertEqual(
            PersonalAccessToken.objects.get().label, "Vince's phone"
        )

    def test_five_wrong_attempts_lock_the_account_even_for_the_right_password(self):
        # axes' own middleware intercepts a locked-out request before this
        # view's authenticate() call ever runs, answering 429 directly --
        # not this endpoint's 401, which only covers a single failed
        # attempt that isn't already locked out. Both mean "no token", and
        # asserting the real status is the point: a test expecting 401
        # here would pass for the wrong reason if axes silently stopped
        # applying to this endpoint.
        for _ in range(5):
            self.post({"username": "alice", "password": "not it"})

        response = self.post({"username": "alice", "password": PASSWORD})

        self.assertEqual(response.status_code, 429)
        self.assertFalse(PersonalAccessToken.objects.exists())
