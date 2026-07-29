from datetime import timedelta
from io import StringIO

from django.core import mail
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from lists.models import Item, List


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
