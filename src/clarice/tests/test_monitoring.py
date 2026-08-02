"""Error monitoring: switched on in production, and deliberately off
everywhere else.

B4 exists because of a specific evening. A contact-form message was
discarded inside the mail provider while SMTP returned 200, Django recorded
a clean send, and the page told the visitor it was on its way. Every
mechanism this project owned reported success. Monitoring is the sense that
was missing — so the thing worth testing is not that Sentry works, which is
Sentry's job, but that Clarice turns it on under exactly the right
conditions and hands it enough metadata to be worth having.

See design/bittern-plan.md, B4.
"""
from django.conf import settings
from django.test import SimpleTestCase

from clarice.monitoring import initialise, sentry_initialiser


DSN = "https://examplekey@o0.ingest.sentry.io/1234567"


class InitialisationTest(SimpleTestCase):
    def setUp(self):
        self.calls = []

    def record(self, **kwargs):
        """Stands in for sentry_sdk.init, so no test ever opens a socket."""
        self.calls.append(kwargs)

    def start(self, **overrides):
        options = {
            "dsn": DSN,
            "environment": "production",
            "release": "abc1234",
            "initialiser": self.record,
        }
        return initialise(**{**options, **overrides})

    def test_no_dsn_means_no_monitoring(self):
        started = self.start(dsn="")

        self.assertFalse(started)
        self.assertEqual(self.calls, [])

    def test_a_dsn_outside_production_is_refused(self):
        # The one that matters for anyone working on this locally. A DSN
        # that leaks into a development environment would report a
        # developer's own broken experiments into the production project,
        # burying real incidents in noise from a laptop.
        started = self.start(environment="development")

        self.assertFalse(started)
        self.assertEqual(self.calls, [])

    def test_production_with_a_dsn_starts_exactly_once(self):
        started = self.start()

        self.assertTrue(started)
        self.assertEqual(len(self.calls), 1)

    def test_an_event_can_be_traced_back_to_a_deploy(self):
        # Without these an event says something broke, but not in which
        # release or on which environment -- which is most of the value.
        self.start(release="abc1234")

        self.assertEqual(self.calls[0]["release"], "abc1234")
        self.assertEqual(self.calls[0]["environment"], "production")

    def test_personal_data_is_not_sent(self):
        # principles.md: send the minimum data needed to support and
        # monitoring. Sentry attaches usernames, cookies and request bodies
        # when send_default_pii is on, which is a lot of somebody's private
        # task list leaving the server to answer "what broke".
        self.start()

        self.assertFalse(self.calls[0]["send_default_pii"])


class RealSdkTest(SimpleTestCase):
    """The injected initialiser above means no test touches the real SDK,
    which is what keeps them fast and offline -- and would also let a
    missing or misnamed dependency reach production unnoticed. This is the
    one place that resolves it for real.
    """

    def test_the_default_initialiser_is_the_installed_sdk(self):
        import sentry_sdk

        self.assertIs(sentry_initialiser(), sentry_sdk.init)


class TestEnvironmentTest(SimpleTestCase):
    def test_running_the_suite_does_not_enable_monitoring(self):
        # An acceptance criterion in its own right: tests must not send
        # events. Asserting on the resolved setting covers the wiring in
        # settings.py, not just the function it calls.
        self.assertFalse(settings.ERROR_MONITORING_ENABLED)
