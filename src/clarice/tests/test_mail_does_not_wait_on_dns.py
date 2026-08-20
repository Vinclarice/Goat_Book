"""Sending a message must not ask the network what this host is called.

**Found from a real failure.** `functional_tests.test_leaving`'s
schedule-deletion journey started failing, and the cause was in neither the
code under test nor the work that landed beside it: `EmailMessage.message()`
stamps a `Message-ID` built from `django.core.mail.utils.DNS_NAME`, which calls
`socket.getfqdn()`. On the machine this was diagnosed on that call took twelve
seconds; Playwright waits ten.

The reverse lookup happens once per process and is then cached, which is what
made it look like a flake and then like a regression -- whichever test sent the
first message paid for it, so the failure moved around with test ordering.

**Production never paid it**, so this guards the two paths that do:
`ResendBackend` builds Resend's JSON from the message's own fields and never
calls `.message()`, where the locmem backend the suite runs on calls it
deliberately to validate headers, and so does the console backend used in
development.
"""

from unittest.mock import patch

from django.core.mail import EmailMessage
from django.test import TestCase


class MailDoesNotWaitOnDnsTest(TestCase):
    def test_building_a_message_does_not_call_getfqdn(self):
        """The assertion is about the *call*, not about how long it took.

        Timing it would make this a slow test on a fast machine and a flaky one
        on a slow network -- which is the whole failure being fixed. What is
        actually wrong is asking at all, so that is what is asserted.
        """
        # Returning a real name so that a regression here reads as this
        # test's own assertion rather than as a crash inside make_msgid.
        with patch("socket.getfqdn", return_value="somewhere.invalid") as lookup:
            EmailMessage(
                subject="Anything",
                body="Anything",
                from_email="accounts@example.com",
                to=["somebody@example.com"],
            ).message()

        self.assertFalse(
            lookup.called,
            "Message-ID generation performed a reverse DNS lookup; "
            "settings.py pre-seeds DNS_NAME precisely so it does not.",
        )

    def test_the_message_id_names_the_domain_the_mail_claims_to_come_from(self):
        message = EmailMessage(
            subject="Anything",
            body="Anything",
            from_email="accounts@example.com",
            to=["somebody@example.com"],
        ).message()

        self.assertTrue(
            message["Message-ID"].endswith("@vinclarice.com>"),
            f"unexpected Message-ID: {message['Message-ID']}",
        )
