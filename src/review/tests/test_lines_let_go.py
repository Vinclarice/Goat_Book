"""A better number than lines open.

`superlists-2.0-plan.md` rule 8's payoff: *the weekly review reports lines let
go, which is a better number than lines open.* An open count only ever goes up
and says nothing about whether anybody is deciding; this counts decisions
taken.
"""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from clarice import leftovers
from lists import services as task_services
from lists.models import Item
from review import reads


class LinesLetGoTest(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.today = timezone.localdate()
        self.week_start, self.week_end = reads.week_bounds(self.today)

    def count(self):
        return reads.let_go_in_week(self.owner, self.week_start, self.week_end)

    def a_task(self, text):
        return Item.objects.create(owner=self.owner, text=text)

    def test_a_quiet_week_reports_none(self):
        self.assertEqual(self.count(), 0)

    def test_each_line_let_go_is_counted(self):
        leftovers.let_go(self.owner, self.a_task("Sort the garage shelves"))
        leftovers.let_go(self.owner, self.a_task("Read the Forster book"))

        self.assertEqual(self.count(), 2)

    def test_filing_a_finished_task_is_not_letting_it_go(self):
        """The distinction the whole event exists for: `archive_item` writes
        `TASK_ARCHIVED` for both, so a count over that would report a tidy-up
        as a week of abandonment.
        """
        task = self.a_task("Done and filed")
        task_services.complete_item(task)
        task_services.archive_item(task)

        self.assertEqual(self.count(), 0)

    def test_a_line_let_go_last_week_is_last_weeks_number(self):
        """Written at its own instant rather than backdated afterwards: the
        log is append-only by database trigger, so an `update` on it raises --
        which is the guard working, and the reason `make_event` exists.
        """
        from clarice import life_log
        from clarice.testing import make_event

        make_event(
            self.owner,
            life_log.TASK_LET_GO,
            timezone.now() - timedelta(days=14),
            task=self.a_task("Long gone"),
        )

        self.assertEqual(self.count(), 0)

    def test_one_persons_week_never_counts_anothers(self):
        intruder = User.objects.create_user(
            "mallory", "mallory@example.com", "another secure password"
        )
        leftovers.let_go(intruder, Item.objects.create(owner=intruder, text="Theirs"))

        self.assertEqual(self.count(), 0)

    def test_the_week_payload_carries_it(self):
        leftovers.let_go(self.owner, self.a_task("Sort the garage shelves"))
        self.client.force_login(self.owner)

        payload = self.client.get("/api/v1/review").json()

        self.assertEqual(payload["let_go"], 1)
