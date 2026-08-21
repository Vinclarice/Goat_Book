"""What changed since yesterday — the day's brief, awareness half.

`clarice-v3-plan.md` splits the daily brief in two. The plan half is
`draft_day`: bounded by capacity, ending in the accept. This is the other, and
its whole contract is **change, not state** — *what changed, and does today
still make sense?*

**That contract is what stops it becoming a dashboard**, which the destination
explicitly refuses: *"the central screen would not be a dashboard full of
metrics"*. Everything here is deliberately something the Day page does **not**
already show. Overdue work is on the page; the fact that you *chose* one of
them yesterday and it did not happen is not. A bill due next week is nowhere on
the page at all.

**Short or absent is the correct output.** On a quiet day this is nothing, and
nothing is what it says — a brief that manufactured three lines every morning
would be read for a week.

**No ranking across the sections.** A slipped commitment against a bill against
a quiet project is `SearchRank` over two document sets again, and the failure
is silent. Three lists, three questions, never one ordering.

**Reading 4 is absent, and that is the honest state.** *Where intention and
attention disagree* needs the temporal substrate; nothing here pretends to it.
"""

import datetime

from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from daily import reads, services
from lists import services as list_services
from lists.models import Item, List, Project


TUESDAY = datetime.date(2026, 8, 4)
MONDAY = datetime.date(2026, 8, 3)


class TheDaysBriefTest(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.bob = User.objects.create_user("bob", "bob@example.com", "a password")
        self.list_ = List.objects.create(owner=self.alice, title="Home")

    def brief(self, *, day=TUESDAY, today=TUESDAY, owner=None):
        return reads.brief_for(owner or self.alice, day, today=today)

    def pinned_on(self, day, text, *, finished=False, owner=None):
        area = self.list_
        if owner is not None:
            area = List.objects.create(owner=owner, title="Theirs")
        task = list_services.create_item(area, text)
        services.pin_task(owner or self.alice, day, task)
        if finished:
            list_services.complete_item(task)
            Item.objects.filter(pk=task.pk).update(
                completed_at=timezone.make_aware(
                    datetime.datetime.combine(day, datetime.time(15, 0))
                )
            )
        return task

    def test_a_quiet_day_says_nothing_at_all(self):
        """Not an empty dashboard: nothing changed, so there is nothing to
        read, and a brief that filled three sections every morning would be
        skipped by the end of the week."""
        brief = self.brief()

        self.assertFalse(brief.has_anything)
        self.assertEqual(brief.slipped, [])

    def test_what_was_chosen_yesterday_and_did_not_happen(self):
        """The Day page already shows overdue work. What it cannot say is that
        you *chose* this one yesterday -- which is the change, and the whole
        reason DailyFocus records a choice rather than a due date."""
        self.pinned_on(MONDAY, "Call the plumber")

        brief = self.brief()

        self.assertEqual([f.task_text for f in brief.slipped], ["Call the plumber"])
        self.assertTrue(brief.has_anything)

    def test_what_was_chosen_yesterday_and_did_happen_is_not_a_change(self):
        self.pinned_on(MONDAY, "Pay rent", finished=True)

        self.assertEqual(self.brief().slipped, [])

    def test_something_deliberately_dropped_is_not_reported_as_slipping(self):
        """`released_at`'s whole purpose again: deciding it was not for
        yesterday is a decommitment, and calling it a slip would be the
        product disagreeing with a decision somebody made."""
        dropped = self.pinned_on(MONDAY, "Reorganise the shed")
        services.unpin_task(self.alice, MONDAY, dropped)
        self.alice.daily_focus.filter(task=dropped).update(
            released_at=timezone.make_aware(
                datetime.datetime.combine(MONDAY, datetime.time(15, 0))
            )
        )

        self.assertEqual(self.brief().slipped, [])

    def test_a_bill_or_task_inside_its_lead_time_is_worth_knowing(self):
        """Nowhere on the Day page at all -- an advance reminder existed only
        in the digest until now."""
        soon = list_services.create_item(
            self.list_, "Property tax", due_date=TUESDAY + datetime.timedelta(days=5)
        )
        list_services.set_lead_days(soon, 7)

        self.assertEqual([t.text for t in self.brief().coming], ["Property tax"])

    def test_a_project_nothing_has_moved_is_worth_knowing(self):
        quiet = Project.objects.create(owner=self.alice, title="The book")
        Project.objects.filter(pk=quiet.pk).update(
            created_at=timezone.now() - datetime.timedelta(days=120)
        )

        self.assertEqual(
            [row.project.title for row in self.brief().gone_quiet], ["The book"]
        )

    def test_a_project_still_moving_is_not_reported_as_quiet(self):
        """`projects_to_confirm` returns every open project because the weekly
        check-in reviews all of them. A brief that listed every project every
        morning would be the dashboard this exists to refuse."""
        Project.objects.create(owner=self.alice, title="Started this morning")

        self.assertEqual(self.brief().gone_quiet, [])

    def test_it_says_nothing_about_a_day_already_lived(self):
        """The same refusal `draft_day` and the closing ritual make: telling
        somebody what changed on a day they have finished is a verdict, not a
        brief."""
        self.pinned_on(MONDAY, "Call the plumber")

        brief = self.brief(day=TUESDAY, today=TUESDAY + datetime.timedelta(days=1))

        self.assertFalse(brief.has_anything)

    def test_one_person_never_sees_anothers_brief(self):
        """The isolation test principles.md asks of every owner-scoped read."""
        self.pinned_on(MONDAY, "Bob's slipped task", owner=self.bob)

        self.assertEqual(self.brief().slipped, [])
