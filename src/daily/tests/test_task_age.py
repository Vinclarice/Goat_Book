"""Crane 2 slice 5 — how long a task has been waiting.

`daily-operating-system-vision.md` asks Crane 2 to "show task age and
overdue context so carry-forward is visible, not silently punitive".
Overdue was already visible: `dueLabel` has said "3 days overdue" since
Crane 1. Age was not, and it is the half that matters more.

**Age is what a moved due date hides.** The vision document's rule is that
an incomplete task stays open and is never silently rewritten at midnight
-- but a person can move a due date themselves, and a task snoozed weekly
for two months reads as "due tomorrow" forever. Its age does not move.
That is the whole reason to show it.

Computed on the server rather than from `created_at` in the browser: age
is a count of days between two *local* dates, and the browser's zone is not
the account's. A phone in Makassar and a laptop in New York must agree
about how long something has been waiting.
"""
from datetime import timedelta

from django.test import Client, TestCase
from django.utils import timezone

from accounts.models import User
from lists import services as list_services
from lists.models import Item, List


PASSWORD = "correct horse battery staple 47!"


class TaskAgeTest(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(
            "alice", "alice@example.com", PASSWORD
        )
        self.list_ = List.objects.create(owner=self.alice, title="Home")
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.alice)

    def action_items(self):
        return self.client.get("/api/v1/day").json()["action_items"]

    def aged(self, task, days):
        """Backdate creation, since auto_now_add cannot be set at create."""
        Item.objects.filter(pk=task.pk).update(
            created_at=timezone.now() - timedelta(days=days)
        )

    def test_a_task_made_today_has_no_age(self):
        list_services.create_item(
            self.list_, "Pay rent", due_date=timezone.localdate()
        )

        self.assertEqual(self.action_items()[0]["age_in_days"], 0)

    def test_a_task_says_how_long_it_has_been_waiting(self):
        task = list_services.create_item(
            self.list_, "Pay rent", due_date=timezone.localdate()
        )
        self.aged(task, 12)

        self.assertEqual(self.action_items()[0]["age_in_days"], 12)

    def test_age_survives_a_due_date_being_moved(self):
        """The point of the whole slice.

        A task snoozed forward reads as due tomorrow and is not overdue at
        all -- so overdue says nothing about it, and age says everything.
        """
        task = list_services.create_item(
            self.list_, "Pay rent", due_date=timezone.localdate() - timedelta(days=9)
        )
        self.aged(task, 30)
        list_services.set_due_date(task, timezone.localdate())

        item = self.action_items()[0]

        self.assertEqual(item["age_in_days"], 30)
        self.assertEqual(item["due_date"], timezone.localdate().isoformat())

    def test_age_is_measured_in_the_owners_own_days(self):
        """Not the browser's. A count of days between two local dates."""
        task = list_services.create_item(
            self.list_, "Pay rent", due_date=timezone.localdate()
        )
        self.aged(task, 3)

        self.assertEqual(self.action_items()[0]["age_in_days"], 3)

    def test_every_action_item_carries_it(self):
        list_services.create_item(
            self.list_, "Pay rent", due_date=timezone.localdate()
        )
        list_services.create_item(
            self.list_,
            "Call the plumber",
            due_date=timezone.localdate() - timedelta(days=2),
        )

        self.assertTrue(
            all("age_in_days" in item for item in self.action_items())
        )

    def test_age_is_never_negative(self):
        """Clock skew or a backdated import must not read as the future."""
        task = list_services.create_item(
            self.list_, "Pay rent", due_date=timezone.localdate()
        )
        Item.objects.filter(pk=task.pk).update(
            created_at=timezone.now() + timedelta(days=2)
        )

        self.assertEqual(self.action_items()[0]["age_in_days"], 0)
