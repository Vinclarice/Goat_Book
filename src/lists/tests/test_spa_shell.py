from django.test import TestCase

from accounts.models import User


class SpaShellTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "alice",
            "alice@example.com",
            "a secure password",
        )

    def test_redirects_anonymous_visitors_to_login(self):
        response = self.client.get("/app/agenda")

        self.assertRedirects(
            response,
            "/accounts/login/?next=/app/agenda",
            fetch_redirect_response=False,
        )

    def test_serves_the_shell_for_logged_in_users(self):
        self.client.force_login(self.user)

        response = self.client.get("/app/agenda")

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "app_shell.html")
        self.assertContains(response, '<div id="app-root">')

    def test_serves_the_shell_for_the_bare_app_root(self):
        self.client.force_login(self.user)

        response = self.client.get("/app/")

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "app_shell.html")

    def test_serves_the_shell_for_nested_paths(self):
        self.client.force_login(self.user)

        response = self.client.get("/app/tasks/42")

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "app_shell.html")
