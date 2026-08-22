"""Whose clock is a morning — **D16, answered August 22, 2026.**

> `occurred_at` is UTC and the task core already has per-user time zones — but
> nothing here names which clock defines a day, a morning, or Part 3's *"the
> following morning"* denominator. Decided once, early, or *"8 nights this
> quarter"* quietly means UTC nights.

**The answer is the person's clock, and it was already decided.**
`per-user-time-zones-plan.md` settled it for the task core on August 1 and
`User.time_zone` has been the single place it is stored ever since. There is no
second answer available and inventing one would be the thing D16 warns about.
So this is not a new policy; it is the knowledge core inheriting one.

**But the strong form is not `timezone.localdate()`, and this is the part D16
actually needed deciding.** `localdate()` reads the zone the middleware
activated *for this request* — the **viewer's** zone. That is right for *today*,
where viewer and owner are the same person, and it is wrong for *which day was
this note on*, which is a property of the record. A note must not fall on a
different day depending on who is looking at it or on whether anyone is: a
nightly management command has no active zone at all and would silently answer
in `settings.TIME_ZONE`.

**So: the day a record belongs to is a function of its owner and its instant,
and of nothing else.** That is `clarice.clocks.day_for`, and it is the rule the
knowledge core now shares with the task core rather than a parallel one.

**D16's stated symptom was wrong, and that is worth recording rather than
quietly fixing.** Both the plan and `roadmap.md` said *every observation Track C
records is stamped UTC*, and it is not: Track C keys entirely on
`DailyEntry.date`, which `daily/api_v1.py::_today_for_request` has always set
from `timezone.localdate()`. **The nights were already the person's nights.**
The clock was running somewhere else — see the two joins below, which is where
it had actually cost something.
"""

import datetime

from django.test import TestCase

from clarice import recall
from clarice.testing import make_node, make_user
from daily.models import DailyEntry
from review.models import WeeklyIntention


#: Chosen because it is west of UTC by enough that an ordinary evening lands on
#: the next UTC day -- which is the whole defect, and is the majority of the
#: inhabited Americas rather than an exotic edge case.
NEW_YORK = "America/New_York"

#: 20:00 on Thursday August 20 in New York is 00:00 UTC on Friday August 21.
#: An unremarkable hour to write something down.
THURSDAY_EVENING = datetime.datetime(2026, 8, 21, 0, 0, tzinfo=datetime.timezone.utc)
THURSDAY = datetime.date(2026, 8, 20)

#: 21:00 on Sunday August 23 in New York is 01:00 UTC on Monday August 24 --
#: which is not merely the wrong day, it is the wrong *week*.
SUNDAY_EVENING = datetime.datetime(2026, 8, 24, 1, 0, tzinfo=datetime.timezone.utc)
THAT_WEEK = datetime.date(2026, 8, 17)


class TheDayARecordBelongsToTest(TestCase):
    """The rule itself, before any caller of it."""

    def setUp(self):
        self.vince = make_user("vince", time_zone=NEW_YORK)

    def test_an_evening_belongs_to_the_evening_it_was(self):
        from clarice import clocks

        self.assertEqual(clocks.day_for(self.vince, THURSDAY_EVENING), THURSDAY)

    def test_it_does_not_depend_on_who_is_looking(self):
        """**The reason this is not `timezone.localdate()`.** A note falling on
        a different day for a different reader is not a time-zone feature, it
        is two answers to one question."""
        from django.utils import timezone

        from clarice import clocks

        timezone.activate("Asia/Makassar")
        try:
            self.assertEqual(clocks.day_for(self.vince, THURSDAY_EVENING), THURSDAY)
        finally:
            timezone.deactivate()

    def test_it_does_not_depend_on_anyone_looking_at_all(self):
        """A management command has no active zone, and must not therefore
        answer in `settings.TIME_ZONE` -- which is how a nightly pass and a
        page disagree about the same note."""
        from django.utils import timezone

        from clarice import clocks

        timezone.deactivate()
        self.assertEqual(clocks.day_for(self.vince, THURSDAY_EVENING), THURSDAY)

    def test_a_retired_zone_falls_back_rather_than_raising(self):
        """`resolve_time_zone` already refuses to break the day over a zone
        tzdata has dropped, and the reason carries: in a nightly pass this
        would stop the run for everyone after them."""
        from clarice import clocks

        self.vince.time_zone = "Mars/Olympus"
        self.assertIsInstance(
            clocks.day_for(self.vince, THURSDAY_EVENING), datetime.date
        )


class ANoteKnowsWhichDayItWasOnTest(TestCase):
    """**S14's own join, and the bug D16 was hiding.**

    `what_surrounded` answered *which day was this note on* with
    `captured_at.date()`, which is the UTC date. For anyone west of UTC an
    evening note asked for **tomorrow's** entry -- which usually does not
    exist, so the answer was not wrong so much as empty. S14 was scored *works*
    on August 22 against tests that all captured notes at UTC midday.
    """

    def setUp(self):
        self.vince = make_user("vince", time_zone=NEW_YORK)
        self.entry = DailyEntry.objects.create(
            owner=self.vince, date=THURSDAY, happenings="the boiler again"
        )

    def test_an_evening_note_finds_that_evening_s_day(self):
        node = make_node(self.vince, when=THURSDAY_EVENING)

        surrounding = recall.what_surrounded(self.vince, node)

        self.assertEqual(surrounding.day, self.entry)

    def test_a_sunday_evening_note_belongs_to_the_week_that_was_ending(self):
        """Worse than the day case, because it does not come back empty. The
        Monday-start week means a Sunday evening in New York is stamped Monday
        in UTC, so the note joined to **next week's** intention and displayed
        it as the intention it was written under."""
        WeeklyIntention.objects.create(
            owner=self.vince, week_start=THAT_WEEK, text="finish the substrate"
        )
        node = make_node(self.vince, when=SUNDAY_EVENING)

        surrounding = recall.what_surrounded(self.vince, node)

        self.assertEqual(surrounding.intention, "finish the substrate")
