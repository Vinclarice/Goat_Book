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
from django.conf import settings
from django.core import mail
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse


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
