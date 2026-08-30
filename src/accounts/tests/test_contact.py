"""The public contact form.

Lives in `accounts` rather than an app of its own, and that is a decision
rather than an accident: this feature has no model, no persistence, and no
lifecycle -- it renders a form and sends one message. The other public,
unauthenticated, mail-sending pages (login, signup, password reset) already
live here. **Reconsideration trigger:** the moment a contact message needs
to be stored, assigned, or replied to from inside Clarice, it has become a
domain with a life cycle and earns its own app.

See design/bittern-plan.md, B3.
"""
from unittest.mock import patch

from django.conf import settings
from django.core import mail
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from accounts.views import _contact_sends_key


VALID = {
    "name": "Edith Piaf",
    "email": "edith@example.com",
    "message": "Does Clarice do recurring subtasks?",
}


class ContactFormTest(TestCase):
    def setUp(self):
        # The rate limiter counts in the cache, which is process-global and
        # would otherwise leak across tests in this file.
        cache.clear()

    def submit(self, **overrides):
        return self.client.post(
            reverse("contact"), data={**VALID, **overrides}, follow=True
        )

    def test_the_page_is_public(self):
        response = self.client.get(reverse("contact"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "message")

    def test_an_anonymous_visitor_is_offered_the_link(self):
        # A support path nobody can find is not a support path. Same
        # instinct as the reset link on the lockout page.
        response = self.client.get(reverse("login"))

        self.assertContains(response, reverse("contact"))

    def test_a_valid_message_sends_exactly_one_email_to_support(self):
        self.submit()

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [settings.SUPPORT_EMAIL])

    def test_the_message_carries_the_name_and_body(self):
        self.submit()

        self.assertIn("Edith Piaf", mail.outbox[0].body)
        self.assertIn("recurring subtasks", mail.outbox[0].body)

    def test_the_visitor_is_the_reply_to_and_never_the_sender(self):
        # Sending *as* the visitor would be forging a From on a domain
        # Clarice doesn't own -- Resend would refuse it, and it would fail
        # SPF and DMARC at the recipient if it didn't.
        self.submit()

        self.assertEqual(mail.outbox[0].reply_to, ["edith@example.com"])
        self.assertEqual(mail.outbox[0].from_email, settings.DEFAULT_FROM_EMAIL)

    def test_success_does_not_reveal_where_the_message_went(self):
        response = self.submit()

        self.assertContains(response, "Thanks")
        self.assertNotContains(response, settings.SUPPORT_EMAIL)


class ContactValidationTest(TestCase):
    def setUp(self):
        cache.clear()

    def submit(self, follow=False, **overrides):
        return self.client.post(
            reverse("contact"), data={**VALID, **overrides}, follow=follow
        )

    def test_an_unreachable_relay_does_not_lose_what_they_typed(self):
        """Production, 2026-08-18: an SMTP connection timeout on this view.

        There is no model behind this page -- its docstring says so, and that
        is a deliberate choice -- so a failed send means the message exists
        nowhere. Unguarded, the visitor got a 500 and their text was gone with
        it. A stranger with a question is exactly the person least able to
        recover from that.
        """
        from smtplib import SMTPException

        with patch(
            "accounts.views.send_support_message",
            side_effect=SMTPException("relay unreachable"),
        ):
            response = self.submit()

        # 503, matching the 429 the rate-limit branch returns: the page
        # rendered and the thing behind it did not.
        self.assertEqual(response.status_code, 503)
        self.assertContains(
            response, "Does Clarice do recurring subtasks?", status_code=503
        )

    def test_it_says_the_message_did_not_go_and_offers_another_way(self):
        """Not "on its way", which is what a success page would claim, and not
        a bare error either: the one thing a person needs here is an address
        that does not depend on the thing that just failed."""
        from smtplib import SMTPException

        with patch(
            "accounts.views.send_support_message",
            side_effect=SMTPException("relay unreachable"),
        ):
            response = self.submit()

        self.assertNotContains(response, "on its way", status_code=503)
        self.assertContains(response, settings.SUPPORT_EMAIL, status_code=503)

    def test_a_failed_send_is_reported_where_sentry_can_see_it(self):
        """Caught, so the visitor is served; logged, so it is still an event.
        The same trade the digest's guarded loop makes -- catching an exception
        moves the decision about who hears about it to us, and the default
        answer becomes nobody."""
        from smtplib import SMTPException

        with patch(
            "accounts.views.send_support_message",
            side_effect=SMTPException("relay unreachable"),
        ):
            with self.assertLogs("accounts.views", level="ERROR") as logged:
                self.submit()

        self.assertIsNotNone(logged.records[0].exc_info)

    def test_a_failed_send_does_not_spend_the_visitors_allowance(self):
        """Already true -- _record_contact_send runs after the send -- and
        pinned here because a relay outage charging people for messages that
        never left is the kind of thing a later refactor restores."""
        from smtplib import SMTPException

        with patch(
            "accounts.views.send_support_message",
            side_effect=SMTPException("relay unreachable"),
        ):
            self.submit()

        self.assertEqual(cache.get(_contact_sends_key("127.0.0.1"), 0), 0)

    def test_an_invalid_address_sends_nothing_and_says_so(self):
        response = self.submit(email="not-an-address")

        self.assertEqual(mail.outbox, [])
        self.assertContains(response, "valid email")

    def test_an_empty_message_sends_nothing(self):
        response = self.submit(message="")

        self.assertEqual(mail.outbox, [])
        self.assertEqual(response.status_code, 200)

    def test_a_filled_honeypot_sends_nothing_but_looks_like_success(self):
        # Telling a bot it was caught only teaches whoever wrote it. A
        # person never sees this field, so filling it is never accidental.
        response = self.submit(website="http://spam.example.com", follow=True)

        self.assertEqual(mail.outbox, [])
        self.assertContains(response, "Thanks")


