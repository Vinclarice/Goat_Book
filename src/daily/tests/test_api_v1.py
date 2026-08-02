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
from datetime import date

from django.test import Client, TestCase

from accounts.models import User
from daily import services


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
