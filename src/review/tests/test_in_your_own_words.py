"""Crane 3 slice 3 — the week in your own words.

What was written belongs to the week, day by day, because a Daily Entry is
dated and reading one back is history rather than inference.

**This file used to cover two more sources and no longer does.** Ideas added in
the week, and unresolved captures from any week, both read models the crossover
deletes — and the second read a *concept* it deletes, since nothing in the graph
waits for triage. Their replacements live in
`test_the_week_reads_the_graph.py`, along with the reasoning for why one became
a truer question and the other became a different one. What is left here is the
part that never depended on the Inbox.

The original note, kept because the contrast is the point:

- Unresolved captures belonged to no week at all. An Inbox is a backlog, and
  a thought from a fortnight ago is exactly the thing a review should
  catch -- filtering it to seven days would hide the ones that have been
  waiting longest, which is precisely backwards.
"""
from datetime import date, datetime, timedelta

from django.test import Client, TestCase
from django.utils import timezone

from accounts.models import User
from daily import services as daily_services
from lists.models import List


PASSWORD = "correct horse battery staple 47!"

JULY_27 = date(2026, 7, 27)
JULY_28 = date(2026, 7, 28)
JULY_30 = date(2026, 7, 30)


def instant_on(day, hour=9):
    return timezone.make_aware(
        datetime.combine(day, datetime.min.time()) + timedelta(hours=hour)
    )


class WeekInWordsTest(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(
            "alice", "alice@example.com", PASSWORD
        )
        self.bob = User.objects.create_user("bob", "bob@example.com", PASSWORD)
        self.client = Client()
        self.client.force_login(self.alice)

    def week(self, week=JULY_27):
        response = self.client.get(f"/api/v1/review/{week}")
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_what_was_written_comes_back_under_the_day_it_was_written_for(self):
        daily_services.write_entry(self.alice, JULY_28, gratitude="The rain")
        daily_services.write_entry(self.alice, JULY_30, intentions="Finish it")

        written = self.week()["written"]

        self.assertEqual(
            [(each["date"], each["gratitude"], each["intentions"]) for each in written],
            [("2026-07-28", "The rain", ""), ("2026-07-30", "", "Finish it")],
        )

    def test_a_day_nobody_wrote_in_is_not_a_day_in_the_review(self):
        """Pinning creates the entry row before a word is typed into it, so
        an empty one is the ordinary state of a planned day rather than
        something to report back as writing."""
        task_list = List.objects.create(owner=self.alice, title="Home")
        from lists import services as list_services

        task = list_services.create_item(task_list, "Pay rent")
        daily_services.pin_task(self.alice, JULY_28, task)

        self.assertEqual(self.week()["written"], [])

    def test_writing_from_another_week_stays_there(self):
        daily_services.write_entry(
            self.alice, JULY_27 - timedelta(days=3), gratitude="Last week"
        )

        self.assertEqual(self.week()["written"], [])

    def test_another_accounts_week_never_appears_in_this_one(self):
        daily_services.write_entry(self.bob, JULY_28, gratitude="Bob's rain")

        week = self.week()

        self.assertEqual(week["written"], [])
        self.assertEqual(week["thoughts"], [])
        self.assertEqual(week["names_to_confirm"], [])
