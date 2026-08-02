"""The routines slice of /api/v1/ — keeping one, and logging against it.

Standings rather than occurrences over the wire. A period nobody has logged
has no row, so an endpoint that returned occurrences would either say
nothing about a routine at 0 of 5 or would have to create a row to describe
one — and a GET that writes is how a page view starts inventing history.
"""
import json

from django.test import Client, TestCase
from django.utils import timezone

from accounts.models import User
from routines import services
from routines.models import Routine, RoutineOccurrence


PASSWORD = "correct horse battery staple 47!"


class RoutineEndpointTest(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(
            "alice", "alice@example.com", PASSWORD
        )
        self.bob = User.objects.create_user("bob", "bob@example.com", PASSWORD)
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.alice)
        response = self.client.get("/accounts/password/change/")
        self.csrf = response.cookies["csrftoken"].value

    def post(self, url, payload):
        return self.client.post(
            url,
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=self.csrf,
        )

    def standings(self):
        return self.client.get("/api/v1/routines").json()["standings"]

    def test_keeping_a_routine(self):
        response = self.post(
            "/api/v1/routines",
            {
                "title": "Practice Spanish",
                "cadence": "daily",
                "target_quantity": 5,
                "unit": "lessons",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [(each["title"], each["progress"], each["target"]) for each in self.standings()],
            [("Practice Spanish", 0, 5)],
        )

    def test_an_unlogged_routine_describes_itself_without_writing_a_row(self):
        """A GET must not create history."""
        services.create_routine(
            self.alice, title="Practice Spanish", target_quantity=5
        )

        self.standings()

        self.assertEqual(RoutineOccurrence.objects.count(), 0)

    def test_logging_progress_moves_the_count(self):
        routine = services.create_routine(
            self.alice, title="Practice Spanish", target_quantity=5
        )

        self.post(f"/api/v1/routines/{routine.id}/log", {"amount": 2})

        standing = self.standings()[0]
        self.assertEqual(standing["progress"], 2)
        self.assertEqual(standing["outcome"], "open")

    def test_reaching_the_target_completes_the_period(self):
        routine = services.create_routine(
            self.alice, title="Move today", target_quantity=1
        )

        self.post(f"/api/v1/routines/{routine.id}/log", {"amount": 1})

        self.assertEqual(self.standings()[0]["outcome"], "completed")

    def test_logging_defaults_to_one(self):
        routine = services.create_routine(
            self.alice, title="Practice Spanish", target_quantity=5
        )

        self.post(f"/api/v1/routines/{routine.id}/log", {})

        self.assertEqual(self.standings()[0]["progress"], 1)

    def test_one_person_cannot_log_against_anothers_routine(self):
        bobs = services.create_routine(self.bob, title="Bob's practice")

        response = self.post(f"/api/v1/routines/{bobs.id}/log", {"amount": 1})

        self.assertIn(response.status_code, (403, 404))
        self.assertEqual(RoutineOccurrence.objects.count(), 0)

    def test_one_person_never_sees_anothers_routines(self):
        services.create_routine(self.bob, title="Bob's practice")

        self.assertEqual(self.standings(), [])

    def test_the_standings_are_for_the_owners_own_today(self):
        """The clock is read at the boundary, in the requesting user's zone."""
        routine = services.create_routine(self.alice, title="Practice Spanish")
        services.log_progress(self.alice, routine, timezone.localdate())

        self.assertEqual(self.standings()[0]["progress"], 1)

    def test_a_weekly_routine_reports_its_period(self):
        services.create_routine(
            self.alice,
            title="Guitar practice",
            cadence=Routine.Cadence.WEEKLY,
            target_quantity=3,
        )

        standing = self.standings()[0]

        self.assertEqual(standing["cadence"], "weekly")
        self.assertIn("period_start", standing)

    def test_signed_out_callers_get_nothing(self):
        self.client.logout()

        self.assertEqual(self.client.get("/api/v1/routines").status_code, 401)

    def test_pausing_takes_it_off_the_standings_and_lists_it_as_paused(self):
        routine = services.create_routine(
            self.alice, title="Practice Spanish", target_quantity=5
        )

        response = self.post(f"/api/v1/routines/{routine.id}/pause", {})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["standings"], [])
        self.assertEqual(
            [each["title"] for each in response.json()["paused"]],
            ["Practice Spanish"],
        )

    def test_a_paused_routine_refuses_to_be_logged(self):
        routine = services.create_routine(
            self.alice, title="Practice Spanish", target_quantity=5
        )
        self.post(f"/api/v1/routines/{routine.id}/pause", {})

        response = self.post(f"/api/v1/routines/{routine.id}/log", {"amount": 1})

        self.assertEqual(response.status_code, 409)
        self.assertEqual(RoutineOccurrence.objects.count(), 0)

    def test_resuming_brings_it_back_without_backfilling(self):
        routine = services.create_routine(
            self.alice, title="Practice Spanish", target_quantity=5
        )
        self.post(f"/api/v1/routines/{routine.id}/log", {"amount": 5})
        self.post(f"/api/v1/routines/{routine.id}/pause", {})

        response = self.post(f"/api/v1/routines/{routine.id}/resume", {})

        self.assertEqual(
            [each["title"] for each in response.json()["standings"]],
            ["Practice Spanish"],
        )
        self.assertEqual(response.json()["paused"], [])
        self.assertEqual(RoutineOccurrence.objects.count(), 1)

    def test_one_person_cannot_pause_anothers_routine(self):
        bobs = services.create_routine(self.bob, title="Bob's practice")

        response = self.post(f"/api/v1/routines/{bobs.id}/pause", {})

        self.assertIn(response.status_code, (403, 404))
        bobs.refresh_from_db()
        self.assertTrue(bobs.is_active)

    def test_correcting_down_reopens_a_completed_period(self):
        routine = services.create_routine(
            self.alice, title="Practice Spanish", target_quantity=5
        )
        self.post(f"/api/v1/routines/{routine.id}/log", {"amount": 5})

        self.post(f"/api/v1/routines/{routine.id}/log", {"amount": -1})

        standing = self.standings()[0]
        self.assertEqual(standing["progress"], 4)
        self.assertEqual(standing["outcome"], "open")

    def test_correcting_a_period_nobody_logged_writes_nothing(self):
        routine = services.create_routine(
            self.alice, title="Practice Spanish", target_quantity=5
        )

        response = self.post(f"/api/v1/routines/{routine.id}/log", {"amount": -1})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(RoutineOccurrence.objects.count(), 0)
        self.assertEqual(self.standings()[0]["progress"], 0)

    def test_skipping_a_period(self):
        routine = services.create_routine(
            self.alice, title="Practice Spanish", target_quantity=5
        )

        response = self.post(f"/api/v1/routines/{routine.id}/skip", {})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.standings()[0]["outcome"], "skipped")

    def test_a_skip_reads_differently_from_a_period_left_alone(self):
        skipped = services.create_routine(
            self.alice, title="Practice Spanish", target_quantity=5
        )
        services.create_routine(
            self.alice, title="Move today", target_quantity=1
        )

        self.post(f"/api/v1/routines/{skipped.id}/skip", {})

        outcomes = {each["title"]: each["outcome"] for each in self.standings()}
        self.assertEqual(outcomes["Practice Spanish"], "skipped")
        self.assertEqual(outcomes["Move today"], "open")

    def test_one_person_cannot_skip_anothers_routine(self):
        bobs = services.create_routine(self.bob, title="Bob's practice")

        response = self.post(f"/api/v1/routines/{bobs.id}/skip", {})

        self.assertIn(response.status_code, (403, 404))
        self.assertEqual(RoutineOccurrence.objects.count(), 0)

    def test_calling_a_period_enough(self):
        """Crane 3 slice 8. Its own route rather than a flag on the log,
        for the same reason skipping got one: logging says what happened,
        and this says what was decided about it."""
        routine = services.create_routine(
            self.alice, title="Practice Spanish", target_quantity=5, unit="lessons"
        )
        self.post(f"/api/v1/routines/{routine.id}/log", {"amount": 3})

        response = self.post(f"/api/v1/routines/{routine.id}/enough", {})

        self.assertEqual(response.status_code, 200)
        [standing] = self.standings()
        self.assertEqual(standing["outcome"], "partial")
        self.assertEqual(standing["progress"], 3)
        # Never a met target, which is the rule crane-plan.md §8 settles
        # along with the outcome itself.
        self.assertFalse(standing["is_met"])

    def test_calling_an_untouched_period_enough_is_refused(self):
        routine = services.create_routine(
            self.alice, title="Practice Spanish", target_quantity=5
        )

        response = self.post(f"/api/v1/routines/{routine.id}/enough", {})

        # 409 rather than 400: the request is well formed and the routine is
        # real, it is the state that refuses -- the same call the log
        # endpoint makes for a paused routine.
        self.assertEqual(response.status_code, 409)
        self.assertEqual(RoutineOccurrence.objects.count(), 0)

    def test_one_person_cannot_close_anothers_period(self):
        bobs = services.create_routine(self.bob, title="Bob's practice")

        response = self.post(f"/api/v1/routines/{bobs.id}/enough", {})

        self.assertIn(response.status_code, (403, 404))
