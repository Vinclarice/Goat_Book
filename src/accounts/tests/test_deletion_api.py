"""The endpoints behind the Preferences danger zone.

Session-authenticated and CSRF-checked like the rest of the router. Three
things here are decisions rather than plumbing, and each has a test:

* **Requesting deletion needs the password again.** Everything else on this
  router is recoverable; this is the one action that ends in data nobody can get
  back, and an open session on a shared machine should not be enough to start it.
* **Cancelling does not.** Undoing a destructive thing must never be harder than
  starting it.
* **Export is session-only.** A `capture:write` token on a phone must not be
  able to walk off with the whole account, and there is no scope that would
  sensibly mean "all of it".
"""

import json
import zipfile
from io import BytesIO

from django.test import Client, TestCase
from django.utils import timezone

from accounts import services
from accounts.models import (
    ANDROID_DEFAULT_SCOPES,
    SCOPE_CAPTURE_WRITE,
    PersonalAccessToken,
    User,
)

PASSWORD = "correct horse battery staple 47!"


def _instant(rendered):
    """A wire datetime back into one that can be compared, to the second.

    Two things differ between what Ninja writes and what `purge_at` returns, and
    neither is a defect. It writes `Z` where `isoformat()` writes `+00:00`, and
    it truncates to milliseconds. Comparing the strings would be asserting
    Ninja's encoder; comparing microseconds would be asserting its precision.
    A date thirty days out is the same date either way.
    """
    from datetime import datetime

    return datetime.fromisoformat(rendered.replace("Z", "+00:00")).replace(
        microsecond=0
    )


class DeletionEndpointTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("alice", "alice@example.com", PASSWORD)
        self.client.force_login(self.user)

    def post(self, url, payload=None):
        return self.client.post(
            url, data=json.dumps(payload or {}), content_type="application/json"
        )

    def test_the_right_password_schedules_it(self):
        response = self.post("/api/v1/me/delete", {"password": PASSWORD})

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.deletion_requested_at)

    def test_it_answers_with_the_date_the_data_goes(self):
        """The one number somebody needs from this screen.

        Compared as instants rather than as strings: Ninja emits `...Z` at
        millisecond precision and `isoformat()` gives `+00:00` with
        microseconds, which are the same moment written two ways. Asserting the
        string would be asserting Ninja's encoder, not this endpoint.
        """
        body = self.post("/api/v1/me/delete", {"password": PASSWORD}).json()

        self.user.refresh_from_db()
        self.assertEqual(
            _instant(body["purge_at"]), services.purge_at(self.user).replace(microsecond=0)
        )

    def test_the_wrong_password_changes_nothing(self):
        response = self.post("/api/v1/me/delete", {"password": "not it"})

        self.assertEqual(response.status_code, 400)
        self.user.refresh_from_db()
        self.assertIsNone(self.user.deletion_requested_at)

    def test_a_wrong_password_here_does_not_count_towards_a_lockout(self):
        """`check_password`, not `authenticate`. Routing this through the auth
        stack would let a typo on the leaving form lock somebody out of the
        account they are trying to leave."""
        from axes.models import AccessAttempt

        for _ in range(6):
            self.post("/api/v1/me/delete", {"password": "not it"})

        self.assertFalse(AccessAttempt.objects.filter(username="alice").exists())

    def test_cancelling_needs_no_password(self):
        self.post("/api/v1/me/delete", {"password": PASSWORD})

        response = self.post("/api/v1/me/delete/cancel")

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertIsNone(self.user.deletion_requested_at)
        self.assertIsNone(response.json()["purge_at"])

    def test_an_anonymous_caller_cannot_schedule_anybody(self):
        response = Client().post(
            "/api/v1/me/delete",
            data=json.dumps({"password": PASSWORD}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 401)
        self.user.refresh_from_db()
        self.assertIsNone(self.user.deletion_requested_at)

    def test_the_nav_carries_the_purge_date_so_the_banner_is_everywhere(self):
        self.post("/api/v1/me/delete", {"password": PASSWORD})

        body = self.client.get("/api/v1/nav").json()

        self.user.refresh_from_db()
        self.assertEqual(
            _instant(body["deletion_purge_at"]), services.purge_at(self.user).replace(microsecond=0)
        )

    def test_the_nav_says_nothing_when_nobody_is_leaving(self):
        self.assertIsNone(self.client.get("/api/v1/nav").json()["deletion_purge_at"])


class ExportEndpointTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("alice", "alice@example.com", PASSWORD)

    def test_it_serves_a_named_zip(self):
        self.client.force_login(self.user)

        response = self.client.get("/api/v1/me/export")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/zip")
        self.assertIn("clarice-alice-", response["Content-Disposition"])
        self.assertIn("attachment", response["Content-Disposition"])

    def test_the_zip_opens_and_holds_the_account(self):
        self.client.force_login(self.user)

        response = self.client.get("/api/v1/me/export")

        archive = zipfile.ZipFile(BytesIO(response.getvalue()))
        data = json.loads(archive.read("clarice.json"))
        self.assertEqual(data["account"]["username"], "alice")

    def test_a_scoped_token_cannot_take_the_whole_account(self):
        """The one that matters. Every Android token carries broad scopes; none
        of them means "export everything", and this endpoint must not treat any
        of them as though it did."""
        _, raw = PersonalAccessToken.generate(
            self.user, scopes=ANDROID_DEFAULT_SCOPES
        )

        response = Client().get(
            "/api/v1/me/export", HTTP_AUTHORIZATION=f"Bearer {raw}"
        )

        self.assertEqual(response.status_code, 401)

    def test_an_anonymous_caller_gets_nothing(self):
        response = Client().get("/api/v1/me/export")

        self.assertEqual(response.status_code, 401)
