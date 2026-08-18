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
        # monitoring. Sentry attaches usernames and cookies when this is on.
        # Request bodies it does *not* attach or withhold -- they have their
        # own option, and RequestBodiesStayOnTheServerTest below covers it.
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

    def test_the_installed_sdk_refuses_a_body_under_the_option_we_pass(self):
        """Asserting the kwarg proves we said something; this proves the SDK
        acts on it. `request_body_within_bounds` is the whole gate, and it
        reads `max_request_body_size` alone -- so this fails if a future SDK
        renames the option out from under us, which the kwarg test cannot.
        """
        from sentry_sdk.integrations._wsgi_common import request_body_within_bounds

        calls = []
        initialise(
            dsn=DSN,
            environment="production",
            release="abc1234",
            initialiser=lambda **kwargs: calls.append(kwargs),
        )

        class ClientWithOurOptions:
            options = {
                "max_request_body_size": calls[0]["max_request_body_size"]
            }

        # The length of a short captured thought, well inside the default
        # "medium" allowance of ten kilobytes.
        self.assertFalse(
            request_body_within_bounds(ClientWithOurOptions(), 200)
        )

    def test_the_sdks_own_scrubber_does_not_cover_query_strings(self):
        """Why a `before_send` is needed at all rather than a setting. The
        default `EventScrubber` reaches `headers`, `cookies` and `data` and
        stops -- so it would carry a shared passage through untouched."""
        from sentry_sdk.scrubber import EventScrubber

        event = {
            "request": {
                "query_string": "text=the+thing+I+cannot+say",
                "headers": {"Authorization": "Bearer secret"},
            }
        }
        EventScrubber().scrub_event(event)

        self.assertEqual(
            event["request"]["query_string"], "text=the+thing+I+cannot+say"
        )
        # The neighbour it *does* cover, so this test fails loudly if the
        # scrubber stops running rather than quietly asserting nothing. Checked
        # as "no longer the secret" rather than against a literal: the SDK
        # replaces the value with an AnnotatedValue, not the string.
        self.assertNotEqual(
            event["request"]["headers"]["Authorization"], "Bearer secret"
        )

    def test_the_sdk_default_would_have_sent_one(self):
        """Why the option is passed at all. Left alone, a capture-sized body
        is within bounds and goes."""
        from sentry_sdk.consts import DEFAULT_OPTIONS
        from sentry_sdk.integrations._wsgi_common import request_body_within_bounds

        class ClientWithSdkDefaults:
            options = {
                "max_request_body_size": DEFAULT_OPTIONS["max_request_body_size"]
            }

        self.assertTrue(
            request_body_within_bounds(ClientWithSdkDefaults(), 200)
        )


class RequestBodiesStayOnTheServerTest(InitialisationTest):
    """The same trap as defect 10, one option over, and the comments asserted
    the opposite of the truth again.

    `send_default_pii` gates **cookies** and nothing else —
    `_wsgi_common.py`'s `extract_into_event` sets `request_info["data"]`
    unconditionally, and the only thing standing between a request body and
    Sentry is `max_request_body_size`, which defaults to `"medium"`: bodies up
    to ten kilobytes are sent. A captured thought, a day's intentions and a
    task's notes are all far under that, so a 500 on `POST /api/v1/capture`,
    `POST /mind/` or `POST /api/v1/day` shipped the text itself to a third
    party.
    """

    def test_request_bodies_are_never_sent(self):
        self.start()

        self.assertEqual(self.calls[0]["max_request_body_size"], "never")

    def test_it_is_passed_explicitly_rather_than_left_to_the_default(self):
        """The default is "medium" and belongs to a dependency. Naming it is
        what makes the guarantee ours rather than whoever last released the
        SDK's."""
        self.assertIn("max_request_body_size", self.start() and self.calls[0])


class QueryStringsStayOnTheServerTest(InitialisationTest):
    """The third field in this family, and the one no option covers.

    `/mind/share/` takes the shared passage as `?text=`, because the PWA share
    target is declared `"method": "GET"` and that is what makes it work without
    a service worker. `/mind/search/` takes the query as `?q=`. So the note text
    is in the URL by design, and `wsgi.py` sets `request_info["query_string"]`
    unconditionally — `should_send_default_pii()` guards only the IP block above
    it. The default `EventScrubber` never touches `query_string` either; it
    reaches `headers`, `cookies` and `data` and stops.

    Unlike the request body there is no option for this, so it takes a
    `before_send`. Narrower than D3's in reach — no `traces_sample_rate` is set,
    so there are no transaction events and the query travels only when an event
    is captured during that request — and the same material.
    """

    def test_a_before_send_hook_is_installed(self):
        self.start()

        self.assertIsNotNone(self.calls[0]["before_send"])

    def test_it_removes_the_query_string_from_an_event(self):
        self.start()
        before_send = self.calls[0]["before_send"]

        event = before_send(
            {"request": {"query_string": "text=the+thing+I+cannot+say", "url": "https://x/mind/share/"}},
            {},
        )

        self.assertNotIn("query_string", event["request"])

    def test_it_leaves_the_rest_of_the_event_alone(self):
        """A scrubber that drops the URL or the method would take the event's
        usefulness with it. `get_request_url` already excludes the query, so
        the path is safe to keep and is most of what makes a 500 locatable."""
        self.start()
        before_send = self.calls[0]["before_send"]

        event = before_send(
            {
                "request": {
                    "query_string": "q=therapy+notes",
                    "url": "https://x/mind/search/",
                    "method": "GET",
                },
                "exception": {"values": []},
            },
            {},
        )

        self.assertEqual(event["request"]["url"], "https://x/mind/search/")
        self.assertEqual(event["request"]["method"], "GET")
        self.assertIn("exception", event)

    def test_an_event_with_no_request_survives(self):
        """Not every event comes from a request -- a management command raising
        has no `request` key at all, and a hook that assumed one would drop the
        event entirely by raising inside Sentry."""
        self.start()
        before_send = self.calls[0]["before_send"]

        event = before_send({"level": "error"}, {})

        self.assertEqual(event, {"level": "error"})


class TestEnvironmentTest(SimpleTestCase):
    def test_running_the_suite_does_not_enable_monitoring(self):
        # An acceptance criterion in its own right: tests must not send
        # events. Asserting on the resolved setting covers the wiring in
        # settings.py, not just the function it calls.
        self.assertFalse(settings.ERROR_MONITORING_ENABLED)


class PrivateTextStaysOnTheServerTest(InitialisationTest):
    """`commercial-blueprint.md` defect 10, and the comments asserted the
    opposite of the truth.

    `send_default_pii=False` withholds usernames and cookies. It says nothing
    about local variables, which are a separate option defaulting to **on** — so every stack frame in a 500 shipped its locals to
    a third party, and on a capture or daily-entry path those locals are
    `text`, `intentions` and `notes`. Somebody's unfiltered thinking, sent
    abroad to answer "what broke", by the code that documented itself as not
    doing that.
    """

    def test_local_variables_are_not_sent(self):
        self.start()

        self.assertIs(self.calls[0]["include_local_variables"], False)

    def test_it_is_passed_explicitly_rather_than_left_to_the_default(self):
        """The default is True and belongs to a dependency, so silence here is
        a decision made by whoever last released the SDK. Naming it is what
        makes the guarantee ours."""
        self.assertIn("include_local_variables", self.start() and self.calls[0])
