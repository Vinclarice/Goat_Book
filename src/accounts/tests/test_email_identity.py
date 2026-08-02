"""Who Clarice's mail appears to come from, and who its internal notices
reach.

The regression these guard is a specific one. `DEFAULT_FROM_EMAIL` used to
be defined as `EMAIL_HOST_USER`, so the credential used to authenticate to
the mail server and the identity shown to the recipient were the same
string -- the developer's personal Gmail account. Every password reset a
stranger received was signed, visibly, by a person rather than a product.

Resend makes that coupling wrong rather than merely untidy: it
authenticates as the literal user "resend" with an API key, and will only
send From an address on a verified domain. A sender inherited from the
credential would now be both embarrassing and undeliverable.

See design/bittern-plan.md, B3.
"""
from django.conf import settings
from django.core import mail
from django.test import TestCase
from django.urls import reverse

from accounts.models import User


PASSWORD = "correct horse battery staple 47!"
SENDING_DOMAIN = "vinclarice.com"


def senders_of(message):
    """Every address a recipient could see this message as being from.

    Reply-To is included deliberately: routing replies to a private inbox
    leaks it just as effectively as putting it in From, and it is the
    header most likely to be added later without thinking about it.
    """
    return [message.from_email, *message.extra_headers.get("Reply-To", "").split(",")]


class OutboundSenderTest(TestCase):
    def setUp(self):
        User.objects.create_user("edith", "edith@example.com", PASSWORD)

    def request_reset(self):
        self.client.post(
            reverse("password_reset"), data={"email": "edith@example.com"}
        )
        return mail.outbox[-1]

    def test_a_password_reset_comes_from_a_clarice_address(self):
        message = self.request_reset()

        self.assertIn(f"@{SENDING_DOMAIN}", message.from_email)

    def test_a_password_reset_is_not_signed_by_a_personal_account(self):
        # The literal defect: a stranger resetting their password should
        # never learn who maintains Clarice, and Resend cannot send as
        # gmail.com at all.
        message = self.request_reset()

        self.assertNotIn("gmail.com", message.from_email)

    def test_a_password_reset_never_carries_the_private_admin_address(self):
        # ADMINS is where lockouts and pending signups go. It is an
        # internal routing decision, and it has no business appearing in a
        # header a user reads.
        admin_address = settings.ADMINS[0][1]

        message = self.request_reset()

        for sender in senders_of(message):
            self.assertNotIn(admin_address, sender)


class AdminNoticeTest(TestCase):
    """Internal notices: a private recipient, but still a sendable sender."""

    def signup(self):
        self.client.post(
            reverse("signup"),
            data={
                "username": "edith",
                "email": "edith@example.com",
                "password1": PASSWORD,
                "password2": PASSWORD,
            },
        )
        return mail.outbox[-1]

    def test_a_pending_signup_notice_reaches_the_admin_and_nobody_else(self):
        message = self.signup()

        self.assertEqual(message.to, [settings.ADMINS[0][1]])

    def test_an_admin_notice_is_labelled_clarice_not_django(self):
        # mail_admins() prefixes the subject with EMAIL_SUBJECT_PREFIX,
        # whose Django default is "[Django] ". Left unset, every notice
        # Clarice sends is labelled with the framework it was built in.
        message = self.signup()

        self.assertTrue(message.subject.startswith("[Clarice] "))
        self.assertNotIn("Django", message.subject)

    def test_an_admin_notice_is_sent_from_a_clarice_address(self):
        # mail_admins() sends From SERVER_EMAIL, whose Django default is
        # root@localhost. Left alone that is not a cosmetic problem: Resend
        # rejects it outright, so the first production lockout would fail
        # to report itself and nothing would say why.
        message = self.signup()

        self.assertIn(f"@{SENDING_DOMAIN}", message.from_email)
