"""The pool prunes itself.

`superlists-2.0-plan.md` rule 8: *a floating line unpicked for a stated number
of days asks one question -- **still want this?** -- and let go archives the
task and retires its facet while the node stays. Paper could not drop a task
without losing the idea. This can.*

**Only a floating line.** A dated one is a promise to somebody and is not
waiting to be noticed; the pool shows it under Fixed with a date beside it, and
asking whether it is still wanted would be asking the wrong question about a
deadline.
"""
import json
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from clarice import leftovers
from daily import services as daily_services
from lists import agenda
from lists import services as task_services
from lists.models import Item


def backdate(item, days):
    """`created_at` is `auto_now_add`, so age has to be written after the fact."""
    Item.objects.filter(pk=item.pk).update(
        created_at=timezone.now() - timedelta(days=days)
    )
    item.refresh_from_db()
    return item


class TheStaleClockTest(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.today = timezone.localdate()

    def rows(self):
        pool = agenda.pool_for(self.owner, self.today)
        return {row["task"]["text"]: row for row in pool["floating"]}

    def old_line(self, text="Sort the garage shelves", days=None):
        days = agenda.STALE_AFTER_DAYS if days is None else days
        return backdate(Item.objects.create(owner=self.owner, text=text), days)

    def test_a_new_line_is_not_asked_about(self):
        Item.objects.create(owner=self.owner, text="Book dentist")

        row = self.rows()["Book dentist"]
        self.assertEqual(row["unpicked_for_days"], 0)
        self.assertFalse(row["asks_to_be_kept"])

    def test_a_line_the_day_before_the_threshold_is_not_asked_about(self):
        self.old_line(days=agenda.STALE_AFTER_DAYS - 1)

        self.assertFalse(self.rows()["Sort the garage shelves"]["asks_to_be_kept"])

    def test_a_line_at_the_threshold_asks(self):
        """The boundary itself, because a threshold nobody pinned is a
        threshold that moves by one the first time somebody touches it.
        """
        self.old_line()

        row = self.rows()["Sort the garage shelves"]
        self.assertTrue(row["asks_to_be_kept"])
        self.assertEqual(row["unpicked_for_days"], agenda.STALE_AFTER_DAYS)

    def test_a_dated_line_is_never_asked_about(self):
        """A promise with a date on it is not waiting to be noticed."""
        old = self.old_line(days=90)
        old.due_date = self.today + timedelta(days=30)
        old.save(update_fields=["due_date"])

        pool = agenda.pool_for(self.owner, self.today)

        self.assertEqual(pool["floating"], [])
        self.assertNotIn("asks_to_be_kept", pool["fixed"][0])

    def test_being_picked_resets_the_clock(self):
        """*Unpicked* is the word rule 8 uses. Choosing something for a day is
        the strongest possible statement that you still want it, so it answers
        the question without being asked.
        """
        old = self.old_line()
        daily_services.pin_task(self.owner, self.today, old)

        row = self.rows()["Sort the garage shelves"]
        self.assertEqual(row["unpicked_for_days"], 0)
        self.assertFalse(row["asks_to_be_kept"])

    def test_a_pin_taken_off_still_counts_as_having_been_picked(self):
        """It was chosen, and then unchosen -- both are engagement, and the
        clock measures neglect rather than success.
        """
        old = self.old_line()
        daily_services.pin_task(self.owner, self.today, old)
        daily_services.unpin_task(self.owner, self.today, old)

        self.assertFalse(self.rows()["Sort the garage shelves"]["asks_to_be_kept"])

    def test_keeping_it_resets_the_clock_so_it_asks_once(self):
        old = self.old_line()

        task_services.keep(old)

        row = self.rows()["Sort the garage shelves"]
        self.assertEqual(row["unpicked_for_days"], 0)
        self.assertFalse(row["asks_to_be_kept"])

    def test_it_asks_again_a_whole_threshold_later(self):
        """*Asks once* is once per stretch of neglect, not once ever. A line
        nobody has touched for six weeks is a different question from the same
        line three weeks ago, and refusing to ask again would make the pool
        stop pruning itself after one pass.
        """
        old = self.old_line()
        task_services.keep(old)
        Item.objects.filter(pk=old.pk).update(
            kept_at=timezone.now() - timedelta(days=agenda.STALE_AFTER_DAYS)
        )

        self.assertTrue(self.rows()["Sort the garage shelves"]["asks_to_be_kept"])

    def test_one_persons_pool_never_asks_about_anothers_line(self):
        intruder = User.objects.create_user(
            "mallory", "mallory@example.com", "another secure password"
        )
        backdate(Item.objects.create(owner=intruder, text="Not mine"), 90)

        self.assertEqual(agenda.pool_for(self.owner, self.today)["floating"], [])


class AnsweringTheQuestionTest(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.today = timezone.localdate()
        self.task = backdate(
            Item.objects.create(owner=self.owner, text="Sort the garage shelves"), 40
        )
        self.client.force_login(self.owner)

    def answer(self, answer, task=None):
        return self.client.post(
            f"/api/v1/pool/{(task or self.task).id}/still-wanted",
            data=json.dumps({"answer": answer}),
            content_type="application/json",
        )

    def test_keep_stops_it_asking_and_leaves_it_open(self):
        response = self.answer("keep")

        self.assertEqual(response.status_code, 200)
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, Item.Status.ACTIVE)
        self.assertIsNotNone(self.task.kept_at)
        [row] = response.json()["floating"]
        self.assertFalse(row["asks_to_be_kept"])

    def test_let_go_archives_it_and_takes_it_out_of_the_pool(self):
        response = self.answer("let_go")

        self.assertEqual(response.status_code, 200)
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, Item.Status.ARCHIVED)
        self.assertEqual(response.json()["floating"], [])

    def test_an_answer_that_is_neither_is_refused(self):
        self.assertEqual(self.answer("maybe").status_code, 422)

    def test_another_persons_line_is_not_found(self):
        intruder = User.objects.create_user(
            "mallory", "mallory@example.com", "another secure password"
        )
        self.client.force_login(intruder)

        response = self.answer("let_go")

        self.assertEqual(response.status_code, 404)
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, Item.Status.ACTIVE)

    def test_it_answers_with_the_pool_so_the_row_goes_away_at_once(self):
        """The same shape every day write uses: one response, so the list and
        the count cannot disagree for a frame.
        """
        payload = self.answer("keep").json()

        self.assertIn("open_count", payload)


class LettingGoIsItsOwnFactTest(TestCase):
    """Rule 8's second half, and what the weekly review counts.

    Archiving a finished task is filing it; letting one go is stopping without
    doing it. `TASK_ARCHIVED` cannot tell those apart -- `archive_item` writes
    it for both -- so letting go records its own event, and the review counts
    that rather than inferring from a status.
    """

    def setUp(self):
        self.owner = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.today = timezone.localdate()

    def events(self, event_type):
        from mind.models import ActivityEvent

        return ActivityEvent.objects.filter(
            owner=self.owner, event_type=event_type
        ).count()

    def test_letting_go_is_recorded_as_letting_go(self):
        from clarice import life_log

        task = Item.objects.create(owner=self.owner, text="Sort the garage shelves")

        leftovers.let_go(self.owner, task)

        self.assertEqual(self.events(life_log.TASK_LET_GO), 1)

    def test_filing_a_finished_task_is_not_letting_it_go(self):
        from clarice import life_log

        task = Item.objects.create(owner=self.owner, text="Done and filed")
        task_services.complete_item(task)
        task_services.archive_item(task)

        self.assertEqual(self.events(life_log.TASK_LET_GO), 0)
        self.assertEqual(self.events(life_log.TASK_ARCHIVED), 1)
