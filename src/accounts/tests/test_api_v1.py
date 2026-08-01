import json

from django.test import TestCase

from accounts.models import User


class MeEndpointTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "alice",
            "alice@example.com",
            "a secure password",
        )

    def test_returns_the_logged_in_user(self):
        self.client.force_login(self.user)

        response = self.client.get("/api/v1/me")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"username": "alice", "email": "alice@example.com"},
        )

    def test_rejects_anonymous_requests(self):
        response = self.client.get("/api/v1/me")

        self.assertEqual(response.status_code, 401)


class PreferencesEndpointTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "alice",
            "alice@example.com",
            "a secure password",
        )
        self.other_user = User.objects.create_user(
            "bob",
            "bob@example.com",
            "another secure password",
        )

    def _patch(self, payload):
        return self.client.patch(
            "/api/v1/me/preferences",
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_rejects_anonymous_requests(self):
        response = self.client.get("/api/v1/me/preferences")

        self.assertEqual(response.status_code, 401)

    def test_returns_the_current_preferences_including_the_theme_default(self):
        self.client.force_login(self.user)

        response = self.client.get("/api/v1/me/preferences")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "username": "alice",
                "email": "alice@example.com",
                "daily_digest": True,
                "theme": "system",
                "time_zone": "America/New_York",
            },
        )

    def test_updates_preferences_including_theme(self):
        self.client.force_login(self.user)

        response = self._patch(
            {
                "username": "alice",
                "email": "alice@example.com",
                "daily_digest": False,
                "theme": "dark",
                "time_zone": "America/New_York",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertFalse(self.user.daily_digest)
        self.assertEqual(self.user.theme, "dark")

    def test_rejects_a_duplicate_email(self):
        self.client.force_login(self.user)

        response = self._patch(
            {
                "username": "alice",
                "email": "bob@example.com",
                "daily_digest": True,
                "theme": "system",
                "time_zone": "America/New_York",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "alice@example.com")
