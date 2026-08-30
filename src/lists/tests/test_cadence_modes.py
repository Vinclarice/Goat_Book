"""Whether a repeating commitment is fixed to the calendar or to the last time.

`design-concept.md` specifies two recurrence modes and calls the distinction
load-bearing. Until now Clarice had one cadence field and could not say which a
commitment was, so August 15 fixed the overdue-successor defect by picking
anchored for everything — right for a mortgage, a few days early for a filter,
and wrong by months for anything annual done late.

**Anchored** — the calendar rule is the truth. The mortgage is due on the 1st
whether it was paid on the 1st, the 5th, or not at all last month.

**Floating** — the elapsed interval is the truth. A furnace filter lasts about a
month from when it was *changed*, not from when it was notionally due.

Anchored stays the default, and that asymmetry is deliberate: a mortgage
silently drifting off the 1st is a missed payment, while a filter changed six
days early is nothing at all. A person who never discovers this setting keeps
the safe behaviour.
"""

import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.test import TestCase

from accounts.models import User
from lists import services
from lists.models import CadenceMode, Item, List

COMPLETED_AT = datetime.datetime(2026, 8, 10, 14, 0, tzinfo=ZoneInfo("UTC"))


class CadenceModeTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("alice", "a@example.com", "pw")
        self.area = List.objects.create(owner=self.user, title="House")

    def spawn(self, *, due, cadence, mode=None, text="Change the furnace filter"):
        task = services.create_item(self.area, text, due_date=due)
        services.set_recurrence(task, cadence, cadence_mode=mode)
        with patch("django.utils.timezone.now", return_value=COMPLETED_AT):
            return services.complete_item(task)._spawned

    # -- floating -----------------------------------------------------------

    def test_a_floating_commitment_counts_from_when_it_was_actually_done(self):
        """The furnace filter, and `design-concept.md`'s own example: changed
        July 4, changed again August 10, so the next one is due a month after
        August 10 rather than a month after a date nobody acted on."""
        spawned = self.spawn(
            due=datetime.date(2026, 7, 4),
            cadence=Item.Recurrence.MONTHLY,
            mode=CadenceMode.FLOATING,
        )

        self.assertEqual(spawned.due_date, datetime.date(2026, 9, 10))

    def test_the_same_series_anchored_keeps_the_calendar_day(self):
        """Same inputs, other mode. This is the pair that shows the setting is
        doing something rather than being decoration."""
        spawned = self.spawn(
            due=datetime.date(2026, 7, 4),
            cadence=Item.Recurrence.MONTHLY,
            mode=CadenceMode.ANCHORED,
        )

        self.assertEqual(spawned.due_date, datetime.date(2026, 9, 4))

    def test_a_floating_weekly_commitment_runs_a_week_from_completion(self):
        spawned = self.spawn(
            due=datetime.date(2026, 6, 1),
            cadence=Item.Recurrence.WEEKLY,
            mode=CadenceMode.FLOATING,
        )

        self.assertEqual(spawned.due_date, datetime.date(2026, 8, 17))

    def test_floating_ignores_the_old_due_date_entirely(self):
        """Even a due date in the future does not pull the next one forward:
        floating means the clock restarts when the work is done."""
        spawned = self.spawn(
            due=datetime.date(2026, 12, 25),
            cadence=Item.Recurrence.DAILY,
            mode=CadenceMode.FLOATING,
        )

        self.assertEqual(spawned.due_date, datetime.date(2026, 8, 11))

    def test_a_floating_month_end_completion_clamps(self):
        with patch(
            "django.utils.timezone.now",
            return_value=datetime.datetime(2026, 1, 31, 9, 0, tzinfo=ZoneInfo("UTC")),
        ):
            task = services.create_item(self.area, "Pay the card")
            services.set_recurrence(
                task, Item.Recurrence.MONTHLY, cadence_mode=CadenceMode.FLOATING
            )
            spawned = services.complete_item(task)._spawned

        self.assertEqual(spawned.due_date, datetime.date(2026, 2, 28))

    # -- the default ---------------------------------------------------------

    def test_a_commitment_is_anchored_unless_somebody_says_otherwise(self):
        """The mortgage protection. Anyone who never finds this setting keeps
        the behaviour that cannot drift."""
        task = services.create_item(self.area, "Pay the mortgage",
                                    due_date=datetime.date(2026, 9, 1))

        repeating = services.set_recurrence(task, Item.Recurrence.MONTHLY)

        self.assertEqual(repeating.commitment.cadence_mode, CadenceMode.ANCHORED)

    def test_an_anchored_mortgage_paid_late_stays_on_the_first(self):
        spawned = self.spawn(
            due=datetime.date(2026, 8, 1),
            cadence=Item.Recurrence.MONTHLY,
            text="Pay the mortgage",
        )

        self.assertEqual(spawned.due_date.day, 1)

    # -- the setting itself --------------------------------------------------

    def test_the_mode_lives_on_the_series_not_the_occurrence(self):
        """A commitment's rule belongs to the commitment, the same way its
        cadence does. An occurrence is a snapshot of what ran, not the rule."""
        task = services.create_item(self.area, "Water the plants")
        services.set_recurrence(
            task, Item.Recurrence.DAILY, cadence_mode=CadenceMode.FLOATING
        )

        task.refresh_from_db()
        self.assertEqual(task.commitment.cadence_mode, CadenceMode.FLOATING)

    def test_the_mode_can_be_changed_afterwards(self):
        task = services.create_item(self.area, "Water the plants")
        services.set_recurrence(task, Item.Recurrence.DAILY)

        services.set_recurrence(
            task, Item.Recurrence.DAILY, cadence_mode=CadenceMode.FLOATING
        )

        task.refresh_from_db()
        self.assertEqual(task.commitment.cadence_mode, CadenceMode.FLOATING)

    def test_leaving_the_mode_unsaid_does_not_reset_it(self):
        """Editing a cadence must not silently drag the mode back to the
        default — that is how a setting somebody chose gets quietly undone."""
        task = services.create_item(self.area, "Water the plants")
        services.set_recurrence(
            task, Item.Recurrence.DAILY, cadence_mode=CadenceMode.FLOATING
        )

        services.set_recurrence(task, Item.Recurrence.WEEKLY)

        task.refresh_from_db()
        self.assertEqual(task.commitment.cadence_mode, CadenceMode.FLOATING)

    def test_an_invalid_mode_is_refused(self):
        task = services.create_item(self.area, "Water the plants")

        with self.assertRaises(services.TaskConflict):
            services.set_recurrence(task, Item.Recurrence.DAILY, cadence_mode="whenever")


