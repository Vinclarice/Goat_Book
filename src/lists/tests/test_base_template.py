from django.contrib.auth.models import AnonymousUser
from django.contrib.messages.storage.fallback import FallbackStorage
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase
from django.urls import reverse

from accounts.models import User


class NewBaseTemplateTest(TestCase):
    """base.html isn't wired to any route yet (see the UI overhaul plan's
    Step 3/Step 5 split) -- this renders it directly to prove the fork
    from base_legacy.html actually works before anything depends on it.
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
