"""Shared setup for the browser smoke suite.

These tests exist to cover the seams nothing else does. Django's tests use
the test client, which never parses HTML, runs JavaScript, or holds a
cookie jar the way a browser does; the Vitest suite renders React into
jsdom with `fetch` stubbed, so it never touches routing, the built bundle,
static file serving, or a real session. Everything between those two --
which is most of what a person actually uses -- was untested until now.

They are deliberately a separate test label rather than part of
`accounts lists capture clarice`. They need a built frontend bundle and a
browser binary, neither of which an ordinary edit-and-test loop should
require. See design/bittern-plan.md, B2.2, and README.md.
"""
import os

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from playwright.sync_api import expect, sync_playwright

from accounts.models import User


PASSWORD = "a browser test password 8812!"

# Generous, because CI runners are slower than laptops and the failure this
# guards against is a flaky suite, which is worse than a slow one: a smoke
# test nobody trusts gets ignored, and then it is not a smoke test.
TIMEOUT_MS = 10_000

# expect() keeps its own timeout, separate from the context's, and defaults
# to 5s -- so without this the assertions would be the flakiest thing in a
# suite whose whole value is being trusted.
expect.set_options(timeout=TIMEOUT_MS)


class BrowserTest(StaticLiveServerTestCase):
    """A real browser against a real server, with real static files.

    StaticLiveServerTestCase rather than LiveServerTestCase: the SPA is a
    built bundle served from `src/lists/static/frontend/`, and a test that
    silently served no JavaScript would pass an empty page and prove
    nothing.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._playwright = sync_playwright().start()
        cls.browser = cls._playwright.chromium.launch(
            headless=os.environ.get("HEADED") != "1",
        )

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls._playwright.stop()
        super().tearDownClass()

    # None means the browser's default desktop window. A subclass sets this
    # to open every page at a phone's width instead -- see PhoneTest.
    viewport = None

    def setUp(self):
        super().setUp()
        # A fresh context per test, so a session from one journey can never
        # authenticate another -- the logout test in particular would pass
        # for the wrong reason if cookies leaked between them.
        self.context = self.browser.new_context(
            **({"viewport": self.viewport} if self.viewport else {})
        )
        self.context.set_default_timeout(TIMEOUT_MS)
        self.page = self.context.new_page()
        self.addCleanup(self.context.close)

    def visit(self, path):
        self.page.goto(f"{self.live_server_url}{path}")

    def horizontal_overflow(self):
        """How far the page scrolls sideways, in pixels. Zero is the answer.

        Measured on documentElement rather than body because the overflow
        usually comes from a child that is wider than the viewport, and the
        document is what ends up scrollable when it does.
        """
        return self.page.evaluate(
            "document.documentElement.scrollWidth"
            " - document.documentElement.clientWidth"
        )

    def overflowing_elements(self):
        """Which elements are wider than the viewport, for a useful failure.

        A bare "the page scrolls sideways" tells you there is a problem and
        nothing about where, which on a page of six sections is most of the
        work. Returns the widest offenders, innermost first.
        """
        return self.page.evaluate(
            """() => {
                const limit = document.documentElement.clientWidth;
                return [...document.querySelectorAll('body *')]
                    .map(el => ({
                        tag: el.tagName.toLowerCase(),
                        id: el.id || null,
                        cls: (el.className && typeof el.className === 'string')
                            ? el.className.slice(0, 60) : null,
                        right: Math.round(el.getBoundingClientRect().right),
                    }))
                    .filter(el => el.right > limit + 1)
                    .sort((a, b) => b.right - a.right)
                    .slice(0, 8);
            }"""
        )

    def make_user(self, username="edith"):
        return User.objects.create_user(
            username, f"{username}@example.com", PASSWORD
        )

    def log_in(self, user):
        """Through the real login form, not by forcing a session cookie.

        force_login() would be faster and would skip the thing most worth
        covering: that the form, its CSRF token, and the session cookie
        actually work together in a browser.
        """
        self.visit("/accounts/login/")
        self.page.fill("#id_username", user.username)
        self.page.fill("#id_password", PASSWORD)
        self.page.click("button[type=submit]")
        expect(self.page).not_to_have_url(
            f"{self.live_server_url}/accounts/login/"
        )
