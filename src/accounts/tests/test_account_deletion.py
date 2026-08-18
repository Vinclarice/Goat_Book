"""Leaving, and changing your mind about it.

`commercial-blueprint.md` calls account deletion and data export a legal blocker
rather than a feature gap: Sentry and Resend already process other people's data,
and until now nobody could remove themselves.

**A grace period, because this is the one irreversible thing a person can do to
themselves.** Requesting deletion changes nothing except a timestamp. The account
keeps working, which is deliberate — it is what makes *cancel* reachable without
inventing a signed-link email flow for a window that is theirs to close.

The erasure itself lives in `accounts.services.purge_account` and needs the
append-only log's owner-scoped exemption to run at all; that half is tested in
`mind/tests/test_erasure.py`, which is where the trigger lives.
"""

from datetime import timedelta

from django.core import mail
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from io import StringIO
from unittest.mock import patch

from accounts import services
from accounts.models import SCOPE_CAPTURE_WRITE, PersonalAccessToken, User
from daily.models import DailyEntry, DailyFocus
from lists.models import Item, List, Project, RecurringCommitment, Tag
from mind.models import ActivityEvent, ConceptCandidate, Node
from review.models import WeeklyReview
from routines.models import Routine, RoutineOccurrence, RoutinePause

PASSWORD = "correct horse battery staple 47!"

# Every model that carries a direct owner. Spelled out rather than discovered by
# reflection, so a model added later is a decision somebody makes here rather
# than something a clever assertion absorbs silently.
OWNED = (
    Item, List, Project, Tag, RecurringCommitment,
    DailyEntry, DailyFocus,
    Routine, RoutineOccurrence, RoutinePause,
    WeeklyReview,
    PersonalAccessToken,
    Node, ConceptCandidate, ActivityEvent,
)


class RequestingDeletionTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("alice", "alice@example.com", PASSWORD)
        self.now = timezone.now()

    def test_it_records_when_they_asked(self):
        services.request_deletion(self.user, now=self.now)

        self.user.refresh_from_db()
        self.assertEqual(self.user.deletion_requested_at, self.now)

    def test_the_account_still_works(self):
        """`is_active` is untouched on purpose -- it means "pending admin
        approval", and one flag for two unrelated states is indistinguishable
        everywhere it is read. Staying usable is also what makes cancelling
        reachable at all."""
        services.request_deletion(self.user, now=self.now)

        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)
        # Through the real login view rather than `client.login`: axes wraps the
        # authentication backend and wants a request, so the shortcut cannot see
        # what a person signing in would.
        response = self.client.post(
            "/accounts/login/", {"username": "alice", "password": PASSWORD}
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("_auth_user_id", self.client.session)

    def test_asking_twice_does_not_push_the_date_further_out(self):
        """A repeated click must not quietly extend the window somebody is
        waiting on."""
        services.request_deletion(self.user, now=self.now)

        services.request_deletion(self.user, now=self.now + timedelta(days=3))

        self.user.refresh_from_db()
        self.assertEqual(self.user.deletion_requested_at, self.now)

    def test_the_purge_date_is_the_request_plus_the_grace_period(self):
        services.request_deletion(self.user, now=self.now)

        self.assertEqual(
            services.purge_at(self.user), self.now + services.ACCOUNT_DELETION_GRACE
        )

    def test_an_account_that_is_not_leaving_has_no_purge_date(self):
        self.assertIsNone(services.purge_at(self.user))

    def test_cancelling_clears_it_and_touches_nothing_else(self):
        services.request_deletion(self.user, now=self.now)
        List.objects.create(owner=self.user, title="Home")

        services.cancel_deletion(self.user)

        self.user.refresh_from_db()
        self.assertIsNone(self.user.deletion_requested_at)
        self.assertTrue(List.objects.filter(owner=self.user).exists())


class LeavingIsAnnouncedByEmailTest(TestCase):
    """The half that protects somebody who did not do this.

    Password re-entry stops a passer-by at an unlocked screen. It does nothing
    against somebody who has the password, and the thirty-day window only helps
    if the person finds out inside it — which a banner cannot guarantee and a
    message to the address on the account can.
    """

    def setUp(self):
        self.user = User.objects.create_user("alice", "alice@example.com", PASSWORD)
        self.now = timezone.now()

    def test_requesting_it_writes_to_the_account_holder(self):
        services.request_deletion(self.user, now=self.now)

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["alice@example.com"])

    def test_the_message_names_the_date_and_says_it_is_permanent(self):
        services.request_deletion(self.user, now=self.now)

        body = mail.outbox[0].body
        self.assertIn(f"{services.purge_at(self.user):%d %B %Y}", body)
        self.assertIn("permanently", body)
        self.assertIn("cannot be undone", body)

    def test_it_tells_them_what_to_do_if_they_did_not_ask(self):
        """The whole reason this is sent to somebody who may not have acted."""
        services.request_deletion(self.user, now=self.now)

        self.assertIn("did not ask for this", mail.outbox[0].body)

    def test_asking_twice_does_not_write_twice(self):
        services.request_deletion(self.user, now=self.now)

        services.request_deletion(self.user, now=self.now + timedelta(days=1))

        self.assertEqual(len(mail.outbox), 1)

    def test_cancelling_says_so_in_the_same_place(self):
        services.request_deletion(self.user, now=self.now)
        mail.outbox.clear()

        services.cancel_deletion(self.user)

        self.assertEqual(len(mail.outbox), 1)
        # The subject has to answer the question from the inbox list, unopened:
        # somebody who got the first message wants to know the second one means
        # it is off.
        self.assertIn("no longer scheduled for deletion", mail.outbox[0].subject)
        self.assertIn("cancelled", mail.outbox[0].body)

    def test_cancelling_twice_does_not_write_twice(self):
        services.request_deletion(self.user, now=self.now)
        services.cancel_deletion(self.user)
        mail.outbox.clear()

        services.cancel_deletion(self.user)

        self.assertEqual(len(mail.outbox), 0)

    def test_the_erasure_sends_a_receipt(self):
        services.request_deletion(self.user, now=self.now)
        mail.outbox.clear()

        services.purge_account(self.user, now=self.now)

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["alice@example.com"])
        self.assertIn("has been deleted", mail.outbox[0].subject)

    def test_the_receipt_survives_the_account_it_reports_on(self):
        """Read before the delete, not after. A receipt that reads the row it is
        confirming the destruction of is one that never sends."""
        services.purge_account(self.user, now=self.now)

        self.assertFalse(User.objects.filter(username="alice").exists())
        self.assertIn("alice", mail.outbox[-1].body)


