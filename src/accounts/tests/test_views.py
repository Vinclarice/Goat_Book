from django.contrib import auth
from django.core import mail
from django.test import TestCase

from accounts.models import User
from lists.models import List


PASSWORD = "correct horse battery staple 47!"


class SignUpViewTest(TestCase):
    def test_renders_signup_form(self):
        response = self.client.get("/accounts/signup/")

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/signup.html")
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

        self.assertRedirects(response, "/dashboard/")
        self.assertEqual(auth.get_user(self.client), self.user)

    def test_welcome_page_form_logs_in_with_valid_credentials(self):
        response = self.client.post(
            "/",
            data={"username": "edith", "password": PASSWORD},
        )

        self.assertRedirects(response, "/dashboard/")
        self.assertEqual(auth.get_user(self.client), self.user)

    def test_rejects_invalid_credentials(self):
        response = self.client.post(
            "/accounts/login/",
            data={"username": "edith", "password": "wrong password"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Please enter a correct username and password.",
        )
        self.assertFalse(auth.get_user(self.client).is_authenticated)

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
    def setUp(self):
        self.user = User.objects.create_user(
            "edith",
            "edith@example.com",
            PASSWORD,
        )
        self.list_ = List.objects.create(owner=self.user, title="Programming")
        self.client.force_login(self.user)

    def test_requires_login(self):
        self.client.logout()

        response = self.client.get("/accounts/settings/")

        self.assertRedirects(
            response,
            "/accounts/login/?next=/accounts/settings/",
        )

    def test_updates_username_and_email_without_changing_ownership(self):
        original_pk = self.user.pk

        response = self.client.post(
            "/accounts/settings/",
            data={"username": "edith-new", "email": "new@example.com"},
        )

        self.user.refresh_from_db()
        self.list_.refresh_from_db()
        self.assertRedirects(response, "/accounts/settings/")
        self.assertEqual(self.user.pk, original_pk)
        self.assertEqual(self.user.username, "edith-new")
        self.assertEqual(self.user.email, "new@example.com")
        self.assertEqual(self.list_.owner, self.user)

    def test_rejects_duplicate_email(self):
        User.objects.create_user("other", "other@example.com", PASSWORD)

        response = self.client.post(
            "/accounts/settings/",
            data={"username": "edith", "email": "other@example.com"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "User with this Email already exists.")

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
        self.assertRedirects(response, "/accounts/settings/")
        self.assertTrue(self.user.check_password(new_password))
        self.assertEqual(auth.get_user(self.client), self.user)
