"""Sending over Resend's HTTP API, because SMTP cannot leave this droplet.

`design/mail-transport-plan.md` §1: DigitalOcean drops outbound 25, 465 and 587
on every Droplet, measured from production on August 18. Ordinary outbound is
fine, and an unauthenticated POST to Resend's API returns 401 from that same
host — the request arrives, and is refused only for credentials.

So the transport moves to HTTPS and every caller stays put. Four
`EmailMessage(...).send()`, two `mail_admins()`, one `send_mail()` and Django's
own `PasswordResetView` all go through the configured backend, which is the
whole reason this is a backend and not a new function to call.

**What is worth testing here is not that HTTP works.** It is that this backend
refuses to lie: that a message it cannot faithfully send raises instead of
arriving diminished, that a non-2xx is a failure rather than a success, and that
`fail_silently` means what Django's contract says. B4 exists because a provider
returned success for a message it had discarded; a backend that treats 403 as
sent would be the same evening again.
"""
import pathlib
from unittest.mock import patch

from django.conf import settings
from django.core.mail import (
    EmailMessage,
    EmailMultiAlternatives,
    get_connection,
    send_mail,
)
from django.test import SimpleTestCase, override_settings

from clarice.mail import ENDPOINT, ResendBackend, ResendError, resend_transport


API_KEY = "re_testkey_0123456789"


class FakeTransport:
    """Stands in for the POST, so no test opens a socket."""

    def __init__(self, status=200, body='{"id": "abc-123"}'):
        self.status = status
        self.body = body
        self.calls = []

    def __call__(self, payload, *, api_key, timeout, idempotency_key):
        self.calls.append(
            {
                "payload": payload,
                "api_key": api_key,
                "timeout": timeout,
                "idempotency_key": idempotency_key,
            }
        )
        return self.status, self.body


def a_message(**overrides):
    fields = {
        "subject": "Your Clarice account is scheduled for deletion",
        "body": "Hello alice,\n\nEverything goes.",
        "from_email": "Clarice <accounts@vinclarice.com>",
        "to": ["alice@example.com"],
    }
    return EmailMessage(**{**fields, **overrides})


@override_settings(RESEND_API_KEY=API_KEY, EMAIL_TIMEOUT=10)
class PayloadTest(SimpleTestCase):
    def send(self, message, **kwargs):
        transport = FakeTransport(**kwargs)
        backend = ResendBackend(transport=transport)
        sent = backend.send_messages([message])
        return transport, sent

    def test_a_message_becomes_the_documented_payload(self):
        transport, sent = self.send(a_message())

        self.assertEqual(sent, 1)
        payload = transport.calls[0]["payload"]
        self.assertEqual(payload["from"], "Clarice <accounts@vinclarice.com>")
        self.assertEqual(payload["to"], ["alice@example.com"])
        self.assertEqual(
            payload["subject"], "Your Clarice account is scheduled for deletion"
        )
        self.assertEqual(payload["text"], "Hello alice,\n\nEverything goes.")

    def test_the_body_travels_as_text_and_never_as_html(self):
        """`text` and `html` are separate fields and Resend generates one from
        the other. Sending a plain-text body as `html` would render somebody's
        newlines away."""
        transport, _ = self.send(a_message())

        self.assertNotIn("html", transport.calls[0]["payload"])

    def test_reply_to_travels_when_set(self):
        """The contact form's one use: the support inbox replies to the
        visitor, and the From stays Clarice's own address because sending as
        them would forge a domain Clarice does not own."""
        transport, _ = self.send(a_message(reply_to=["visitor@example.com"]))

        self.assertEqual(
            transport.calls[0]["payload"]["reply_to"], ["visitor@example.com"]
        )

    def test_reply_to_is_absent_rather_than_empty(self):
        transport, _ = self.send(a_message())

        self.assertNotIn("reply_to", transport.calls[0]["payload"])

    def test_cc_and_bcc_travel(self):
        """Nothing sends these today. Mapped rather than refused because
        Resend has both fields natively, and a bcc that vanished silently
        would be the kind of quiet wrong this backend exists to avoid."""
        transport, _ = self.send(
            a_message(cc=["cc@example.com"], bcc=["bcc@example.com"])
        )

        payload = transport.calls[0]["payload"]
        self.assertEqual(payload["cc"], ["cc@example.com"])
        self.assertEqual(payload["bcc"], ["bcc@example.com"])

    def test_the_key_travels_as_a_bearer_credential(self):
        transport, _ = self.send(a_message())

        self.assertEqual(transport.calls[0]["api_key"], API_KEY)

    def test_the_request_is_bounded_by_the_email_timeout(self):
        """The setting introduced two days ago, for the same reason: this runs
        on a request thread, on one worker with four of them."""
        transport, _ = self.send(a_message())

        self.assertEqual(transport.calls[0]["timeout"], settings.EMAIL_TIMEOUT)

    def test_several_messages_are_each_sent_and_counted(self):
        transport = FakeTransport()
        backend = ResendBackend(transport=transport)

        sent = backend.send_messages([a_message(), a_message(subject="Second")])

        self.assertEqual(sent, 2)
        self.assertEqual(len(transport.calls), 2)

    def test_a_message_with_no_recipients_is_skipped_not_sent(self):
        """Django's SMTP backend does the same. An API call with an empty `to`
        is a 400 for a message nobody was owed."""
        transport = FakeTransport()
        backend = ResendBackend(transport=transport)

        sent = backend.send_messages([a_message(to=[])])

        self.assertEqual(sent, 0)
        self.assertEqual(transport.calls, [])


