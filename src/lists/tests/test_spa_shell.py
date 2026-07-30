from django.test import TestCase, override_settings

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

    def test_loads_site_css_so_reused_components_stay_styled(self):
        """Regression check: reused components (AgendaWorkspace,
        TaskWorkspace) still depend on site.css's classes and the
        CSS-module styles compiled into app.css -- both silently missing
        from the shell at one point, leaving those pages fully unstyled.
        """
        self.client.force_login(self.user)

        response = self.client.get("/app/agenda")

        self.assertContains(response, "site.css")
        self.assertContains(response, "frontend/app")

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

    @override_settings(DEBUG=True)
    def test_serves_the_dev_gallery_in_debug(self):
        self.client.force_login(self.user)

        response = self.client.get("/app/dev/ui")

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "app_shell.html")

    @override_settings(DEBUG=False)
    def test_hides_the_dev_gallery_outside_debug(self):
        self.client.force_login(self.user)

        response = self.client.get("/app/dev/ui")

        self.assertEqual(response.status_code, 404)