class WhoIsDueTest(TestCase):
    def setUp(self):
        self.now = timezone.now()

    def leaving(self, username, *, days_ago):
        user = User.objects.create_user(username, f"{username}@example.com", PASSWORD)
        services.request_deletion(user, now=self.now - timedelta(days=days_ago))
        return user

    def test_an_account_inside_its_grace_period_is_not_due(self):
        self.leaving("alice", days_ago=29)

        self.assertEqual(list(services.due_for_purge(self.now)), [])

    def test_an_account_past_it_is(self):
        alice = self.leaving("alice", days_ago=31)

        self.assertEqual(list(services.due_for_purge(self.now)), [alice])

    def test_an_account_that_never_asked_is_never_due(self):
        User.objects.create_user("bob", "bob@example.com", PASSWORD)

        self.assertEqual(list(services.due_for_purge(self.now)), [])


class PurgeTest(TestCase):
    """What erasure actually removes.

    `TestCase` rather than `TransactionTestCase`: the append-only exemption is
    transaction-local, and a test wrapped in one outer transaction still sees it
    for the duration of the purge. The trigger's own behaviour under real
    commits is covered in `mind/tests/test_erasure.py`.
    """

    def setUp(self):
        self.now = timezone.now()
        self.alice = self.a_full_account("alice")
        self.bob = self.a_full_account("bob")

    def a_full_account(self, username):
        """One row in every model that carries an owner.

        Every one of these earns its place: a purge test that never created the
        row proves nothing about that model, and the "another account is
        untouched" assertion below is what caught four of them missing.
        """
        from mind import services as mind_services
        from mind.models import NodeSource

        user = User.objects.create_user(username, f"{username}@example.com", PASSWORD)
        area = List.objects.create(owner=user, title=f"{username}'s home")
        task = Item.objects.create(list=area, owner=user, text=f"{username}'s task")
        Project.objects.create(owner=user, title=f"{username}'s project")
        Tag.objects.create(owner=user, name=f"{username}-tag")
        RecurringCommitment.objects.create(
            owner=user, text=f"{username}'s commitment", list=area
        )

        entry = DailyEntry.objects.create(owner=user, date=timezone.localdate())
        DailyFocus.objects.create(
            owner=user, entry=entry, task=task, task_text=task.text
        )
        WeeklyReview.objects.create(
            owner=user, week_start=timezone.localdate() - timedelta(days=7)
        )

        routine = Routine.objects.create(owner=user, title=f"{username}'s routine")
        RoutineOccurrence.objects.create(
            owner=user, routine=routine,
            period_start=timezone.localdate(), target_quantity=1,
        )
        RoutinePause.objects.create(owner=user, routine=routine, paused_at=self.now)

        PersonalAccessToken.generate(user, scopes=[SCOPE_CAPTURE_WRITE])

        node = mind_services.capture(
            user, content=f"{username} thought something", captured_at=self.now,
            source=NodeSource.WEB, actor=username,
        )
        mind_services.record_typed_tags(
            node, [f"{username}-concept"], now=self.now, actor=username
        )
        return user

    def test_the_fixture_populates_every_owned_model(self):
        """Guards the two tests below, which both pass vacuously against a model
        nobody created a row in. Four were missing when this file was written."""
        for model in OWNED:
            with self.subTest(model=model.__name__):
                self.assertTrue(
                    model.objects.filter(owner_id=self.alice.pk).exists(),
                    f"a_full_account creates no {model.__name__}",
                )

    def test_nothing_of_theirs_is_left_in_any_owned_model(self):
        services.purge_account(self.alice, now=self.now)

        for model in OWNED:
            with self.subTest(model=model.__name__):
                self.assertFalse(
                    model.objects.filter(owner_id=self.alice.pk).exists(),
                    f"{model.__name__} still holds rows for the purged account",
                )

    def test_the_account_itself_is_gone(self):
        services.purge_account(self.alice, now=self.now)

        self.assertFalse(User.objects.filter(username="alice").exists())

    def test_the_other_account_is_untouched(self):
        """The half that matters most. An erasure that took a neighbour's data
        with it would be a worse failure than not erasing at all."""
        services.purge_account(self.alice, now=self.now)

        for model in OWNED:
            with self.subTest(model=model.__name__):
                self.assertTrue(
                    model.objects.filter(owner_id=self.bob.pk).exists(),
                    f"{model.__name__} lost rows belonging to another account",
                )

    def test_it_reports_what_it_removed(self):
        """What it removed, not what existed -- the lesson `migrate_inbox` left,
        where a dry run counted its input and read as though it would write all
        of it."""
        removed = services.purge_account(self.alice, now=self.now)

        self.assertGreater(removed["mind.ActivityEvent"], 0)
        self.assertEqual(removed["accounts.User"], 1)
        self.assertNotIn(
            0, [v for k, v in removed.items() if k == "mind.ActivityEvent"]
        )


