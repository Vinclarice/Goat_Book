from django.test import TestCase

from accounts.models import User


PASSWORD = "correct horse battery staple 47!"


class UserAdminTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            "admin", "admin@example.com", PASSWORD
        )
        self.client.force_login(self.admin)

    def test_user_changelist_renders(self):
        response = self.client.get("/admin/accounts/user/")
        self.assertEqual(response.status_code, 200)

    def test_user_add_page_renders(self):
        response = self.client.get("/admin/accounts/user/add/")
        self.assertEqual(response.status_code, 200)

    def test_approving_a_pending_user_via_the_change_form(self):
        pending = User.objects.create_user(
            "edith", "edith@example.com", PASSWORD, is_active=False
        )

        response = self.client.get(f"/admin/accounts/user/{pending.pk}/change/")
        self.assertEqual(response.status_code, 200)

        response = self.client.post(
            f"/admin/accounts/user/{pending.pk}/change/",
            data={
                "username": "edith",
                "email": "edith@example.com",
                "is_active": "on",
                "initial-last_login": "",
                "date_joined_0": "",
                "date_joined_1": "",
            },
        )

        pending.refresh_from_db()
        self.assertTrue(pending.is_active)
