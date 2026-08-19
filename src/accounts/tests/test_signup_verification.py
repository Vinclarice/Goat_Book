"""Signing up and getting in, without waiting for a person.

`product-stories.md` S1's fourth requires: **self-service signup with email
verification**. Until now an account was created `is_active=False` and an admin
ticked a box in `/admin/`; `accounts/emails.py` had six functions and none of
them told the applicant it had happened, so the honest description of the flow
was that somebody signed up and then waited, with no way to tell whether they
were waiting for a minute or forever.

**Two gates, deliberately.** Confirming an address is self-service; approval is
still a person's decision, Vince's call on August 18, 2026, because the site is
invitation-only and there is no privacy policy yet.

**So S1 does not close**, and this docstring is the honest place to say so: its
"done means" asks for a usable workspace *without waiting for a human*, and
approval is a human. What does close is the smaller, real complaint underneath
it -- that somebody could sign up and be told nothing at all, with no way to
tell a minute's wait from a permanent one.

`is_active` is approval; `email_confirmed_at` is confirmation. One flag could
not hold both, which is why the field exists.
"""
import re
from datetime import timedelta
from smtplib import SMTPException
from unittest.mock import patch

from django.conf import settings
from django.contrib import auth
from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from accounts.models import User
from accounts.tokens import activation_token


PASSWORD = "correct horse battery staple 47!"


def without_nonce(response):
    """The body with the per-request CSP nonce removed.

    Two responses that must be indistinguishable to a stranger still differ in
    their nonce, which is exactly what a nonce is for.
    """
    return re.sub(rb'nonce="[^"]+"', b'nonce=""', response.content)


def signup_payload(**overrides):
    return {
        "username": "sam",
        "email": "sam@example.com",
        "password1": PASSWORD,
        "password2": PASSWORD,
        **overrides,
    }


class SignUpSendsAVerificationEmailTest(TestCase):
    def test_the_email_goes_to_the_applicant(self):
        """The one message this flow has always been missing."""
        self.client.post(reverse("signup"), data=signup_payload())

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["sam@example.com"])

    def test_it_carries_a_link_that_activates_this_account(self):
        self.client.post(reverse("signup"), data=signup_payload())
        user = User.objects.get(username="sam")

        path = reverse(
            "activate",
            kwargs={
                "uidb64": urlsafe_base64_encode(force_bytes(user.pk)),
                "token": activation_token.make_token(user),
            },
        )
        # The token in the mail is not the one built here -- both are valid,
        # which is the property that matters. Asserting on the prefix rather
        # than the whole path keeps this from testing the generator's salt.
        self.assertIn(path.rsplit("/", 2)[0], mail.outbox[0].body)

    def test_the_account_starts_unverified(self):
        self.client.post(reverse("signup"), data=signup_payload())

        self.assertFalse(User.objects.get(username="sam").is_active)
        self.assertFalse(auth.get_user(self.client).is_authenticated)

    def test_admins_hear_nothing_until_the_address_is_confirmed(self):
        """The review is worth an admin's attention once somebody has proved
        they read their mail. Before that it is a form submission, and on a
        public form most of those are abandoned or invented."""
        self.client.post(reverse("signup"), data=signup_payload())

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["sam@example.com"])


