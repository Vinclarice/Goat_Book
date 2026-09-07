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
from datetime import timedelta

from django.test import Client, TestCase
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from accounts.models import SCOPE_IDENTITY_READ, PersonalAccessToken, User


PASSWORD = "correct horse battery staple 47!"


class MeWithBearerTokenTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", PASSWORD
        )
        self.token_row, self.raw = PersonalAccessToken.generate(
            self.user, label="Phone", scopes=[SCOPE_IDENTITY_READ]
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
        # The whole body, deliberately: an exact-dict assertion is what
        # notices a field arriving here that nobody meant to expose.
        #
        # **It gained two on September 7, 2026** --
        # `android-login-redesign-plan.md` Half A -- and this expectation was
        # *updated* rather than loosened to `assertIn`. `principles.md` allows
        # changing an assertion to reach green only when the contract genuinely
        # changed, which it did; loosening it instead would have bought the
        # same green while retiring the guard that makes this test worth
        # having.
        self.assertEqual(
            response.json(),
            {
                "username": "alice",
                "email": "alice@example.com",
                "scopes": ["identity:read"],
                "expires_at": None,
            },
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
        _, bobs_raw = PersonalAccessToken.generate(
            bob, scopes=[SCOPE_IDENTITY_READ]
        )

        response = self.get_me(bobs_raw)

        self.assertEqual(response.json()["username"], "bob")

    def test_a_token_without_identity_read_is_refused(self):
        # Valid, unexpired, wrong capability -- a capture-only token must
        # not also be able to read who it belongs to.
        _, capture_only = PersonalAccessToken.generate(
            self.user, scopes=["capture:write"]
        )

        response = self.get_me(capture_only)

        self.assertEqual(response.status_code, 401)

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


class MeDescribesTheTokenItselfTest(TestCase):
    """A credential that can explain itself — `android-login-redesign-plan.md`
    Half A, increment 1.

    **The phone was structurally blind and it cost a day.** `/me` returned a
    username and an email, which is the entire self-knowledge a connected
    phone had — so a missing scope, an expired token and a revoked one all
    arrived as one sentence, *Reconnect in Settings*, naming a cure rather
    than a cause. A token lacking `day:read` reported the account fine while
    the Day screen refused, and Settings said *connected*.

    **This is not the oracle `TokenAuth` refuses to be.** That refusal — one
    undifferentiated 401 for unknown, expired and wrong-scope — protects
    against *an attacker holding an unknown token* learning which scope to go
    steal next. Here the caller has already presented a valid token carrying
    `identity:read` and is asking what that same token can do. It has passed
    the gate; the answer describes the credential in its own hand, and adds
    nothing it could not establish by trying each endpoint once.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", PASSWORD
        )

    def token(self, scopes, expires_at=None):
        _, raw = PersonalAccessToken.generate(
            self.user, label="Phone", scopes=scopes, expires_at=expires_at
        )
        return raw

    def get_me(self, raw):
        return self.client.get("/api/v1/me", HTTP_AUTHORIZATION=f"Bearer {raw}")

    def test_a_token_reports_the_scopes_it_holds(self):
        raw = self.token([SCOPE_IDENTITY_READ, "day:read", "capture:write"])

        body = self.get_me(raw).json()

        self.assertEqual(
            body["scopes"], ["capture:write", "day:read", "identity:read"]
        )

    def test_the_scopes_are_sorted_rather_than_set_ordered(self):
        """`scope_set` is a `set`, whose iteration order is not stable across
        runs. Unsorted, this field would churn the OpenAPI contract's examples
        and make any assertion on it flaky for reasons unrelated to scopes."""
        first = self.get_me(self.token(["day:read", SCOPE_IDENTITY_READ])).json()
        second = self.get_me(self.token([SCOPE_IDENTITY_READ, "day:read"])).json()

        self.assertEqual(first["scopes"], second["scopes"])
        self.assertEqual(first["scopes"], sorted(first["scopes"]))

    def test_a_token_reports_what_it_does_not_hold_by_omission(self):
        """The half the phone actually acts on: `day:read` absent is what
        lets it say *this connection cannot read your day* instead of
        *reconnect*."""
        raw = self.token([SCOPE_IDENTITY_READ])

        self.assertNotIn("day:read", self.get_me(raw).json()["scopes"])

    def test_an_expiring_token_reports_when(self):
        when = timezone.now() + timedelta(days=90)
        raw = self.token([SCOPE_IDENTITY_READ], expires_at=when)

        body = self.get_me(raw).json()

        self.assertIsNotNone(body["expires_at"])
        # To the second, not the microsecond. The store-and-serialise round
        # trip does not preserve sub-millisecond precision -- written first as
        # an exact equality, which failed by 551 microseconds. **The test was
        # wrong rather than the code**: nothing about a ninety-day expiry is
        # decided below a second, so an assertion that tight was asserting the
        # round trip's internals rather than the behaviour, and would have gone
        # red on an unrelated change to either end of it.
        self.assertAlmostEqual(
            parse_datetime(body["expires_at"]), when, delta=timedelta(seconds=1)
        )

    def test_a_token_that_never_expires_reports_null_rather_than_a_date(self):
        """Null means never in the model, and it has to keep meaning that
        here — a client inventing a far-future date would warn about an
        expiry that is not coming."""
        raw = self.token([SCOPE_IDENTITY_READ])

        self.assertIsNone(self.get_me(raw).json()["expires_at"])

    def test_a_session_reports_no_scopes_at_all(self):
        """A session is not scoped and does not expire the way a token does,
        so both fields are null rather than a full list — which would read as
        *this credential holds everything* and be acted on by a client that
        cannot tell the two apart.

        The SPA reads this endpoint by session, so this is the case that must
        not acquire a misleading answer.
        """
        self.client.force_login(self.user)

        body = self.client.get("/api/v1/me").json()

        self.assertEqual(body["username"], "alice")
        self.assertIsNone(body["scopes"])
        self.assertIsNone(body["expires_at"])
