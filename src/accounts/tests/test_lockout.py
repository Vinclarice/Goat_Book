from django.core import mail
from django.test import TestCase

from accounts.models import User


PASSWORD = "correct horse battery staple 47!"


class LockoutNotificationTest(TestCase):
    def test_emails_admins_when_an_account_is_locked_out(self):
        User.objects.create_user("edith", "edith@example.com", PASSWORD)

        for _ in range(5):
            self.client.post(
                "/accounts/login/",
                data={"username": "edith", "password": "wrong password"},
            )

        lockout_emails = [
            message for message in mail.outbox if "locked out" in message.subject
        ]
        self.assertEqual(len(lockout_emails), 1)
        self.assertIn("edith", lockout_emails[0].body)
