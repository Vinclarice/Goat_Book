from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from lists.models import Item, List


class LandingPageTest(TestCase):
    def test_renders_a_landing_page_that_is_not_the_login_form(self):
        """product-stories.md S1, in one assertion.

        Its requires line ends "a landing page that is not a login form", and
        the page it scored greeted a stranger with a username field under the
        words "Welcome back". The form still exists at /accounts/login/; what
        must not be here is a password field, because its presence is the whole
        defect.
        """
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/landing.html")
        self.assertNotContains(response, 'type="password"')
        self.assertContains(response, "Most task apps forget what you promised.")

    def test_the_landing_page_says_how_to_ask_for_an_account(self):
        """A page that explains the product and offers no way in is a
        different failure from the one above, and just as complete."""
        response = self.client.get("/")

        self.assertContains(response, reverse("signup"))
        self.assertContains(response, reverse("login"))

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


# `class NewListTest` stood here until August 30, 2026 and is gone with the
# view it tested -- coherence-audit-2026-08-30.md F1 retired `new_list` for
# `POST /api/v1/areas`. **The coverage moved rather than went**: every case
# it made is remade in lists.tests.test_api_v1.CreateAreaEndpointTest --
# named area with a first task, the title falling back to the task's text,
# an empty task saving nothing, and anonymous requests refused.


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
