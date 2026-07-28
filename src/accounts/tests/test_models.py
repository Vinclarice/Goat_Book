from django.contrib import auth
from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase

from accounts.models import User


class UserModelTest(TestCase):
    def test_model_is_configured_for_django_auth(self):
        self.assertEqual(auth.get_user_model(), User)

    def test_user_can_authenticate_with_username_and_password(self):
        user = User.objects.create_user(
            username="edith",
            email="edith@example.com",
            password="correct horse battery staple",
        )

        self.assertTrue(user.check_password("correct horse battery staple"))
        # AxesBackend (see AUTHENTICATION_BACKENDS) needs a request to track
        # attempts by IP, so authenticate() needs one too, unlike before.
        request = RequestFactory().post("/accounts/login/")
        self.assertEqual(
            auth.authenticate(
                request,
                username="edith",
                password="correct horse battery staple",
            ),
            user,
        )

    def test_user_has_numeric_primary_key_and_unique_email(self):
        user = User.objects.create_user(
            username="edith",
            email="edith@example.com",
            password="a secure password",
        )

        self.assertIsInstance(user.pk, int)
        self.assertEqual(user.email, "edith@example.com")

        duplicate = User(username="other", email="edith@example.com")
        with self.assertRaisesMessage(
            ValidationError,
            "User with this Email already exists.",
        ):
            duplicate.full_clean()

    def test_username_is_required_and_unique(self):
        User.objects.create_user(
            username="edith",
            email="edith@example.com",
            password="a secure password",
        )
        duplicate = User(username="edith", email="other@example.com")

        with self.assertRaisesMessage(
            ValidationError,
            "User with this Username already exists.",
        ):
            duplicate.full_clean()
