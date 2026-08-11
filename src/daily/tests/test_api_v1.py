"""GET/PATCH /api/v1/day -- reading and writing one person's day.

Slice 1's acceptance condition lives here, because it is stated in terms of
a person and a page rather than a model: write an intention and a gratitude
line, reload, find both still there -- and a second user on the same
calendar date sees their own day, never the first user's.

The date in the path is the *owner's* local date. It is not parsed from
anything the server guesses: the client asks for a named day, and the
undated form answers with whatever "today" means in the requesting user's
own time zone.
"""
import json
from datetime import date, timedelta

from django.test import Client, TestCase
from django.utils import timezone

from accounts.models import (
    SCOPE_DAY_READ,
    SCOPE_DAY_WRITE,
    PersonalAccessToken,
    User,
)
from daily import services
from daily import services as daily_services
from daily.models import DailyFocus
from lists import services as list_services
from lists.models import List, Project


PASSWORD = "correct horse battery staple 47!"
AUGUST_3 = date(2026, 8, 3)
URL = "/api/v1/day/2026-08-03"


class DayEndpointTest(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(
            "alice", "alice@example.com", PASSWORD
        )
        self.bob = User.objects.create_user("bob", "bob@example.com", PASSWORD)
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.alice)
        response = self.client.get("/accounts/password/change/")
        self.csrf = response.cookies["csrftoken"].value

    def patch(self, payload, url=URL):
        return self.client.patch(
            url,
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=self.csrf,
        )

    def test_an_unwritten_day_reads_as_empty_rather_than_404(self):
        """A day nobody has written is a blank page, not a missing one."""
        response = self.client.get(URL)

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["date"], "2026-08-03")
        self.assertEqual(body["intentions"], "")
        self.assertEqual(body["gratitude"], "")
        self.assertEqual(body["happenings"], "")

    def test_writing_then_reloading_keeps_what_was_written(self):
        """Slice 1's stated acceptance condition, end to end."""
        written = self.patch(
            {"intentions": "Finish the slice", "gratitude": "Rain, finally"}
        )
        self.assertEqual(written.status_code, 200)

        reloaded = self.client.get(URL).json()

        self.assertEqual(reloaded["intentions"], "Finish the slice")
        self.assertEqual(reloaded["gratitude"], "Rain, finally")

    def test_a_partial_write_leaves_the_other_sections_alone(self):
        self.patch({"intentions": "Ship it", "gratitude": "Rain"})

        self.patch({"happenings": "Shipped"})

        reloaded = self.client.get(URL).json()
        self.assertEqual(reloaded["intentions"], "Ship it")
        self.assertEqual(reloaded["gratitude"], "Rain")
        self.assertEqual(reloaded["happenings"], "Shipped")

    def test_the_same_date_shows_each_person_their_own_day(self):
        """The other half of slice 1's acceptance, and the isolation test
        principles.md asks of every owner-scoped surface."""
        services.write_entry(self.bob, AUGUST_3, intentions="Bob's private day")

        body = self.client.get(URL).json()

        self.assertEqual(body["intentions"], "")

    def test_one_person_cannot_write_into_anothers_day(self):
        services.write_entry(self.bob, AUGUST_3, intentions="Bob's private day")

        self.patch({"intentions": "Alice was here"})

        from daily import reads

        self.assertEqual(
            reads.entry_for(self.bob, AUGUST_3).intentions, "Bob's private day"
        )
        self.assertEqual(
            reads.entry_for(self.alice, AUGUST_3).intentions, "Alice was here"
        )

    def test_the_undated_form_answers_with_the_owners_today(self):
        """So the client never has to decide what day it is."""
        response = self.client.get("/api/v1/day")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["date"], response.json()["today"])

    def test_every_response_carries_todays_date_for_navigation(self):
        body = self.client.get(URL).json()

        self.assertIn("today", body)
        # Not the requested date -- the point is that a page for the 3rd can
        # tell whether the 3rd is today without asking a second endpoint.
        self.assertNotEqual(body["today"], "")

    def test_signed_out_callers_get_nothing(self):
        self.client.logout()

        self.assertEqual(self.client.get(URL).status_code, 401)

    def test_a_nonsense_date_is_refused_rather_than_guessed(self):
        self.assertEqual(self.client.get("/api/v1/day/not-a-date").status_code, 422)