class FollowingTheLinkTest(TestCase):
    def setUp(self):
        self.client.post(reverse("signup"), data=signup_payload())
        self.user = User.objects.get(username="sam")

    def activation_url(self, user=None, token=None):
        user = user or self.user
        return reverse(
            "activate",
            kwargs={
                "uidb64": urlsafe_base64_encode(force_bytes(user.pk)),
                "token": token or activation_token.make_token(user),
            },
        )

    def test_it_confirms_the_address_without_letting_them_in(self):
        """The first gate, and only the first.

        Signing them in here would be a way straight past approval, which is
        the gate that was kept. `is_active` must be untouched.
        """
        response = self.client.get(self.activation_url())

        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.email_confirmed_at)
        self.assertFalse(self.user.is_active)
        self.assertFalse(auth.get_user(self.client).is_authenticated)
        self.assertTemplateUsed(response, "accounts/activation_confirmed.html")

    def test_confirming_is_what_tells_the_admins(self):
        self.client.get(self.activation_url())

        notice = mail.outbox[-1]
        self.assertEqual(notice.to, [settings.ADMINS[0][1]])
        self.assertIn("awaiting approval", notice.subject)

    def test_following_the_link_twice_does_not_move_the_confirmation_date(self):
        """The second visit is refused, and the date it already holds is the
        reason -- re-stamping it would mint a fresh token and make a spent link
        live again. The page it lands on says there is nothing more to do."""
        self.client.get(self.activation_url())
        self.user.refresh_from_db()
        first = self.user.email_confirmed_at

        self.client.get(self.activation_url())

        self.user.refresh_from_db()
        self.assertEqual(self.user.email_confirmed_at, first)

    def test_the_link_stops_working_once_it_has_been_used(self):
        """`email_confirmed_at` is in the token's hash, so confirming kills it.

        A link that stays valid is one sitting in an inbox, and in a forwarded
        message or a shared screenshot it is a way into somebody's account.
        """
        url = self.activation_url()
        self.client.get(url)

        response = self.client.get(url)

        self.assertTemplateUsed(response, "accounts/activation_failed.html")

    def test_a_tampered_token_offers_a_way_forward_rather_than_a_dead_end(self):
        """`principles.md`: failure is recoverable and visible. A 404 here
        leaves somebody holding an account they cannot reach and no idea what
        to do about it."""
        response = self.client.get(self.activation_url(token="not-a-real-token"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/activation_failed.html")
        self.assertContains(response, reverse("resend_activation"))
        self.assertIsNone(User.objects.get(username="sam").email_confirmed_at)

    def test_an_unknown_account_looks_the_same_as_a_bad_token(self):
        """Two failures a stranger must not be able to tell apart, or the page
        answers "is this a real account" for anybody who asks."""
        response = self.client.get(
            reverse(
                "activate",
                kwargs={
                    "uidb64": urlsafe_base64_encode(force_bytes(9999)),
                    "token": "whatever",
                },
            )
        )

        self.assertTemplateUsed(response, "accounts/activation_failed.html")

    def test_an_expired_link_fails_rather_than_letting_them_in(self):
        with patch(
            "django.contrib.auth.tokens.PasswordResetTokenGenerator._now",
            return_value=activation_token._now() - timedelta(days=400),
        ):
            stale = activation_token.make_token(self.user)

        response = self.client.get(self.activation_url(token=stale))

        self.user.refresh_from_db()
        self.assertIsNone(self.user.email_confirmed_at)
        self.assertTemplateUsed(response, "accounts/activation_failed.html")


class ResendTest(TestCase):
    def setUp(self):
        self.client.post(reverse("signup"), data=signup_payload())
        mail.outbox.clear()

    def test_a_fresh_link_can_be_asked_for(self):
        """Without this, one lost email is the dead end the whole story is
        about -- and it would be a dead end nobody can escape, because the
        username is taken and the account cannot log in."""
        response = self.client.post(
            reverse("resend_activation"), data={"email": "sam@example.com"}
        )

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["sam@example.com"])
        self.assertTemplateUsed(response, "accounts/activation_sent.html")

    def test_an_unknown_address_renders_identically_and_sends_nothing(self):
        """The same rule the password reset follows, for the same reason: a
        page that differs tells a stranger which addresses hold accounts."""
        known = self.client.post(
            reverse("resend_activation"), data={"email": "sam@example.com"}
        )
        mail.outbox.clear()

        unknown = self.client.post(
            reverse("resend_activation"), data={"email": "nobody@example.com"}
        )

        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(unknown.status_code, known.status_code)
        # Nonce-normalised: the CSP nonce is per-request by design and is the
        # one thing that *must* differ between two responses. Comparing raw
        # bytes would fail for the one reason that is not a disclosure.
        self.assertEqual(without_nonce(unknown), without_nonce(known))

    def test_a_confirmed_address_is_not_sent_another_link(self):
        """Nothing is left for the link to do: the address is confirmed and the
        account is waiting on a person. A second link would invite somebody to
        click a thing that changes nothing."""
        user = User.objects.get(username="sam")
        user.email_confirmed_at = timezone.now()
        user.save(update_fields=["email_confirmed_at"])

        self.client.post(
            reverse("resend_activation"), data={"email": "sam@example.com"}
        )

        self.assertEqual(len(mail.outbox), 0)


class UnverifiedLoginTest(TestCase):
    def setUp(self):
        self.client.post(reverse("signup"), data=signup_payload())

    def test_an_unconfirmed_account_is_sent_to_its_inbox(self):
        response = self.client.post(
            reverse("login"), data={"username": "sam", "password": PASSWORD}
        )

        self.assertFalse(auth.get_user(self.client).is_authenticated)
        self.assertContains(response, "been confirmed")
        self.assertContains(response, reverse("resend_activation"))

    def test_a_confirmed_account_is_told_it_is_waiting_on_a_person(self):
        """The two waits must not be confused. Telling somebody who already
        confirmed to check their inbox sends them hunting for a link that will
        not work, and offering a resend would be the same mistake twice."""
        user = User.objects.get(username="sam")
        user.email_confirmed_at = timezone.now()
        user.save(update_fields=["email_confirmed_at"])

        response = self.client.post(
            reverse("login"), data={"username": "sam", "password": PASSWORD}
        )

        self.assertContains(response, "waiting to be")
        self.assertNotContains(response, reverse("resend_activation"))


class MailFailureTest(TestCase):
    def test_a_failed_send_does_not_500_or_strand_the_account(self):
        """The same shape as the August 18 contact-form outage. The account is
        created before the send, so an unguarded raise leaves a real account
        behind an error page: they never learn whether it worked, and trying
        again fails on a duplicate username."""
        with patch(
            "accounts.views.send_activation_email",
            side_effect=SMTPException("relay unreachable"),
        ):
            response = self.client.post(reverse("signup"), data=signup_payload())

        self.assertEqual(response.status_code, 200)
        self.assertTrue(User.objects.filter(username="sam").exists())
        # Named on the page, because the only way out of a failed send is to
        # ask for another one.
        self.assertContains(response, reverse("resend_activation"))

    def test_the_failure_is_reported_where_sentry_can_see_it(self):
        with patch(
            "accounts.views.send_activation_email",
            side_effect=SMTPException("relay unreachable"),
        ):
            with self.assertLogs("accounts.views", level="ERROR") as logged:
                self.client.post(reverse("signup"), data=signup_payload())

        self.assertIsNotNone(logged.records[0].exc_info)


class SignedOutPagesLookSignedOutTest(TestCase):
    """Neither page in this flow may render the signed-in app bar.

    Found in a browser, not by a test: `signup_pending.html` showed the
    username and a Log out button to somebody with no session, because the
    view passed `{"user": user}` and that name is the context processor's.
    `AbstractBaseUser.is_authenticated` is True on any real instance, so the
    bar had no way to tell.

    Every assertion in the suite passed throughout — they all read the copy
    they expected rather than the chrome around it.
    """

    def confirmed_response(self):
        self.client.post(reverse("signup"), data=signup_payload())
        user = User.objects.get(username="sam")
        return self.client.get(
            reverse(
                "activate",
                kwargs={
                    "uidb64": urlsafe_base64_encode(force_bytes(user.pk)),
                    "token": activation_token.make_token(user),
                },
            )
        )

    def test_the_pending_page_offers_a_way_in_not_a_way_out(self):
        response = self.client.post(reverse("signup"), data=signup_payload())

        self.assertNotContains(response, 'id="id_logout"')
        self.assertContains(response, reverse("login"))

    def test_the_confirmed_page_offers_a_way_in_not_a_way_out(self):
        response = self.confirmed_response()

        self.assertNotContains(response, 'id="id_logout"')
        self.assertContains(response, reverse("login"))


class ApprovalIsAnnouncedTest(TestCase):
    """The promise three surfaces make, and nothing was keeping.

    `activation_confirmed.html`, the confirmation email and the login form all
    say some version of "we'll write to you once yours is open" — and when the
    two-gate flow shipped, nothing did. No signal, no hook, no function. It is
    the same defect this whole flow exists to remove, one step further along:
    somebody does what is asked and then waits on a message that is never sent.

    Approval is an admin ticking `is_active` in `/admin/`, so the transition is
    what has to be watched rather than any particular view.
    """

    def setUp(self):
        self.client.post(reverse("signup"), data=signup_payload())
        self.user = User.objects.get(username="sam")
        self.user.email_confirmed_at = timezone.now()
        self.user.save(update_fields=["email_confirmed_at"])
        mail.outbox.clear()

    def approve(self):
        user = User.objects.get(pk=self.user.pk)
        user.is_active = True
        user.save()
        return user

    def test_approving_an_account_writes_to_the_person(self):
        self.approve()

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["sam@example.com"])

    def test_the_message_says_they_can_now_log_in(self):
        self.approve()

        self.assertIn(reverse("login"), mail.outbox[0].body)

    def test_saving_an_already_active_account_says_nothing(self):
        """Every login writes `last_login`, so a naive hook would email on
        every sign-in for the rest of the account's life."""
        approved = self.approve()
        mail.outbox.clear()

        approved.last_login = timezone.now()
        approved.save()

        self.assertEqual(len(mail.outbox), 0)

    def test_an_account_an_admin_creates_outright_is_not_written_to(self):
        """It never waited for anything, so there is nothing to announce."""
        mail.outbox.clear()

        User.objects.create_user("edith", "edith@example.com", PASSWORD)

        self.assertEqual(len(mail.outbox), 0)

    def test_a_failed_send_does_not_break_the_approval(self):
        """The admin's tick is the real work and it has already happened. A
        mail failure must not roll it back or 500 the admin page -- that would
        turn a missing email into an account nobody can open."""
        with patch(
            "accounts.emails.send_account_approved",
            side_effect=SMTPException("relay unreachable"),
        ):
            with self.assertLogs("accounts.apps", level="ERROR"):
                self.approve()

        self.assertTrue(User.objects.get(pk=self.user.pk).is_active)