@override_settings(RESEND_API_KEY=API_KEY, EMAIL_TIMEOUT=10)
class RefusesWhatItCannotSendFaithfullyTest(SimpleTestCase):
    """Raising, rather than sending a diminished message.

    Nothing in the tree attaches a file or sends HTML today. The refusals are
    here so that the day somebody does, they find out at once instead of
    shipping mail with the attachment missing — the same instinct as
    `commitments._UNHOLDABLE`, where widening the rule means deleting a line
    first.
    """

    def send(self, message):
        return ResendBackend(transport=FakeTransport()).send_messages([message])

    def test_an_attachment_is_refused(self):
        message = a_message()
        message.attach("export.zip", b"not really a zip", "application/zip")

        with self.assertRaises(ResendError) as raised:
            self.send(message)

        self.assertIn("attachment", str(raised.exception).lower())

    def test_an_html_alternative_is_refused(self):
        message = EmailMultiAlternatives(
            subject="Hello", body="plain", from_email="a@b.com", to=["c@d.com"]
        )
        message.attach_alternative("<p>rich</p>", "text/html")

        with self.assertRaises(ResendError):
            self.send(message)

    def test_an_html_content_subtype_is_refused(self):
        """The other route to the same thing: a body that is HTML because the
        message says so rather than because an alternative was attached."""
        message = a_message()
        message.content_subtype = "html"

        with self.assertRaises(ResendError):
            self.send(message)

    def test_a_refusal_is_still_silenced_by_fail_silently(self):
        """It is a send failure like any other. Django's contract does not
        carve out an exception for the ones we chose."""
        message = a_message()
        message.attach("export.zip", b"x", "application/zip")

        sent = ResendBackend(
            transport=FakeTransport(), fail_silently=True
        ).send_messages([message])

        self.assertEqual(sent, 0)


