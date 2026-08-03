from django.test import TestCase
from django.utils import html

from accounts.models import User
from lists.forms import EMPTY_ITEM_ERROR
from lists.models import Item, List


class LandingPageTest(TestCase):
    def test_renders_welcome_page_with_login(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/login.html")
        self.assertContains(response, "Welcome back to what matters.")
        self.assertContains(response, 'name="username"')
        self.assertNotContains(response, 'name="text"')

    def test_authenticated_user_is_sent_to_dashboard(self):
        user = User.objects.create_user(
            "alice",
            "alice@example.com",
            "a secure password",
        )
        self.client.force_login(user)

        response = self.client.get("/")

        self.assertRedirects(
            response, "/dashboard/", target_status_code=302,
        )


class DashboardTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "alice",
            "alice@example.com",
            "a secure password",
        )
        self.client.force_login(self.user)

    def test_requires_login(self):
        self.client.logout()

        response = self.client.get("/dashboard/")

        self.assertRedirects(response, "/accounts/login/?next=/dashboard/")

    def test_redirects_to_the_surface_the_user_landed_on(self):
        """Crane 1 slice 6 moved this from a fixed route to a preference.

        It used to assert /app/agenda unconditionally. The Daily Page is now
        the default home surface, and this view is the one place that
        decides -- so both answers are asserted here rather than only the
        new one. Reaching either surface directly is covered in
        daily/tests/test_landing.py.
        """
        response = self.client.get("/dashboard/")

        self.assertRedirects(
            response, "/app/day", fetch_redirect_response=False,
        )

        self.user.landing_surface = User.LandingSurface.AGENDA
        self.user.save(update_fields=["landing_surface"])

        response = self.client.get("/dashboard/")

        self.assertRedirects(
            response, "/app/agenda", fetch_redirect_response=False,
        )


class NewListTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "alice",
            "alice@example.com",
            "a secure password",
        )
        self.client.force_login(self.user)

    def test_requires_login(self):
        self.client.logout()

        response = self.client.post("/areas/new", data={"text": "Private item"})

        self.assertRedirects(response, "/accounts/login/?next=/areas/new")
        self.assertEqual(Item.objects.count(), 0)

    def test_saves_item_and_owner_then_redirects(self):
        response = self.client.post(
            "/areas/new",
            data={"title": "Programming", "text": "A new list item"},
        )

        new_list = List.objects.get()
        new_item = Item.objects.get()
        self.assertEqual(new_list.owner, self.user)
        self.assertEqual(new_list.title, "Programming")
        self.assertEqual(new_item.text, "A new list item")
        self.assertEqual(new_item.list, new_list)
        self.assertRedirects(
            response, f"/areas/{new_list.id}/", target_status_code=302,
        )

    def test_uses_first_item_as_name_when_name_is_omitted(self):
        self.client.post(
            "/areas/new",
            data={"title": "", "text": "Plan the weekend"},
        )

        self.assertEqual(List.objects.get().title, "Plan the weekend")

    def test_invalid_input_renders_the_new_list_form_without_saving(self):
        response = self.client.post("/areas/new", data={"text": ""})

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "new_list_form.html")
        self.assertContains(response, html.escape(EMPTY_ITEM_ERROR))
        self.assertEqual(Item.objects.count(), 0)
        self.assertEqual(List.objects.count(), 0)


class ListViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "alice",
            "alice@example.com",
            "a secure password",
        )
        self.client.force_login(self.user)

    def create_list(self):
        list_ = List.objects.create(owner=self.user, title="My list")
        Item.objects.create(list=list_, text="First item")
        return list_

    def test_requires_login(self):
        list_ = self.create_list()
        self.client.logout()

        response = self.client.get(f"/areas/{list_.id}/")

        self.assertRedirects(
            response,
            f"/accounts/login/?next=/areas/{list_.id}/",
        )

    def test_redirects_to_the_spa_list_route(self):
        list_ = self.create_list()

        response = self.client.get(f"/areas/{list_.id}/")

        self.assertRedirects(
            response, f"/app/areas/{list_.id}", fetch_redirect_response=False,
        )


class TaskDetailRedirectTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "alice",
            "alice@example.com",
            "a secure password",
        )
        self.client.force_login(self.user)
        self.list_ = List.objects.create(owner=self.user, title="Programming")
        self.item = Item.objects.create(list=self.list_, text="Write tests")

    def test_requires_login(self):
        self.client.logout()

        response = self.client.get(f"/areas/items/{self.item.id}/edit")

        self.assertRedirects(
            response,
            f"/accounts/login/?next=/areas/items/{self.item.id}/edit",
        )

    def test_redirects_to_the_spa_task_route(self):
        response = self.client.get(f"/areas/items/{self.item.id}/edit")

        self.assertRedirects(
            response, f"/app/tasks/{self.item.id}", fetch_redirect_response=False,
        )
