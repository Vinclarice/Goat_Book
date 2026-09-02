from datetime import date, datetime, timedelta
from io import StringIO
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core import mail
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from decimal import Decimal

from money import services as bills
from lists.models import Direction, Item, List


class SendDueDigestTest(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.user = User.objects.create_user(
            "vince", "vince@example.com", "sekrit-password"
        )
        self.work = List.objects.create(owner=self.user, title="Work")

    def make(self, text, due_offset=None, owner=None):
        for_list = (
            self.work
            if owner is None
            else List.objects.create(owner=owner, title="Theirs")
        )
        return Item.objects.create(
            list=for_list,
            text=text,
            due_date=(
                None
                if due_offset is None
                else self.today + timedelta(days=due_offset)
            ),
        )

    def run_command(self, **options):
        # These cover what a digest says, not when it goes out. Opening the
        # hour gate keeps them from depending on what time the suite runs
        # at; the scheduling rules have their own tests below.
        options.setdefault("send_hour", 0)
        options.setdefault("until_hour", 24)
        out = StringIO()
        call_command("send_due_digest", stdout=out, **options)
        return out.getvalue()

    def test_emails_overdue_and_due_today(self):
        self.make("Renew insurance", due_offset=-3)
        self.make("Ship the fix", due_offset=0)

        self.run_command()

        [message] = mail.outbox
        self.assertEqual(message.to, ["vince@example.com"])
        self.assertIn("Renew insurance", message.body)
        self.assertIn("Ship the fix", message.body)

    def test_leaves_out_tasks_that_are_not_due_yet(self):
        self.make("Ship the fix", due_offset=0)
        self.make("Next week", due_offset=6)
        self.make("No deadline")

        self.run_command()

        [message] = mail.outbox
        self.assertNotIn("Next week", message.body)
        self.assertNotIn("No deadline", message.body)

    def test_sends_a_digest_when_a_due_task_has_no_area(self):
        """`Item.list` went nullable on August 14 and `_describe` still reached
        through it, so a single unfiled due task raised and the digest was
        never sent -- not degraded, not partial, absent. An unfiled task is one
        tap from the knowledge core's `confirm_actionable`, and the send loop
        orders by username, so this starved every recipient sorting after the
        affected one as well."""
        self.make("Renew insurance", due_offset=-3)
        Item.objects.create(
            list=None, owner=self.user, text="Dentist", due_date=self.today
        )

        self.run_command()

        [message] = mail.outbox
        self.assertIn("Dentist", message.body)
        self.assertIn("Renew insurance", message.body)

    def test_names_no_area_for_an_unfiled_task(self):
        """Absent rather than borrowed or invented, following `0857835`: an
        unfiled task gets the absence of the signal, so the line carries its
        timing and nothing where the Area would be."""
        Item.objects.create(
            list=None, owner=self.user, text="Dentist", due_date=self.today
        )

        self.run_command()

        body = mail.outbox[0].body
        self.assertIn("  - Dentist (due today)", body)

    def test_each_task_carries_a_link_to_itself(self):
        """`commercial-blueprint.md` Part 3: the digest was the product's only
        outbound channel and ended "Open Clarice to work through them." with
        nothing clickable -- so the one message that reaches somebody on a
        phone made them go and find the task by hand.

        Absolute, and from `settings.SITE_URL`, because there is no request to
        build one against. That is the same setting `accounts/apps.py` already
        uses for the login link in an approval mail."""
        task = self.make("Pay rent", due_offset=0)

        self.run_command()

        body = mail.outbox[0].body
        self.assertIn(f"{settings.SITE_URL}/app/tasks/{task.id}", body)

    def test_the_closing_line_is_a_link_rather_than_an_instruction(self):
        self.make("Pay rent", due_offset=0)

        self.run_command()

        body = mail.outbox[0].body
        self.assertIn(f"{settings.SITE_URL}/app/day", body)
        self.assertNotIn("Open Clarice to work through them.", body)

    def test_one_rejected_recipient_does_not_starve_everybody_after_them(self):
        """The loop orders by username and had no guard, so a raise on the
        first recipient ended the run. For anyone in the same or an earlier
        time zone -- which at three users is everybody -- the digest was not
        delayed, it was never delivered, and the write-off path stamped
        `last_digest_date` anyway, so the day was recorded as decided.

        This file already guards the *other* one-user-blocks-everyone failure,
        two lines up: `resolve_time_zone(...) or ZoneInfo(...)`. The class was
        recognised; the likelier instance was not.
        """
        from smtplib import SMTPRecipientsRefused

        alice = User.objects.create_user("alice", "alice@example.com", "pw")
        alice_area = List.objects.create(owner=alice, title="Hers")
        Item.objects.create(list=alice_area, text="Alice task", due_date=self.today)
        self.make("Vince task", due_offset=0)

        def refuse_alice(*args, **kwargs):
            if kwargs["recipient_list"] == ["alice@example.com"]:
                raise SMTPRecipientsRefused({"alice@example.com": (550, b"nope")})
            return mail.send_mail(*args, **kwargs)

        with patch(
            "lists.management.commands.send_due_digest.send_mail",
            side_effect=refuse_alice,
        ):
            # Raised at the end, after everybody else has been served -- see
            # test_a_failed_send_is_reported_rather_than_swallowed.
            with self.assertRaises(CommandError):
                self.run_command()

        self.assertEqual([message.to for message in mail.outbox], [["vince@example.com"]])

    def test_a_recipient_whose_send_failed_is_not_written_off(self):
        """Their day was not decided, so it must not be stamped -- otherwise
        the next hourly run skips them and a transient rejection costs a whole
        day silently."""
        from smtplib import SMTPRecipientsRefused

        self.make("Ship the fix", due_offset=0)

        with patch(
            "lists.management.commands.send_due_digest.send_mail",
            side_effect=SMTPRecipientsRefused({"vince@example.com": (550, b"nope")}),
        ):
            with self.assertRaises(CommandError):
                self.run_command()

        self.user.refresh_from_db()
        self.assertIsNone(self.user.last_digest_date)

    def test_a_failed_send_is_reported_rather_than_swallowed(self):
        """Catching the exception is what keeps the run going; saying nothing
        about it is how a daily failure becomes invisible. The command names
        who failed and exits non-zero."""
        from smtplib import SMTPRecipientsRefused

        self.make("Ship the fix", due_offset=0)

        with patch(
            "lists.management.commands.send_due_digest.send_mail",
            side_effect=SMTPRecipientsRefused({"vince@example.com": (550, b"nope")}),
        ):
            with self.assertRaises(CommandError) as raised:
                self.run_command()

        self.assertIn("vince", str(raised.exception))

    def test_a_failed_send_is_logged_where_sentry_can_see_it(self):
        """Catching the exception must not cost the report of it.

        Before the loop was guarded, a send that raised crashed the command and
        Sentry caught the traceback -- which is how the 2026-08-16 SMTP
        connection timeout was found at all. Guarding it turned that into a
        CommandError, and `BaseCommand.run_from_argv` catches CommandError,
        writes to stderr and exits: it never propagates, so Sentry never sees
        it. Cron has no MAILTO and the host has no MTA, so stderr goes nowhere
        either, and the fix for D6 would have made the next outage silent.

        `logger.exception` is what puts it back: sentry-sdk installs
        LoggingIntegration by default with an event level of ERROR, so this
        becomes an event without the command importing the SDK.
        """
        from smtplib import SMTPRecipientsRefused

        self.make("Ship the fix", due_offset=0)

        with patch(
            "lists.management.commands.send_due_digest.send_mail",
            side_effect=SMTPRecipientsRefused({"vince@example.com": (550, b"nope")}),
        ):
            with self.assertLogs(
                "lists.management.commands.send_due_digest", level="ERROR"
            ) as logged:
                with self.assertRaises(CommandError):
                    self.run_command()

        [record] = logged.records
        self.assertEqual(record.levelname, "ERROR")
        # exc_info is what carries the traceback into the Sentry event. Without
        # it the event says a digest failed and not what it failed on.
        self.assertIsNotNone(record.exc_info)
        self.assertIn("vince", record.getMessage())

    def test_says_how_overdue_each_task_is(self):
        self.make("Renew insurance", due_offset=-3)
        self.make("Call back", due_offset=-1)

        self.run_command()

        body = mail.outbox[0].body
        self.assertIn("3 days overdue", body)
        self.assertIn("due yesterday", body)

    def test_subject_summarises_the_workload(self):
        self.make("Renew insurance", due_offset=-3)
        self.make("Ship the fix", due_offset=0)

        self.run_command()

        self.assertIn("1 overdue", mail.outbox[0].subject)
        self.assertIn("1 due today", mail.outbox[0].subject)

    def test_sends_nothing_when_there_is_nothing_due(self):
        self.make("Next week", due_offset=6)

        self.run_command()

        self.assertEqual(mail.outbox, [])

    def test_skips_users_who_opted_out(self):
        self.user.daily_digest = False
        self.user.save()
        self.make("Ship the fix", due_offset=0)

        self.run_command()

        self.assertEqual(mail.outbox, [])

    def test_skips_inactive_accounts(self):
        self.user.is_active = False
        self.user.save()
        self.make("Ship the fix", due_offset=0)

        self.run_command()

        self.assertEqual(mail.outbox, [])

    def test_each_user_only_hears_about_their_own_tasks(self):
        other = User.objects.create_user(
            "someone", "someone@example.com", "sekrit-password"
        )
        self.make("Mine", due_offset=0)
        self.make("Theirs", due_offset=0, owner=other)

        self.run_command()

        bodies = {message.to[0]: message.body for message in mail.outbox}
        self.assertIn("Mine", bodies["vince@example.com"])
        self.assertNotIn("Theirs", bodies["vince@example.com"])
        self.assertIn("Theirs", bodies["someone@example.com"])
        self.assertNotIn("Mine", bodies["someone@example.com"])

    def test_username_option_limits_who_is_considered(self):
        other = User.objects.create_user(
            "someone", "someone@example.com", "sekrit-password"
        )
        self.make("Mine", due_offset=0)
        self.make("Theirs", due_offset=0, owner=other)

        self.run_command(username="vince")

        self.assertEqual([m.to[0] for m in mail.outbox], ["vince@example.com"])

    def test_dry_run_prints_without_sending(self):
        self.make("Ship the fix", due_offset=0)

        output = self.run_command(dry_run=True)

        self.assertEqual(mail.outbox, [])
        self.assertIn("Ship the fix", output)

    def test_archived_and_completed_tasks_are_not_reported(self):
        completed = self.make("Already done", due_offset=0)
        completed.status = Item.Status.COMPLETED
        completed.completed_at = timezone.now()
        completed.save()

        self.run_command()

        self.assertEqual(mail.outbox, [])


# One hour apart, chosen so the two real users are on opposite sides of
# the 07:00 rule at the same instant:
#
#   22:00 UTC -> 06:00 Aug 2 in Makassar (too early), 18:00 Aug 1 in New York
#   23:00 UTC -> 07:00 Aug 2 in Makassar (due),       19:00 Aug 1 in New York
#
# The twelve-hour spread is why one daily run cannot serve both.
BEFORE_MAKASSAR_MORNING = datetime(2026, 8, 1, 22, 0, tzinfo=ZoneInfo("UTC"))
AT_MAKASSAR_MORNING = datetime(2026, 8, 1, 23, 0, tzinfo=ZoneInfo("UTC"))
MID_MAKASSAR_MORNING = datetime(2026, 8, 2, 1, 0, tzinfo=ZoneInfo("UTC"))

# 15:00 Aug 2 in Makassar -- his morning is spent. Also 03:00 Aug 2 in New
# York, before Edith's window opens, so she stays out of the way here.
MAKASSAR_AFTERNOON = datetime(2026, 8, 2, 7, 0, tzinfo=ZoneInfo("UTC"))

# 07:00 Aug 2 in New York. The two windows never overlap -- Obi's 07:00-12:00
# is 23:00-04:00 UTC and Edith's is 11:00-16:00 UTC -- which is the whole
# point, and why these tests assert per user rather than about the outbox.
NEW_YORK_MORNING = datetime(2026, 8, 2, 11, 0, tzinfo=ZoneInfo("UTC"))


class BillsInTheDigestTest(TestCase):
    """The digest keeps mentioning bills after they stop being tasks.

    **The flip is where this could have gone silently wrong.** The digest reads
    `agenda.open_items_for`, which after increment 4 of
    `bill-as-a-model-plan.md` returns no bills at all, because there are none
    left to return -- a bill is not an `Item`. Nothing in the digest's own
    tests named a bill, so the one outbound channel this product has would have
    quietly stopped mentioning the thing it is most useful for.

    **Its own section, and its own link.** A bill has no area to name and no
    `/tasks/{id}` to open, so rendering it through `_describe` would print a
    task's sentence about a record that is not one.
    """

    def setUp(self):
        self.today = timezone.localdate()
        self.user = User.objects.create_user(
            "vince", "vince@example.com", "sekrit-password"
        )

    def run_command(self, **options):
        options.setdefault("send_hour", 0)
        options.setdefault("until_hour", 24)
        out = StringIO()
        call_command("send_due_digest", stdout=out, **options)
        return out.getvalue()

    def bill(self, payee, due_offset, **kwargs):
        return bills.record(
            self.user,
            payee=payee,
            amount=Decimal("120.00"),
            due_date=self.today + timedelta(days=due_offset),
            **kwargs,
        )

    def test_an_overdue_bill_is_in_the_email(self):
        self.bill("Landlord", -3)

        self.run_command()

        [message] = mail.outbox
        self.assertIn("Landlord", message.body)

    def test_a_bill_links_to_money_rather_than_to_a_task(self):
        """`/tasks/{id}` would 404 on a record that is not a task, and the
        link is the whole reason the digest is worth clicking."""
        bill = self.bill("Landlord", 0)

        self.run_command()

        [message] = mail.outbox
        self.assertIn(f"money/bills/{bill.id}", message.body)
        self.assertNotIn(f"tasks/{bill.id}", message.body)

    def test_a_settled_bill_is_not_mentioned(self):
        bill = self.bill("Landlord", 0)
        bills.settle(bill)

        self.run_command()

        self.assertEqual(mail.outbox, [])

    def test_a_bill_alone_is_worth_a_message(self):
        """The same rule advance notice already has: gating on tasks would
        leave the channel silent on exactly the morning a bill is due."""
        self.bill("Landlord", 0)

        self.run_command()

        self.assertEqual(len(mail.outbox), 1)

    def test_money_coming_in_is_not_a_morning_reminder(self):
        """`open_bills_for` excludes income for the reason the agenda does: a
        salary is not something to do."""
        self.bill("Work", 0, direction=Direction.IN)

        self.run_command()

        self.assertEqual(mail.outbox, [])


class DigestSchedulingTest(TestCase):
    """When the hourly run decides each person's morning has arrived."""

    def setUp(self):
        self.obi = self.make_user("obi", "Asia/Makassar")
        self.edith = self.make_user("edith", "America/New_York")
        # Each has one task due on their own August date.
        self.give(self.obi, "Pay the landlord", date(2026, 8, 2))
        self.give(self.edith, "Renew insurance", date(2026, 8, 1))

    def make_user(self, username, time_zone):
        return User.objects.create_user(
            username,
            f"{username}@example.com",
            "sekrit-password",
            time_zone=time_zone,
        )

    def give(self, user, text, due_date):
        Item.objects.create(
            list=List.objects.create(owner=user, title=f"{user.username}'s"),
            text=text,
            due_date=due_date,
        )

    def run_at(self, moment, **options):
        out = StringIO()
        with patch("django.utils.timezone.now", return_value=moment):
            call_command("send_due_digest", stdout=out, **options)
        return out.getvalue()

    def recipients(self):
        return sorted(message.to[0] for message in mail.outbox)

    def got_mail(self, user):
        return user.email in self.recipients()

    def test_sends_when_the_users_own_morning_arrives(self):
        self.run_at(AT_MAKASSAR_MORNING)

        self.assertTrue(self.got_mail(self.obi))

    def test_does_not_send_before_the_users_morning(self):
        # 06:00 for Obi. Not sent, and left undecided -- his morning is
        # still ahead of him, unlike a written-off one.
        self.run_at(BEFORE_MAKASSAR_MORNING)
        self.obi.refresh_from_db()

        self.assertFalse(self.got_mail(self.obi))
        self.assertIsNone(self.obi.last_digest_date)

    def test_the_far_side_of_the_world_gets_a_different_hour_entirely(self):
        self.run_at(AT_MAKASSAR_MORNING)
        obi_hour = AT_MAKASSAR_MORNING
        mail.outbox.clear()

        self.run_at(NEW_YORK_MORNING)

        self.assertTrue(self.got_mail(self.edith))
        self.assertEqual(NEW_YORK_MORNING - obi_hour, timedelta(hours=12))

    def test_running_again_the_same_local_day_sends_nothing(self):
        self.run_at(AT_MAKASSAR_MORNING)
        mail.outbox.clear()

        self.run_at(MID_MAKASSAR_MORNING)

        self.assertEqual(mail.outbox, [])

    def test_a_missed_morning_still_gets_its_digest_later(self):
        # The 07:00 run never happened -- reboot, slow image pull, a DST
        # transition that skipped the hour. 09:00 local should still send.
        self.run_at(MID_MAKASSAR_MORNING)

        self.assertIn("obi@example.com", self.recipients())

    def test_a_quiet_day_is_still_marked_decided(self):
        # Nothing due, so no mail -- but the day must be recorded as
        # handled, or a task turning overdue at 14:00 mails a "good
        # morning" at 15:00.
        Item.objects.filter(list__owner=self.obi).delete()

        self.run_at(AT_MAKASSAR_MORNING)
        self.obi.refresh_from_db()

        self.assertNotIn("obi@example.com", self.recipients())
        self.assertEqual(self.obi.last_digest_date, date(2026, 8, 2))

    def test_stamps_the_users_own_local_date(self):
        self.run_at(AT_MAKASSAR_MORNING)
        self.obi.refresh_from_db()
        self.edith.refresh_from_db()

        # The same instant, recorded as two different dates.
        self.assertEqual(self.obi.last_digest_date, date(2026, 8, 2))
        self.assertEqual(self.edith.last_digest_date, date(2026, 8, 1))

    def test_dry_run_decides_nothing(self):
        self.run_at(AT_MAKASSAR_MORNING, dry_run=True)
        self.obi.refresh_from_db()

        self.assertEqual(mail.outbox, [])
        self.assertIsNone(self.obi.last_digest_date)

        # And the real run that follows is unaffected by it.
        self.run_at(AT_MAKASSAR_MORNING)
        self.assertIn("obi@example.com", self.recipients())

    def test_an_unresolvable_stored_zone_does_not_stop_the_run(self):
        User.objects.filter(pk=self.obi.pk).update(time_zone="Mars/Olympus_Mons")

        self.run_at(NEW_YORK_MORNING)

        # Obi falls back to the project default rather than raising, so
        # Edith -- who is sorted after him -- is still reached.
        self.assertTrue(self.got_mail(self.edith))

    def test_a_morning_missed_entirely_is_written_off_not_sent_late(self):
        # By 15:00 a "Good morning, here is your day" is no longer useful,
        # it is just wrong. The day is marked decided so tomorrow's run
        # starts clean, and nothing is sent.
        self.run_at(MAKASSAR_AFTERNOON)
        self.obi.refresh_from_db()

        self.assertNotIn("obi@example.com", self.recipients())
        self.assertEqual(self.obi.last_digest_date, date(2026, 8, 2))

    def test_writing_off_one_day_does_not_touch_the_next(self):
        self.run_at(MAKASSAR_AFTERNOON)
        mail.outbox.clear()

        # 07:00 Aug 3 in Makassar.
        self.run_at(MAKASSAR_AFTERNOON + timedelta(hours=16))

        self.assertIn("obi@example.com", self.recipients())

    def test_someone_whose_window_has_not_opened_is_left_undecided(self):
        # Edith is at 03:00 here. Not sent, and crucially not written off
        # either -- her morning is still ahead of her.
        self.run_at(MAKASSAR_AFTERNOON)
        self.edith.refresh_from_db()

        self.assertNotIn("edith@example.com", self.recipients())
        self.assertIsNone(self.edith.last_digest_date)

    def test_eighteen_hourly_runs_send_exactly_one_digest_each(self):
        # Long enough to contain both windows -- Obi's opens at 23:00 UTC,
        # Edith's at 11:00 -- and short enough not to reach anyone's second
        # morning, where another digest would be correct rather than a
        # duplicate.
        for hour in range(18):
            self.run_at(BEFORE_MAKASSAR_MORNING + timedelta(hours=hour))

        self.assertEqual(
            self.recipients(), ["edith@example.com", "obi@example.com"]
        )
