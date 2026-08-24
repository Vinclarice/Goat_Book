"""Zooming out to a quarter — **S8**, and v3's *wider horizons*.

> Three months in, Vince wants to know whether the shape of his life matched
> what he said it would be.

**Done means:** the same honest denominators aggregate across twelve weeks of
reviews and routine history, and **weeks with no data read as absent rather than
zero**.

**Verdict before this: impossible** — *"`WeeklyReview` is the only review model;
`TREND_WEEKS = 5`."* **Requires:** *longer-horizon reviews reusing the weekly
model. The null-not-zero discipline already exists in `review/reads.py` and must
carry up.*

**One instrument parameterised by horizon, not five instruments**, which is the
release's own framing. So `recent_weeks` takes a count instead of reading a
constant, and the aggregate sits above it. No new model, no second review, and
nothing recorded — the same refusal `recent_weeks` already makes: *no new table
and no new record.*

**The whole of S8 is the denominator, and there are three states rather than
two.** A quarter that averaged over all twelve weeks would divide by weeks
somebody was not here, which is the mistake the weekly trend already refuses one
level down:

- **before the record** — no account activity yet, so `planned_total` is `None`;
- **recorded and empty** — you were here and pinned nothing, so it is `0`;
- **recorded** — a real figure.

*Recorded and empty* is a fact about the quarter and belongs in the
denominator. *Before the record* is not, and does not. Collapsing them is the
same error as reading an unrecorded night as a sober one, three axes over.
"""

from datetime import date, datetime, timedelta, timezone as dt_timezone

from django.test import TestCase

from accounts.models import User
from daily import services as daily_services
from lists import services as list_services
from lists.models import Item, List
from review import reads


UTC = dt_timezone.utc

#: Mondays. The quarter under test ends on the week of 22 June.
FIRST_WEEK = date(2026, 4, 6)
LAST_WEEK = date(2026, 6, 22)
TODAY = date(2026, 6, 26)


def at(day, hour=15):
    return datetime(day.year, day.month, day.day, hour, 0, tzinfo=UTC)


class TheQuarterTest(TestCase):
    def setUp(self):
        self.vince = User.objects.create_user(
            "vince", "vince@example.com", "a secure password"
        )
        self.area = List.objects.create(owner=self.vince, title="Home")

    def pin(self, text, *, day, finished=False):
        task = list_services.create_item(self.area, text)
        daily_services.pin_task(self.vince, day, task)
        if finished:
            list_services.complete_item(task)
            Item.objects.filter(pk=task.pk).update(completed_at=at(day))
        return task

    def quarter(self, weeks=12):
        return reads.over_weeks(self.vince, LAST_WEEK, TODAY, weeks=weeks)

    # -- the instrument is the weekly one, widened -------------------------

    def test_it_reports_a_week_for_every_week_in_the_horizon(self):
        """*One instrument parameterised by horizon, not five instruments.*"""
        self.pin("Something", day=LAST_WEEK, finished=True)

        self.assertEqual(len(self.quarter().weeks), 12)

    def test_the_horizon_is_a_parameter_rather_than_a_second_read(self):
        """A month is the same question over four weeks. If this needed its own
        function the release's framing would already be lost."""
        self.pin("Something", day=LAST_WEEK, finished=True)

        self.assertEqual(len(self.quarter(weeks=4).weeks), 4)

    def test_the_weekly_trend_still_answers_five(self):
        """The existing caller is unchanged: `recent_weeks` keeps its default,
        so widening the instrument did not widen the weekly page."""
        self.pin("Something", day=LAST_WEEK, finished=True)

        self.assertEqual(
            len(reads.recent_weeks(self.vince, LAST_WEEK, TODAY)),
            reads.TREND_WEEKS,
        )

    # -- the aggregate, and its denominator --------------------------------

    def test_it_adds_up_what_was_planned_and_met(self):
        self.pin("One", day=FIRST_WEEK, finished=True)
        self.pin("Two", day=FIRST_WEEK)
        self.pin("Three", day=LAST_WEEK, finished=True)

        quarter = self.quarter()

        self.assertEqual(quarter.planned_met, 2)
        self.assertEqual(quarter.planned_total, 3)

    def test_weeks_before_the_record_are_absent_rather_than_zero(self):
        """**S8's own sentence**, and the reason the aggregate cannot simply
        divide by twelve. A week before somebody was using Clarice is not a week
        in which they planned nothing."""
        self.pin("Only one", day=LAST_WEEK, finished=True)

        quarter = self.quarter()

        self.assertEqual(quarter.weeks_before_the_record, 11)
        self.assertEqual(quarter.weeks_counted, 1)

    def test_a_week_you_were_here_and_planned_nothing_still_counts(self):
        """The other half, and the distinction the whole read turns on. Being
        present and planning nothing is a fact about the quarter; not being
        here yet is not."""
        self.pin("Week one", day=FIRST_WEEK, finished=True)
        self.pin("Week twelve", day=LAST_WEEK, finished=True)

        quarter = self.quarter()

        self.assertEqual(quarter.weeks_before_the_record, 0)
        self.assertEqual(quarter.weeks_counted, 12)
        self.assertEqual(quarter.planned_total, 2)

    def test_an_empty_quarter_claims_nothing(self):
        quarter = self.quarter()

        self.assertIsNone(quarter.planned_total)
        self.assertEqual(quarter.weeks_counted, 0)
        self.assertFalse(quarter.has_anything)

    def test_it_says_what_it_could_not_see(self):
        """The sentence travels with the figure, which is this codebase's rule
        wherever a denominator is involved: a count that can be separated from
        what it was out of is a count somebody reads as *of the whole
        quarter*."""
        self.pin("Only one", day=LAST_WEEK, finished=True)

        says = self.quarter().denominator_says

        self.assertIn("1 of the 12", says)
        self.assertIn("were not recording", says)

    def test_a_full_quarter_does_not_apologise_for_itself(self):
        """No sentence when there is nothing to explain. A read that always
        printed a caveat would train somebody to skip it."""
        self.pin("Week one", day=FIRST_WEEK, finished=True)
        self.pin("Week twelve", day=LAST_WEEK, finished=True)

        self.assertEqual(self.quarter().denominator_says, "")

    def test_it_does_not_read_another_persons_quarter(self):
        priya = User.objects.create_user("priya", "p@example.com", "another password")
        area = List.objects.create(owner=priya, title="Theirs")
        task = list_services.create_item(area, "Theirs")
        daily_services.pin_task(priya, LAST_WEEK, task)

        self.assertIsNone(self.quarter().planned_total)


