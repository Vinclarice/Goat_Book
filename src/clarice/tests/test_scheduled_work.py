"""Noticing that a scheduled job stopped, which nothing did.

Three cron entries -- the mind maintenance pass, the due digest, the erasure
sweep. The commands print for a reader (`purge_deleted_accounts.py`: *"a command
that prints nothing when there is nothing to do is indistinguishable from a
command that did not run"*) into a stream with no `MAILTO` and no MTA behind it.
Failures inside their loops now reach Sentry through `logger.exception`. **A job
that stops being scheduled still produces nothing at all**, and that is the half
this covers.

**It watches outcomes, not heartbeats**, which is the design decision worth
stating. A heartbeat answers "did the command run"; these answer "is the work
this command exists to do actually done". The second is strictly stronger --
it catches the job not running, the job running and failing, and the job running
and silently skipping somebody, which a ping cannot tell apart.

That choice is also what makes this possible without a new model. Every signal
below already exists: `deletion_requested_at`, `last_digest_date`, and mind's
`MAINTENANCE_RAN` events. `clarice` is not an installed app and could not hold a
`ScheduledJobRun` without becoming one.
"""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from accounts import services as account_services
from accounts.models import User
from clarice.health import scheduled_work_is_current


PASSWORD = "correct horse battery staple 47!"


class NothingScheduledYetTest(TestCase):
    def test_an_empty_site_is_current(self):
        """No accounts, no digests owed, nothing overdue. A check that reported
        trouble on a site with no work to do would be read as noise and then
        not read at all."""
        self.assertTrue(scheduled_work_is_current(now=timezone.now()))


class ErasureTest(TestCase):
    """The sweep whose failure is a legal obligation left outstanding.

    Outcome rather than heartbeat: an account still present days after its
    grace period ended means the erasure is not happening, whether the cron
    entry vanished, the command raised, or it ran and skipped that one.
    """

    def setUp(self):
        self.now = timezone.now()
        self.user = User.objects.create_user("alice", "alice@example.com", PASSWORD)

    def test_an_account_just_past_its_grace_period_is_not_yet_a_problem(self):
        """The sweep runs at 04:40. Something becoming due at 04:41 is due for
        a day before anybody should hear about it."""
        account_services.request_deletion(
            self.user,
            now=self.now - account_services.ACCOUNT_DELETION_GRACE - timedelta(hours=2),
        )

        self.assertTrue(scheduled_work_is_current(now=self.now))

    def test_an_account_days_past_its_grace_period_is(self):
        account_services.request_deletion(
            self.user,
            now=self.now - account_services.ACCOUNT_DELETION_GRACE - timedelta(days=3),
        )

        self.assertFalse(scheduled_work_is_current(now=self.now))

    def test_an_account_inside_its_grace_period_is_not(self):
        account_services.request_deletion(self.user, now=self.now)

        self.assertTrue(scheduled_work_is_current(now=self.now))


class DigestTest(TestCase):
    """`send_due_digest` stamps `last_digest_date` for every eligible user each
    morning -- including the write-off path, which stamps when nothing was sent.
    That makes the stamp a genuine record of the command having reached that
    user, rather than a record of mail going out.
    """

    def setUp(self):
        self.now = timezone.now()
        self.today = timezone.localdate()
        self.user = User.objects.create_user("alice", "alice@example.com", PASSWORD)
        self.user.daily_digest = True
        self.user.save(update_fields=["daily_digest"])

    def test_a_user_stamped_today_is_current(self):
        self.user.last_digest_date = self.today
        self.user.save(update_fields=["last_digest_date"])

        self.assertTrue(scheduled_work_is_current(now=self.now))

    def test_a_user_never_stamped_is_not_a_problem_on_their_first_day(self):
        """A brand-new account has no stamp and has not missed anything. This
        is the case a naive "is the max stamp recent" check gets wrong."""
        self.assertTrue(scheduled_work_is_current(now=self.now))

    def test_a_user_stale_by_days_is_a_problem(self):
        self.user.last_digest_date = self.today - timedelta(days=4)
        self.user.save(update_fields=["last_digest_date"])

        self.assertFalse(scheduled_work_is_current(now=self.now))

    def test_a_user_who_turned_the_digest_off_is_not_counted(self):
        self.user.daily_digest = False
        self.user.last_digest_date = self.today - timedelta(days=30)
        self.user.save(update_fields=["daily_digest", "last_digest_date"])

        self.assertTrue(scheduled_work_is_current(now=self.now))

    def test_an_inactive_account_is_not_counted(self):
        """`send_due_digest` filters on `is_active`, so a pending signup is not
        somebody the digest is failing."""
        self.user.is_active = False
        self.user.last_digest_date = self.today - timedelta(days=30)
        self.user.save(update_fields=["is_active", "last_digest_date"])

        self.assertTrue(scheduled_work_is_current(now=self.now))


