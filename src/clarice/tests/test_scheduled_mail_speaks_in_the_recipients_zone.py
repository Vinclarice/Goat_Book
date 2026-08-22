"""Scheduled mail composes in the recipient's own zone — **D16's second half**.

`deliver_once_a_day` already worked out each recipient's local day, and passing
it down was not enough. **The reads underneath `compose` convert their own
timestamps**, with `timezone.localtime`, which reads the *active* zone — and out
here there is no middleware, so every recipient was composed in
`settings.TIME_ZONE` whatever zone they had chosen.

**It was live.** `send_closing_nudge` asks `planned_in_week` what was finished
today; for a recipient west of the setting a task finished at 21:00 was dated
*tomorrow*, failed *on or before today*, and the mail said **"You finished 0 of
2"** an hour after they finished one.
`daily/tests/test_send_closing_nudge.py` holds that case.

**This is the same contract one level up**, because the defect is the mailer's
rather than the nudge's and **the digest shares it** — untested until now, since
`deliver_once_a_day` had no test of its own and was only ever exercised through
the two commands.

`accounts.auth._resolve_scoped_token` made this exact move for token requests
after six endpoints each forgot to. *A note telling the next person to remember
something is not a mechanism* is already written in `accounts/middleware.py`;
this is the mechanism for the third path.
"""

import datetime

from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from clarice import scheduled_mail


#: **An instant where the clocks disagree, chosen deliberately.** 22:00 on
#: August 4 in Los Angeles is already 01:00 on the 5th in `settings.TIME_ZONE`,
#: and 13:00 on the 5th in Makassar. An instant where they agree would let this
#: whole file pass against the bug it exists to catch -- which is exactly how
#: `what_surrounded` and the nudge both shipped broken.
WHEN = datetime.datetime(2026, 8, 5, 5, 0, tzinfo=datetime.timezone.utc)


class ScheduledMailSpeaksInTheRecipientsZoneTest(TestCase):
    def setUp(self):
        self.vince = User.objects.create_user(
            "vince", "vince@example.com", "a secure password"
        )
        self.vince.time_zone = "America/Los_Angeles"
        self.vince.save(update_fields=["time_zone"])
        self.seen = []

    def run_mailer(self, **overrides):
        def compose(user, today):
            # What any read underneath would see. `localdate` with no argument
            # is exactly what `daily`, `lists`, `routines` and `review` call.
            self.seen.append((timezone.localdate(WHEN), today))
            return None

        return scheduled_mail.deliver_once_a_day(
            recipients=User.objects.all(),
            now=WHEN,
            compose=compose,
            deliver=lambda user, subject, body: None,
            stamp_field="last_digest_date",
            label="test",
            send_hour=overrides.get("send_hour", 6),
            until_hour=overrides.get("until_hour", 23),
        )

    def test_the_active_zone_is_the_recipients_while_composing(self):
        self.run_mailer()

        seen_by_a_read, passed_in = self.seen[0]
        # August 4 in Los Angeles. `settings.TIME_ZONE` would say the 5th, and
        # did until August 22.
        self.assertEqual(seen_by_a_read, datetime.date(2026, 8, 4))
        self.assertEqual(seen_by_a_read, passed_in)

    def test_one_recipient_does_not_leave_their_zone_behind(self):
        """`override` rather than the middleware's activate/deactivate pair:
        this runs in a loop, and `deactivate` clears where `override` restores.
        A recipient must not be able to change the zone the next one is
        composed in -- which is the leak the middleware's own docstring
        describes for request threads."""
        makassar = User.objects.create_user(
            "priya", "priya@example.com", "a secure password"
        )
        makassar.time_zone = "Asia/Makassar"
        makassar.save(update_fields=["time_zone"])

        with timezone.override(datetime.timezone.utc):
            self.run_mailer()
            still_utc = timezone.localdate(WHEN)

        self.assertEqual(len(self.seen), 2)
        # Ordered by username: priya (Makassar, already the 5th) then vince
        # (Los Angeles, still the 4th). Two recipients, two different days,
        # from one instant -- which is the whole point of a per-user clock.
        self.assertEqual(self.seen[0][0], datetime.date(2026, 8, 5))
        self.assertEqual(self.seen[1][0], datetime.date(2026, 8, 4))
        self.assertEqual(still_utc, datetime.date(2026, 8, 5))

    def test_a_retired_zone_does_not_stop_the_run(self):
        """`clocks.zone_for` falls back rather than raising, and the reason is
        this loop: one recipient holding a zone tzdata has dropped must not
        take the mail down for everybody after them."""
        self.vince.time_zone = "Mars/Olympus"
        self.vince.save(update_fields=["time_zone"])

        sent, failed = self.run_mailer()

        self.assertEqual(failed, [])
