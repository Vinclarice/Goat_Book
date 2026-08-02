"""Crane 3 slice 3 — the week in your own words, and what is still waiting.

Three sources, gathered by three different rules, and the differences are
deliberate rather than an oversight:

- What was written belongs to the week, day by day, because a Daily Entry
  is dated and reading one back is history rather than inference.
- Ideas belong to the week they were added, which is what
  `daily-operating-system-vision.md` means by "recently added Ideas".
- Unresolved captures belong to no week at all. An Inbox is a backlog, and
  a thought from a fortnight ago is exactly the thing a review should
  catch -- filtering it to seven days would hide the ones that have been
  waiting longest, which is precisely backwards.
"""
from datetime import date, datetime, timedelta

from django.test import Client, TestCase
from django.utils import timezone

from accounts.models import User
from capture import services as capture_services
from capture.models import Capture, Idea
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

    def capture_on(self, owner, text, day):
        capture = capture_services.create_capture(owner, text)
        Capture.objects.filter(pk=capture.pk).update(created_at=instant_on(day))
        capture.refresh_from_db()
        return capture

    def idea_on(self, owner, text, day):
        idea = Idea.objects.create(owner=owner, text=text)
        Idea.objects.filter(pk=idea.pk).update(created_at=instant_on(day))
        idea.refresh_from_db()
        return idea

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

    def test_an_idea_added_in_the_week_is_part_of_it(self):
        self.idea_on(self.alice, "A quieter inbox", JULY_28)
        self.idea_on(self.alice, "Something from last month", JULY_27 - timedelta(days=30))

        self.assertEqual(
            [each["text"] for each in self.week()["ideas"]], ["A quieter inbox"]
        )

    def test_a_capture_still_in_the_inbox_appears_however_old_it_is(self):
        """The rule that is deliberately not week-scoped."""
        self.capture_on(self.alice, "Ask about the lease", JULY_27 - timedelta(days=14))

        [waiting] = self.week()["unresolved_captures"]

        self.assertEqual(waiting["text"], "Ask about the lease")
        self.assertEqual(
            waiting["age_in_days"],
            (timezone.localdate() - (JULY_27 - timedelta(days=14))).days,
        )

    def test_a_capture_already_triaged_is_not_still_waiting(self):
        capture = self.capture_on(self.alice, "Sorted on Thursday", JULY_28)
        capture_services.discard_capture(capture)

        self.assertEqual(self.week()["unresolved_captures"], [])

    def test_the_oldest_thing_waiting_is_at_the_top(self):
        """Newest-first is right for an Inbox you are adding to. A review
        reads the other way round: what has been sitting longest is the
        thing worth deciding about."""
        self.capture_on(self.alice, "Newer", JULY_30)
        self.capture_on(self.alice, "Older", JULY_27 - timedelta(days=20))

        self.assertEqual(
            [each["text"] for each in self.week()["unresolved_captures"]],
            ["Older", "Newer"],
        )

    def test_another_accounts_week_never_appears_in_this_one(self):
        daily_services.write_entry(self.bob, JULY_28, gratitude="Bob's rain")
        self.idea_on(self.bob, "Bob's idea", JULY_28)
        self.capture_on(self.bob, "Bob's thought", JULY_28)

        week = self.week()

        self.assertEqual(week["written"], [])
        self.assertEqual(week["ideas"], [])
        self.assertEqual(week["unresolved_captures"], [])