@override_settings(RESEND_API_KEY=API_KEY, EMAIL_TIMEOUT=10)
class OnlyTwoHundredsCountAsSentTest(SimpleTestCase):
    """B4's evening, in one class.

    A contact-form message was discarded inside the mail provider while SMTP
    returned 200 and Django recorded a clean send. Every mechanism this project
    owned reported success. A backend that treated Resend's 403 for a bad key,
    or its 429 for rate limiting, as delivery would be that failure again with
    a new transport.
    """

    def test_a_bad_key_is_a_failure_not_a_send(self):
        transport = FakeTransport(
            status=403, body='{"name": "invalid_api_key", "message": "API key is invalid."}'
        )

        with self.assertRaises(ResendError) as raised:
            ResendBackend(transport=transport).send_messages([a_message()])

        self.assertIn("403", str(raised.exception))

    def test_rate_limiting_is_a_failure_not_a_send(self):
        transport = FakeTransport(status=429, body='{"message": "Too many requests."}')

        with self.assertRaises(ResendError):
            ResendBackend(transport=transport).send_messages([a_message()])

    def test_the_providers_message_is_carried_into_the_error(self):
        """So the Sentry event says which of Resend's refusals it was, rather
        than only that something failed."""
        transport = FakeTransport(status=400, body='{"message": "Invalid `to` field."}')

        with self.assertRaises(ResendError) as raised:
            ResendBackend(transport=transport).send_messages([a_message()])

        self.assertIn("Invalid `to` field", str(raised.exception))

    def test_a_failure_is_silenced_when_asked_and_counted_as_unsent(self):
        transport = FakeTransport(status=403, body="{}")

        sent = ResendBackend(
            transport=transport, fail_silently=True
        ).send_messages([a_message()])

        self.assertEqual(sent, 0)

    def test_a_transport_level_failure_raises_too(self):
        """A timeout or a DNS failure, which is what the SMTP backend was
        producing for three days before anybody knew why."""

        def refuse(payload, **kwargs):
            raise TimeoutError("timed out")

        with self.assertRaises(ResendError):
            ResendBackend(transport=refuse).send_messages([a_message()])

    def test_no_key_configured_is_a_failure_rather_than_an_anonymous_post(self):
        transport = FakeTransport()

        with override_settings(RESEND_API_KEY=""):
            with self.assertRaises(ResendError) as raised:
                ResendBackend(transport=transport).send_messages([a_message()])

        self.assertIn("RESEND_API_KEY", str(raised.exception))
        self.assertEqual(transport.calls, [])


@override_settings(RESEND_API_KEY=API_KEY, EMAIL_TIMEOUT=10)
class RetryingDoesNotSendTwiceTest(SimpleTestCase):
    """Why an idempotency key is worth taking rather than skipping.

    The digest deliberately does not stamp `last_digest_date` when a send
    fails, so it tries again the next hour — and a request that timed out
    *after* Resend accepted it would otherwise deliver a second copy. Resend
    dedupes on this header for 24 hours.

    The trade, stated: two byte-identical messages to the same address inside a
    day collapse into one. For a digest whose body carries the date, and a
    contact form, that is the cheaper mistake.
    """

    def key_for(self, message):
        transport = FakeTransport()
        ResendBackend(transport=transport).send_messages([message])
        return transport.calls[0]["idempotency_key"]

    def test_the_same_message_carries_the_same_key(self):
        self.assertEqual(self.key_for(a_message()), self.key_for(a_message()))

    def test_a_different_body_carries_a_different_key(self):
        self.assertNotEqual(
            self.key_for(a_message()),
            self.key_for(a_message(body="Hello alice,\n\nSomething else.")),
        )

    def test_a_different_recipient_carries_a_different_key(self):
        """The digest sends near-identical mail to several people. Keying on
        the body alone would deliver to the first and dedupe the rest."""
        self.assertNotEqual(
            self.key_for(a_message()),
            self.key_for(a_message(to=["bob@example.com"])),
        )

    def test_the_key_fits_inside_the_documented_limit(self):
        self.assertLessEqual(len(self.key_for(a_message())), 256)


