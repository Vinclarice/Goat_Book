"""Blockers and carryover, triaged against the outcomes — increment 6.

**Ordering is the whole design.** Increment 5 put outcomes ahead of triage
precisely so this step has a criterion: a question is a blocker when it bears on
something the week is *for*, and a leftover task is worth keeping when it serves
one. Without the outcomes both lists are piles, which is what the plan means by
"deciding what to keep before deciding what the week is for is triage with no
criterion".

**Two decisions this rests on, both narrower than they looked.**

D5 — may the review decide things? It already does, and always through the
owning core: pinning a task to today goes to the day's service, pausing a
project to the task core's. The read-only rule was never "the review may not
write"; it is that the review holds no write path of its own, and nothing here
adds one.

D6 — where the session lives, given two review surfaces. It does not bind here.
`mind/views.py` is explicit that a question carries **no review window** —
"nothing expires, nothing ripens, and leaving it alone is a permanent and
costless answer" — where a proposal is surfaced *and* stamped. So acting on a
question from another surface cannot disturb the machinery that interprets
silence, and D6 stays open for the proposals, which are the only things it was
ever really about.
"""
from datetime import date, timedelta

from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from lists import services as list_services
from lists.models import Item, List, Project
from mind import services as mind_services
from mind.models import NodeSource
from review import reads, services

MONDAY = date(2026, 6, 1)
WEDNESDAY = date(2026, 6, 3)
NOW = timezone.now()


class BlockersTest(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )

    def capture(self, content, days_ago=20):
        return mind_services.capture(
            self.alice,
            content=content,
            captured_at=NOW - timedelta(days=days_ago),
            source=NodeSource.WEB,
            actor="alice",
        )

    def test_no_outcomes_means_no_blockers(self):
        """Not "every open question". A blocker is defined against what the
        week is for, and a week with nothing chosen has nothing to block."""
        self.capture("Which booking form should the venue use for enquiries?")

        self.assertEqual(reads.blockers_for(self.alice, MONDAY, now=NOW), [])

    def test_a_question_bearing_on_an_outcome_is_a_blocker(self):
        question = self.capture(
            "Which booking form should the venue use for enquiries?"
        )
        services.choose_outcome(
            self.alice,
            MONDAY,
            text="The booking form is live and collecting venue enquiries.",
        )

        found = reads.blockers_for(self.alice, MONDAY, now=NOW)

        self.assertEqual([each.question.node for each in found], [question])

    def test_a_question_about_something_else_is_not(self):
        self.capture("Should we repaint the kitchen or leave it?")
        services.choose_outcome(
            self.alice,
            MONDAY,
            text="The booking form is live and collecting venue enquiries.",
        )

        self.assertEqual(reads.blockers_for(self.alice, MONDAY, now=NOW), [])

    def test_a_blocker_says_which_outcome_it_blocks(self):
        """The evidence for calling it a blocker at all. Without the outcome
        named, this is a list of questions with an adjective attached."""
        self.capture("Which booking form should the venue use for enquiries?")
        outcome = services.choose_outcome(
            self.alice,
            MONDAY,
            text="The booking form is live and collecting venue enquiries.",
        )

        found = reads.blockers_for(self.alice, MONDAY, now=NOW)

        self.assertEqual(found[0].outcome, outcome)

    def test_a_blocker_says_how_long_it_has_been_open(self):
        self.capture(
            "Which booking form should the venue use for enquiries?", days_ago=11
        )
        services.choose_outcome(
            self.alice,
            MONDAY,
            text="The booking form is live and collecting venue enquiries.",
        )

        found = reads.blockers_for(self.alice, MONDAY, now=NOW)

        self.assertEqual(found[0].question.days_open, 11)

    def test_an_answered_question_is_no_longer_a_blocker(self):
        question = self.capture(
            "Which booking form should the venue use for enquiries?"
        )
        services.choose_outcome(
            self.alice,
            MONDAY,
            text="The booking form is live and collecting venue enquiries.",
        )
        mind_services.resolve_question(question, now=NOW, actor="alice")

        self.assertEqual(reads.blockers_for(self.alice, MONDAY, now=NOW), [])

    def test_one_dismissed_as_never_a_question_is_not_a_blocker(self):
        question = self.capture(
            "Which booking form should the venue use for enquiries?"
        )
        services.choose_outcome(
            self.alice,
            MONDAY,
            text="The booking form is live and collecting venue enquiries.",
        )
        mind_services.dismiss_as_question(question, now=NOW, actor="alice")

        self.assertEqual(reads.blockers_for(self.alice, MONDAY, now=NOW), [])

    def test_one_question_blocking_two_outcomes_is_listed_once(self):
        """A thing shown twice makes a surface untrustworthy about its own
        contents -- the rule `brief_for` and `upcoming_constraints` both keep."""
        self.capture("Which booking form should the venue use for enquiries?")
        services.choose_outcome(
            self.alice, MONDAY, text="The booking form is live for enquiries."
        )
        services.choose_outcome(
            self.alice, MONDAY, text="The venue booking form collects enquiries."
        )

        found = reads.blockers_for(self.alice, MONDAY, now=NOW)

        self.assertEqual(len(found), 1)

    def test_one_person_s_questions_do_not_block_another_s_week(self):
        bob = User.objects.create_user(
            "bob", "bob@example.com", "another secure password"
        )
        mind_services.capture(
            bob,
            content="Which booking form should the venue use for enquiries?",
            captured_at=NOW - timedelta(days=20),
            source=NodeSource.WEB,
            actor="bob",
        )
        services.choose_outcome(
            self.alice,
            MONDAY,
            text="The booking form is live and collecting venue enquiries.",
        )

        self.assertEqual(reads.blockers_for(self.alice, MONDAY, now=NOW), [])

    def test_reading_them_writes_nothing(self):
        """A question has no review window, which is what makes reading it
        from a second surface safe at all -- see this module's docstring."""
        self.capture("Which booking form should the venue use for enquiries?")
        services.choose_outcome(
            self.alice,
            MONDAY,
            text="The booking form is live and collecting venue enquiries.",
        )
        before = list(
            reads.blockers_for(self.alice, MONDAY, now=NOW)[0].question.node.facets.all()
        )

        reads.blockers_for(self.alice, MONDAY, now=NOW)

        self.assertEqual(
            list(
                reads.blockers_for(self.alice, MONDAY, now=NOW)[
                    0
                ].question.node.facets.all()
            ),
            before,
        )


