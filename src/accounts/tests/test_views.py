from smtplib import SMTPException
from unittest.mock import patch

from django.contrib import auth
from django.core import mail
from django.test import TestCase

from accounts.models import User


PASSWORD = "correct horse battery staple 47!"


class SignUpViewTest(TestCase):
    def test_renders_signup_form(self):
        response = self.client.get("/accounts/signup/")

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/signup.html")
        self.assertTemplateUsed(response, "base.html")
        self.assertContains(response, 'name="username"')
        self.assertContains(response, 'name="email"')
        self.assertContains(response, 'name="password1"')

    def test_creates_an_inactive_account_pending_approval(self):
        response = self.client.post(
            "/accounts/signup/",
            data={
                "username": "edith",
                "email": "edith@example.com",
                "password1": PASSWORD,
                "password2": PASSWORD,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/signup_pending.html")
        self.assertContains(response, "pending approval")

        user = User.objects.get(username="edith")
        self.assertEqual(user.email, "edith@example.com")
        self.assertTrue(user.check_password(PASSWORD))
        self.assertFalse(user.is_active)
        self.assertFalse(auth.get_user(self.client).is_authenticated)

    def test_emails_admins_about_the_pending_signup(self):
        self.client.post(
            "/accounts/signup/",
            data={
                "username": "edith",
                "email": "edith@example.com",
                "password1": PASSWORD,
                "password2": PASSWORD,
            },
        )

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("edith", mail.outbox[0].subject)
        self.assertIn("edith@example.com", mail.outbox[0].body)

    def test_an_unreachable_relay_does_not_500_a_created_account(self):
        """The same class as the contact form's 2026-08-18 outage, and worse.

        The account is created before the notification is sent, so an
        unguarded raise left a real account behind a 500 page -- the person is
        never shown "pending approval", never learns whether it worked, and a
        second attempt fails on a duplicate username. Two ways to be stuck, on
        somebody's first minute with the product.
        """
        with patch(
            "accounts.views.notify_admins_of_pending_signup",
            side_effect=SMTPException("relay unreachable"),
        ):
            response = self.client.post(
                "/accounts/signup/",
                data={
                    "username": "edith",
                    "email": "edith@example.com",
                    "password1": PASSWORD,
                    "password2": PASSWORD,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/signup_pending.html")
        self.assertTrue(User.objects.filter(username="edith").exists())

    def test_a_failed_notification_is_reported_where_sentry_can_see_it(self):
        """The account is not rolled back -- signing up is the person's own
        action and it succeeded, unlike request_deletion where the email *is*
        the protection. But an admin who never hears about a pending signup
        leaves somebody waiting forever, so this has to be an event."""
        with patch(
            "accounts.views.notify_admins_of_pending_signup",
            side_effect=SMTPException("relay unreachable"),
        ):
            with self.assertLogs("accounts.views", level="ERROR") as logged:
                self.client.post(
                    "/accounts/signup/",
                    data={
                        "username": "edith",
                        "email": "edith@example.com",
                        "password1": PASSWORD,
                        "password2": PASSWORD,
                    },
                )

        self.assertIsNotNone(logged.records[0].exc_info)

    def test_rejects_duplicate_username(self):
        User.objects.create_user("edith", "edith@example.com", PASSWORD)

        response = self.client.post(
            "/accounts/signup/",
            data={
                "username": "edith",
                "email": "other@example.com",
                "password1": PASSWORD,
                "password2": PASSWORD,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "User with this Username already exists.")
        self.assertEqual(User.objects.count(), 1)

    def test_normalizes_signup_email(self):
        self.client.post(
            "/accounts/signup/",
            data={
                "username": "edith",
                "email": "Edith@Example.COM",
                "password1": PASSWORD,
                "password2": PASSWORD,
            },
        )

        self.assertEqual(
            User.objects.get(username="edith").email,
            "edith@example.com",
        )


class LoginViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "edith",
            "edith@example.com",
            PASSWORD,
        )

    def test_logs_in_with_valid_credentials(self):
        response = self.client.post(
            "/accounts/login/",
            data={"username": "edith", "password": PASSWORD},
        )

        self.assertRedirects(response, "/dashboard/", target_status_code=302)
        self.assertEqual(auth.get_user(self.client), self.user)

    def test_welcome_page_form_logs_in_with_valid_credentials(self):
        response = self.client.post(
            "/",
            data={"username": "edith", "password": PASSWORD},
        )

        self.assertRedirects(response, "/dashboard/", target_status_code=302)
        self.assertEqual(auth.get_user(self.client), self.user)

    def test_rejects_invalid_credentials(self):
        response = self.client.post(
            "/accounts/login/",
            data={"username": "edith", "password": "wrong password"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertContains(
            response,
            "Please enter a correct username and password.",
        )
        self.assertFalse(auth.get_user(self.client).is_authenticated)

    def test_too_many_failed_attempts_renders_the_lockout_page(self):
        for _ in range(5):
            response = self.client.post(
                "/accounts/login/",
                data={"username": "edith", "password": "wrong password"},
            )

        self.assertTemplateUsed(response, "accounts/lockout.html")
        self.assertTemplateUsed(response, "base.html")
        self.assertContains(response, "Temporarily locked out", status_code=429)

    def test_rejects_login_for_a_pending_inactive_account(self):
        self.user.is_active = False
        self.user.save()

        response = self.client.post(
            "/accounts/login/",
            data={"username": "edith", "password": PASSWORD},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "hasn&#x27;t been approved yet")
        self.assertFalse(auth.get_user(self.client).is_authenticated)

    def test_wrong_password_for_a_pending_account_gives_the_generic_error(self):
        # Doesn't confirm a pending account exists to someone who hasn't
        # proven they know its password.
        self.user.is_active = False
        self.user.save()

        response = self.client.post(
            "/accounts/login/",
            data={"username": "edith", "password": "wrong password"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Please enter a correct username and password.",
        )
        self.assertNotContains(response, "hasn&#x27;t been approved yet")

    def test_logout_requires_post_and_ends_the_session(self):
        self.client.force_login(self.user)

        get_response = self.client.get("/accounts/logout/")
        self.assertEqual(get_response.status_code, 405)

        post_response = self.client.post("/accounts/logout/")
        self.assertRedirects(post_response, "/")
        self.assertFalse(auth.get_user(self.client).is_authenticated)


class AccountSettingsViewTest(TestCase):
    """Account settings moved to /app/preferences (its own API, tested in
    accounts/tests/test_api_v1.py); this URL is now a thin redirect kept
    alive for old bookmarks and the navbar link in base.html."""

    def setUp(self):
        self.user = User.objects.create_user(
            "edith",
            "edith@example.com",
            PASSWORD,
        )
        self.client.force_login(self.user)

    def test_requires_login(self):
        self.client.logout()

        response = self.client.get("/accounts/settings/")

        self.assertRedirects(
            response,
            "/accounts/login/?next=/accounts/settings/",
        )

    def test_redirects_to_the_spa_preferences_route(self):
        response = self.client.get("/accounts/settings/")

        self.assertRedirects(
            response, "/app/preferences", fetch_redirect_response=False,
        )

    def test_renders_change_password_form(self):
        response = self.client.get("/accounts/password/change/")

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/change_password.html")
        self.assertTemplateUsed(response, "base.html")
        self.assertContains(response, 'name="old_password"')

    def test_changes_password_and_preserves_session(self):
        new_password = "a different secure password 92!"

        response = self.client.post(
            "/accounts/password/change/",
            data={
                "old_password": PASSWORD,
                "new_password1": new_password,
                "new_password2": new_password,
            },
        )

        self.user.refresh_from_db()
        self.assertRedirects(
            response, "/accounts/settings/", target_status_code=302,
        )
        self.assertTrue(self.user.check_password(new_password))
        self.assertEqual(auth.get_user(self.client), self.user)
