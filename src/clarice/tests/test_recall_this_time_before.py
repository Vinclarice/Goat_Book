"""What you were doing on this date before — **D17, the cyclic axis**.

> **D17. Does Resurfacing include cyclic cues?** The time axis as drafted is
> linear — `around()`, `since()`, windows — but human temporal cueing is
> substantially cyclic: *this time last year*, anniversaries, the same Sunday
> evening. An on-this-day read over `occurred_at` and `captured_at` is pure
> derivation from recorded facts — no ML, no floors, no budget — and is exactly
> Resurfacing's *"cued by the person's present,"* where the present includes the
> date. Leaving the axis linear leaves the cheapest honest resurfacing unbuilt.

**Answered: yes**, and this read is the answer. It derives from `occurred_at`
alone, so Part 1's *facts, not derivations* holds — there is no row to write and
nothing to backfill. Every anniversary this returns was already in the log.

**It is built on D16 and could not have been built before it.** *This day last
year* is a claim about a calendar day, and a calendar day does not exist until
somebody says whose clock it is on. A note written at 21:00 in Los Angeles is
stamped the 22nd in UTC; asking UTC for "the 21st" would return the day before
it and miss the note entirely — the same defect `what_surrounded` had, one axis
over.

**The absence discipline is the design, not a caveat.** Three states, and
collapsing any two of them is the mistake:

- **an anniversary** — the log holds something from that day;
- **a silent year** — you were recording, and that day holds nothing;
- **before the record** — you were not recording yet.

A silent year and a year before you started look identical in an empty list and
are completely different facts about somebody's life. This is D5's shape and
Track C's *"an unrecorded night is not a sober one"*, on the cyclic axis.
"""

import datetime

from django.test import TestCase

from clarice import recall
from clarice.testing import make_area, make_event, make_task, make_user
from mind.models import EventType


NEW_YORK = "America/New_York"

#: Saturday August 22, 2026 — the day this was written.
TODAY = datetime.date(2026, 8, 22)


def at(year, month, day, hour, minute=0):
    """An instant in UTC. The tests say what that is locally where it matters."""
    return datetime.datetime(
        year, month, day, hour, minute, tzinfo=datetime.timezone.utc
    )


class ThisTimeBeforeTest(TestCase):
    def setUp(self):
        self.vince = make_user("vince", time_zone=NEW_YORK)
        self.area = make_area(self.vince)

    def a_completion(self, when, text=None):
        # Unique per call: `create_item` refuses a duplicate in one area, which
        # is the task core working as designed and not this read's business.
        task = make_task(self.area, text or f"Call the plumber ({when:%Y-%m-%d})")
        return make_event(self.vince, EventType.TASK_COMPLETED, when, task=task)

    def test_it_finds_what_happened_a_year_ago_today(self):
        self.a_completion(at(2025, 8, 22, 15))

        before = recall.this_time_before(self.vince, on=TODAY)

        self.assertEqual([year.years_ago for year in before.years], [1])
        self.assertEqual(len(before.years[0].neighbours), 1)

    def test_it_reaches_back_more_than_one_year(self):
        self.a_completion(at(2025, 8, 22, 15))
        self.a_completion(at(2024, 8, 22, 15))

        before = recall.this_time_before(self.vince, on=TODAY)

        self.assertEqual([year.years_ago for year in before.years], [1, 2])

    def test_the_nearest_year_comes_first(self):
        """*Cued by the person's present* — last year is the year the present
        most resembles, and a list that opened four years back would be a
        museum rather than a cue."""
        self.a_completion(at(2023, 8, 22, 15), "Older")
        self.a_completion(at(2025, 8, 22, 15), "Newer")

        before = recall.this_time_before(self.vince, on=TODAY)

        self.assertEqual([year.year for year in before.years], [2025, 2023])

    def test_a_different_day_is_not_an_anniversary(self):
        self.a_completion(at(2025, 8, 21, 15))

        before = recall.this_time_before(self.vince, on=TODAY)

        self.assertEqual(before.years, [])

    def test_today_is_not_its_own_anniversary(self):
        """The present is the cue, never the thing cued."""
        self.a_completion(at(2026, 8, 22, 15))

        before = recall.this_time_before(self.vince, on=TODAY)

        self.assertEqual(before.years, [])

    def test_it_does_not_read_another_persons_log(self):
        priya = make_user("priya", time_zone=NEW_YORK)
        make_event(
            priya,
            EventType.TASK_COMPLETED,
            at(2025, 8, 22, 15),
            task=make_task(make_area(priya)),
        )

        before = recall.this_time_before(self.vince, on=TODAY)

        self.assertEqual(before.years, [])