class CarryoverServesTheOutcomesTest(TestCase):
    """Overdue work, ordered by whether it serves what the week is for.

    Not filtered. A leftover that serves nothing chosen is exactly the row
    worth seeing before deciding to drop it -- so everything stays and the
    connected ones come first, which is the difference between triage and a
    hidden backlog.
    """

    def setUp(self):
        self.alice = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.project = Project.objects.create(
            owner=self.alice, title="Website launch"
        )
        self.area = List.objects.create(
            owner=self.alice, title="Site", project=self.project
        )
        self.elsewhere = List.objects.create(owner=self.alice, title="Home")

    def overdue(self, text, area):
        return Item.objects.create(
            owner=self.alice,
            list=area,
            text=text,
            due_date=MONDAY - timedelta(days=3),
        )

    def test_work_serving_a_chosen_outcome_is_marked(self):
        self.overdue("Write the copy", self.area)
        services.choose_outcome(
            self.alice, MONDAY, text="The form is live.", project=self.project
        )

        found = reads.carryover_for(self.alice, MONDAY, today=MONDAY)

        self.assertTrue(found[0].serves_an_outcome)

    def test_work_serving_nothing_chosen_is_not(self):
        self.overdue("Fix the gate", self.elsewhere)
        services.choose_outcome(
            self.alice, MONDAY, text="The form is live.", project=self.project
        )

        found = reads.carryover_for(self.alice, MONDAY, today=MONDAY)

        self.assertFalse(found[0].serves_an_outcome)

    def test_nothing_is_hidden_by_the_triage(self):
        """A leftover connected to nothing is the row most worth deciding
        about. Filtering it out would turn triage into a backlog nobody sees."""
        self.overdue("Write the copy", self.area)
        self.overdue("Fix the gate", self.elsewhere)
        services.choose_outcome(
            self.alice, MONDAY, text="The form is live.", project=self.project
        )

        found = reads.carryover_for(self.alice, MONDAY, today=MONDAY)

        self.assertEqual(len(found), 2)

    def test_the_connected_ones_come_first(self):
        self.overdue("Fix the gate", self.elsewhere)
        self.overdue("Write the copy", self.area)
        services.choose_outcome(
            self.alice, MONDAY, text="The form is live.", project=self.project
        )

        found = reads.carryover_for(self.alice, MONDAY, today=MONDAY)

        self.assertEqual(
            [each.task.text for each in found], ["Write the copy", "Fix the gate"]
        )

    def test_with_no_outcomes_nothing_is_marked_and_order_is_kept(self):
        first = self.overdue("Fix the gate", self.elsewhere)
        second = self.overdue("Write the copy", self.area)

        found = reads.carryover_for(self.alice, MONDAY, today=MONDAY)

        self.assertEqual([each.task for each in found], [first, second])
        self.assertFalse(any(each.serves_an_outcome for each in found))
