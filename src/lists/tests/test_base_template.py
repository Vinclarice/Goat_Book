from django.contrib.auth.models import AnonymousUser
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.staticfiles import finders
from django.template import TemplateDoesNotExist
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase
from django.urls import reverse

from accounts.models import User


class NewBaseTemplateTest(TestCase):
    """Every surviving Django page (login, signup, signup_pending,
    lockout, change_password, 403, new_list_form) extends base.html as
    of Step 5 -- base_legacy.html and Bootstrap are gone. This still
    renders base.html directly rather than through any one of those
    pages, so it exercises the template itself independent of what any
    particular page puts in {% block content %}.
    """

    def setUp(self):
        self.factory = RequestFactory()

    def _request(self, user):
        request = self.factory.get("/")
        request.user = user
        request.session = {}
        request._messages = FallbackStorage(request)
        return request

    def test_shows_login_links_when_anonymous(self):
        html = render_to_string("base.html", request=self._request(AnonymousUser()))

        self.assertIn(reverse("login"), html)
        self.assertNotIn('id="id_logout"', html)

    def test_shows_account_nav_when_authenticated(self):
        user = User.objects.create_user("alice", "alice@example.com", "a secure password")

        html = render_to_string("base.html", request=self._request(user))

        self.assertIn('id="id_logout"', html)
        self.assertIn("alice", html)

    def test_loads_the_token_stylesheet_and_theme_script(self):
        html = render_to_string("base.html", request=self._request(AnonymousUser()))

        self.assertIn("frontend/tokens", html)
        self.assertIn("clarice-theme", html)
        self.assertNotIn("bootstrap", html.lower())

    def test_anonymous_visitors_resolve_purely_client_side(self):
        html = render_to_string("base.html", request=self._request(AnonymousUser()))

        self.assertIn("SERVER_THEME = null", html)

    def test_authenticated_visitors_get_their_persisted_theme_inlined(self):
        user = User.objects.create_user(
            "alice", "alice@example.com", "a secure password", theme="dark",
        )

        html = render_to_string("base.html", request=self._request(user))

        self.assertIn('SERVER_THEME = "dark"', html)


class BootstrapRemovalTest(TestCase):
    """Guards the two things Step 5 was supposed to retire -- there's no
    CI in this repo to enforce it automatically, so this stands in for
    the "fail CI on Bootstrap remnants / base_legacy.html" check the UI
    overhaul plan calls for.
    """

    def test_base_legacy_template_no_longer_exists(self):
        with self.assertRaises(TemplateDoesNotExist):
            render_to_string("base_legacy.html")

    def test_bootstrap_static_files_are_gone(self):
        self.assertIsNone(finders.find("bootstrap/css/bootstrap.min.css"))
