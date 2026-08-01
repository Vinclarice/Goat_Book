"""B2: ending a session from inside the SPA.

The Django base.html has always had a POST logout form, but the SPA is
served by app_shell.html and rendered neither that form nor any control of
its own -- so a user could change their password or mint a token from the
SPA and still had nowhere to log out.

An endpoint rather than a copied template form: the typed client already
sends X-CSRFToken on non-GET requests, Django's own logout() keeps its
session-invalidation behaviour, and the SPA gets a success/failure contract
to decide on before it navigates away.
"""
import json

from django.test import Client, TestCase

from accounts.models import User


PASSWORD = "correct horse battery staple 47!"


class LogoutEndpointTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", PASSWORD
        )
        # enforce_csrf_checks, because the whole point of this endpoint is
        # that it stays a CSRF-protected POST. The default test client
        # disables that and would pass regardless.
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.user)
        response = self.client.get("/accounts/password/change/")
        self.csrf_token = response.cookies["csrftoken"].value

    def logout(self, csrf=True):
        headers = {"HTTP_X_CSRFTOKEN": self.csrf_token} if csrf else {}
        return self.client.post(
            "/api/v1/me/logout",
            data=json.dumps({}),
            content_type="application/json",
            **headers,
        )

    def test_logs_the_session_out_and_returns_no_content(self):
        response = self.logout()

        self.assertEqual(response.status_code, 204)

    def test_the_session_is_really_gone_afterwards(self):
        # The assertion that matters: not that the endpoint answered, but
        # that the credential it invalidated no longer opens anything.
        self.assertEqual(self.client.get("/api/v1/me").status_code, 200)

        self.logout()

        self.assertEqual(self.client.get("/api/v1/me").status_code, 401)

    def test_rejects_an_anonymous_caller(self):
        # Given a *valid* CSRF token, so this isolates "no session" rather
        # than also failing the CSRF check. Ninja's SessionAuth runs that
        # check before it looks for a session (see accounts.auth), so an
        # anonymous caller with no token gets 403 for the other reason --
        # covered separately below.
        anonymous = Client(enforce_csrf_checks=True)
        token = anonymous.get("/accounts/login/").cookies["csrftoken"].value

        response = anonymous.post(
            "/api/v1/me/logout",
            data=json.dumps({}),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
        )

        self.assertEqual(response.status_code, 401)

    def test_rejects_an_anonymous_caller_with_no_csrf_token_either(self):
        anonymous = Client(enforce_csrf_checks=True)

        response = anonymous.post(
            "/api/v1/me/logout",
            data=json.dumps({}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)

    def test_rejects_a_post_without_a_csrf_token(self):
        response = self.logout(csrf=False)

        self.assertEqual(response.status_code, 403)
        # And the session survives a rejected attempt, so a cross-site POST
        # cannot log someone out as a nuisance.
        self.assertEqual(self.client.get("/api/v1/me").status_code, 200)

    def test_is_not_reachable_by_get(self):
        # A logout that a GET can trigger is one a prefetch or a crawler can
        # trigger.
        response = self.client.get("/api/v1/me/logout")

        self.assertIn(response.status_code, (404, 405))
        self.assertEqual(self.client.get("/api/v1/me").status_code, 200)


class AppShellCsrfCookieTest(TestCase):
    """The SPA can only send X-CSRFToken if something gave it the cookie.

    Before this, that depended on the user having passed through a
    Django-rendered form -- true in practice via the login page, but an
    accident rather than a guarantee, and one that breaks the moment login
    moves into the SPA.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", PASSWORD
        )
        self.client.force_login(self.user)

    def test_the_shell_hands_out_a_csrf_cookie(self):
        response = self.client.get("/app/agenda")

        self.assertEqual(response.status_code, 200)
        self.assertIn("csrftoken", response.cookies)