class MaintenanceTest(TestCase):
    """The pass that extracts concepts and runs detectors.

    Recorded per owner by `record_maintenance_run`, and only for owners with
    notes -- which is the same set the command itself iterates, so the check and
    the command agree about who is owed a pass.
    """

    def setUp(self):
        self.now = timezone.now()
        self.owner = User.objects.create_user("alice", "alice@example.com", PASSWORD)

    def capture(self):
        from mind import services as mind_services
        from mind.models import NodeSource

        return mind_services.capture(
            self.owner,
            content="the boiler is making that noise again",
            captured_at=self.now,
            source=NodeSource.WEB,
            actor="alice",
        )

    def test_an_owner_with_no_notes_is_owed_nothing(self):
        self.assertTrue(scheduled_work_is_current(now=self.now))

    def test_an_owner_whose_pass_ran_today_is_current(self):
        from mind import services as mind_services

        self.capture()
        mind_services.record_maintenance_run(
            self.owner, now=self.now, actor="scheduler"
        )

        self.assertTrue(scheduled_work_is_current(now=self.now))

    def test_an_owner_with_notes_and_no_pass_for_days_is_a_problem(self):
        self.capture()

        self.assertFalse(
            scheduled_work_is_current(now=self.now + timedelta(days=4))
        )


class TheEndpointTest(TestCase):
    """What a monitor actually sees.

    Separate from `/healthz` on purpose: the site being down is an outage and a
    cron job running two days late is not, and a monitor that cannot page
    differently on them is one somebody learns to ignore.
    """

    def setUp(self):
        self.user = User.objects.create_user("alice", "alice@example.com", PASSWORD)

    def test_a_current_site_answers_two_hundred(self):
        response = self.client.get("/healthz/scheduled")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"ok")

    def test_an_overdue_erasure_answers_five_oh_three(self):
        account_services.request_deletion(
            self.user,
            now=timezone.now()
            - account_services.ACCOUNT_DELETION_GRACE
            - timedelta(days=3),
        )

        response = self.client.get("/healthz/scheduled")

        self.assertEqual(response.status_code, 503)

    def test_it_names_no_job_no_account_and_no_date(self):
        """`healthz`'s discipline, kept. This URL answers anybody forever, and
        which of three scheduled jobs is failing is a fact about the inside of
        the system."""
        account_services.request_deletion(
            self.user,
            now=timezone.now()
            - account_services.ACCOUNT_DELETION_GRACE
            - timedelta(days=3),
        )

        body = self.client.get("/healthz/scheduled").content.decode()

        self.assertEqual(body, "overdue")
        for leak in ("alice", "erasure", "purge", "digest", "maintenance"):
            self.assertNotIn(leak, body.lower())

    def test_it_needs_no_account(self):
        """Like `healthz`: a monitor has no session."""
        self.assertEqual(self.client.get("/healthz/scheduled").status_code, 200)

    def test_head_is_allowed_because_monitors_default_to_it(self):
        self.assertEqual(self.client.head("/healthz/scheduled").status_code, 200)

    def test_a_broken_check_reports_overdue_rather_than_fine(self):
        """The failure direction, pinned. A bug here becomes an alarm that will
        not clear, which somebody investigates -- rather than a check silently
        broken for a month and indistinguishable from good news."""
        from unittest.mock import patch

        with patch("clarice.health._overdue", side_effect=RuntimeError("boom")):
            response = self.client.get("/healthz/scheduled")

        self.assertEqual(response.status_code, 503)