class WiredThroughDjangoTest(SimpleTestCase):
    """The path `settings.py` names, resolved the way Django resolves it.

    `EMAIL_BACKEND` is a dotted string imported at send time, so a typo in it is
    not a boot failure -- it is a failure on the first message somebody sends,
    which on this deployment would be a password reset. Nothing else in the
    suite would notice, because every other test either uses locmem or injects
    a backend directly.
    """

    def test_the_dotted_path_resolves_to_this_backend(self):
        connection = get_connection("clarice.mail.ResendBackend")

        self.assertIsInstance(connection, ResendBackend)

    def test_the_constructor_takes_what_get_connection_passes_it(self):
        """`get_connection` forwards `fail_silently` and any extra keywords, so
        the signature has to accept them rather than only Django's own."""
        transport = FakeTransport()

        connection = get_connection(
            "clarice.mail.ResendBackend", fail_silently=True, transport=transport
        )

        self.assertTrue(connection.fail_silently)
        self.assertIs(connection.transport, transport)

    @override_settings(
        EMAIL_BACKEND="clarice.mail.ResendBackend",
        RESEND_API_KEY=API_KEY,
        EMAIL_TIMEOUT=10,
    )
    def test_an_ordinary_send_mail_goes_out_over_https(self):
        """End to end through Django's own entry point, with `urlopen` patched
        at the last moment: this is what every caller in the tree does, and it
        is the one assertion that covers the setting, the path, the backend and
        the request together."""
        reached = {}

        class FakeResponse:
            status = 200

            def read(self):
                return b'{"id": "x"}'

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        def fake_urlopen(request, timeout=None):
            reached["url"] = request.full_url
            reached["body"] = request.data
            return FakeResponse()

        with patch("clarice.mail.urlopen", fake_urlopen):
            sent = send_mail(
                "Good morning",
                "  - Renew insurance (Home, due today)",
                "Clarice <accounts@vinclarice.com>",
                ["vince@example.com"],
            )

        self.assertEqual(sent, 1)
        self.assertEqual(reached["url"], ENDPOINT)
        self.assertIn(b"Renew insurance", reached["body"])


class SettingsSelectItTest(SimpleTestCase):
    """`settings.py`'s own branch, run rather than read.

    Every other test here names `clarice.mail.ResendBackend` as a literal --
    the same string `settings.py` names, written twice. A typo in *its* copy
    would leave all of them green and every message undeliverable, so this
    imports the settings module in a fresh interpreter with the environment set
    and asks what it actually resolved.

    A subprocess because Django settings are import-once per process, and
    reloading them under a running suite is the kind of clever that produces a
    test which passes for a reason nobody can name.
    """

    def resolve(self, **env):
        import os
        import subprocess
        import sys

        code = (
            "import django; django.setup();"
            "from django.conf import settings;"
            "print(settings.EMAIL_BACKEND)"
        )
        environment = {
            **os.environ,
            "DJANGO_SETTINGS_MODULE": "clarice.settings",
            "PYTHONPATH": str(pathlib.Path(__file__).resolve().parents[2]),
            **env,
        }
        return subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            env=environment,
        )

    def test_resend_selects_this_backend(self):
        result = self.resolve(
            DJANGO_EMAIL_BACKEND="resend", DJANGO_RESEND_API_KEY=API_KEY
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "clarice.mail.ResendBackend")

    def test_selecting_it_with_a_blank_key_refuses_to_boot(self):
        """Blank, not merely absent, and that distinction is the point: the
        playbook templates this variable to '' on the other arms, so a
        misconfiguration arrives present-and-empty. A bare os.environ lookup
        would accept it, boot cleanly, and fail on the first password reset."""
        result = self.resolve(DJANGO_EMAIL_BACKEND="resend", DJANGO_RESEND_API_KEY="")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DJANGO_RESEND_API_KEY", result.stderr)

    def test_selecting_it_with_no_key_at_all_refuses_to_boot(self):
        """The absent case, alongside the blank one above. `resolve` inherits
        this shell's environment, so skip rather than assert a falsehood if the
        variable happens to be set here."""
        import os

        if os.environ.get("DJANGO_RESEND_API_KEY"):
            self.skipTest("DJANGO_RESEND_API_KEY is set in this shell")

        result = self.resolve(DJANGO_EMAIL_BACKEND="resend")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DJANGO_RESEND_API_KEY", result.stderr)

    def test_console_still_works_for_development(self):
        result = self.resolve(DJANGO_EMAIL_BACKEND="console")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("console", result.stdout)

    def test_an_unknown_value_is_still_refused(self):
        result = self.resolve(DJANGO_EMAIL_BACKEND="carrier-pigeon")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DJANGO_EMAIL_BACKEND", result.stderr)


