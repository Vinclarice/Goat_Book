"""TokenAuth's scope and expiry enforcement -- token-scopes-plan.md.

Endpoint-level wiring (/me, /capture, /day each requiring their own scope)
lives in each endpoint's own test file; this is TokenAuth itself, called
directly rather than through Ninja's routing since authenticate() only
needs a request and a raw token.
"""
from datetime import timedelta

from django.http import HttpRequest
from django.test import TestCase
from django.utils import timezone

from accounts.auth import TokenAuth
from accounts.models import PersonalAccessToken, User


PASSWORD = "correct horse battery staple 47!"


class TokenAuthScopeTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", PASSWORD
        )

    def _request(self):
        return HttpRequest()

    def test_a_token_with_the_required_scope_authenticates(self):
        _, raw = PersonalAccessToken.generate(self.user, scopes=["day:read"])

        result = TokenAuth("day:read").authenticate(self._request(), raw)

        self.assertEqual(result, self.user)

    def test_a_token_missing_the_required_scope_is_refused(self):
        # Valid token, wrong capability -- capture:write must not also mean
        # day:read.
        _, raw = PersonalAccessToken.generate(self.user, scopes=["capture:write"])

        result = TokenAuth("day:read").authenticate(self._request(), raw)

        self.assertIsNone(result)

    def test_a_token_with_no_scopes_at_all_is_refused(self):
        _, raw = PersonalAccessToken.generate(self.user)

        result = TokenAuth("day:read").authenticate(self._request(), raw)

        self.assertIsNone(result)

    def test_an_expired_token_is_refused_even_with_the_right_scope(self):
        _, raw = PersonalAccessToken.generate(
            self.user,
            scopes=["day:read"],
            expires_at=timezone.now() - timedelta(seconds=1),
        )

        result = TokenAuth("day:read").authenticate(self._request(), raw)

        self.assertIsNone(result)

    def test_a_token_with_no_expiry_still_authenticates(self):
        _, raw = PersonalAccessToken.generate(self.user, scopes=["day:read"])

        result = TokenAuth("day:read").authenticate(self._request(), raw)

        self.assertEqual(result, self.user)

    def test_a_token_not_yet_expired_still_authenticates(self):
        _, raw = PersonalAccessToken.generate(
            self.user,
            scopes=["day:read"],
            expires_at=timezone.now() + timedelta(days=1),
        )

        result = TokenAuth("day:read").authenticate(self._request(), raw)

        self.assertEqual(result, self.user)

    def test_a_successful_scope_check_stamps_last_used_at(self):
        token, raw = PersonalAccessToken.generate(self.user, scopes=["day:read"])
        self.assertIsNone(token.last_used_at)

        TokenAuth("day:read").authenticate(self._request(), raw)

        token.refresh_from_db()
        self.assertIsNotNone(token.last_used_at)

    def test_a_missing_scope_does_not_stamp_last_used_at(self):
        # A token that never actually authenticated was never used --
        # last_used_at means "this token did something", not "something
        # tried this token".
        token, raw = PersonalAccessToken.generate(self.user, scopes=["capture:write"])

        TokenAuth("day:read").authenticate(self._request(), raw)

        token.refresh_from_db()
        self.assertIsNone(token.last_used_at)

    def test_an_expired_token_does_not_stamp_last_used_at(self):
        token, raw = PersonalAccessToken.generate(
            self.user,
            scopes=["day:read"],
            expires_at=timezone.now() - timedelta(seconds=1),
        )

        TokenAuth("day:read").authenticate(self._request(), raw)

        token.refresh_from_db()
        self.assertIsNone(token.last_used_at)
