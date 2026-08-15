"""The weekly review reads the graph, not the Inbox.

The review asked two questions of the knowledge half: *what ideas did you add
this week*, and *what is still sitting in your inbox untriaged*. Both are
questions about a model the crossover deletes, and the second is a question
about a concept it deletes — there is no triage in the graph, so nothing can be
waiting for it.

This is the prerequisite step 4 of `one-capture-surface-plan.md` did not know it
had. `review/reads.py` imports `Capture` and `Idea` directly, so retiring those
models would break the weekly review — which `roadmap.md` calls the single
strongest thing built here. Found by checking rather than assuming, which that
plan explicitly asked for on a different question and got right for the wrong
one.

**The two questions become one true one and one better one.**

*Ideas added* becomes *thoughts captured*: simpler, still true afterwards, and
no longer pretending that a retained thought is a different kind of object from
a captured one.

*Still in your inbox* has no graph equivalent and gets none. Inventing a backlog
would reimport the exact concept the crossover exists to remove. What replaces
it is the one queue this design does permit — concept candidates that have
earned a question by recurring — because a weekly ritual is precisely when the
Attention Policy says a queue may be shown.
"""

from datetime import date, datetime, timedelta, timezone as dt_timezone

from django.test import Client, TestCase

from accounts.models import User
from mind import services
from mind.models import NodeSource
from review import reads

PASSWORD = "correct horse battery staple"
UTC = dt_timezone.utc

# A Monday, and the week it opens.
WEEK_START = date(2026, 6, 8)
WEEK_END = WEEK_START + timedelta(days=7)
IN_WEEK = datetime(2026, 6, 10, 9, 0, tzinfo=UTC)
BEFORE = datetime(2026, 5, 2, 9, 0, tzinfo=UTC)


class TheWeekReadsTheGraphTest(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user("alice", "a@example.com", PASSWORD)
        self.bob = User.objects.create_user("bob", "b@example.com", PASSWORD)
        self.client = Client()
        self.client.force_login(self.alice)

    def capture(self, owner, text, when=IN_WEEK):
        return services.capture(
            owner, content=text, captured_at=when,
            source=NodeSource.WEB, actor=owner.get_username(),
        )

    # -- thoughts captured -------------------------------------------------

    def test_a_thought_captured_this_week_is_in_the_review(self):
        self.capture(self.alice, "the boiler is making that noise")

        thoughts = reads.thoughts_captured_in_week(self.alice, WEEK_START, WEEK_END)

        self.assertEqual([t.original_content for t in thoughts],
                         ["the boiler is making that noise"])

    def test_a_thought_from_another_week_is_not(self):
        self.capture(self.alice, "an older thought", when=BEFORE)

        self.assertEqual(
            reads.thoughts_captured_in_week(self.alice, WEEK_START, WEEK_END), []
        )

    def test_it_reads_the_thoughts_own_time_not_the_row_s(self):
        """A node carries `captured_at` — when the thought happened — separately
        from `created_at`. The 34 captures migrated from the Inbox all have an
        original date months before the row was written, and a review that read
        the row would file every one of them into the week of the migration."""
        node = self.capture(self.alice, "migrated from the Inbox", when=IN_WEEK)
        self.assertNotEqual(node.captured_at.date(), node.created_at.date())

        thoughts = reads.thoughts_captured_in_week(self.alice, WEEK_START, WEEK_END)

        self.assertEqual(len(thoughts), 1)

    def test_archived_thoughts_are_left_out(self):
        """22 of the migrated captures were discards, archived on the way in.
        A review of the week should not open with a fortnight of device-test
        residue."""
        node = self.capture(self.alice, "Offline test 3")
        services.archive_node(node, now=IN_WEEK, actor="migration")

        self.assertEqual(
            reads.thoughts_captured_in_week(self.alice, WEEK_START, WEEK_END), []
        )

    def test_one_persons_week_holds_only_their_thoughts(self):
        self.capture(self.bob, "bob's thought")

        self.assertEqual(
            reads.thoughts_captured_in_week(self.alice, WEEK_START, WEEK_END), []
        )

    # -- names worth confirming --------------------------------------------

    def test_a_name_that_has_earned_a_question_is_surfaced(self):
        """The one queue this design permits: three mentions spanning a day,
        which is what makes it finite. A weekly ritual is exactly when the
        Attention Policy says a queue may be shown."""
        for day in range(3):
            node = self.capture(
                self.alice, f"spoke to Marguerite about it, {day}",
                when=IN_WEEK + timedelta(days=day),
            )
            services.extract_and_record_concepts(node, now=IN_WEEK)

        names = reads.names_worth_confirming(self.alice)

        self.assertIn("Marguerite", [c.label for c in names])

    def test_a_name_seen_once_is_not(self):
        node = self.capture(self.alice, "watched Down Periscope")
        services.extract_and_record_concepts(node, now=IN_WEEK)

        self.assertEqual(reads.names_worth_confirming(self.alice), [])

    def test_a_name_already_confirmed_is_not_asked_about_again(self):
        node = self.capture(self.alice, "the invention of lying")
        services.record_typed_tags(node, ["movie"], now=IN_WEEK, actor="alice")

        self.assertEqual(
            [c.label for c in reads.names_worth_confirming(self.alice)], []
        )

    # -- the payload -------------------------------------------------------

    def test_the_api_carries_both_and_no_longer_mentions_the_inbox(self):
        self.capture(self.alice, "the boiler again")

        payload = self.client.get(f"/api/v1/review/{WEEK_START}").json()

        self.assertIn("thoughts", payload)
        self.assertIn("names_to_confirm", payload)
        self.assertNotIn("unresolved_captures", payload)
        self.assertNotIn("ideas", payload)

    def test_a_thought_arrives_with_the_day_it_was_captured(self):
        self.capture(self.alice, "the boiler again")

        payload = self.client.get(f"/api/v1/review/{WEEK_START}").json()

        self.assertEqual(payload["thoughts"][0]["text"], "the boiler again")
        self.assertEqual(payload["thoughts"][0]["captured_on"], "2026-06-10")