class ItIsTheOwnersCalendarDayTest(TestCase):
    """**D16 underneath D17.** An anniversary is a claim about a calendar day,
    and a calendar day belongs to whoever lived it."""

    def setUp(self):
        self.vince = make_user("vince", time_zone=NEW_YORK)
        self.area = make_area(self.vince)

    def test_an_evening_last_year_belongs_to_that_evening(self):
        """21:00 on August 22 in New York is 01:00 on the 23rd in UTC. Asking
        UTC for "the 22nd" would miss it — which is exactly how
        `what_surrounded` was broken, one axis over."""
        make_event(
            self.vince,
            EventType.TASK_COMPLETED,
            at(2025, 8, 23, 1),
            task=make_task(self.area),
        )

        before = recall.this_time_before(self.vince, on=TODAY)

        self.assertEqual([year.years_ago for year in before.years], [1])

    def test_an_evening_before_does_not_get_dragged_forward(self):
        """22:00 UTC on the 21st is 18:00 on the 21st in New York, and stays
        there."""
        make_event(
            self.vince,
            EventType.TASK_COMPLETED,
            at(2025, 8, 21, 22),
            task=make_task(self.area),
        )

        before = recall.this_time_before(self.vince, on=TODAY)

        self.assertEqual(before.years, [])


class TheThreeKindsOfNothingTest(TestCase):
    """**A silent year and a year before you started are different facts.**

    Both render as an empty list, and an empty list says neither. This is D5's
    shape and Track C's refusal to read an unrecorded night as a sober one, on
    the cyclic axis.
    """

    def setUp(self):
        self.vince = make_user("vince", time_zone=NEW_YORK)
        self.area = make_area(self.vince)

    def a_completion_in(self, when):
        return make_event(
            self.vince,
            EventType.TASK_COMPLETED,
            when,
            task=make_task(self.area),
        )

    def test_a_year_you_were_recording_but_wrote_nothing_that_day_is_named(self):
        self.a_completion_in(at(2025, 3, 4, 15))

        before = recall.this_time_before(self.vince, on=TODAY)

        self.assertEqual(before.silent_years, [2025])

    def test_a_year_before_the_log_begins_is_a_different_answer(self):
        self.a_completion_in(at(2025, 3, 4, 15))

        before = recall.this_time_before(self.vince, on=TODAY, years=3)

        self.assertEqual(before.silent_years, [2025])
        self.assertEqual(before.before_the_record, [2024, 2023])

    def test_it_says_so_in_words(self):
        """The sentence is the product, the same way Track C's denominator is.
        A count a surface has to phrase itself is a count two surfaces will
        phrase differently."""
        self.a_completion_in(at(2025, 3, 4, 15))

        before = recall.this_time_before(self.vince, on=TODAY, years=3)

        self.assertIn("2025", before.absence_says)
        self.assertIn("nothing recorded", before.absence_says)
        self.assertIn("were not recording", before.absence_says)

    def test_an_empty_log_claims_nothing_at_all(self):
        before = recall.this_time_before(self.vince, on=TODAY)

        self.assertEqual(before.years, [])
        self.assertEqual(before.silent_years, [])
        self.assertFalse(before.has_anything)


class LeapDayTest(TestCase):
    """**February 29 matches exactly and is not slid.**

    A note from February 29 could be surfaced on the 28th or on March 1 in a
    common year, and both are guesses about which one somebody meant. The date
    is a recorded fact; *near enough to the date* is a derivation, and this read
    exists because the cyclic axis was available without inventing one. So a
    leap day's anniversary falls on the next leap day, and the read says which
    years could not have one rather than returning a confusing blank.
    """

    def setUp(self):
        self.vince = make_user("vince", time_zone=NEW_YORK)
        self.area = make_area(self.vince)
        make_event(
            self.vince,
            EventType.TASK_COMPLETED,
            at(2024, 2, 29, 15),
            task=make_task(self.area),
        )

    def test_a_leap_day_has_no_anniversary_on_the_day_before(self):
        before = recall.this_time_before(
            self.vince, on=datetime.date(2025, 2, 28), years=2
        )

        self.assertEqual(before.years, [])

    def test_asking_on_a_leap_day_names_the_years_that_had_no_such_date(self):
        before = recall.this_time_before(
            self.vince, on=datetime.date(2028, 2, 29), years=4
        )

        self.assertEqual([year.year for year in before.years], [2024])
        self.assertIn("2027", before.absence_says)
        self.assertIn("no February 29", before.absence_says)