class PurgeCommandTest(TestCase):
    def setUp(self):
        self.now = timezone.now()

    def leaving(self, username, *, days_ago):
        user = User.objects.create_user(username, f"{username}@example.com", PASSWORD)
        services.request_deletion(user, now=self.now - timedelta(days=days_ago))
        return user

    def run_command(self, *args):
        out = StringIO()
        call_command("purge_deleted_accounts", *args, stdout=out)
        return out.getvalue()

    def test_it_purges_an_account_past_its_grace_period(self):
        self.leaving("alice", days_ago=31)

        self.run_command()

        self.assertFalse(User.objects.filter(username="alice").exists())

    def test_one_failed_erasure_does_not_block_the_rest(self):
        """Same shape as the digest's send loop. `purge_account` sends a
        confirmation, and a rejected address rolls that erasure back --
        deliberate, since a half-erased account is worse than an unerased one.
        Unguarded, it also blocked every account after it, nightly and
        alphabetically, so the same person's bad address held everyone else's
        erasure open indefinitely."""
        from smtplib import SMTPRecipientsRefused
        from django.core.management.base import CommandError

        self.leaving("alice", days_ago=31)
        self.leaving("bob", days_ago=31)

        real = services.purge_account

        def fail_for_alice(user, **kwargs):
            if user.get_username() == "alice":
                raise SMTPRecipientsRefused({"alice@example.com": (550, b"nope")})
            return real(user, **kwargs)

        with patch.object(services, "purge_account", side_effect=fail_for_alice):
            with self.assertRaises(CommandError) as raised:
                self.run_command()

        self.assertTrue(User.objects.filter(username="alice").exists())
        self.assertFalse(User.objects.filter(username="bob").exists())
        self.assertIn("alice", str(raised.exception))

    def test_it_leaves_one_still_inside_its_window(self):
        self.leaving("alice", days_ago=10)

        self.run_command()

        self.assertTrue(User.objects.filter(username="alice").exists())

    def test_it_leaves_an_account_that_never_asked(self):
        User.objects.create_user("bob", "bob@example.com", PASSWORD)

        self.run_command()

        self.assertTrue(User.objects.filter(username="bob").exists())

    def test_a_dry_run_writes_nothing_and_says_who_it_would_take(self):
        self.leaving("alice", days_ago=31)

        out = self.run_command("--dry-run")

        self.assertTrue(User.objects.filter(username="alice").exists())
        self.assertIn("alice", out)
        self.assertIn("Dry run", out)

    def test_it_says_so_when_there_is_nothing_to_do(self):
        """A command that prints nothing is indistinguishable from a command
        that did not run, which is how a cron job stops being noticed."""
        out = self.run_command()

        self.assertIn("0 account(s)", out)
