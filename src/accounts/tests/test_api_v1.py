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
                # The evening nudge, added August 20, 2026. False here rather
                # than absent, and false rather than true, because a second
                # recurring message is a different thing to agree to --
                # `/privacy/` says so in published text and a test holds the
                # two together.
                "closing_nudge": False,
                "theme": "system",
                "time_zone": "America/New_York",
                # Crane 1 slice 5 added the Personal Compass to this payload.
                # Empty for an account that has never written one, and empty
                # rather than absent so the client never narrows a maybe-null.
                "compass_purpose": "",
                "compass_question": "",
                # Crane 1 slice 6. "day" is the default because Crane makes
                # the Daily Page the home surface.
                "landing_surface": "day",
            },
        )

    def test_the_compass_saves_and_comes_back(self):
        """Edited once, here, and displayed on every Daily Page."""
        self.client.force_login(self.user)

        response = self.client.patch(
            "/api/v1/me/preferences",
            data=json.dumps(
                {
                    "username": "alice",
                    "email": "alice@example.com",
                    "daily_digest": True,
                    "theme": "system",
                    "time_zone": "America/New_York",
                    "compass_purpose": "Build something worth maintaining.",
                    "compass_question": "What is the most I can do?",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(
            self.user.compass_purpose, "Build something worth maintaining."
        )
        self.assertEqual(self.user.compass_question, "What is the most I can do?")

    def test_saving_without_a_compass_does_not_demand_one(self):
        """It is a standing note, not a required field -- and an account that
        has never written one must still be able to change its time zone."""
        self.client.force_login(self.user)

        response = self.client.patch(
            "/api/v1/me/preferences",
            data=json.dumps(
                {
                    "username": "alice",
                    "email": "alice@example.com",
                    "daily_digest": True,
                    "theme": "system",
                    "time_zone": "Asia/Makassar",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.time_zone, "Asia/Makassar")
        self.assertEqual(self.user.compass_purpose, "")

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
