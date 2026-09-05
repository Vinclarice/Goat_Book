"""Something that asks him to close the day — product-stories.md S5.

Its verdict was that the good half already existed: `DailyEntry.happenings` is
there and `DailyFocus` preserves the morning's choice honestly. What was
missing was the ask -- *"nothing ever asks him to write it: no evening surface,
no prompt, no reminder"*.

**The counts are borrowed, not re-decided.** `planned_in_week` for a one-day
window, exactly as `typical_day_for` does it, and for the reason D2 gives: two
definitions of "what I got through" would drift. It is safe on a day still in
progress because it judges against the window's *end* -- with the window ending
today, a task finished today counts as met and one released today as set aside,
which is precisely "so far".

**A released pin is not a failure.** That is `released_at`'s whole purpose and
the reason the closing line reports it apart from what is still open.

**It cannot close a day retroactively.** *"I wrote nothing on the 3rd"* and *"I
have never opened the 3rd"* are different facts -- which is why `DailyEntry` has
no deleted or archived state -- and a prompt that appeared on a past day would
be asking somebody to reconstruct one. A day nobody answered closes unclosed,
and that is itself a record.

**The clock is injected.** The hour is read once at the request boundary in the
owner's own zone and passed down, like every other date decision in this
module; `DIGEST_HOUR` is the precedent for naming the threshold rather than
scattering it.
"""

from datetime import date, datetime, timedelta

from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from daily import reads, services
from lists import services as list_services
from lists.models import Item, List


TUESDAY = date(2026, 8, 4)
EVENING = reads.CLOSING_HOUR
MORNING = 9


class ClosingTheDayTest(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.list_ = List.objects.create(owner=self.alice, title="Home")

    def pin(self, text, *, day=TUESDAY):
        task = list_services.create_item(self.list_, text)
        services.pin_task(self.alice, day, task)
        return task

    def finish(self, task, *, on=TUESDAY):
        list_services.complete_item(task)
        Item.objects.filter(pk=task.pk).update(
            completed_at=timezone.make_aware(
                datetime.combine(on, datetime.min.time()) + timedelta(hours=15)
            )
        )

    def release(self, task, *, on=TUESDAY):
        """Unpin, then move the release onto the day being described.

        `unpin_task` stamps the real clock, and `planned_in_week` judges
        against the window's end -- so a release stamped today would fall
        outside a window ending on TUESDAY and read as unfinished. The same
        helper `test_what_was_planned.py` needs, for the same reason.
        """
        services.unpin_task(self.alice, on, task)
        self.alice.daily_focus.filter(task=task).update(
            released_at=timezone.make_aware(
                datetime.combine(on, datetime.min.time()) + timedelta(hours=15)
            )
        )

    def closing(self, *, day=TUESDAY, today=TUESDAY, hour=EVENING):
        return reads.closing_for(self.alice, day, today=today, hour=hour)

    def test_it_says_nothing_before_the_evening(self):
        self.pin("Pay rent")

        self.assertIsNone(self.closing(hour=MORNING))

    def test_in_the_evening_it_reports_what_the_day_held(self):
        finished = self.pin("Pay rent")
        self.finish(finished)
        self.pin("Call the plumber")

        closing = self.closing()

        self.assertEqual((closing.chosen, closing.finished), (2, 1))
        self.assertEqual(closing.unfinished, 1)

    def test_a_released_pin_is_reported_apart_from_what_is_still_open(self):
        """`released_at`'s whole purpose: "I decided this wasn't for today" and
        "I never got to it" are different facts, and a closing line that
        blurred them would report a number nobody should act on."""
        dropped = self.pin("Reorganise the shed")
        self.release(dropped)

        closing = self.closing()

        self.assertEqual(closing.released, 1)
        self.assertEqual((closing.chosen, closing.unfinished), (0, 0))

    def test_it_says_nothing_about_a_day_already_lived(self):
        """A prompt on a past day would ask somebody to reconstruct one, and
        the whole point of the record is that it was written while it was
        still true."""
        self.pin("Pay rent")

        self.assertIsNone(
            self.closing(day=TUESDAY, today=TUESDAY + timedelta(days=1))
        )

    def test_it_says_nothing_about_a_day_not_yet_lived(self):
        self.pin("Pay rent", day=TUESDAY + timedelta(days=1))

        self.assertIsNone(
            self.closing(day=TUESDAY + timedelta(days=1), today=TUESDAY)
        )

    def test_it_keeps_reading_the_day_back_after_something_is_written(self):
        """~~"it stops asking once the day has been written"~~ --
        **September 4, 2026, Vince's call**: the three prose fields left the Day
        page, so this block no longer asks for anything.

        The gate existed because a prompt that stayed after the writing would
        be nagging about something done. What is left is the numbers and rule
        7's three moves, and **a leftover does not stop needing a decision
        because somebody wrote a paragraph.** The evening mail still asks and
        still stops -- `closing_summary_for` keeps the gate, and the test
        below holds it.
        """
        self.pin("Pay rent")
        services.write_entry(self.alice, TUESDAY, happenings="Rained all day.")

        closing = self.closing()
        self.assertIsNotNone(closing)
        self.assertEqual([each.text for each in closing.leftovers], ["Pay rent"])

    def test_the_evening_mail_still_stops_once_the_day_is_written(self):
        """The half that is still an ask, and therefore still stops. The two
        were one question until the fields left the page; keeping the mail's
        gate is what stops it nagging for something already done.
        """
        from daily import reads

        self.pin("Pay rent")
        services.write_entry(self.alice, TUESDAY, happenings="Rained all day.")

        self.assertIsNone(reads.closing_summary_for(self.alice, TUESDAY))

    def test_a_day_nobody_planned_is_still_worth_closing(self):
        """The record is the point, not the score. A day with no pins can
        still be the one worth reading in six months."""
        closing = self.closing()

        self.assertIsNotNone(closing)
        self.assertEqual(closing.chosen, 0)
