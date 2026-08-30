from django.conf import settings
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
    lockout, change_password, 403) extends base.html as of Step 5 --
    base_legacy.html and Bootstrap are gone. `new_list_form` was in that
    list until August 30, 2026, when coherence-audit-2026-08-30.md F1
    retired it along with the view it was the error page for. This still
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


class TemplateCommentSyntaxTest(TestCase):
    """No template may open a `{#` it doesn't close on the same line.

    Django's `{# #}` is single-line only: spread one over two lines and it
    stops being a comment, rendering verbatim on the page. It has now
    happened twice -- on the password reset pages, then again on the Ideas
    page -- and both times the suite stayed green, because assertions look
    for the copy they expect rather than the noise they don't.

    A static sweep of the files rather than a sweep of rendered pages, on
    purpose: this one covers templates nobody has written yet, which is
    exactly what the two page-scoped versions of this check failed to do.
    """

    def test_no_template_opens_a_comment_it_does_not_close(self):
        offenders = []
        for path in (settings.BASE_DIR).rglob("templates/**/*.html"):
            for number, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), start=1
            ):
                if "{#" in line and "#}" not in line:
                    offenders.append(f"{path.name}:{number}")

        self.assertEqual(
            offenders,
            [],
            "Multi-line {# #} renders as visible page text -- "
            "use {% comment %} instead.",
        )

    def test_the_sweep_actually_reaches_the_templates(self):
        # A positive control: an empty file list would make the check above
        # pass forever, and silently, if the layout ever moves.
        found = list((settings.BASE_DIR).rglob("templates/**/*.html"))

        self.assertGreater(len(found), 5)


class BootstrapRemovalTest(TestCase):
    """Guards the two things Step 5 was supposed to retire.

    Written when there was no CI, as a stand-in for the "fail CI on
    Bootstrap remnants / base_legacy.html" check the UI overhaul plan
    called for. There is CI now (.github/workflows/ci.yml), and it runs
    this suite -- so the stand-in became the real thing rather than being
    replaced by it.

    What the sweep never covered is what Bootstrap took *with* it:
    .visually-hidden lived in bootstrap-utilities.css and its callers
    outlived the file. See test_frontend_style_contract.py.
    """

    def test_base_legacy_template_no_longer_exists(self):
        with self.assertRaises(TemplateDoesNotExist):
            render_to_string("base_legacy.html")

    def test_bootstrap_static_files_are_gone(self):
        self.assertIsNone(finders.find("bootstrap/css/bootstrap.min.css"))