class DayFocusEndpointTest(TestCase):
    """Slice 4 over the wire: choosing work, and unchoosing it."""

    def setUp(self):
        self.alice = User.objects.create_user(
            "alice", "alice@example.com", PASSWORD
        )
        self.bob = User.objects.create_user("bob", "bob@example.com", PASSWORD)
        self.list_ = List.objects.create(owner=self.alice, title="Home")
        self.task = list_services.create_item(self.list_, "Pay rent")
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.alice)
        response = self.client.get("/accounts/password/change/")
        self.csrf = response.cookies["csrftoken"].value

    def day_url(self):
        return f"/api/v1/day/{timezone.localdate().isoformat()}"

    def pin(self, task):
        return self.client.post(
            f"{self.day_url()}/focus",
            data=json.dumps({"task_id": task.id}),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=self.csrf,
        )

    def unpin(self, task):
        return self.client.delete(
            f"{self.day_url()}/focus/{task.id}",
            HTTP_X_CSRFTOKEN=self.csrf,
        )

    def focus_texts(self):
        return [row["text"] for row in self.client.get(self.day_url()).json()["focus"]]

    def test_pinning_puts_the_task_on_the_day(self):
        self.assertEqual(self.pin(self.task).status_code, 200)

        self.assertEqual(self.focus_texts(), ["Pay rent"])

    def test_pinning_leaves_the_task_untouched(self):
        before = (self.task.due_date, self.task.status)

        self.pin(self.task)

        self.task.refresh_from_db()
        self.assertEqual((self.task.due_date, self.task.status), before)

    def test_unpinning_takes_it_off_but_keeps_the_record(self):
        self.pin(self.task)

        self.assertEqual(self.unpin(self.task).status_code, 200)

        self.assertEqual(self.focus_texts(), [])
        self.assertIsNotNone(DailyFocus.objects.get(task=self.task).released_at)

    def test_one_person_cannot_pin_anothers_task(self):
        bobs_list = List.objects.create(owner=self.bob, title="Bob's home")
        bobs_task = list_services.create_item(bobs_list, "Bob's private task")

        response = self.pin(bobs_task)

        self.assertIn(response.status_code, (403, 404))
        self.assertEqual(DailyFocus.objects.count(), 0)

    def test_one_person_cannot_unpin_anothers_pin(self):
        bobs_list = List.objects.create(owner=self.bob, title="Bob's home")
        bobs_task = list_services.create_item(bobs_list, "Bob's private task")
        daily_services.pin_task(self.bob, timezone.localdate(), bobs_task)

        self.unpin(bobs_task)

        self.assertIsNone(DailyFocus.objects.get(task=bobs_task).released_at)

    def test_the_focus_list_keeps_the_order_pins_were_made_in(self):
        second = list_services.create_item(self.list_, "Call the plumber")
        self.pin(self.task)
        self.pin(second)

        self.assertEqual(self.focus_texts(), ["Pay rent", "Call the plumber"])

    def test_a_focus_row_carries_what_it_needs_to_render(self):
        self.pin(self.task)

        row = self.client.get(self.day_url()).json()["focus"][0]

        for field in ("task_id", "text", "status", "due_date", "selected_at"):
            self.assertIn(field, row)

    def test_a_pinned_task_still_appears_in_the_broader_action_items(self):
        """The focus list sits above the agenda rather than carving it up --
        'the broader embedded Agenda output', in the vision document's words.
        Hiding a pinned task from it would make the two lists disagree about
        what is due."""
        task = list_services.create_item(
            self.list_, "Due today", due_date=timezone.localdate()
        )
        self.pin(task)

        body = self.client.get(self.day_url()).json()

        self.assertIn("Due today", [row["text"] for row in body["focus"]])
        self.assertIn("Due today", [row["text"] for row in body["action_items"]])


