"""Crane 3 slice 4 — writing the review down, and planning the coming week.

The first thing the review app stores rather than derives, and the first
migration in it.

Two decisions are under test here rather than assumed. A review is
addressed by any date in its week and snaps to the Monday
`routines.periods.period_start_for` gives, so two links to the same week
cannot produce two records. And **completing a review stamps the figure it
reported**: `DailyFocus.task` is SET_NULL, so permanently deleting an
archived task quietly moves a live recount of a week somebody has already
reviewed. The denominator survives that -- `task_text` is the snapshot --
but the numerator does not, and a conclusion drawn on a Sunday should not
be edited afterwards by a tidy-up on a Tuesday.
"""
import json
from datetime import date, datetime, timedelta

from django.test import Client, TestCase
from django.utils import timezone

from accounts.models import User
from daily import services as daily_services
from lists import services as list_services
from lists.models import Item, List
from review.models import WeeklyReview


PASSWORD = "correct horse battery staple 47!"

JULY_27 = date(2026, 7, 27)
JULY_29 = date(2026, 7, 29)


class WritingTheReviewTest(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(
            "alice", "alice@example.com", PASSWORD
        )
        self.bob = User.objects.create_user("bob", "bob@example.com", PASSWORD)
        self.alices_list = List.objects.create(owner=self.alice, title="Home")
        self.client = Client()
        self.client.force_login(self.alice)

    def patch(self, payload, week=JULY_27):
        return self.client.patch(
            f"/api/v1/review/{week}",
            data=json.dumps(payload),
            content_type="application/json",
        )

    def post(self, path, week=JULY_27):
        return self.client.post(f"/api/v1/review/{week}/{path}")

    def week(self, week=JULY_27):
        response = self.client.get(f"/api/v1/review/{week}")
        self.assertEqual(response.status_code, 200)
        return response.json()

    def pin_and_finish(self, text, finished_on=JULY_29):
        task = list_services.create_item(self.alices_list, text)
        daily_services.pin_task(self.alice, JULY_27, task)
        list_services.complete_item(task)
        Item.objects.filter(pk=task.pk).update(
            completed_at=timezone.make_aware(
                datetime.combine(finished_on, datetime.min.time())
                + timedelta(hours=9)
            )
        )
        task.refresh_from_db()
        return task

    # `test_a_plan_for_the_coming_week_is_kept` lived here and is gone --
    # `planning-assistant-v2-plan.md` D7 retired that write path on August 26,
    # 2026. What replaces it is
    # `review/tests/test_the_plan_field_is_retired.py`, which asserts the
    # opposite. The three tests below used `plan` only as a convenient second
    # field and now use `reflections`; what each is actually about is unchanged.

    def test_writing_one_field_leaves_the_other_alone(self):
        """The same partial-write contract the day has, for the same
        reason: a page saving one section must not blank another.

        Reflections against the recorded figures now, since `plan` is no
        longer writable. The contract is the point, not the pair of fields.
        """
        self.patch({"reflections": "Quieter than last week"})

        self.patch({})

        review = self.week()["review"]
        self.assertEqual(review["reflections"], "Quieter than last week")

    def test_any_date_in_the_week_writes_the_same_record(self):
        self.patch({"reflections": "Written on the Monday"})

        self.patch({}, week=JULY_29)

        self.assertEqual(WeeklyReview.objects.filter(owner=self.alice).count(), 1)
        self.assertEqual(self.week()["review"]["reflections"], "Written on the Monday")

    def test_another_account_has_its_own_review_of_the_same_week(self):
        self.patch({"reflections": "Alice's week"})

        self.client.force_login(self.bob)
        self.assertEqual(self.week()["review"]["reflections"], "")

    def test_reading_a_week_does_not_bring_a_review_into_existence(self):
        """An unwritten review is a blank page, not a missing one -- and a
        GET that created the row would be a page view inventing a record,
        which is the obligation this whole surface carries."""
        self.week()

        self.assertEqual(WeeklyReview.objects.count(), 0)

    def test_completing_a_review_records_the_figure_it_reported(self):
        self.pin_and_finish("Pay rent")
        unfinished = list_services.create_item(self.alices_list, "Call the bank")
        daily_services.pin_task(self.alice, JULY_27, unfinished)

        response = self.post("complete")

        self.assertEqual(response.status_code, 200)
        review = response.json()["review"]
        self.assertIsNotNone(review["completed_at"])
        self.assertEqual(
            (review["recorded_met"], review["recorded_total"]), (1, 2)
        )

    def test_deleting_the_evidence_afterwards_does_not_edit_the_conclusion(self):
        """Slice 4's acceptance condition, and the reason for stamping.

        The live recount moves because DailyFocus.task is SET_NULL and
        there is nothing left to ask about a deleted task. What somebody
        concluded on the day they reviewed the week does not move with it.
        """
        finished = self.pin_and_finish("Pay rent")
        self.post("complete")

        list_services.archive_item(finished)
        list_services.delete_archived_item(finished)

        week = self.week()
        self.assertEqual(week["planned"]["met"], 0)
        self.assertEqual(week["review"]["recorded_met"], 1)
        self.assertEqual(week["review"]["recorded_total"], 1)

    def test_completing_a_second_time_keeps_the_first_answer(self):
        """It records when the week was reviewed, not when somebody last
        pressed the button -- the same rule pausing a routine follows."""
        self.pin_and_finish("Pay rent")
        first = self.post("complete").json()["review"]["completed_at"]

        again = self.post("complete").json()["review"]

        self.assertEqual(again["completed_at"], first)

    def test_a_review_can_be_reopened_and_goes_back_to_live_numbers(self):
        """A mis-tap on a one-way door is not a recoverable failure, and
        principles.md asks that failure be recoverable."""
        self.pin_and_finish("Pay rent")
        self.post("complete")

        response = self.post("reopen")

        review = response.json()["review"]
        self.assertIsNone(review["completed_at"])
        self.assertIsNone(review["recorded_met"])
        self.assertIsNone(review["recorded_total"])

    def test_a_review_is_not_writable_without_a_session(self):
        self.assertEqual(
            Client().patch(
                f"/api/v1/review/{JULY_27}",
                data=json.dumps({"reflections": "nope"}),
                content_type="application/json",
            ).status_code,
            401,
        )