class CadenceModeOverHttpTest(TestCase):
    """Reachable, not merely stored.

    A setting the domain honours and no surface can change is the same as no
    setting -- the knowledge core's detectors are the cautionary example, built
    and tested and switched off. So this exercises the round trip a person
    actually makes: read the task, change the mode, read it back.
    """

    def setUp(self):
        self.user = User.objects.create_user("alice", "a@example.com", "pw")
        self.client.force_login(self.user)
        self.area = List.objects.create(owner=self.user, title="House")
        self.task = services.create_item(self.area, "Change the furnace filter")
        services.set_recurrence(self.task, Item.Recurrence.MONTHLY)

    def test_the_detail_payload_reports_the_mode(self):
        response = self.client.get(f"/api/v1/tasks/{self.task.id}")

        self.assertEqual(response.json()["cadence_mode"], CadenceMode.ANCHORED)

    def test_a_task_that_does_not_repeat_reports_no_mode(self):
        """Null rather than a default, because "anchored" would assert a
        decision nobody made about a task with no schedule at all."""
        one_off = services.create_item(self.area, "Post the letter")

        response = self.client.get(f"/api/v1/tasks/{one_off.id}")

        self.assertIsNone(response.json()["cadence_mode"])

    def test_the_mode_can_be_changed_through_the_api(self):
        response = self.client.patch(
            f"/api/v1/tasks/{self.task.id}",
            data={"cadence_mode": CadenceMode.FLOATING},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.task.refresh_from_db()
        self.assertEqual(self.task.commitment.cadence_mode, CadenceMode.FLOATING)

    def test_an_invalid_mode_is_rejected_rather_than_stored(self):
        """422 rather than 400 since coherence-audit-2026-08-30.md F2 made
        `cadence_mode` a Literal -- see test_priority for the same move."""
        response = self.client.patch(
            f"/api/v1/tasks/{self.task.id}",
            data={"cadence_mode": "whenever"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 422)
        self.task.refresh_from_db()
        self.assertEqual(self.task.commitment.cadence_mode, CadenceMode.ANCHORED)
