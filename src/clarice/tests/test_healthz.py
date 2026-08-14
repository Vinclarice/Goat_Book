"""The endpoint that lets something notice the site is down.

Sentry reports errors from a *running* application, so a dead container, a dead
host, an expired certificate or a hung gunicorn produce zero events -- which is
indistinguishable from a quiet night. `commercial-blueprint.md` defect 9. The
external monitor is the other half and cannot be tested here; this is the thing
it polls.

**It checks the database, not just that Python is running.** A liveness check
that always returns 200 answers "did gunicorn accept a socket", and gunicorn
accepting sockets while every request 500s on a dead connection pool is a real
and unremarkable way to be down. The monitor is only as good as the weakest
thing this endpoint is willing to notice.

**It says almost nothing.** No version, no hostname, no database name, no
exception text. This is the one URL on the site that answers anybody, forever,
and a health endpoint that reports its own internals is free reconnaissance --
including, on a bad day, a connection string in an error message.
"""

from unittest.mock import patch

from django.db import OperationalError
from django.test import TestCase
from django.urls import reverse


class HealthCheckTest(TestCase):
    def test_it_answers_without_a_login(self):
        """The whole point. A monitor has no account, and an endpoint that
        redirected to a login would report a healthy 302 forever."""
        response = self.client.get("/healthz")

        self.assertEqual(response.status_code, 200)

    def test_it_is_reachable_at_the_documented_path(self):
        self.assertEqual(reverse("healthz"), "/healthz")

    def test_a_healthy_site_says_so_in_one_word(self):
        response = self.client.get("/healthz")

        self.assertEqual(response.content, b"ok")
        self.assertEqual(response["Content-Type"], "text/plain")

    def test_a_broken_database_is_reported_as_down(self):
        """Not 200-with-a-sad-message. A monitor reads the status code, and
        anything in the 200s is "fine" to every uptime service there is."""
        with patch("clarice.health.database_reachable", return_value=False):
            response = self.client.get("/healthz")

        self.assertEqual(response.status_code, 503)

    def test_it_does_not_say_what_broke(self):
        with patch("clarice.health.database_reachable", return_value=False):
            response = self.client.get("/healthz")

        self.assertEqual(response.content, b"unhealthy")

    def test_it_is_never_cached(self):
        """A cached health check is a health check that reports the last good
        minute forever -- and nginx, a CDN or the monitor's own client are all
        entitled to cache a plain 200 without being asked not to."""
        response = self.client.get("/healthz")

        self.assertIn("no-store", response["Cache-Control"])

    def test_only_GET_and_HEAD_are_allowed(self):
        """HEAD because several uptime services default to it, and a 405 there
        would read as an outage on a working site."""
        self.assertEqual(self.client.head("/healthz").status_code, 200)
        self.assertEqual(self.client.post("/healthz").status_code, 405)


class DatabaseReachableTest(TestCase):
    """The check itself, separately from the view that reports it."""

    def test_a_working_database_is_reachable(self):
        from clarice.health import database_reachable

        self.assertIs(database_reachable(), True)

    def test_a_refused_connection_is_not_an_exception_to_the_caller(self):
        """It returns False rather than raising, so the view has one job and a
        500 from the health check itself becomes impossible -- an endpoint that
        can 500 while reporting health is reporting its own bug as an outage.
        """
        from clarice import health

        with patch.object(
            health.connection, "ensure_connection", side_effect=OperationalError("no")
        ):
            self.assertIs(health.database_reachable(), False)