class ContactHeaderInjectionTest(TestCase):
    """A regression guard, and honest about being one: it passes by
    construction rather than by filtering. Nothing a visitor types reaches a
    header -- the subject is fixed, the name and message go in the body, and
    the only header built from input is Reply-To, from a value EmailField
    has already validated. These assert that that stays true.
    """

    def setUp(self):
        cache.clear()

    def test_newlines_in_the_name_cannot_add_a_header(self):
        self.client.post(
            reverse("contact"),
            data={**VALID, "name": "Edith\nBcc: victim@example.com"},
            follow=True,
        )

        if mail.outbox:
            headers = dict(mail.outbox[0].message().items())
            self.assertNotIn("Bcc", headers)
            self.assertNotIn("victim@example.com", str(headers))

    def test_an_address_carrying_a_header_is_rejected_outright(self):
        response = self.client.post(
            reverse("contact"),
            data={**VALID, "email": "edith@example.com\nBcc: victim@example.com"},
        )

        self.assertEqual(mail.outbox, [])
        self.assertContains(response, "valid email")


class ContactRateLimitTest(TestCase):
    """Rate limiting is two layers, matching the login flow: nginx throttles
    by IP before the request arrives (see infra/templates/nginx-clarice.conf.j2)
    and this is the layer that can actually be tested.
    """

    def setUp(self):
        cache.clear()

    def submit(self, ip="203.0.113.5"):
        return self.client.post(
            reverse("contact"),
            data=VALID,
            headers={"x-real-ip": ip},
            follow=True,
        )

    def test_a_burst_from_one_address_is_cut_off(self):
        for _ in range(settings.CONTACT_MAX_PER_HOUR):
            self.submit()
        sent_before = len(mail.outbox)

        response = self.submit()

        self.assertEqual(len(mail.outbox), sent_before)
        self.assertContains(response, "too many", status_code=429)

    def test_the_limit_follows_the_visitor_and_not_the_proxy(self):
        # The one that matters. Django sits behind nginx, so REMOTE_ADDR is
        # nginx for every visitor on earth -- a limit keyed on it would let
        # the first spammer lock out everybody. The client IP has to come
        # from X-Real-IP, which nginx overwrites and a client cannot forge.
        for _ in range(settings.CONTACT_MAX_PER_HOUR):
            self.submit(ip="203.0.113.5")

        response = self.submit(ip="198.51.100.9")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), settings.CONTACT_MAX_PER_HOUR + 1)


class SignedInContactTest(TestCase):
    """The same support path, for somebody who already has an account.

    coherence-audit-2026-08-30.md F7. The Contact link lived only in the
    logged-out branch of the app bar, so the person most likely to have
    something worth reporting had the worst route to reporting it -- which
    `roadmap.md` had been describing as *promotable, not deferred* since B4
    shipped the error monitoring its trigger named.

    Three separate things follow from having an identity, and each has a test
    below: the link exists, the two fields already known are not asked for,
    and the rate limit stops being keyed on an address.
    """

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="edith",
            email="edith@example.com",
            password="terrible-password-123",
        )
        self.client.force_login(self.user)

    def submit(self, **overrides):
        return self.client.post(
            reverse("contact"),
            data={"message": "The agenda lost my Tuesday.", **overrides},
            follow=True,
        )

    def test_a_signed_in_person_is_offered_the_link(self):
        # The mirror of test_an_anonymous_visitor_is_offered_the_link above,
        # and the whole of F7: the bar rendered the link in the {% else %}
        # branch only.
        response = self.client.get(reverse("dashboard"), follow=True)

        self.assertContains(response, reverse("contact"))

    def test_it_does_not_ask_for_what_the_account_already_says(self):
        response = self.client.get(reverse("contact"))

        self.assertNotContains(response, 'name="name"')
        self.assertNotContains(response, 'name="email"')

    def test_the_message_carries_the_account_identity(self):
        self.submit()

        self.assertEqual(len(mail.outbox), 1)
        # Reply-To is the account's address rather than one retyped into a
        # form -- the reason roadmap.md gives for not simply prefilling it.
        self.assertEqual(mail.outbox[0].reply_to, ["edith@example.com"])
        self.assertIn("edith", mail.outbox[0].body)

    def test_the_message_still_arrives(self):
        self.submit()

        self.assertEqual(mail.outbox[0].to, [settings.SUPPORT_EMAIL])
        self.assertIn("The agenda lost my Tuesday.", mail.outbox[0].body)

    def test_an_empty_message_sends_nothing(self):
        self.submit(message="")

        self.assertEqual(len(mail.outbox), 0)

    def test_the_limit_follows_the_account_and_not_the_address(self):
        # Per-IP is the wrong key once there is an identity: two people
        # behind one office NAT share an address and do not share an account.
        for _ in range(settings.CONTACT_MAX_PER_HOUR):
            self.submit()
        sent_before = len(mail.outbox)

        # Same address, different account, and their allowance is untouched.
        other = User.objects.create_user(
            username="mireille",
            email="mireille@example.com",
            password="terrible-password-123",
        )
        self.client.force_login(other)
        response = self.submit()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), sent_before + 1)

    def test_a_burst_from_one_account_is_still_cut_off(self):
        for _ in range(settings.CONTACT_MAX_PER_HOUR):
            self.submit()
        sent_before = len(mail.outbox)

        response = self.submit()

        self.assertEqual(len(mail.outbox), sent_before)
        self.assertContains(response, "too many", status_code=429)
