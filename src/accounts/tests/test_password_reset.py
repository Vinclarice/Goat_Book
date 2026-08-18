"""The self-service reset flow, including the one piece that isn't Django's
own: finishing a reset clears an axes lockout.

See design/password-reset-plan.md -- this exists because someone was locked
out, had forgotten the password, and had no way back in from any page.
"""
import re

from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.forms import PasswordResetForm
from django.core import mail
from django.test import TestCase
from django.urls import reverse

from accounts.models import User


PASSWORD = "correct horse battery staple 47!"
NEW_PASSWORD = "a different horse entirely 91!"
FAILURE_LIMIT = 5


def reset_link_in(message):
    """The confirm URL out of a sent reset email.

    Read from the email rather than built with reverse(), so the test also
    covers the email template actually rendering a usable link -- a broken
    {% url %} in there would otherwise go unnoticed.
    """
    found = re.search(r"/accounts/password/reset/confirm/[^\s]+", message.body)
    return found.group(0) if found else None



def without_nonces(response):
    """A response's body with CSP nonces blanked.

    `clarice.middleware.ContentSecurityPolicyMiddleware` mints one per request,
    so two renders of the same page never match byte for byte. That difference
    is random and carries no information; everything else on these two pages
    has to match exactly.
    """
    return re.sub(rb'nonce="[^"]*"', b'nonce=""', response.content)


class PasswordResetRequestTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "edith", "edith@example.com", PASSWORD
        )

    def request_reset(self, email):
        return self.client.post(
            reverse("password_reset"), data={"email": email}, follow=True
        )

    def test_sends_one_email_for_a_real_account(self):
        response = self.request_reset("edith@example.com")

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, "Reset your Clarice password")
        self.assertIn("edith", mail.outbox[0].body)
        self.assertIsNotNone(reset_link_in(mail.outbox[0]))
        self.assertContains(response, "Check your email")

    def test_the_login_page_offers_a_way_in_without_a_password(self):
        response = self.client.get(reverse("login"))

        self.assertContains(response, reverse("password_reset"))

    def test_an_unknown_address_looks_identical_and_sends_nothing(self):
        # Don't-reveal-existence, same instinct as accounts.forms.LoginForm.
        response = self.request_reset("nobody@example.com")

        self.assertEqual(mail.outbox, [])
        self.assertContains(response, "Check your email")

    def test_an_unreachable_relay_does_not_500_the_recovery_page(self):
        """Django's PasswordResetView sends inside form_valid, so a send
        failure was an unhandled 500 -- on a public page, for the one person
        who by definition cannot log in and work around it.

        Live on this deployment until the transport moved: DigitalOcean drops
        outbound SMTP, so *every* reset for a real account 500d.
        """
        from smtplib import SMTPException

        with patch.object(
            PasswordResetForm, "save", side_effect=SMTPException("relay unreachable")
        ):
            response = self.request_reset("edith@example.com")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Check your email")

    def test_a_failed_send_is_indistinguishable_from_an_unknown_address(self):
        """The constraint the contact form did not have, and the reason this
        guard cannot simply show the error the contact form shows.

        `password_reset_done.html` says it in its own comment: the page renders
        the same way whether or not the address matched, so it cannot be used
        to find out which addresses are registered. A send only *fails* when an
        account matched -- so an error page shown on failure would announce
        exactly what that comment protects.
        """
        from smtplib import SMTPException

        with patch.object(
            PasswordResetForm, "save", side_effect=SMTPException("relay unreachable")
        ):
            failed = self.request_reset("edith@example.com")
        unknown = self.request_reset("nobody@example.com")

        self.assertEqual(failed.status_code, unknown.status_code)
        self.assertEqual(failed.redirect_chain, unknown.redirect_chain)
        # Byte-identical apart from the CSP nonce, which is fresh per request
        # by design and tells an observer nothing about which case they hit.
        # Asserting on the raw bytes would fail for a reason that is not the
        # property under test.
        self.assertEqual(without_nonces(failed), without_nonces(unknown))

    def test_a_failed_send_is_reported_where_sentry_can_see_it(self):
        """Since the page deliberately cannot say anything, this is the only
        place the failure is visible at all."""
        from smtplib import SMTPException

        with patch.object(
            PasswordResetForm, "save", side_effect=SMTPException("relay unreachable")
        ):
            with self.assertLogs("accounts.views", level="ERROR") as logged:
                self.request_reset("edith@example.com")

        self.assertIsNotNone(logged.records[0].exc_info)

    def test_the_page_always_offers_a_way_to_ask_a_human(self):
        """Shown on every reset, not only the failed ones -- a line that
        appeared only on failure would be the same disclosure by another
        route. It costs nothing when the mail arrives and is the only route
        left when it does not."""
        response = self.request_reset("edith@example.com")

        self.assertContains(response, settings.SUPPORT_EMAIL)

    def test_a_pending_account_looks_identical_and_sends_nothing(self):
        # An unapproved signup has nothing worth resetting into yet, and
        # PasswordResetForm.get_users() already excludes is_active=False.
        User.objects.create_user(
            "pending", "pending@example.com", PASSWORD, is_active=False
        )

        response = self.request_reset("pending@example.com")

        self.assertEqual(mail.outbox, [])
        self.assertContains(response, "Check your email")


class PasswordResetConfirmTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "edith", "edith@example.com", PASSWORD
        )

    def start_reset(self):
        """Requests a reset and follows the emailed link to the form page.

        Returns the URL to POST the new password to -- Django's confirm view
        redirects the real token to a set-password/ URL and stashes the token
        in the session, so the POST target isn't the link from the email.
        """
        self.client.post(
            reverse("password_reset"), data={"email": "edith@example.com"}
        )
        response = self.client.get(reset_link_in(mail.outbox[-1]), follow=True)
        return response, response.redirect_chain[-1][0]

    def test_a_valid_link_offers_the_new_password_form(self):
        response, _ = self.start_reset()

        self.assertTrue(response.context["validlink"])
        self.assertContains(response, "Set a new password")

    def test_setting_a_new_password_replaces_the_old_one(self):
        _, post_url = self.start_reset()

        self.client.post(
            post_url,
            data={"new_password1": NEW_PASSWORD, "new_password2": NEW_PASSWORD},
        )

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(NEW_PASSWORD))
        self.assertFalse(self.user.check_password(PASSWORD))

    def test_a_bad_token_offers_no_form_at_all(self):
        response = self.client.get(
            reverse(
                "password_reset_confirm",
                kwargs={"uidb64": "MQ", "token": "not-a-real-token"},
            )
        )

        self.assertFalse(response.context["validlink"])
        self.assertContains(response, "This link no longer works")
        self.assertNotContains(response, "new_password1")

    def test_a_link_cannot_be_used_twice(self):
        _, post_url = self.start_reset()
        self.client.post(
            post_url,
            data={"new_password1": NEW_PASSWORD, "new_password2": NEW_PASSWORD},
        )

        # The token is derived from the password hash, so changing it spends
        # the link -- a second visit lands on the expired branch.
        response = self.client.get(reset_link_in(mail.outbox[-1]), follow=True)

        self.assertFalse(response.context["validlink"])


class LockedOutPasswordResetTest(TestCase):
    """The case that prompted the whole feature: locked out *and* unable to
    remember the password.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            "edith", "edith@example.com", PASSWORD
        )
        for _ in range(FAILURE_LIMIT):
            self.client.post(
                reverse("login"),
                data={"username": "edith", "password": "wrong password"},
            )

    def log_in(self, password):
        return self.client.post(
            reverse("login"),
            data={"username": "edith", "password": password},
        )

    def test_the_lockout_page_offers_the_way_out(self):
        # The whole point of the incident: this is the page you land on, so
        # it has to be the page that tells you a reset exists.
        response = self.log_in(PASSWORD)

        self.assertContains(
            response, reverse("password_reset"), status_code=429
        )

    def test_the_lockout_is_real(self):
        # Guards the tests below: without this, they'd still pass if axes
        # silently stopped locking anyone out.
        response = self.log_in(PASSWORD)

        # 429, not 403: axes answers a lockout as Too Many Requests.
        self.assertContains(response, "Temporarily locked out", status_code=429)

    def test_a_locked_out_user_can_still_reach_the_reset_flow(self):
        # axes only wraps the login view, so nothing here should be blocked.
        request_page = self.client.get(reverse("password_reset"))
        self.client.post(
            reverse("password_reset"), data={"email": "edith@example.com"}
        )
        confirm_page = self.client.get(reset_link_in(mail.outbox[-1]), follow=True)

        self.assertEqual(request_page.status_code, 200)
        self.assertTrue(confirm_page.context["validlink"])

    def test_completing_a_reset_clears_the_lockout(self):
        self.client.post(
            reverse("password_reset"), data={"email": "edith@example.com"}
        )
        response = self.client.get(reset_link_in(mail.outbox[-1]), follow=True)
        self.client.post(
            response.redirect_chain[-1][0],
            data={"new_password1": NEW_PASSWORD, "new_password2": NEW_PASSWORD},
        )

        logged_in = self.log_in(NEW_PASSWORD)

        # A redirect, not the lockout template: no hour of waiting with a
        # password that already works.
        self.assertEqual(logged_in.status_code, 302)
        self.assertIn("_auth_user_id", self.client.session)


class NoLeakedTemplateCommentsTest(TestCase):
    """Django's {# #} is a *single-line* comment: spread one over two lines
    and it stops being a comment, rendering verbatim on the page instead.

    Caught on a real page, not by a test -- every assertion here was written
    against the copy it expected to find, which is still there either way.
    Hence this: one cheap check that no page is showing its own annotations.
    """

    def setUp(self):
        User.objects.create_user("edith", "edith@example.com", PASSWORD)

    def test_no_reset_page_renders_a_raw_comment(self):
        self.client.post(
            reverse("password_reset"), data={"email": "edith@example.com"}
        )
        urls = [
            reverse("login"),
            reverse("password_reset"),
            reverse("password_reset_done"),
            reset_link_in(mail.outbox[-1]),
            reverse("password_reset_complete"),
        ]

        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url, follow=True)

                self.assertNotContains(response, "{#")
                self.assertNotContains(response, "{%")


class AdminPasswordResetLinkTest(TestCase):
    """The admin login page renders its reset link with
    {% url 'admin_password_reset' as ... %}, which swallows NoReverseMatch
    and renders nothing at all when the name is missing. A regression in
    clarice/urls.py's ordering would drop the link silently rather than
    error, so it's worth asserting on directly.
    """

    def test_the_name_resolves(self):
        self.assertEqual(
            reverse("admin_password_reset"), "/admin/password_reset/"
        )

    def test_it_redirects_into_the_one_real_reset_flow(self):
        response = self.client.get("/admin/password_reset/")

        self.assertRedirects(
            response, reverse("password_reset"), fetch_redirect_response=False
        )

    def test_the_admin_login_page_shows_the_link(self):
        response = self.client.get("/admin/login/")

        self.assertContains(response, "/admin/password_reset/")
