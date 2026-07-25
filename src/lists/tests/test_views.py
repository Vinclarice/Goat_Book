import lxml.html
from django.test import TestCase
from django.utils import html
from django.utils import timezone

from accounts.models import User
from lists.forms import DUPLICATE_ITEM_ERROR, EMPTY_ITEM_ERROR
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

        self.assertRedirects(response, "/dashboard/")


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

    def test_renders_active_lists_and_new_list_form(self):
        first_list = List.objects.create(owner=self.user, title="Weekend")
        Item.objects.create(list=first_list, text="Plan the weekend")
        other_user = User.objects.create_user(
            "bob",
            "bob@example.com",
            "another secure password",
        )
        hidden_list = List.objects.create(owner=other_user, title="Bob's private list")
        Item.objects.create(list=hidden_list, text="Bob's private list")

        response = self.client.get("/dashboard/")

        self.assertTemplateUsed(response, "dashboard.html")
        self.assertContains(response, "Welcome, alice.")
        self.assertContains(response, "Weekend")
        self.assertNotContains(response, "Bob&#x27;s private list")
        self.assertContains(response, '<form method="post" action="/lists/new"')
        self.assertContains(response, 'name="title"')

    def test_renders_empty_state(self):
        response = self.client.get("/dashboard/")

        self.assertContains(response, "Your first list starts here.")
        self.assertContains(response, "Done &amp; archived tasks")
        self.assertContains(
            response,
            "Tasks moved to the archive will stay here until you restore or delete them.",
        )

    def test_shows_archived_tasks_below_active_lists(self):
        active_list = List.objects.create(owner=self.user, title="Programming")
        archived_task = Item.objects.create(
            list=active_list,
            text="Finished project",
            status=Item.Status.ARCHIVED,
            completed_at=timezone.now(),
            archived_at=timezone.now(),
        )

        response = self.client.get("/dashboard/")
        content = response.content.decode()

        self.assertIn(active_list, response.context["active_lists"])
        self.assertIn(archived_task, response.context["archived_tasks"])
        self.assertLess(
            content.index("Programming"),
            content.index("Finished project"),
        )

    def test_renders_safe_archive_data_and_working_html_fallback(self):
        list_ = List.objects.create(owner=self.user, title="Programming")
        Item.objects.create(
            list=list_,
            text="</script><script>alert('no')</script>",
            status=Item.Status.ARCHIVED,
            completed_at=timezone.now(),
            archived_at=timezone.now(),
        )

        response = self.client.get("/dashboard/")

        self.assertContains(response, 'id="archive-manager-data"')
        self.assertContains(response, 'id="archive-manager-root"')
        self.assertContains(response, 'id="archive-manager-fallback"')
        self.assertContains(response, "\\u003C/script\\u003E", count=2)
        self.assertNotContains(response, "</script><script>")
        self.assertContains(response, 'action="/lists/items/1/restore"')


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

        response = self.client.post("/lists/new", data={"text": "Private item"})

        self.assertRedirects(response, "/accounts/login/?next=/lists/new")
        self.assertEqual(Item.objects.count(), 0)

    def test_saves_item_and_owner_then_redirects(self):
        response = self.client.post(
            "/lists/new",
            data={"title": "Programming", "text": "A new list item"},
        )

        new_list = List.objects.get()
        new_item = Item.objects.get()
        self.assertEqual(new_list.owner, self.user)
        self.assertEqual(new_list.title, "Programming")
        self.assertEqual(new_item.text, "A new list item")
        self.assertEqual(new_item.list, new_list)
        self.assertRedirects(response, f"/lists/{new_list.id}/")

    def test_uses_first_item_as_name_when_name_is_omitted(self):
        self.client.post(
            "/lists/new",
            data={"title": "", "text": "Plan the weekend"},
        )

        self.assertEqual(List.objects.get().title, "Plan the weekend")

    def test_invalid_input_renders_dashboard_without_saving(self):
        response = self.client.post("/lists/new", data={"text": ""})

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "dashboard.html")
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

    def create_list(self, first_item="First item"):
        list_ = List.objects.create(owner=self.user, title="My list")
        Item.objects.create(list=list_, text=first_item)
        return list_

    def test_requires_login(self):
        list_ = self.create_list()
        self.client.logout()

        response = self.client.get(f"/lists/{list_.id}/")

        self.assertRedirects(
            response,
            f"/accounts/login/?next=/lists/{list_.id}/",
        )

    def test_uses_list_template_and_renders_form(self):
        list_ = self.create_list()
        url = f"/lists/{list_.id}/"

        response = self.client.get(url)
        parsed = lxml.html.fromstring(response.content)
        forms = parsed.cssselect("form[method=post]")

        self.assertTemplateUsed(response, "list.html")
        self.assertIn(url, [form.get("action") for form in forms])
        [form] = [form for form in forms if form.get("action") == url]
        self.assertIn("text", [input_.get("name") for input_ in form.cssselect("input")])

    def test_renders_react_data_without_removing_html_fallback(self):
        list_ = self.create_list()

        response = self.client.get(f"/lists/{list_.id}/")

        self.assertContains(response, 'id="task-workspace-data"')
        self.assertContains(response, 'id="task-workspace-root"')
        self.assertContains(response, 'id="task-workspace-fallback"')
        self.assertContains(response, f'"/api/lists/{list_.id}/items/"')
        self.assertContains(response, 'name="text"')

    def test_displays_only_items_for_requested_list(self):
        correct_list = self.create_list("itemey 1")
        Item.objects.create(text="itemey 2", list=correct_list)
        other_list = self.create_list("other list item 1")

        response = self.client.get(f"/lists/{correct_list.id}/")

        self.assertContains(response, "itemey 1")
        self.assertContains(response, "itemey 2")
        self.assertNotContains(response, "other list item 1")

    def test_displays_creation_time_and_hides_archived_items(self):
        list_ = self.create_list("Visible item")
        visible_item = list_.item_set.get(text="Visible item")
        Item.objects.create(
            list=list_,
            text="Archived item",
            status=Item.Status.ARCHIVED,
            completed_at=timezone.now(),
            archived_at=timezone.now(),
        )

        response = self.client.get(f"/lists/{list_.id}/")

        self.assertContains(
            response,
            visible_item.created_at.strftime("%b").replace(" 0", " "),
        )
        self.assertContains(response, "Created")
        self.assertNotContains(response, "Archived item")

    def test_user_cannot_view_or_edit_another_users_list(self):
        other_user = User.objects.create_user(
            "bob",
            "bob@example.com",
            "another secure password",
        )
        other_list = List.objects.create(owner=other_user)
        Item.objects.create(list=other_list, text="Bob's private item")

        get_response = self.client.get(f"/lists/{other_list.id}/")
        post_response = self.client.post(
            f"/lists/{other_list.id}/",
            data={"text": "Intruding item"},
        )

        self.assertEqual(get_response.status_code, 404)
        self.assertEqual(post_response.status_code, 404)
        self.assertEqual(other_list.item_set.count(), 1)

    def test_can_save_to_an_existing_list_and_redirect(self):
        list_ = self.create_list()

        response = self.client.post(
            f"/lists/{list_.id}/",
            data={"text": "A new item for an existing list"},
        )

        self.assertTrue(
            list_.item_set.filter(text="A new item for an existing list").exists()
        )
        self.assertRedirects(response, f"/lists/{list_.id}/")

    def test_invalid_input_stays_on_list_and_shows_error(self):
        list_ = self.create_list()

        response = self.client.post(f"/lists/{list_.id}/", data={"text": ""})
        parsed = lxml.html.fromstring(response.content)
        [input_] = parsed.cssselect("input[name=text]")

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "list.html")
        self.assertContains(response, html.escape(EMPTY_ITEM_ERROR))
        self.assertIn("is-invalid", set(input_.classes))

    def test_duplicate_item_shows_validation_error(self):
        list_ = self.create_list("no twins")

        response = self.client.post(
            f"/lists/{list_.id}/",
            data={"text": "no twins"},
        )

        self.assertContains(response, html.escape(DUPLICATE_ITEM_ERROR))
        self.assertTemplateUsed(response, "list.html")
        self.assertEqual(list_.item_set.count(), 1)


class ListManagementTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "alice",
            "alice@example.com",
            "a secure password",
        )
        self.other_user = User.objects.create_user(
            "bob",
            "bob@example.com",
            "another secure password",
        )
        self.client.force_login(self.user)
        self.list_ = List.objects.create(owner=self.user, title="Programming")

    def test_owner_can_rename_list(self):
        response = self.client.post(
            f"/lists/{self.list_.id}/rename",
            data={"title": "Work"},
        )

        self.list_.refresh_from_db()
        self.assertEqual(self.list_.title, "Work")
        self.assertRedirects(response, self.list_.get_absolute_url())

    def test_blank_name_is_rejected_without_changing_list(self):
        response = self.client.post(
            f"/lists/{self.list_.id}/rename",
            data={"title": "   "},
        )

        self.list_.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.list_.title, "Programming")
        self.assertContains(response, "Give this list a name")

    def test_user_cannot_rename_another_users_list(self):
        private_list = List.objects.create(
            owner=self.other_user,
            title="Private",
        )

        response = self.client.post(
            f"/lists/{private_list.id}/rename",
            data={"title": "Stolen"},
        )

        private_list.refresh_from_db()
        self.assertEqual(response.status_code, 404)
        self.assertEqual(private_list.title, "Private")

    def test_management_actions_require_post(self):
        response = self.client.get(f"/lists/{self.list_.id}/rename")

        self.assertEqual(response.status_code, 405)

    def test_delete_confirmation_shows_task_counts_then_deletes(self):
        Item.objects.create(list=self.list_, text="Open")
        Item.objects.create(
            list=self.list_,
            text="Completed",
            status=Item.Status.COMPLETED,
            completed_at=timezone.now(),
        )

        confirmation = self.client.get(f"/lists/{self.list_.id}/delete")

        self.assertContains(confirmation, "Delete this list?")
        self.assertContains(confirmation, "This cannot be undone.")
        response = self.client.post(f"/lists/{self.list_.id}/delete")

        self.assertRedirects(response, "/dashboard/")
        self.assertFalse(List.objects.filter(pk=self.list_.pk).exists())

    def test_user_cannot_delete_another_users_list(self):
        private_list = List.objects.create(
            owner=self.other_user,
            title="Private",
        )

        response = self.client.post(f"/lists/{private_list.id}/delete")

        self.assertEqual(response.status_code, 404)
        self.assertTrue(List.objects.filter(pk=private_list.pk).exists())


class TaskManagementTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "alice",
            "alice@example.com",
            "a secure password",
        )
        self.other_user = User.objects.create_user(
            "bob",
            "bob@example.com",
            "another secure password",
        )
        self.client.force_login(self.user)
        self.list_ = List.objects.create(owner=self.user, title="Programming")
        self.item = Item.objects.create(list=self.list_, text="Write tests")

    def test_marks_task_complete_but_keeps_it_in_the_list(self):
        response = self.client.post(
            f"/lists/items/{self.item.id}/complete",
        )

        self.item.refresh_from_db()
        self.assertEqual(self.item.status, Item.Status.COMPLETED)
        self.assertIsNotNone(self.item.completed_at)
        self.assertRedirects(response, self.list_.get_absolute_url())

        list_response = self.client.get(self.list_.get_absolute_url())
        self.assertContains(list_response, "Write tests")
        self.assertContains(list_response, "Reopen")

    def test_reopens_completed_task(self):
        self.item.status = Item.Status.COMPLETED
        self.item.completed_at = timezone.now()
        self.item.save()

        response = self.client.post(
            f"/lists/items/{self.item.id}/reopen",
        )

        self.item.refresh_from_db()
        self.assertEqual(self.item.status, Item.Status.ACTIVE)
        self.assertIsNone(self.item.completed_at)
        self.assertRedirects(response, self.list_.get_absolute_url())

    def test_complete_and_archive_moves_task_out_of_list(self):
        response = self.client.post(
            f"/lists/items/{self.item.id}/archive",
        )

        self.item.refresh_from_db()
        self.assertEqual(self.item.status, Item.Status.ARCHIVED)
        self.assertIsNotNone(self.item.completed_at)
        self.assertIsNotNone(self.item.archived_at)
        self.assertRedirects(response, self.list_.get_absolute_url())

        list_response = self.client.get(self.list_.get_absolute_url())
        dashboard_response = self.client.get("/dashboard/")
        self.assertNotContains(list_response, "Write tests")
        self.assertContains(dashboard_response, "Write tests")

    def test_restores_archived_task_as_completed(self):
        self.item.status = Item.Status.ARCHIVED
        self.item.completed_at = timezone.now()
        self.item.archived_at = timezone.now()
        self.item.save()

        response = self.client.post(
            f"/lists/items/{self.item.id}/restore",
        )

        self.item.refresh_from_db()
        self.assertEqual(self.item.status, Item.Status.COMPLETED)
        self.assertIsNone(self.item.archived_at)
        self.assertRedirects(response, "/dashboard/")

    def test_does_not_restore_when_same_active_task_exists(self):
        self.item.status = Item.Status.ARCHIVED
        self.item.completed_at = timezone.now()
        self.item.archived_at = timezone.now()
        self.item.save()
        Item.objects.create(list=self.list_, text=self.item.text)

        response = self.client.post(
            f"/lists/items/{self.item.id}/restore",
            follow=True,
        )

        self.item.refresh_from_db()
        self.assertEqual(self.item.status, Item.Status.ARCHIVED)
        self.assertContains(
            response,
            "That task already exists in its original list",
        )

    def test_delete_requires_confirmation_and_only_deletes_after_post(self):
        self.item.status = Item.Status.ARCHIVED
        self.item.completed_at = timezone.now()
        self.item.archived_at = timezone.now()
        self.item.save()
        url = f"/lists/items/{self.item.id}/delete"

        confirmation = self.client.get(url)

        self.assertContains(confirmation, "Delete this task?")
        self.assertContains(confirmation, "This cannot be undone.")
        self.assertTrue(Item.objects.filter(id=self.item.id).exists())

        response = self.client.post(url)

        self.assertRedirects(response, "/dashboard/")
        self.assertFalse(Item.objects.filter(id=self.item.id).exists())

    def test_unarchived_task_cannot_be_permanently_deleted(self):
        response = self.client.post(
            f"/lists/items/{self.item.id}/delete",
        )

        self.assertEqual(response.status_code, 404)
        self.assertTrue(Item.objects.filter(id=self.item.id).exists())

    def test_user_cannot_change_another_users_task(self):
        private_list = List.objects.create(
            owner=self.other_user,
            title="Private",
        )
        private_item = Item.objects.create(
            list=private_list,
            text="Private task",
            status=Item.Status.ARCHIVED,
            completed_at=timezone.now(),
            archived_at=timezone.now(),
        )
        actions = ("complete", "reopen", "archive", "restore", "delete")

        for action in actions:
            with self.subTest(action=action):
                response = self.client.post(
                    f"/lists/items/{private_item.id}/{action}",
                )
                self.assertEqual(response.status_code, 404)

    def test_task_state_changes_require_post(self):
        for action in ("complete", "reopen", "archive", "restore"):
            with self.subTest(action=action):
                response = self.client.get(
                    f"/lists/items/{self.item.id}/{action}",
                )
                self.assertEqual(response.status_code, 405)

    def test_owner_can_edit_task_text(self):
        response = self.client.post(
            f"/lists/items/{self.item.id}/edit",
            data={"text": "Write better tests"},
        )

        self.item.refresh_from_db()
        self.assertEqual(self.item.text, "Write better tests")
        self.assertRedirects(response, self.list_.get_absolute_url())

    def test_user_cannot_edit_another_users_task(self):
        private_list = List.objects.create(
            owner=self.other_user,
            title="Private",
        )
        private_item = Item.objects.create(list=private_list, text="Private")

        response = self.client.post(
            f"/lists/items/{private_item.id}/edit",
            data={"text": "Changed"},
        )

        self.assertEqual(response.status_code, 404)
        private_item.refresh_from_db()
        self.assertEqual(private_item.text, "Private")
