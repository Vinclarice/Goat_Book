"""Commitments that come round less often than a month.

`Item.Recurrence` was `none`, `daily`, `weekly`, `monthly`, so a property tax
bill due 5 October every year could not be expressed at all -- which is the
first thing bills need and has nothing to do with money.

**Both are the monthly arithmetic with a multiplier**, not new branches.
`_nth_occurrence_after` computes from the anchor each time rather than stepping
off the last result, and the reason it gives for monthly is the reason these
inherit it: the 31st advanced through February and carried forward would spend
the rest of the year on the 28th. February is the only month that clamps, and
March is the 31st again. A quarterly bill anchored on the 31st behaves the same
way for free, and a leap-day annual clamps once and returns.

**Missed periods are still skipped, not replayed.** Three missed quarters
produce one occurrence, not three -- occurrences that did not happen are not
invented.
"""

import datetime

from django.test import TestCase

from accounts.models import User
from lists import services
from lists.models import Item, List


class LongerCadencesTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.list_ = List.objects.create(owner=self.user, title="Home")

    def advance(self, due, cadence, *, today):
        return services._advance_due_date(due, cadence, today=today)

    def test_quarterly_moves_three_months_and_keeps_the_day(self):
        nxt = self.advance(
            datetime.date(2026, 1, 15),
            Item.Recurrence.QUARTERLY,
            today=datetime.date(2026, 1, 20),
        )

        self.assertEqual(nxt, datetime.date(2026, 4, 15))

    def test_annual_moves_a_year(self):
        """The property tax bill this exists for: due 5 October, and the next
        one is 5 October."""
        nxt = self.advance(
            datetime.date(2026, 10, 5),
            Item.Recurrence.ANNUAL,
            today=datetime.date(2026, 10, 6),
        )

        self.assertEqual(nxt, datetime.date(2027, 10, 5))

    def test_a_quarterly_anchored_on_the_31st_clamps_only_where_it_must(self):
        """Inherited from monthly rather than re-decided. November has 30
        days, so a 31 August anchor clamps there -- and the following one is
        the 28th or 29th of February, not the 30th carried forward."""
        nxt = self.advance(
            datetime.date(2026, 8, 31),
            Item.Recurrence.QUARTERLY,
            today=datetime.date(2026, 9, 1),
        )

        self.assertEqual(nxt, datetime.date(2026, 11, 30))

    def test_a_leap_day_annual_clamps_and_does_not_stay_clamped(self):
        clamped = self.advance(
            datetime.date(2028, 2, 29),
            Item.Recurrence.ANNUAL,
            today=datetime.date(2028, 3, 1),
        )
        self.assertEqual(clamped, datetime.date(2029, 2, 28))

        # Every non-leap year clamps, and none of them skips ahead to find a
        # 29th -- the schedule is "29 February, or the 28th when there is no
        # 29th", not "every fourth year".
        self.assertEqual(
            self.advance(
                datetime.date(2028, 2, 29),
                Item.Recurrence.ANNUAL,
                today=datetime.date(2030, 1, 1),
            ),
            datetime.date(2030, 2, 28),
        )

        # And the clamp does not stick: four years on the anchor is intact,
        # because each occurrence is computed from it rather than from the
        # last clamped result. This is the assertion the test was for; the
        # first draft asserted this date for the wrong year and was wrong
        # about the domain rather than about the code.
        self.assertEqual(
            self.advance(
                datetime.date(2028, 2, 29),
                Item.Recurrence.ANNUAL,
                today=datetime.date(2031, 6, 1),
            ),
            datetime.date(2032, 2, 29),
        )

    def test_missed_quarters_produce_one_occurrence_rather_than_three(self):
        """The skip rule, inherited: a fabricated history is worse than an
        absent one."""
        nxt = self.advance(
            datetime.date(2026, 1, 15),
            Item.Recurrence.QUARTERLY,
            today=datetime.date(2026, 11, 1),
        )

        self.assertEqual(nxt, datetime.date(2027, 1, 15))

    def test_a_yearly_task_spawns_its_successor_a_year_on(self):
        """End to end, through the service a person actually reaches."""
        task = services.create_item(
            self.list_, "Property tax", due_date=datetime.date(2026, 10, 5)
        )
        services.set_recurrence(task, Item.Recurrence.ANNUAL)
        task.refresh_from_db()

        spawned = services.complete_item(task)._spawned

        self.assertEqual(spawned.due_date.month, 10)
        self.assertEqual(spawned.due_date.day, 5)
        self.assertGreater(spawned.due_date.year, 2026)
