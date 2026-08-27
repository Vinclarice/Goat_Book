"""Being told before a thing is due, rather than on the day.

Nothing in Clarice could remind you of anything *in advance*: the digest lists
what is overdue or due today, and a bill you find out about on the morning it
is due is a bill you find out about too late. That is the second half of what
bills needed and the first that is not about bills at all -- "tell me a week
before" is a sentence about any commitment.

**On `Item`, not on `MoneyLine`.** A lead time is not a property of costing money.
Putting it on the sidecar would have made "remind me before the MOT" impossible
without inventing an amount.

**Carried by the series, like priority and the Area.** A lead time set on
"pay rent" that came back zero next month would be the one attribute somebody
had to set again forever.

**It does not change what is due.** A task with a lead time is not overdue
early and is not due early; it is *mentioned* early, in a section of its own.
`bucket_for` is untouched, which also keeps this out of the three languages
that mirror it.
"""

import datetime

from django.core import mail
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from io import StringIO

from accounts.models import User
from lists import agenda, services
from lists.models import Item, List


class LeadTimeTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "vince", "vince@example.com", "a secure password"
        )
        self.list_ = List.objects.create(owner=self.user, title="Home")
        self.today = timezone.localdate()

    def task(self, text, *, due_in, lead=0):
        item = services.create_item(
            self.list_,
            text,
            due_date=self.today + datetime.timedelta(days=due_in),
        )
        if lead:
            services.set_lead_days(item, lead)
            item.refresh_from_db()
        return item

    def test_a_task_starts_with_no_lead_time(self):
        self.assertEqual(self.task("Pay rent", due_in=3).lead_days, 0)

    def test_a_task_inside_its_lead_time_is_coming_up(self):
        self.task("Property tax", due_in=5, lead=7)

        coming = agenda.coming_up_for(self.user, self.today)

        self.assertEqual([item.text for item in coming], ["Property tax"])

    def test_a_task_outside_its_lead_time_is_not_mentioned_yet(self):
        self.task("Property tax", due_in=30, lead=7)

        self.assertEqual(agenda.coming_up_for(self.user, self.today), [])

    def test_a_task_due_today_is_not_also_coming_up(self):
        """It belongs to the digest's own list, and saying it twice in one
        email is how a reminder starts being skimmed."""
        self.task("Pay rent", due_in=0, lead=7)

        self.assertEqual(agenda.coming_up_for(self.user, self.today), [])

    def test_an_overdue_task_is_not_coming_up_either(self):
        self.task("Pay rent", due_in=-2, lead=7)

        self.assertEqual(agenda.coming_up_for(self.user, self.today), [])

    def test_a_task_with_no_lead_time_is_never_coming_up(self):
        """Zero is off, not "the day itself" -- otherwise every dated task in
        the product would join the reminder."""
        self.task("Ordinary", due_in=1)

        self.assertEqual(agenda.coming_up_for(self.user, self.today), [])

    def test_setting_it_on_a_repeating_task_sets_it_on_the_series(self):
        task = self.task("Pay rent", due_in=5)
        services.set_recurrence(task, Item.Recurrence.MONTHLY)
        task.refresh_from_db()

        services.set_lead_days(task, 7)

        task.refresh_from_db()
        self.assertEqual(task.commitment.lead_days, 7)

    def test_the_next_occurrence_inherits_it(self):
        task = self.task("Pay rent", due_in=0)
        services.set_recurrence(task, Item.Recurrence.MONTHLY)
        task.refresh_from_db()
        services.set_lead_days(task, 7)
        task.refresh_from_db()

        spawned = services.complete_item(task)._spawned

        self.assertEqual(spawned.lead_days, 7)

    def test_one_person_never_sees_anothers_coming_up(self):
        other = User.objects.create_user("bob", "bob@example.com", "a password")
        theirs = List.objects.create(owner=other, title="Theirs")
        item = services.create_item(
            theirs, "Bob's bill", due_date=self.today + datetime.timedelta(days=2)
        )
        services.set_lead_days(item, 7)

        self.assertEqual(agenda.coming_up_for(self.user, self.today), [])


class LeadTimeInTheDigestTest(TestCase):
    """The reason it exists: somewhere for an advance reminder to arrive."""

    def setUp(self):
        self.user = User.objects.create_user(
            "vince", "vince@example.com", "a secure password"
        )
        self.list_ = List.objects.create(owner=self.user, title="Home")
        self.today = timezone.localdate()

    def run_command(self):
        call_command(
            "send_due_digest", stdout=StringIO(), send_hour=0, until_hour=24
        )

    def test_the_digest_says_what_is_coming_before_it_is_due(self):
        due_today = services.create_item(
            self.list_, "Pay rent", due_date=self.today
        )
        soon = services.create_item(
            self.list_,
            "Property tax",
            due_date=self.today + datetime.timedelta(days=5),
        )
        services.set_lead_days(soon, 7)
        self.assertIsNotNone(due_today)

        self.run_command()

        body = mail.outbox[0].body
        self.assertIn("Coming up", body)
        self.assertIn("Property tax", body)

    def test_a_day_with_only_something_coming_up_still_sends(self):
        """Otherwise the one message that exists to warn you in advance is
        silent on exactly the quiet day it is for."""
        soon = services.create_item(
            self.list_,
            "Property tax",
            due_date=self.today + datetime.timedelta(days=5),
        )
        services.set_lead_days(soon, 7)

        self.run_command()

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Property tax", mail.outbox[0].body)
