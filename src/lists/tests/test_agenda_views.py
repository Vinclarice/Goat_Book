from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from lists.models import Item, List, Tag


class AgendaViewTest(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.user = User.objects.create_user(
            "vince", "vince@example.com", "sekrit-password"
        )
        self.client.force_login(self.user)
        self.work = List.objects.create(owner=self.user, title="Work")
        self.home = List.objects.create(owner=self.user, title="Home")

    def make(self, text, due_offset=None, for_list=None):
        return Item.objects.create(
            list=for_list or self.work,
            text=text,
            due_date=(
                None
                if due_offset is None
                else self.today + timedelta(days=due_offset)
            ),
        )

    def test_uses_agenda_template(self):
        response = self.client.get("/dashboard/")

        self.assertTemplateUsed(response, "agenda.html")

    def test_shows_tasks_from_every_list_grouped_by_due_date(self):
        self.make("Renew insurance", due_offset=-4)
        self.make("Buy milk", due_offset=0, for_list=self.home)

        response = self.client.get("/dashboard/")
        buckets = {b["key"]: b for b in response.context["buckets"]}

        self.assertEqual(
            [i.text for i in buckets["overdue"]["items"]], ["Renew insurance"]
        )
        self.assertEqual([i.text for i in buckets["today"]["items"]], ["Buy milk"])

    def test_overdue_row_says_how_late_it_is(self):
        self.make("Renew insurance", due_offset=-4)

        response = self.client.get("/dashboard/")

        self.assertContains(response, "4 days overdue")

    def test_one_day_overdue_reads_as_yesterday(self):
        self.make("Call back", due_offset=-1)

        response = self.client.get("/dashboard/")

        self.assertContains(response, "Yesterday")

    def test_far_off_buckets_start_collapsed(self):
        self.make("Someday", due_offset=None)
        self.make("Distant", due_offset=40)
        self.make("Now", due_offset=0)

        response = self.client.get("/dashboard/")
        collapsed = {
            b["key"]: b["collapsed"] for b in response.context["buckets"]
        }

        self.assertTrue(collapsed["later"])
        self.assertTrue(collapsed["someday"])
        self.assertFalse(collapsed["today"])

    def test_filtering_expands_every_bucket_it_returns(self):
        self.make("Distant", due_offset=40)

        response = self.client.get("/dashboard/?scope=week")
        response = self.client.get(f"/dashboard/?list={self.work.id}")
        collapsed = {
            b["key"]: b["collapsed"] for b in response.context["buckets"]
        }

        self.assertFalse(collapsed["later"])

    def test_scope_filter_narrows_rows_but_not_the_headline_counts(self):
        self.make("Late", due_offset=-2)
        self.make("Soon", due_offset=3)

        response = self.client.get("/dashboard/?scope=overdue")

        self.assertEqual(response.context["visible_count"], 1)
        self.assertEqual(response.context["counts"]["open"], 2)

    def test_unknown_filter_values_are_ignored(self):
        self.make("Something", due_offset=0)

        response = self.client.get("/dashboard/?scope=nonsense&list=999999")

        self.assertEqual(response.context["filters"]["scope"], None)
        self.assertEqual(response.context["filters"]["list"], None)
        self.assertEqual(response.context["visible_count"], 1)

    def test_cannot_filter_by_another_users_list(self):
        other = User.objects.create_user(
            "someone", "someone@example.com", "sekrit-password"
        )
        theirs = List.objects.create(owner=other, title="Theirs")
        self.make("Mine", due_offset=0)

        response = self.client.get(f"/dashboard/?list={theirs.id}")

        self.assertIsNone(response.context["filters"]["list"])
        self.assertEqual(response.context["visible_count"], 1)

    def test_tag_filter_narrows_rows(self):
        errand = Tag.objects.create(owner=self.user, name="errand")
        self.make("Post office", due_offset=0).tags.add(errand)
        self.make("Write code", due_offset=0)

        response = self.client.get("/dashboard/?tag=errand")

        self.assertEqual(response.context["visible_count"], 1)

    def test_sidebar_lists_carry_open_and_overdue_counts(self):
        self.make("Late", due_offset=-1)
        self.make("Chores", for_list=self.home)

        response = self.client.get("/dashboard/")
        by_title = {each.title: each for each in response.context["agenda_lists"]}

        self.assertEqual(by_title["Work"].overdue_count, 1)
        self.assertEqual(by_title["Home"].open_count, 1)

    def test_completed_today_is_listed_so_it_can_be_undone(self):
        item = self.make("Ticked", due_offset=0)
        self.client.post(f"/lists/items/{item.id}/complete", {"next": "/dashboard/"})

        response = self.client.get("/dashboard/")

        self.assertEqual(
            [i.text for i in response.context["completed_today"]], ["Ticked"]
        )

    def test_bootstrap_payload_matches_the_rendered_agenda(self):
        self.make("Late", due_offset=-1)
        self.make("Chores", for_list=self.home)

        data = self.client.get("/dashboard/").context["agenda_workspace_data"]

        self.assertEqual(data["today"], self.today.isoformat())
        self.assertEqual(len(data["items"]), 2)
        self.assertEqual(len(data["lists"]), 2)
        self.assertEqual(data["username"], "vince")
        self.assertIn("create_item_url", data["lists"][0])

    def test_empty_agenda_invites_a_first_list(self):
        List.objects.all().delete()

        response = self.client.get("/dashboard/")

        self.assertContains(response, "Start your first list")

    def test_login_is_required(self):
        self.client.logout()

        response = self.client.get("/dashboard/")

        self.assertRedirects(response, "/accounts/login/?next=/dashboard/")


class QuickAddTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "vince", "vince@example.com", "sekrit-password"
        )
        self.client.force_login(self.user)
        self.work = List.objects.create(owner=self.user, title="Work")

    def test_adds_a_task_to_the_chosen_list(self):
        self.client.post(
            "/lists/add",
            {"text": "Ship the fix", "list": self.work.id, "due_date": ""},
        )

        item = Item.objects.get()
        self.assertEqual(item.text, "Ship the fix")
        self.assertEqual(item.list, self.work)

    def test_stores_the_due_date(self):
        due = timezone.localdate() + timedelta(days=2)

        self.client.post(
            "/lists/add",
            {
                "text": "Ship the fix",
                "list": self.work.id,
                "due_date": due.isoformat(),
            },
        )

        self.assertEqual(Item.objects.get().due_date, due)

    def test_returns_to_the_agenda(self):
        response = self.client.post(
            "/lists/add",
            {"text": "Ship the fix", "list": self.work.id, "next": "/dashboard/"},
        )

        self.assertRedirects(response, "/dashboard/")

    def test_will_not_add_to_someone_elses_list(self):
        other = User.objects.create_user(
            "someone", "someone@example.com", "sekrit-password"
        )
        theirs = List.objects.create(owner=other, title="Theirs")

        response = self.client.post(
            "/lists/add", {"text": "Sneaky", "list": theirs.id}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Item.objects.count(), 0)

    def test_duplicate_text_is_reported_not_saved(self):
        Item.objects.create(list=self.work, text="Ship the fix")

        response = self.client.post(
            "/lists/add", {"text": "Ship the fix", "list": self.work.id}
        )

        self.assertEqual(Item.objects.count(), 1)
        self.assertContains(response, "You&#x27;ve already got this in your list")

    def test_rejects_an_off_site_redirect(self):
        response = self.client.post(
            "/lists/add",
            {
                "text": "Ship the fix",
                "list": self.work.id,
                "next": "https://evil.example.com/",
            },
        )

        self.assertRedirects(response, "/dashboard/")


