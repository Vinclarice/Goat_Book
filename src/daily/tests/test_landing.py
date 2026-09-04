"""Crane 1 slice 6 — the Daily Page becomes the front door, and can be closed.

The default is the Daily Page: a fresh account lands there without being
asked, because the product should take a position about where a day starts.
The preference exists because the surface somebody opens every morning is a
poor place to be told they are wrong -- see crane-plan.md §6, answered
August 2, 2026.

`/dashboard/` is the one place that decides. It is `LOGIN_REDIRECT_URL`, so
making it read the preference means every path in -- the login form, a
bookmark, the Django shell's own "Today" link -- agrees without any of them
knowing the rule.
"""
from django.test import Client, TestCase

from accounts.models import User


PASSWORD = "correct horse battery staple 47!"


class LandingSurfaceTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", PASSWORD
        )
        self.client = Client()

    def test_a_new_account_defaults_to_the_daily_page(self):
        self.assertEqual(self.user.landing_surface, User.LandingSurface.DAY)

    def test_logging_in_lands_on_the_daily_page(self):
        """The first half of the acceptance condition."""
        response = self.client.post(
            "/accounts/login/",
            {"username": "alice", "password": PASSWORD},
            follow=True,
        )

        self.assertEqual(response.redirect_chain[-1][0], "/app/day")

    def test_a_stored_preference_for_the_agenda_still_lands_on_the_day(self):
        """~~"choosing the agenda makes the next login land there"~~ --
        **superlists-2.0-plan.md increment 8**, September 4, 2026: the Agenda
        retired into the day, which carries the head of the pool beside it.

        The stored value is deliberately *not* migrated away, so this is the
        case that matters: somebody who chose the Agenda months ago must land
        somewhere real rather than on a redirect to a redirect.
        """
        self.user.landing_surface = User.LandingSurface.AGENDA
        self.user.save(update_fields=["landing_surface"])

        response = self.client.post(
            "/accounts/login/",
            {"username": "alice", "password": PASSWORD},
            follow=True,
        )

        self.assertEqual(response.redirect_chain[-1][0], "/app/day")

    def test_the_agendas_address_still_resolves_rather_than_404ing(self):
        """~~"the agenda stays reachable whatever the preference says"~~. It is
        the SPA shell either way -- the client-side table is what redirects
        `/agenda` to `/day`, and `AppRoutes.test.tsx` holds that. What this
        holds is the half the server owns: the path is served, so a bookmark
        does not meet a 404 before the router ever runs.
        """
        self.client.force_login(self.user)

        response = self.client.get("/app/agenda")

        self.assertEqual(response.status_code, 200)

    def test_the_nav_payload_carries_the_preference(self):
        """So the SPA's own index route can agree with the server about
        where /app/ goes, rather than hard-coding a second answer."""
        self.client.force_login(self.user)

        body = self.client.get("/api/v1/nav").json()

        self.assertEqual(body["landing_surface"], "day")

    def test_signed_out_visitors_are_not_sent_anywhere_private(self):
        response = self.client.get("/dashboard/")

        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])
