"""Choosing a time zone: the API, the form, and the admin.

The storage and activation layer is covered in test_time_zones.py; this is
about how a person actually changes the setting.
"""
import json

from django.test import TestCase

from accounts.forms import AccountSettingsForm
from clarice.testing import sign_into_the_admin
from accounts.models import DEFAULT_TIME_ZONE, User


PASSWORD = "correct horse battery staple 47!"


class TimeZonePreferenceApiTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", PASSWORD
        )
        sign_into_the_admin(self.client, self.user)

    def patch(self, **overrides):
        payload = {
            "username": "alice",
            "email": "alice@example.com",
            "daily_digest": True,
            "theme": "system",
            "time_zone": "Asia/Makassar",
        }
        payload.update(overrides)
        return self.client.patch(
            "/api/v1/me/preferences",
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_preferences_report_the_current_zone(self):
        response = self.client.get("/api/v1/me/preferences")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["time_zone"], DEFAULT_TIME_ZONE)

    def test_a_zone_can_be_chosen(self):
        response = self.patch()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["time_zone"], "Asia/Makassar")
        self.user.refresh_from_db()
        self.assertEqual(self.user.time_zone, "Asia/Makassar")

    def test_an_unknown_zone_is_refused_and_changes_nothing(self):
        response = self.patch(time_zone="Mars/Olympus_Mons")

        self.assertEqual(response.status_code, 400)
        self.user.refresh_from_db()
        self.assertEqual(self.user.time_zone, DEFAULT_TIME_ZONE)

    def test_an_empty_zone_is_refused(self):
        response = self.patch(time_zone="")

        self.assertEqual(response.status_code, 400)

    def test_changing_another_preference_leaves_the_zone_alone(self):
        self.patch()

        self.patch(daily_digest=False, time_zone="Asia/Makassar")

        self.user.refresh_from_db()
        self.assertEqual(self.user.time_zone, "Asia/Makassar")
        self.assertFalse(self.user.daily_digest)


class TimeZoneOptionsApiTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", PASSWORD
        )

    def test_offers_the_zones_the_server_will_accept(self):
        # Served rather than built in the browser: Intl's list and the
        # server's tzdata can disagree, and the disagreement would surface
        # as a validation error on a zone the picker offered.
        sign_into_the_admin(self.client, self.user)

        response = self.client.get("/api/v1/time-zones")

        self.assertEqual(response.status_code, 200)
        zones = response.json()["time_zones"]
        self.assertIn("America/New_York", zones)
        self.assertIn("Asia/Makassar", zones)
        self.assertEqual(zones, sorted(zones))

    def test_rejects_anonymous_requests(self):
        response = self.client.get("/api/v1/time-zones")

        self.assertEqual(response.status_code, 401)


class AccountSettingsFormTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", PASSWORD
        )

    def build(self, time_zone):
        return AccountSettingsForm(
            data={
                "username": "alice",
                "email": "alice@example.com",
                "daily_digest": True,
                "time_zone": time_zone,
            },
            instance=self.user,
        )

    def test_accepts_a_real_zone(self):
        form = self.build("Asia/Makassar")

        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.user.refresh_from_db()
        self.assertEqual(self.user.time_zone, "Asia/Makassar")

    def test_refuses_an_unknown_zone(self):
        form = self.build("Mars/Olympus_Mons")

        self.assertFalse(form.is_valid())
        self.assertIn("time_zone", form.errors)


class TimeZoneInAdminTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            "admin", "admin@example.com", PASSWORD
        )
        sign_into_the_admin(self.client, self.admin)

    def test_the_change_form_exposes_the_zone(self):
        # UserAdmin declares explicit fieldsets, so a new field is invisible
        # here until it is named in one.
        edith = User.objects.create_user(
            "edith", "edith@example.com", PASSWORD, time_zone="Asia/Makassar"
        )

        response = self.client.get(f"/admin/accounts/user/{edith.pk}/change/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "time_zone")
        self.assertContains(response, "Asia/Makassar")