class SetDueDateTest(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.user = User.objects.create_user(
            "vince", "vince@example.com", "sekrit-password"
        )
        self.client.force_login(self.user)
        self.work = List.objects.create(owner=self.user, title="Work")
        self.item = Item.objects.create(
            list=self.work, text="Renew insurance", due_date=self.today
        )

    def test_snoozing_moves_the_due_date(self):
        tomorrow = self.today + timedelta(days=1)

        self.client.post(
            f"/lists/items/{self.item.id}/due",
            {"due_date": tomorrow.isoformat(), "next": "/dashboard/"},
        )

        self.item.refresh_from_db()
        self.assertEqual(self.item.due_date, tomorrow)

    def test_an_empty_value_clears_the_due_date(self):
        self.client.post(
            f"/lists/items/{self.item.id}/due", {"due_date": ""}
        )

        self.item.refresh_from_db()
        self.assertIsNone(self.item.due_date)

    def test_returns_to_where_the_button_was_clicked(self):
        response = self.client.post(
            f"/lists/items/{self.item.id}/due",
            {"due_date": "", "next": "/dashboard/?scope=today"},
        )

        self.assertRedirects(
            response, "/dashboard/?scope=today", fetch_redirect_response=False
        )

    def test_cannot_reschedule_someone_elses_task(self):
        other = User.objects.create_user(
            "someone", "someone@example.com", "sekrit-password"
        )
        theirs = List.objects.create(owner=other, title="Theirs")
        their_item = Item.objects.create(list=theirs, text="Not yours")

        response = self.client.post(
            f"/lists/items/{their_item.id}/due", {"due_date": ""}
        )

        self.assertEqual(response.status_code, 404)


class ArchivePageTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "vince", "vince@example.com", "sekrit-password"
        )
        self.client.force_login(self.user)
        self.work = List.objects.create(owner=self.user, title="Work")

    def archive(self, text):
        item = Item.objects.create(list=self.work, text=text)
        item.status = Item.Status.ARCHIVED
        item.completed_at = timezone.now()
        item.archived_at = timezone.now()
        item.save()
        return item

    def test_archive_has_its_own_page(self):
        self.archive("Old business")

        response = self.client.get("/archive/")

        self.assertTemplateUsed(response, "archive.html")
        self.assertContains(response, "Old business")

    def test_archived_tasks_are_not_on_the_agenda(self):
        self.archive("Old business")

        response = self.client.get("/dashboard/")

        self.assertNotContains(response, "Old business")

    def test_restoring_returns_to_the_archive(self):
        item = self.archive("Old business")

        response = self.client.post(f"/lists/items/{item.id}/restore")

        self.assertRedirects(response, "/archive/")

    def test_deleting_returns_to_the_archive(self):
        item = self.archive("Old business")

        response = self.client.post(f"/lists/items/{item.id}/delete")

        self.assertRedirects(response, "/archive/")

    def test_login_is_required(self):
        self.client.logout()

        response = self.client.get("/archive/")

        self.assertRedirects(response, "/accounts/login/?next=/archive/")