class ItReusesTheWeeklyJudgementTest(TestCase):
    """**Reusing the weekly model** is the require, and this is what it means in
    practice: the figures a quarter reports are the ones each week reported, not
    a fresh count over a longer window.

    That matters because a week's figure is judged *at that week's end* — a task
    finished the following Tuesday was unfinished when the week closed. A
    quarter counting completions across ninety days would quietly turn every
    slipped week into a met one.
    """

    def setUp(self):
        self.vince = User.objects.create_user(
            "vince", "vince@example.com", "a secure password"
        )
        self.area = List.objects.create(owner=self.vince, title="Home")

    def test_a_task_finished_the_following_week_is_not_met_in_the_quarter(self):
        task = list_services.create_item(self.area, "Slipped")
        daily_services.pin_task(self.vince, FIRST_WEEK, task)
        list_services.complete_item(task)
        Item.objects.filter(pk=task.pk).update(
            completed_at=at(FIRST_WEEK + timedelta(days=9))
        )

        quarter = reads.over_weeks(self.vince, LAST_WEEK, TODAY, weeks=12)

        self.assertEqual(quarter.planned_met, 0)
        self.assertEqual(quarter.planned_total, 1)


class TheQuarterHasItsOwnRouteTest(TestCase):
    """**Its own route rather than more of `WeekOut`.**

    Twelve weeks means twelve `planned_in_week` and twelve `habits_in_week`, and
    the weekly page is opened far more often than *how did the quarter go* is
    asked. Same argument that gave the project brief its own route.
    """

    def setUp(self):
        self.vince = User.objects.create_user(
            "vince", "vince@example.com", "a secure password"
        )
        self.area = List.objects.create(owner=self.vince, title="Home")
        self.client.force_login(self.vince)

    def ask(self, horizon="quarter"):
        return self.client.get(
            f"/api/v1/review/{LAST_WEEK.isoformat()}/horizon?horizon={horizon}"
        )

    def test_it_reports_the_quarter(self):
        task = list_services.create_item(self.area, "Something")
        daily_services.pin_task(self.vince, LAST_WEEK, task)
        list_services.complete_item(task)
        Item.objects.filter(pk=task.pk).update(completed_at=at(LAST_WEEK))

        payload = self.ask().json()

        self.assertEqual(payload["planned_met"], 1)
        self.assertEqual(len(payload["weeks"]), 12)

    def test_a_month_is_the_same_route(self):
        self.assertEqual(len(self.ask("month").json()["weeks"]), 4)

    def test_it_carries_the_sentence_rather_than_leaving_it_to_the_client(self):
        task = list_services.create_item(self.area, "Something")
        daily_services.pin_task(self.vince, LAST_WEEK, task)

        self.assertIn("were not recording", self.ask().json()["denominator_says"])

    def test_an_unknown_horizon_is_refused_rather_than_guessed(self):
        """**A named set rather than any integer.** An open parameter would let
        somebody ask for four hundred weeks of `planned_in_week` without anybody
        having decided that was reasonable."""
        self.assertEqual(self.ask("decade").status_code, 422)

    def test_it_answers_for_the_person_asking_and_nobody_else(self):
        priya = User.objects.create_user("priya", "p@example.com", "another password")
        area = List.objects.create(owner=priya, title="Theirs")
        daily_services.pin_task(
            priya, LAST_WEEK, list_services.create_item(area, "Theirs")
        )

        self.assertIsNone(self.ask().json()["planned_total"])