class TheRealTransportTest(SimpleTestCase):
    """The injected transport above means no test touches the network, which is
    what keeps them fast and offline — and would also let a misspelled endpoint
    or a missing import reach production unnoticed. This is the one place that
    resolves the real thing, still without calling it.

    Same arrangement as `monitoring.py`'s `sentry_initialiser`, for the same
    reason.
    """

    @override_settings(RESEND_API_KEY=API_KEY, EMAIL_TIMEOUT=10)
    def test_a_backend_built_with_no_transport_really_posts(self):
        """Identity is the wrong assertion here -- `resend_transport()` builds a
        fresh closure per call, so `is` could only ever pin an implementation
        detail. What matters is that the default path reaches the network layer
        rather than a stub, so this sends through it with `urlopen` patched at
        the last possible moment."""
        reached = {}

        class FakeResponse:
            status = 200

            def read(self):
                return b'{"id": "x"}'

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        def fake_urlopen(request, timeout=None):
            reached["url"] = request.full_url
            return FakeResponse()

        with patch("clarice.mail.urlopen", fake_urlopen):
            sent = ResendBackend().send_messages([a_message()])

        self.assertEqual(sent, 1)
        self.assertEqual(reached["url"], ENDPOINT)

    def test_it_posts_json_to_resends_documented_endpoint(self):
        """Asserts on the request it would make, without making it."""
        captured = {}

        class FakeResponse:
            status = 200

            def read(self):
                return b'{"id": "x"}'

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        def fake_urlopen(request, timeout=None):
            captured["url"] = request.full_url
            captured["method"] = request.get_method()
            captured["headers"] = {k.lower(): v for k, v in request.header_items()}
            captured["body"] = request.data
            captured["timeout"] = timeout
            return FakeResponse()

        with patch("clarice.mail.urlopen", fake_urlopen):
            status, _ = resend_transport()(
                {"from": "a@b.com", "to": ["c@d.com"], "subject": "s", "text": "t"},
                api_key=API_KEY,
                timeout=10,
                idempotency_key="deadbeef",
            )

        self.assertEqual(status, 200)
        self.assertEqual(captured["url"], ENDPOINT)
        self.assertEqual(captured["method"], "POST")
        self.assertEqual(captured["headers"]["authorization"], f"Bearer {API_KEY}")
        self.assertEqual(captured["headers"]["content-type"], "application/json")
        # Cloudflare fronts api.resend.com and blocks `Python-urllib` by
        # signature -- error 1010, a 403 that never reaches Resend. Found on
        # the 2026-08-18 deploy, because every test here either injects a
        # transport or patches urlopen, so none of them had ever made a real
        # request. Any other agent gets through; urllib's default does not.
        self.assertIn("user-agent", captured["headers"])
        self.assertNotIn("urllib", captured["headers"]["user-agent"].lower())
        self.assertIn("Clarice", captured["headers"]["user-agent"])
        self.assertEqual(captured["headers"]["idempotency-key"], "deadbeef")
        self.assertEqual(captured["timeout"], 10)
        self.assertIn(b'"subject": "s"', captured["body"])

    def test_a_non_2xx_is_returned_rather_than_raised_by_the_transport(self):
        """urlopen raises HTTPError on 4xx, which would lose the body Resend
        explains itself in. The transport unwraps it so the backend decides
        what a status means -- and the backend's tests are what pin that."""
        from urllib.error import HTTPError

        def raising_urlopen(request, timeout=None):
            raise HTTPError(
                request.full_url, 403, "Forbidden", {}, __import__("io").BytesIO(
                    b'{"message": "API key is invalid."}'
                )
            )

        with patch("clarice.mail.urlopen", raising_urlopen):
            status, body = resend_transport()(
                {"from": "a@b.com", "to": ["c@d.com"], "subject": "s", "text": "t"},
                api_key=API_KEY,
                timeout=10,
                idempotency_key="deadbeef",
            )

        self.assertEqual(status, 403)
        self.assertIn("API key is invalid", body)
