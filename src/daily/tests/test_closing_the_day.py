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

import json
from datetime import date, datetime, timedelta

from django.test import TestCase
from django.utils import timezone

from accounts.models import (
    SCOPE_DAY_READ,
    SCOPE_DAY_WRITE,
    PersonalAccessToken,
    User,
)
from daily import reads, services
from daily.models import DailyFocus
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


class LeftoverDecisionsFromAPhoneTest(TestCase):
    """Rule 7's three moves, reachable by a bearer -- android-overhaul-plan.md
    increment 4.

    **The endpoint asked to be asked, and this is the asking.** Its docstring
    said *session only. The phone has no evening ritual, and letting go
    archives a task -- widening a bearer that sits in a keystore for ninety
    days to do that should be asked for rather than arrive with a closing
    prompt.* The phone has an evening now, and the widening is the increment
    rather than a side effect of one.

    **All three moves, including `let_go`, and the reason is evidence rather
    than judgement.** `TaskStatus` includes `"archived"` and
    `PATCH /api/v1/tasks/{task_id}` is already token-authenticated and already
    accepts `status` -- so a bearer can archive a task today, through a door
    that has been open since August. Refusing `let_go` here would guard a
    capability the same token already has, which is an inconsistency rather
    than a protection, and the kind that gets discovered later as a seam.

    `day:write`, the scope every other write on this router takes. Pinning a
    focus and choosing a leftover for tomorrow are the same act reached two
    ways -- `leftovers.tomorrow` calls `pin_task`.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", "correct horse battery staple 47!"
        )
        self.today = timezone.localdate()

    def a_pinned_task(self, text="Write the plan doc"):
        task = Item.objects.create(owner=self.user, text=text)
        services.pin_task(self.user, self.today, task)
        return task

    def decide(self, task, decision, token):
        return self.client.post(
            f"/api/v1/day/{self.today.isoformat()}/leftovers/{task.id}",
            data=json.dumps({"decision": decision}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

    def a_token(self, *scopes):
        _, raw = PersonalAccessToken.generate(self.user, scopes=list(scopes))
        return raw

    def test_a_token_can_choose_a_leftover_for_tomorrow(self):
        task = self.a_pinned_task()

        response = self.decide(task, "tomorrow", self.a_token(SCOPE_DAY_WRITE))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            DailyFocus.objects.filter(
                owner=self.user,
                entry__date=self.today + timedelta(days=1),
                task=task,
            ).exists()
        )

    def test_choosing_tomorrow_is_never_a_date_move(self):
        """Rule 7, and the defect the website fixed on September 3, 2026: a due
        date is a promise to somebody, and choosing to work on something
        tomorrow is not the same act as re-promising it."""
        task = self.a_pinned_task()

        self.decide(task, "tomorrow", self.a_token(SCOPE_DAY_WRITE))

        task.refresh_from_db()
        self.assertIsNone(task.due_date)

    def test_a_token_can_put_a_leftover_back_in_the_pool(self):
        task = self.a_pinned_task()

        response = self.decide(task, "pool", self.a_token(SCOPE_DAY_WRITE))

        self.assertEqual(response.status_code, 200)
        task.refresh_from_db()
        self.assertEqual(task.status, Item.Status.ACTIVE)

    def test_a_token_can_let_a_leftover_go(self):
        """Allowed rather than refused, and not because archiving is harmless:
        because a bearer already reaches it through
        `PATCH /api/v1/tasks/{task_id}`, which accepts `status: "archived"`.
        A guard here would stop nothing."""
        task = self.a_pinned_task()

        response = self.decide(task, "let_go", self.a_token(SCOPE_DAY_WRITE))

        self.assertEqual(response.status_code, 200)
        task.refresh_from_db()
        self.assertEqual(task.status, Item.Status.ARCHIVED)

    def test_a_token_without_day_write_is_refused(self):
        task = self.a_pinned_task()

        response = self.decide(task, "tomorrow", self.a_token(SCOPE_DAY_READ))

        self.assertEqual(response.status_code, 401)
        self.assertFalse(
            DailyFocus.objects.filter(
                owner=self.user, entry__date=self.today + timedelta(days=1)
            ).exists()
        )

    def test_a_token_cannot_decide_about_someone_elses_leftover(self):
        other = User.objects.create_user(
            "bob", "bob@example.com", "correct horse battery staple 47!"
        )
        theirs = Item.objects.create(owner=other, text="Bob's loose end")

        response = self.decide(theirs, "let_go", self.a_token(SCOPE_DAY_WRITE))

        # 404 rather than 403, so the endpoint does not confirm that somebody
        # else's task id exists.
        self.assertEqual(response.status_code, 404)
        theirs.refresh_from_db()
        self.assertEqual(theirs.status, Item.Status.ACTIVE)
