"""Personal access tokens: the model, and the page you manage them from.

The endpoint they exist to authenticate lives in capture/tests/test_api_v1.py.
"""
from django.test import TestCase
from django.urls import reverse

from accounts.models import PersonalAccessToken, User, hash_token


PASSWORD = "correct horse battery staple 47!"


class TokenModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", PASSWORD
        )

    def test_stores_only_a_hash_of_the_raw_value(self):
        token, raw = PersonalAccessToken.generate(self.user, label="Phone")

        self.assertEqual(token.token_hash, hash_token(raw))
        # The one thing that must never be true of this table.
        self.assertNotIn(raw, str(PersonalAccessToken.objects.values().first()))

    def test_every_token_is_different(self):
        _, first = PersonalAccessToken.generate(self.user)
        _, second = PersonalAccessToken.generate(self.user)

        self.assertNotEqual(first, second)

    def test_a_label_is_optional(self):
        token, _ = PersonalAccessToken.generate(self.user)

        self.assertEqual(token.label, "")


class TokenPageTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", PASSWORD
        )
        self.client.force_login(self.user)

    def test_requires_login(self):
        self.client.logout()

        response = self.client.get(reverse("tokens"))

        self.assertRedirects(
            response, f"{reverse('login')}?next={reverse('tokens')}"
        )

    def test_creating_a_token_shows_the_raw_value_exactly_once(self):
        created = self.client.post(
            reverse("new_token"), data={"label": "Phone"}, follow=True
        )
        raw = created.context["raw_token"]

        self.assertIsNotNone(raw)
        self.assertContains(created, raw)

        # Second load of the same page: gone for good.
        again = self.client.get(reverse("tokens"))

        self.assertIsNone(again.context["raw_token"])
        self.assertNotContains(again, raw)

    def test_the_created_token_actually_works(self):
        # Belt and braces on the above: the value shown has to be the one
        # that authenticates, not merely some random string.
        created = self.client.post(
            reverse("new_token"), data={"label": "Phone"}, follow=True
        )

        self.assertEqual(
            PersonalAccessToken.objects.get(owner=self.user).token_hash,
            hash_token(created.context["raw_token"]),
        )

    def test_lists_only_your_own_tokens(self):
        intruder = User.objects.create_user(
            "bob", "bob@example.com", PASSWORD
        )
        PersonalAccessToken.generate(self.user, label="Mine")
        PersonalAccessToken.generate(intruder, label="Theirs")

        response = self.client.get(reverse("tokens"))

        self.assertContains(response, "Mine")
        self.assertNotContains(response, "Theirs")

    def test_revoking_deletes_the_row(self):
        token, _ = PersonalAccessToken.generate(self.user)

        self.client.post(reverse("delete_token", args=[token.id]))

        self.assertFalse(PersonalAccessToken.objects.filter(pk=token.pk).exists())

    def test_an_intruder_cannot_revoke_someone_elses_token(self):
        # The one id-addressable surface this feature adds -- same
        # discipline as lists/tests/test_isolation.py, 404 rather than 403.
        owner = User.objects.create_user("bob", "bob@example.com", PASSWORD)
        token, _ = PersonalAccessToken.generate(owner, label="Theirs")

        response = self.client.post(reverse("delete_token", args=[token.id]))

        self.assertEqual(response.status_code, 404)
        self.assertTrue(PersonalAccessToken.objects.filter(pk=token.pk).exists())

    def test_the_token_page_rejects_a_get_on_the_mutating_routes(self):
        token, _ = PersonalAccessToken.generate(self.user)

        self.assertEqual(self.client.get(reverse("new_token")).status_code, 405)
        self.assertEqual(
            self.client.get(reverse("delete_token", args=[token.id])).status_code,
            405,
        )
