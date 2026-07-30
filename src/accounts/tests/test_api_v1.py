from django.test import TestCase

from accounts.models import User


class MeEndpointTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "alice",
            "alice@example.com",
            "a secure password",
        )

    def test_returns_the_logged_in_user(self):
        self.client.force_login(self.user)

        response = self.client.get("/api/v1/me")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"username": "alice", "email": "alice@example.com"},
        )

    def test_rejects_anonymous_requests(self):
        response = self.client.get("/api/v1/me")

        self.assertEqual(response.status_code, 401)
