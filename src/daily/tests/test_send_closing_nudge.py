"""The nudge that actually reaches him — S5's third absence.

Its verdict named three: *"no evening surface, no prompt, no reminder"*. The
first two shipped with the closing ritual, and the third stayed true, because
an in-page prompt asks when you open the day and does nothing if you do not.

**A second scheduled message, not a second scheduler.** Everything hard about
delivering once per person per local day -- the zone, the stamp, at-or-after,
the closing window, stamping a quiet day, one failure staying one person's --
is `clarice.scheduled_mail`'s, extracted before this was written precisely so
this could not copy it.

**Off by default, unlike the digest.** A second recurring message is a
different thing to agree to, and turning one on is a smaller ask than
discovering one. `/privacy/` said *"the one recurring message is the daily
summary"*; that sentence is amended with this, because a published promise the
code contradicts is worse than no promise.

**It stops once the record exists**, the same rule the in-page prompt follows
and through the same read: the ask is for the writing, so a nudge that arrived
after it would be nagging about something already done.
"""

from datetime import date, datetime, timedelta
from io import StringIO
from zoneinfo import ZoneInfo

from django.core import mail
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from daily import services
from lists import services as list_services
from lists.models import Item, List


TUESDAY = date(2026, 8, 4)


class SendClosingNudgeTest(TestCase):
    def setUp(self):
        self.vince = User.objects.create_user(
            "vince", "vince@example.com", "a secure password"
        )
        self.vince.closing_nudge = True
        self.vince.save(update_fields=["closing_nudge"])
        self.list_ = List.objects.create(owner=self.vince, title="Home")

    def run_at(self, hour=19, **options):
        """Run as if it were `hour` in the recipient's own zone."""
        evening = timezone.make_aware(
            datetime.combine(TUESDAY, datetime.min.time())
            + timedelta(hours=hour),
            ZoneInfo(self.vince.time_zone or "UTC"),
        )
        out = StringIO()
        with timezone.override(ZoneInfo("UTC")):
            call_command(
                "send_closing_nudge", stdout=out, now=evening.isoformat(), **options
            )
        return out.getvalue()

    def pin(self, text="Pay rent", *, finish=False):
        task = list_services.create_item(self.list_, text)
        services.pin_task(self.vince, TUESDAY, task)
        if finish:
            list_services.complete_item(task)
            Item.objects.filter(pk=task.pk).update(
                completed_at=timezone.make_aware(
                    datetime.combine(TUESDAY, datetime.min.time())
                    + timedelta(hours=15)
                )
            )
        return task

    def test_it_asks_in_the_evening(self):
        self.pin()

        self.run_at()

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("vince@example.com", mail.outbox[0].to)

    def test_it_says_nothing_before_the_evening(self):
        self.pin()

        self.run_at(hour=9)

        self.assertEqual(mail.outbox, [])

    def test_it_reports_what_the_day_held_and_links_to_it(self):
        self.pin("Pay rent", finish=True)
        self.pin("Call the plumber")

        self.run_at()

        body = mail.outbox[0].body
        self.assertIn("1 of 2", body)
        self.assertIn("/app/day/2026-08-04", body)

    def test_it_stops_once_the_day_has_been_written(self):
        """The ask is for the record, so it ends when the record exists --
        the same rule the in-page prompt follows, through the same read."""
        self.pin()
        services.write_entry(self.vince, TUESDAY, happenings="Rained all day.")

        self.run_at()

        self.assertEqual(mail.outbox, [])

    def test_nobody_gets_it_who_has_not_asked_for_it(self):
        """Off by default, unlike the digest. A second recurring message is a
        different thing to agree to."""
        self.vince.closing_nudge = False
        self.vince.save(update_fields=["closing_nudge"])
        self.pin()

        self.run_at()

        self.assertEqual(mail.outbox, [])

    def test_it_is_off_by_default(self):
        fresh = User.objects.create_user("sam", "sam@example.com", "a password")

        self.assertFalse(fresh.closing_nudge)

    def test_an_hourly_run_does_not_ask_twice(self):
        """The stamp is the scheduler's, and this is the test that it is
        wired -- twelve evening runs must cost one message."""
        self.pin()

        self.run_at()
        self.run_at(hour=20)

        self.assertEqual(len(mail.outbox), 1)

    def test_a_dry_run_neither_sends_nor_spends_the_day(self):
        self.pin()

        self.run_at(dry_run=True)

        self.assertEqual(mail.outbox, [])
        self.vince.refresh_from_db()
        self.assertIsNone(self.vince.last_closing_nudge_date)
