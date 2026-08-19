"""What a day actually holds — product-stories.md S3, at the grain it asks for.

S3 wants the day to say so *while he is still planning*, and `kestrel` shipped
the signal a week wide and on the review: `typical_week_for` and
`draft_week`'s `over_committed`. That moved the story from *impossible* to
*bends* and left the grain wrong — his story pins five things to a **Tuesday**.

**D2 named this grain, not the week's.** Its worked example is *"you have
pinned nine for Tuesday; you have finished more than five on two of the last
thirty days"*, and its instruction is explicit: *"Reuse, do not reimplement.
`review/reads.py` already computes planned against completed for a week with
the honest-denominator discipline intact. The daily grain is the same
computation, and two definitions of 'what I got through' would drift."*

So this borrows `planned_in_week` for a one-day window rather than counting
completions its own way. What is decided here is the window and how little
evidence is too little; what counts as *finished* stays that function's call
and only its -- the same split `DAY_BUCKETS` makes against `bucket_for` a few
lines above the read.
"""
from datetime import date, datetime, timedelta

from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from daily import reads, services
from daily.models import DailyFocus
from lists import services as list_services
from lists.models import Item, List


# A Tuesday, because S3's is.
TUESDAY = date(2026, 8, 4)


class TypicalDayTest(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.bob = User.objects.create_user(
            "bob", "bob@example.com", "another password"
        )
        self.list_ = List.objects.create(owner=self.alice, title="Home")

    def plan(self, day, *, pinned, finished, owner=None):
        """Pin ``pinned`` tasks to ``day`` and finish ``finished`` of them.

        Finishing is stamped on the day itself, because `planned_in_week`
        judges at the window's end: a task finished the following Tuesday was
        unfinished when that day closed, and this helper must not accidentally
        assert otherwise.
        """
        owner = owner or self.alice
        area = List.objects.filter(owner=owner).first() or List.objects.create(
            owner=owner, title="Home"
        )
        for index in range(pinned):
            task = list_services.create_item(area, f"{day} #{index}")
            services.pin_task(owner, day, task)
            if index < finished:
                list_services.complete_item(task)
                Item.objects.filter(pk=task.pk).update(
                    completed_at=timezone.make_aware(
                        datetime.combine(day, datetime.min.time())
                        + timedelta(hours=9)
                    )
                )

    def test_no_figure_at_all_without_enough_planned_days(self):
        """Null is not zero, and the two call for opposite responses.

        "No evidence yet" and "you have room" would render identically if this
        returned 0 -- the same call `typical_week_for` makes at two planned
        weeks, and the reason it returns None rather than a number.
        """
        for offset in range(1, reads.TYPICAL_DAY_MINIMUM_SAMPLE):
            self.plan(TUESDAY - timedelta(days=offset), pinned=3, finished=2)

        self.assertIsNone(reads.typical_day_for(self.alice, TUESDAY))

    def test_the_median_of_what_planned_days_actually_finished(self):
        """The median, not the mean -- one heroic day and one lost to flu
        should not move what a typical day looks like, and a planner is
        exactly where an outlier would do damage."""
        for offset, finished in enumerate((1, 2, 3, 9, 9), start=1):
            self.plan(
                TUESDAY - timedelta(days=offset), pinned=9, finished=finished
            )

        self.assertEqual(reads.typical_day_for(self.alice, TUESDAY), 3)

    def test_days_with_no_plan_are_skipped_rather_than_counted_as_zero(self):
        """A day nobody planned is not a day that finished nothing.

        Averaging it in would drag the figure toward a number nobody lived --
        the discipline `review/reads.py` holds everywhere else, and the one
        most easily lost by writing this as a query over a date range.
        """
        for offset in (1, 2, 3, 4, 5):
            self.plan(TUESDAY - timedelta(days=offset), pinned=4, finished=4)
        # Six unplanned days in the same window. If they counted as zeros the
        # median would collapse to 0 and the page would say so.

        self.assertEqual(reads.typical_day_for(self.alice, TUESDAY), 4)

    def test_the_day_being_planned_is_not_its_own_evidence(self):
        """Pins made for Tuesday cannot be evidence about Tuesday.

        The read looks strictly backwards. Counting today would make the
        signal move as somebody pinned, which is the opposite of what a
        capacity figure is for.
        """
        for offset in range(1, 6):
            self.plan(TUESDAY - timedelta(days=offset), pinned=2, finished=2)
        self.plan(TUESDAY, pinned=9, finished=9)

        self.assertEqual(reads.typical_day_for(self.alice, TUESDAY), 2)

    def test_days_beyond_the_window_are_not_evidence(self):
        for offset in range(1, 6):
            self.plan(TUESDAY - timedelta(days=offset), pinned=2, finished=1)
        self.plan(
            TUESDAY - timedelta(days=reads.TYPICAL_DAY_LOOKBACK + 1),
            pinned=9,
            finished=9,
        )

        self.assertEqual(reads.typical_day_for(self.alice, TUESDAY), 1)

    def test_a_pin_taken_off_is_not_a_finish_and_not_a_failure(self):
        """Borrowed rather than re-decided. `planned_in_week` already sorts a
        released pin out of both the numerator and the denominator, and this
        asserts the day grain inherits that rather than re-implementing it."""
        for offset in range(1, 6):
            self.plan(TUESDAY - timedelta(days=offset), pinned=2, finished=2)
        # A sixth day where both pins were taken off: no plan survives it, so
        # it is a day with no plan rather than a day that finished nothing.
        released = TUESDAY - timedelta(days=6)
        self.plan(released, pinned=2, finished=0)
        DailyFocus.objects.filter(entry__date=released).update(
            released_at=timezone.now()
        )

        self.assertEqual(reads.typical_day_for(self.alice, TUESDAY), 2)

    def test_another_person_s_days_are_not_evidence(self):
        for offset in range(1, 6):
            self.plan(TUESDAY - timedelta(days=offset), pinned=1, finished=1)
            self.plan(
                TUESDAY - timedelta(days=offset),
                pinned=9,
                finished=9,
                owner=self.bob,
            )

        self.assertEqual(reads.typical_day_for(self.alice, TUESDAY), 1)

    def test_reading_it_writes_nothing(self):
        """`daily.reads` must not write, and a capacity read that created a
        `DailyEntry` for every day it looked at would be the easiest possible
        way to break that -- thirty of them, per page view."""
        for offset in range(1, 6):
            self.plan(TUESDAY - timedelta(days=offset), pinned=1, finished=1)
        before = DailyFocus.objects.count()

        reads.typical_day_for(self.alice, TUESDAY)

        self.assertEqual(DailyFocus.objects.count(), before)


class TheDayCarriesItTest(TestCase):
    """S3's sentence, asserted through the surface that has to carry it.

    The read is half of *"the day says so while he is still planning"*; the
    claim is about what a day **shows**. S9 shipped a payload no component read
    and that gap survived a release, so the payload is asserted here and the
    rendering in `DayRoute.test.tsx` — neither on its own is the story.
    """

    def setUp(self):
        self.alice = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.client.force_login(self.alice)
        self.list_ = List.objects.create(owner=self.alice, title="Home")

    def day(self, on):
        return self.client.get(f"/api/v1/day/{on.isoformat()}").json()

    def plan(self, day, *, pinned, finished):
        for index in range(pinned):
            task = list_services.create_item(self.list_, f"{day} #{index}")
            services.pin_task(self.alice, day, task)
            if index < finished:
                list_services.complete_item(task)
                Item.objects.filter(pk=task.pk).update(
                    completed_at=timezone.make_aware(
                        datetime.combine(day, datetime.min.time())
                        + timedelta(hours=9)
                    )
                )

    def test_the_day_reports_what_it_typically_holds(self):
        for offset in range(1, 6):
            self.plan(TUESDAY - timedelta(days=offset), pinned=5, finished=3)

        self.assertEqual(self.day(TUESDAY)["typical_day"], 3)

    def test_too_little_history_sends_null_and_not_zero(self):
        """Over the wire as well as in the read. A zero here would be rendered
        as "you have finished 0 on a typical day", which is a sentence about a
        person that the evidence does not support."""
        self.assertIsNone(self.day(TUESDAY)["typical_day"])


class WhatItCostsTest(TestCase):
    """The query count, pinned rather than guessed at.

    This runs on every Day page load, which is the most-visited page in the
    application, so the cost is worth stating in a test rather than discovering
    later. It is one query per day looked back.

    **It is not one query over the range, and that is semantics rather than
    laziness.** `planned_in_week` judges at the window's end, so asking it for
    thirty days at once would judge a task pinned on the 1st and finished on
    the 20th as *met* for the 1st — which is exactly the retrospective
    rewriting the focus model exists to prevent. Each day has to be judged at
    its own end, and `planned_in_week` is the only thing allowed to make that
    judgement (D2: two definitions of "what I got through" would drift).

    If this ever needs to be cheaper, the shape is to lift the per-pin
    judgement out of `planned_in_week` into something both grains call with an
    explicit boundary, and fetch the window once. That is a refactor of the
    review's read module rather than a tweak here, which is why it has not been
    done for a cost nobody has yet felt.
    """

    def setUp(self):
        self.alice = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.list_ = List.objects.create(owner=self.alice, title="Home")

    def test_it_costs_one_query_per_day_looked_back(self):
        for offset in range(1, 6):
            day = TUESDAY - timedelta(days=offset)
            task = list_services.create_item(self.list_, f"{day}")
            services.pin_task(self.alice, day, task)

        with self.assertNumQueries(reads.TYPICAL_DAY_LOOKBACK):
            reads.typical_day_for(self.alice, TUESDAY)
