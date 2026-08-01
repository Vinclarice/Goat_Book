"""The per-user time zone field and the middleware that applies it.

Bucketing and digest behaviour are tested where they live (lists); this
covers the storage and activation layer they both rely on.
"""
from datetime import date
from zoneinfo import ZoneInfo

from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase
from django.utils import timezone

from accounts.middleware import TimeZoneMiddleware
from accounts.models import DEFAULT_TIME_ZONE, User, known_time_zones


def make_user(username="edith", **extra):
    return User.objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password="correct horse battery staple",
        **extra,
    )


class TimeZoneFieldTest(TestCase):
    def test_defaults_to_the_zone_everyone_had_before_the_field_existed(self):
        # The point of the default: adding the field changes nobody's day.
        self.assertEqual(make_user().time_zone, DEFAULT_TIME_ZONE)

    def test_accepts_a_real_iana_key(self):
        user = make_user(time_zone="Asia/Makassar")
        user.full_clean()

        user.refresh_from_db()
        self.assertEqual(user.time_zone, "Asia/Makassar")

    def test_rejects_a_key_the_server_cannot_resolve(self):
        user = make_user(time_zone="Mars/Olympus_Mons")

        with self.assertRaises(ValidationError) as caught:
            user.full_clean()

        self.assertIn("time_zone", caught.exception.error_dict)

    def test_known_zones_include_both_ends_of_the_current_spread(self):
        zones = known_time_zones()

        self.assertIn("America/New_York", zones)
        self.assertIn("Asia/Makassar", zones)
        self.assertEqual(list(zones), sorted(zones))

    def test_last_digest_date_starts_empty(self):
        # Null means "never sent", which is what lets the first hourly run
        # after deploy send rather than assume the day is handled.
        self.assertIsNone(make_user().last_digest_date)

    def test_last_digest_date_round_trips(self):
        user = make_user()
        user.last_digest_date = date(2026, 8, 1)
        user.save(update_fields=["last_digest_date"])

        user.refresh_from_db()
        self.assertEqual(user.last_digest_date, date(2026, 8, 1))


class TimeZoneMiddlewareTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def activated_during(self, request):
        """The zone that was active while the view ran."""
        seen = {}

        def view(_):
            seen["zone"] = timezone.get_current_timezone()
            return "response"

        TimeZoneMiddleware(view)(request)
        return seen["zone"]

    def test_activates_the_authenticated_users_zone(self):
        request = self.factory.get("/app/agenda")
        request.user = make_user(time_zone="Asia/Makassar")

        self.assertEqual(self.activated_during(request), ZoneInfo("Asia/Makassar"))

    def test_two_users_get_their_own_zones(self):
        makassar = self.factory.get("/app/agenda")
        makassar.user = make_user("obi", time_zone="Asia/Makassar")
        new_york = self.factory.get("/app/agenda")
        new_york.user = make_user("edith", time_zone="America/New_York")

        self.assertEqual(self.activated_during(makassar), ZoneInfo("Asia/Makassar"))
        self.assertEqual(self.activated_during(new_york), ZoneInfo("America/New_York"))

    def test_anonymous_request_falls_back_to_the_project_default(self):
        request = self.factory.get("/")
        request.user = None

        self.assertEqual(
            self.activated_during(request), ZoneInfo(DEFAULT_TIME_ZONE)
        )

    def test_unresolvable_stored_zone_falls_back_instead_of_erroring(self):
        # tzdata can retire a zone. That must not 500 the person holding it.
        request = self.factory.get("/app/agenda")
        request.user = make_user(time_zone="Mars/Olympus_Mons")

        self.assertEqual(
            self.activated_during(request), ZoneInfo(DEFAULT_TIME_ZONE)
        )

    def test_zone_does_not_leak_into_the_next_request_on_the_same_thread(self):
        # activate() sets a thread-local and worker threads are reused, so
        # without the middleware's finally this is how one user's day would
        # silently become another's.
        request = self.factory.get("/app/agenda")
        request.user = make_user(time_zone="Asia/Makassar")

        self.activated_during(request)

        self.assertEqual(timezone.get_current_timezone(), ZoneInfo(DEFAULT_TIME_ZONE))

    def test_zone_is_released_even_when_the_view_raises(self):
        request = self.factory.get("/app/agenda")
        request.user = make_user(time_zone="Asia/Makassar")

        def exploding_view(_):
            raise RuntimeError("boom")

        with self.assertRaises(RuntimeError):
            TimeZoneMiddleware(exploding_view)(request)

        self.assertEqual(timezone.get_current_timezone(), ZoneInfo(DEFAULT_TIME_ZONE))
