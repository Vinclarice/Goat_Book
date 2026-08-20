"""Marking a task as more or less pressing than the rest.

`commercial-blueprint.md` Part 3 calls the absence unbalanced: "a to-do core
with recurrence, routines, pauses and snapshot denominators, and no priority
field". The last item of v3's *Usable* release, and the only one of them that
needed a column.

**Three values, and there is deliberately no "medium".** Priority marks a
*departure* from normal, so an unmarked task already means medium -- offering
both would invite the distinction every to-do app collapses into, where
everything is medium and the field says nothing. `NONE` is the absence of the
signal rather than another value of it, which is the same call
`0857835` made for an unfiled task's Area.

**It belongs to the series, not to one occurrence.** A commitment carries
text, notes, tags, Area and cadence to its successor; a priority somebody set
on "pay rent" that reset every month would be the one attribute that did not,
and they would have to set it again forever.

**It does not outrank a due date.** Sorting priority above `due_date` would
hide overdue work behind emphasis, so it sorts *within* a day -- the ordering
is server-side only (`lists/agenda.py`), so unlike `bucket_for` this touches
no mirrored rule.
"""

import datetime
import json

from django.test import Client, TestCase
from django.utils import timezone

from accounts.models import User
from lists import services
from lists.models import Item, List, Priority


PASSWORD = "a secure password"


class PriorityTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", PASSWORD
        )
        self.list_ = List.objects.create(owner=self.user, title="Home")
        self.item = services.create_item(self.list_, "Pay rent")
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.user)
        response = self.client.get("/accounts/password/change/")
        self.csrf = response.cookies["csrftoken"].value

    def patch(self, item, payload):
        return self.client.patch(
            f"/api/items/{item.id}/",
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=self.csrf,
        )

    def test_a_task_starts_with_no_priority(self):
        """The absence of the signal, not a middle value nobody chose."""
        self.assertEqual(self.item.priority, Priority.NONE)

    def test_setting_it_through_the_api_sticks(self):
        response = self.patch(self.item, {"priority": Priority.HIGH})

        self.assertEqual(response.status_code, 200)
        self.item.refresh_from_db()
        self.assertEqual(self.item.priority, Priority.HIGH)

    def test_it_is_serialised_back_so_a_client_can_show_it(self):
        response = self.patch(self.item, {"priority": Priority.LOW})

        self.assertEqual(response.json()["data"]["priority"], Priority.LOW)

    def test_an_unknown_priority_is_refused_rather_than_stored(self):
        response = self.patch(self.item, {"priority": "urgent-ish"})

        self.assertEqual(response.status_code, 400)
        self.assertIn("priority", response.json()["errors"])
        self.item.refresh_from_db()
        self.assertEqual(self.item.priority, Priority.NONE)

    def test_setting_it_on_a_repeating_task_sets_it_on_the_series(self):
        """The same "this and future" rule renaming already follows. Without
        the write-through the next occurrence would come back unmarked."""
        self.patch(self.item, {"recurrence": Item.Recurrence.MONTHLY})

        self.patch(self.item, {"priority": Priority.HIGH})

        self.item.refresh_from_db()
        self.assertEqual(self.item.commitment.priority, Priority.HIGH)

    def test_the_next_occurrence_inherits_it(self):
        """The test that would fail silently: the series carries the value and
        the spawn has to read it, and a spawn that ignored it would look
        correct in every other test here."""
        self.patch(self.item, {"recurrence": Item.Recurrence.MONTHLY})
        self.patch(self.item, {"priority": Priority.HIGH})
        self.item.refresh_from_db()

        spawned = services.complete_item(self.item)._spawned

        self.assertEqual(spawned.priority, Priority.HIGH)


class PriorityOrderingTest(TestCase):
    """Where it shows, and where it deliberately does not."""

    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", PASSWORD
        )
        self.list_ = List.objects.create(owner=self.user, title="Home")
        self.today = timezone.localdate()

    def task(self, text, priority=Priority.NONE, due=None):
        item = services.create_item(self.list_, text, due_date=due)
        if priority != Priority.NONE:
            services.set_priority(item, priority)
        return item

    def texts(self):
        from lists import agenda

        return [item.text for item in agenda.open_items_for(self.user)]

    def test_the_pressing_one_comes_first_among_things_due_the_same_day(self):
        self.task("Ordinary", due=self.today)
        self.task("Pressing", priority=Priority.HIGH, due=self.today)

        self.assertEqual(self.texts()[:2], ["Pressing", "Ordinary"])

    def test_a_low_one_sinks_below_the_rest_of_its_day(self):
        self.task("Ordinary", due=self.today)
        self.task("Whenever", priority=Priority.LOW, due=self.today)

        self.assertEqual(self.texts()[:2], ["Ordinary", "Whenever"])

    def test_priority_never_outranks_a_due_date(self):
        """The one that matters. Emphasis must not hide something overdue --
        a to-do app that buries a late task under a starred one is worse than
        one with no priority at all."""
        self.task("Late", due=self.today - datetime.timedelta(days=3))
        self.task("Pressing but not yet due", priority=Priority.HIGH,
                  due=self.today + datetime.timedelta(days=3))

        self.assertEqual(self.texts()[0], "Late")