class DayActionItemsTest(TestCase):
    """Slice 2 over the wire: the day shows tasks it does not own."""

    def setUp(self):
        self.alice = User.objects.create_user(
            "alice", "alice@example.com", PASSWORD
        )
        self.bob = User.objects.create_user("bob", "bob@example.com", PASSWORD)
        self.list_ = List.objects.create(owner=self.alice, title="Home")
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.alice)

    def today(self):
        return timezone.localdate()

    def action_item_texts(self, url="/api/v1/day"):
        return [item["text"] for item in self.client.get(url).json()["action_items"]]

    def test_todays_work_appears_on_todays_page(self):
        list_services.create_item(self.list_, "Pay rent", due_date=self.today())

        self.assertEqual(self.action_item_texts(), ["Pay rent"])

    def test_completing_a_task_elsewhere_shows_on_the_next_load(self):
        """The acceptance condition, end to end and through the ordinary path."""
        task = list_services.create_item(
            self.list_, "Pay rent", due_date=self.today()
        )
        self.assertEqual(self.action_item_texts(), ["Pay rent"])

        list_services.complete_item(task)

        self.assertEqual(self.action_item_texts(), [])

    def test_another_persons_work_never_appears(self):
        bobs_list = List.objects.create(owner=self.bob, title="Bob's home")
        list_services.create_item(
            bobs_list, "Bob's private task", due_date=self.today()
        )

        self.assertEqual(self.action_item_texts(), [])

    def test_a_past_day_shows_no_action_items_rather_than_todays(self):
        """A task carries no history, so today's open work bucketed against
        a past date would assert something that was never true."""
        list_services.create_item(self.list_, "Pay rent", due_date=self.today())
        yesterday = (self.today() - timedelta(days=1)).isoformat()

        body = self.client.get(f"/api/v1/day/{yesterday}").json()

        self.assertEqual(body["action_items"], [])
        self.assertFalse(body["shows_action_items"])

    def test_todays_page_says_it_is_showing_action_items(self):
        body = self.client.get("/api/v1/day").json()

        self.assertTrue(body["shows_action_items"])

    def test_an_action_item_carries_what_a_task_row_needs_to_render(self):
        list_services.create_item(self.list_, "Pay rent", due_date=self.today())

        item = self.client.get("/api/v1/day").json()["action_items"][0]

        for field in ("id", "text", "status", "due_date", "area_id", "url"):
            self.assertIn(field, item)

    def test_carries_the_caller_s_areas_and_projects_so_a_row_can_show_them(self):
        """ui-second-pass-plan.md F2/the sitting's Daily Page finding: an
        action item already carried area_id and project_id (TaskOut), but
        the day had nothing for a row to join them against -- unlike the
        Agenda, which has always carried `areas`. This is that join, plus
        the same one for `projects` the Agenda just gained.
        """
        project = Project.objects.create(owner=self.alice, title="Kitchen remodel")
        Project.objects.create(owner=self.bob, title="Not mine")

        body = self.client.get("/api/v1/day").json()

        self.assertEqual(len(body["areas"]), 1)
        self.assertEqual(body["areas"][0]["title"], "Home")
        self.assertEqual(body["areas"][0]["url"], self.list_.get_absolute_url())
        self.assertEqual(len(body["projects"]), 1)
        self.assertEqual(body["projects"][0]["title"], "Kitchen remodel")
        self.assertEqual(body["projects"][0]["url"], f"/app/projects/{project.id}")


class DayEndpointTokenAuthTest(TestCase):
    """GET /api/v1/day and /api/v1/day/{day} accepting a Bearer token --
    android-full-client-plan.md slice 1, found blocked on a real device
    because this router used to be session-only by design. See
    token-scopes-plan.md for the scope this adds and why.

    Read-only: the router's write endpoints (focus, the day's own text)
    are untouched by this and stay session-only, covered by
    DayEndpointTest above.
    """

    def setUp(self):
        self.alice = User.objects.create_user(
            "alice", "alice@example.com", PASSWORD
        )
        self.client = Client(enforce_csrf_checks=True)

    def get(self, url, token=None):
        extra = {}
        if token is not None:
            extra["HTTP_AUTHORIZATION"] = f"Bearer {token}"
        return self.client.get(url, **extra)

    def test_a_token_with_day_read_reads_today(self):
        _, raw = PersonalAccessToken.generate(
            self.alice, scopes=[SCOPE_DAY_READ]
        )

        response = self.get("/api/v1/day", token=raw)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["date"], response.json()["today"])

    def test_a_token_with_day_read_reads_a_named_day(self):
        _, raw = PersonalAccessToken.generate(
            self.alice, scopes=[SCOPE_DAY_READ]
        )

        response = self.get(URL, token=raw)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["date"], "2026-08-03")

    def test_a_token_without_day_read_is_refused(self):
        # Valid, unexpired, wrong capability -- a capture-only token must
        # not also be able to read the Compass and journal text.
        _, capture_only = PersonalAccessToken.generate(
            self.alice, scopes=["capture:write"]
        )

        response = self.get("/api/v1/day", token=capture_only)

        self.assertEqual(response.status_code, 401)

    def test_no_credential_at_all_is_401(self):
        # Confirms the router no longer silently falls back to something
        # more permissive than session-or-scoped-token.
        response = self.get("/api/v1/day")

        self.assertEqual(response.status_code, 401)

    def test_one_users_token_never_reads_another_users_day(self):
        bob = User.objects.create_user("bob", "bob@example.com", PASSWORD)
        services.write_entry(bob, AUGUST_3, intentions="Bob's own plan")
        _, alices_raw = PersonalAccessToken.generate(
            self.alice, scopes=[SCOPE_DAY_READ]
        )

        response = self.get(URL, token=alices_raw)

        self.assertNotEqual(response.json()["intentions"], "Bob's own plan")

    def test_a_logged_in_session_still_works_unchanged(self):
        # Token auth is additive -- the SPA's own path must not have moved.
        self.client.force_login(self.alice)

        response = self.client.get("/api/v1/day")

        self.assertEqual(response.status_code, 200)


