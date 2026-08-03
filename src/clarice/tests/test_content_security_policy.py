"""A content security policy, in report-only mode to begin with.

architecture-trajectory.md 6 carried this as the genuine remaining gap:
X-Frame-Options and content-type-nosniff are already covered by
XFrameOptionsMiddleware and SecurityMiddleware, and CSP was not.

**Report-only deliberately.** A policy tight enough to be worth having can
break the application, and report-only says so in the browser console without
costing anyone a page. What it is *not* is a way to defer knowing: the one
inline script this application has -- the theme resolution script, which must
run before first paint to avoid a flash of the wrong theme -- is handled with
a nonce here rather than left to be discovered as a violation nobody was
surprised by.

`style-src` keeps 'unsafe-inline' and that is not an oversight. app_shell.html
carries an inline <style> block, and React writes inline style attributes for
the area colour dots. A nonce cannot cover a style *attribute*, so removing
'unsafe-inline' would mean a refactor for a much narrower class of attack than
script injection. Stated rather than silently accepted.
"""
import re

from django.test import TestCase

from accounts.models import User


HEADER = "Content-Security-Policy-Report-Only"


class ContentSecurityPolicyHeaderTest(TestCase):
    def test_the_policy_is_report_only_for_now(self):
        response = self.client.get("/")

        self.assertIn(HEADER, response)
        # The enforcing header must not appear yet: shipping both would make
        # the report-only one pointless and could break a page.
        self.assertNotIn("Content-Security-Policy", response.headers.keys())

    def test_it_locks_down_the_directives_that_matter(self):
        policy = self.client.get("/").headers[HEADER]

        self.assertIn("default-src 'self'", policy)
        self.assertIn("object-src 'none'", policy)
        self.assertIn("frame-ancestors 'none'", policy)
        self.assertIn("base-uri 'self'", policy)
        self.assertIn("form-action 'self'", policy)

    def test_scripts_are_not_blanket_inline(self):
        """The point of the whole exercise.

        script-src 'unsafe-inline' would leave the policy worth almost
        nothing against injected script, which is the attack CSP exists for.
        """
        policy = self.client.get("/").headers[HEADER]

        script_src = re.search(r"script-src ([^;]+)", policy).group(1)
        self.assertNotIn("unsafe-inline", script_src)
        self.assertIn("'self'", script_src)

    def test_styles_allow_inline_and_say_why(self):
        policy = self.client.get("/").headers[HEADER]

        style_src = re.search(r"style-src ([^;]+)", policy).group(1)
        self.assertIn("unsafe-inline", style_src)


class ThemeScriptNonceTest(TestCase):
    """The inline theme script is allowed by name, not by blanket permission."""

    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )

    def nonce_from(self, policy):
        found = re.search(r"'nonce-([A-Za-z0-9_-]+)'", policy)
        self.assertIsNotNone(found, f"no nonce in {policy}")
        return found.group(1)

    def test_the_landing_page_script_carries_the_policy_s_nonce(self):
        response = self.client.get("/")

        nonce = self.nonce_from(response.headers[HEADER])
        self.assertContains(response, f'<script nonce="{nonce}"')

    def test_the_app_shell_script_carries_it_too(self):
        self.client.force_login(self.user)

        response = self.client.get("/app/agenda")

        nonce = self.nonce_from(response.headers[HEADER])
        self.assertContains(response, f'<script nonce="{nonce}"')

    def test_a_fresh_nonce_per_request(self):
        """A reused nonce is barely better than 'unsafe-inline': an attacker
        who can read one page could reuse it in an injection on the next.
        """
        first = self.nonce_from(self.client.get("/").headers[HEADER])
        second = self.nonce_from(self.client.get("/").headers[HEADER])

        self.assertNotEqual(first, second)
