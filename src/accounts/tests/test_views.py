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

    def test_creates_an_unconfirmed_account(self):
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
        self.assertContains(response, "Check your email")

        user = User.objects.get(username="edith")
        self.assertEqual(user.email, "edith@example.com")
        self.assertTrue(user.check_password(PASSWORD))
        self.assertFalse(user.is_active)
        self.assertFalse(auth.get_user(self.client).is_authenticated)

    # The mail-failure pair that stood here moved to
    # test_signup_verification.py with the message they are about: the send
    # that matters on signup is the one to the applicant now, and there is no
    # admin notification left to fail.

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

    def test_the_landing_page_no_longer_authenticates_anybody(self):
        """"/" served the login form until August 2026 and accepted its POST.

        It is a landing page now, and this is the half of that change worth a
        test: credentials posted there must not log anyone in. nginx still
        carries a POST-keyed limiter on "/" precisely because a form could
        come back, so the assertion is that the view does not quietly still
        be one.
        """
        response = self.client.post(
            "/",
            data={"username": "edith", "password": PASSWORD},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(auth.get_user(self.client).is_authenticated)

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

    def test_rejects_login_for_an_unapproved_account(self):
        """Which of the two waits it names is covered in
        test_signup_verification.py; what this asserts is that a correct
        password on an account that may not be used yet still says so, rather
        than falling through to the generic error."""
        self.user.is_active = False
        self.user.save()

        response = self.client.post(
            "/accounts/login/",
            data={"username": "edith", "password": PASSWORD},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "been confirmed")
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
        self.assertNotContains(response, "been confirmed")

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
