"""A day written from the phone belongs to the same day as one written from a browser.

`TimeZoneMiddleware` activates the owner's zone from `request.user`, and on a
token request `request.user` is still anonymous when middleware runs — Ninja
resolves the bearer header later, inside the view. So every date-bearing token
endpoint computed its day in the *server's* zone.

The middleware's own docstring predicted this exactly: "a future date-bearing
token endpoint has to activate the owner's zone itself." Six such endpoints then
shipped across `daily` and `routines` and none of them did. `commercial-blueprint.md`
defect 2.

**This is a durable record being silently wrong, which `principles.md` says must
not happen.** A routine logged from Jakarta at 06:00 lands at 23:00 UTC the
previous day, so it counts toward yesterday's period — the streak breaks, the
day's entry appears under the wrong date, and nothing anywhere reports an error.
There is a real user in Indonesia; this is their records, not a hypothetical.

The fix belongs where the owner first becomes known on the token path, so that
both auth paths converge on one answer rather than six endpoints each
remembering. These tests exercise the endpoints rather than the seam, because
the seam is not what was broken — the promise to the endpoints was.
"""

from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.conf import settings
from django.test import TestCase
from django.utils import timezone

from accounts.models import PersonalAccessToken, User
from routines.models import Routine

# The same instant lists/tests/test_agenda_time_zones.py uses, and for the same
# reason: 23:30 UTC on August 1st is already the 2nd in Makassar (+8) and still
# the 1st in New York (-4). Two real users, twelve hours apart, on different
# dates at one moment.
SPLIT_MOMENT = datetime(2026, 8, 1, 23, 30, tzinfo=ZoneInfo("UTC"))

MAKASSAR_TODAY = "2026-08-02"
NEW_YORK_TODAY = "2026-08-01"


class TokenRequestUsesTheOwnersDayTest(TestCase):
    def setUp(self):
        self.obi = User.objects.create_user(
            username="obi",
            email="obi@example.com",
            password="correct horse battery staple",
            time_zone="Asia/Makassar",
        )
        self.edith = User.objects.create_user(
            username="edith",
            email="edith@example.com",
            password="correct horse battery staple",
            time_zone="America/New_York",
        )

    def bearer(self, user, scopes):
        _, raw = PersonalAccessToken.generate(user, scopes=scopes)
        return {"HTTP_AUTHORIZATION": f"Bearer {raw}"}

    def get_day(self, user):
        with patch("django.utils.timezone.now", return_value=SPLIT_MOMENT):
            return self.client.get(
                "/api/v1/day", **self.bearer(user, ["day:read"])
            ).json()

    def test_today_from_a_token_is_the_owners_today(self):
        self.assertEqual(self.get_day(self.obi)["today"], MAKASSAR_TODAY)
        self.assertEqual(self.get_day(self.edith)["today"], NEW_YORK_TODAY)

    def test_a_routine_logged_from_a_phone_counts_toward_the_owners_day(self):
        """The one that costs a streak. Logged at 07:30 Makassar time, which is
        23:30 UTC the day before — so without the owner's zone this occurrence
        is filed against August 1st, a period they had already finished."""
        routine = Routine.objects.create(owner=self.obi, title="Push-ups")

        with patch("django.utils.timezone.now", return_value=SPLIT_MOMENT):
            response = self.client.post(
                f"/api/v1/routines/{routine.id}/log",
                content_type="application/json",
                data={"amount": 1},
                **self.bearer(self.obi, ["routines:write"]),
            )

        self.assertEqual(response.status_code, 200, response.content)
        occurrence = routine.occurrences.get()
        self.assertEqual(str(occurrence.period_start), MAKASSAR_TODAY)

    def test_the_session_path_still_agrees(self):
        """A regression guard on the half that already worked. The fix must not
        move the answer for the browser, and a token and a cookie naming the
        same person at the same instant must not disagree about the date."""
        self.client.force_login(self.obi)
        with patch("django.utils.timezone.now", return_value=SPLIT_MOMENT):
            session_day = self.client.get("/api/v1/day").json()["today"]
        self.client.logout()

        self.assertEqual(session_day, self.get_day(self.obi)["today"])

    def test_one_users_zone_does_not_leak_into_the_next_request(self):
        """The thread-local hazard the middleware's `finally` exists for.

        Activating a zone mid-request means something must still deactivate it,
        and worker threads are reused — so a Makassar request followed by an
        unauthenticated one must not leave Makassar active for whoever that
        thread serves next.
        """
        self.get_day(self.obi)

        self.assertEqual(timezone.get_current_timezone_name(), settings.TIME_ZONE)
