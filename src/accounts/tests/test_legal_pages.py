"""The two documents, and the one property that makes them worth having.

A privacy policy describing a system nobody checked is a liability with a
reassuring tone. These tests do not grade the prose — they hold the few claims
that would become false if the code changed underneath them, so that changing
the code fails here rather than silently making a published promise a lie.

They are deliberately not a re-statement of the documents. Only the claims with
a mechanical counterpart are asserted; everything else is Vince's to keep true
by reading it.
"""

from django.conf import settings
from django.test import TestCase
from django.urls import reverse

from accounts.models import User


class ReachableWithoutAnAccountTest(TestCase):
    """The whole point of publishing them.

    Somebody deciding whether to hand over an email address has to be able to
    read both first. A policy behind a login is a policy for people who already
    agreed to it.
    """

    def test_both_pages_are_public(self):
        for name in ("privacy", "terms"):
            with self.subTest(page=name):
                response = self.client.get(reverse(name))

                self.assertEqual(response.status_code, 200)

    def test_every_signed_out_page_carries_the_links(self):
        """Via base.html's footer, which is why this checks a page that is
        neither of them and has nothing to do with either."""
        response = self.client.get(reverse("home"))

        self.assertContains(response, reverse("privacy"))
        self.assertContains(response, reverse("terms"))

    def test_the_signup_form_says_what_pressing_the_button_means(self):
        response = self.client.get(reverse("signup"))

        self.assertContains(response, reverse("privacy"))
        self.assertContains(response, reverse("terms"))

    def test_they_point_at_each_other(self):
        self.assertContains(self.client.get(reverse("privacy")), reverse("terms"))
        self.assertContains(self.client.get(reverse("terms")), reverse("privacy"))


class OwnerIsNamedTest(TestCase):
    """Who is responsible is the one thing a policy exists to establish.

    Held as a test because it is the claim most likely to be quietly outgrown:
    an entity name changes, or a document gets rewritten from a template that
    does not know about it, and a policy naming nobody is a policy nobody is
    bound by.
    """

    OWNER = "Vinclarice, LLC"

    def test_both_documents_name_the_owner(self):
        for name in ("privacy", "terms"):
            with self.subTest(page=name):
                self.assertContains(self.client.get(reverse(name)), self.OWNER)

    def test_the_terms_say_who_the_agreement_is_with(self):
        """"An agreement between you and ..." is the sentence that makes the
        rest of the document mean anything."""
        response = self.client.get(reverse("terms"))

        self.assertContains(response, "agreement between you and")

    def test_the_footer_names_the_owner_on_every_page(self):
        response = self.client.get(reverse("home"))

        self.assertContains(response, self.OWNER)


class ContactAddressIsRealTest(TestCase):
    """Both documents tell people to write to somebody.

    Typed into the templates it would be one more thing to forget; read from
    settings there is a single place it can be wrong, and this proves the
    reading works rather than rendering an empty mailto.
    """

    def test_the_support_address_is_the_configured_one(self):
        for name in ("privacy", "terms"):
            with self.subTest(page=name):
                response = self.client.get(reverse(name))

                self.assertContains(response, settings.SUPPORT_EMAIL)
                self.assertNotContains(response, 'href="mailto:"')


class ClaimsThatMustStayTrueTest(TestCase):
    """Each of these has a counterpart in code that could change without
    anybody thinking about this page."""

    def test_the_stated_deletion_window_is_the_one_the_code_uses(self):
        from accounts.services import ACCOUNT_DELETION_GRACE

        self.assertEqual(ACCOUNT_DELETION_GRACE.days, 30)
        for name in ("privacy", "terms"):
            with self.subTest(page=name):
                self.assertContains(self.client.get(reverse(name)), "30 days")

    def test_the_evening_nudge_is_described_as_off_by_default(self):
        """The second recurring message, and the reason this page had to
        change with it: it said "the one recurring message is the daily
        summary", and a published promise the code contradicts is worse than
        no promise. Off by default, and the page and the model must agree
        about which -- the same pairing the test below makes."""
        self.assertFalse(User._meta.get_field("closing_nudge").default)
        self.assertContains(self.client.get(reverse("privacy")), "off by default")

    def test_the_page_does_not_still_claim_only_one_recurring_message(self):
        """The claim that went stale. Asserted as an absence, because a
        positive test would pass with the old sentence still sitting beside
        the new paragraph."""
        page = self.client.get(reverse("privacy")).content.decode()

        self.assertNotIn("The one recurring message", page)

    def test_the_daily_summary_is_described_as_on_by_default(self):
        """It defaults to True, so a policy calling it opt-in would be wrong in
        the direction that matters."""
        self.assertTrue(User._meta.get_field("daily_digest").default)
        self.assertContains(self.client.get(reverse("privacy")), "on by default")

    def test_the_sentry_exclusions_are_the_ones_actually_configured(self):
        """The policy makes four specific promises about error reports. Each is
        a keyword argument in clarice/monitoring.py, and each would be silently
        undone by a default if it were ever removed -- two of them already were
        once, which is how they came to be passed explicitly."""
        source = (
            settings.BASE_DIR / "clarice" / "monitoring.py"
        ).read_text(encoding="utf-8")

        self.assertIn("send_default_pii=False", source)
        self.assertIn("include_local_variables=False", source)
        self.assertIn('max_request_body_size="never"', source)
        self.assertIn("query_string", source)

    def test_no_analytics_is_claimed_and_none_is_loaded(self):
        """The claim is absolute, so the check is too: no page a visitor can
        reach may pull in a third-party script."""
        for name in ("home", "privacy", "terms", "signup", "login"):
            with self.subTest(page=name):
                body = self.client.get(reverse(name)).content.decode()

                for tracker in (
                    "google-analytics",
                    "googletagmanager",
                    "gtag(",
                    "plausible.io",
                    "posthog",
                    "mixpanel",
                ):
                    self.assertNotIn(tracker, body)