class DayWriteTokenAuthTest(TestCase):
    """POST/DELETE .../focus and PATCH /api/v1/day/{day} accepting a Bearer
    token -- android-full-client-plan.md's Daily-edit slice, day:write half.
    Same shape as DayEndpointTokenAuthTest's read-only tests.
    """

    def setUp(self):
        self.alice = User.objects.create_user(
            "alice", "alice@example.com", PASSWORD
        )
        self.list_ = List.objects.create(owner=self.alice, title="Home")
        self.task = list_services.create_item(self.list_, "Pay rent")
        self.client = Client(enforce_csrf_checks=True)

    def day_url(self):
        return f"/api/v1/day/{timezone.localdate().isoformat()}"

    def post(self, url, payload, token=None):
        extra = {}
        if token is not None:
            extra["HTTP_AUTHORIZATION"] = f"Bearer {token}"
        return self.client.post(
            url, data=json.dumps(payload), content_type="application/json", **extra
        )

    def test_a_token_with_day_write_pins_a_task_with_no_csrf_token_sent(self):
        _, raw = PersonalAccessToken.generate(self.alice, scopes=[SCOPE_DAY_WRITE])

        response = self.post(f"{self.day_url()}/focus", {"task_id": self.task.id}, token=raw)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["focus"][0]["text"], "Pay rent")

    def test_a_token_with_day_write_unpins_a_task(self):
        _, raw = PersonalAccessToken.generate(self.alice, scopes=[SCOPE_DAY_WRITE])
        self.post(f"{self.day_url()}/focus", {"task_id": self.task.id}, token=raw)

        response = self.client.delete(
            f"{self.day_url()}/focus/{self.task.id}",
            HTTP_AUTHORIZATION=f"Bearer {raw}",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["focus"], [])

    def test_a_token_with_day_write_saves_the_days_own_text(self):
        _, raw = PersonalAccessToken.generate(self.alice, scopes=[SCOPE_DAY_WRITE])

        response = self.client.patch(
            self.day_url(),
            data=json.dumps({"intentions": "Ship the slice"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {raw}",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["intentions"], "Ship the slice")

    def test_a_token_without_day_write_cannot_pin(self):
        _, raw = PersonalAccessToken.generate(self.alice, scopes=[SCOPE_DAY_READ])

        response = self.post(f"{self.day_url()}/focus", {"task_id": self.task.id}, token=raw)

        self.assertEqual(response.status_code, 401)

    def test_a_token_without_day_write_cannot_edit_the_days_text(self):
        _, raw = PersonalAccessToken.generate(self.alice, scopes=[SCOPE_DAY_READ])

        response = self.client.patch(
            self.day_url(),
            data=json.dumps({"intentions": "Forged"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {raw}",
        )

        self.assertEqual(response.status_code, 401)

    def test_a_token_cannot_pin_someone_elses_task(self):
        bob = User.objects.create_user("bob", "bob@example.com", PASSWORD)
        _, raw = PersonalAccessToken.generate(bob, scopes=[SCOPE_DAY_WRITE])

        response = self.post(f"{self.day_url()}/focus", {"task_id": self.task.id}, token=raw)

        self.assertEqual(response.status_code, 404)

    def test_a_logged_in_session_can_still_pin_without_a_token(self):
        self.client.force_login(self.alice)
        csrf = self.client.get("/accounts/password/change/").cookies["csrftoken"].value

        response = self.client.post(
            f"{self.day_url()}/focus",
            data=json.dumps({"task_id": self.task.id}),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=csrf,
        )

        self.assertEqual(response.status_code, 200)
