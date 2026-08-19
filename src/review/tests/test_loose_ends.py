"""Loose ends and upcoming constraints — the weekly review's two missing halves.

`planning-assistant-plan.md` increment 5. The review already answers *what
happened*: completed work, planned against met with the honest denominator,
what was written, what was captured, habits. What it has never answered is
**what is still hanging** and **what is about to arrive**, which are the two
questions a review is actually for.

Extractive throughout. Every item here already exists and already belongs to the
person; nothing is proposed, nothing is confirmed, and no sentence is generated.
That is the whole of increment 5 — `roadmap.md` and the ML policy both say v1
ships no generation, and a summary assembled from records the person wrote needs
none.

**Reuse, never redefine.** Overdue means what `agenda.bucket_for` says it means,
unanswered means what `mind.queries.unresolved_questions` says, and the week's
bounds come from `review.weeks`. Three definitions of "overdue" in one
application is how a review stops agreeing with the page it summarises.
"""
from datetime import date, datetime, timedelta, timezone as dt_timezone

from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from lists.models import Item, List, Project
from lists import services as list_services
from mind import services as mind_services
from mind.models import FacetKind, NodeSource
from review import reads

UTC = dt_timezone.utc
MONDAY = date(2026, 6, 1)
SUNDAY = date(2026, 6, 7)
NOW = datetime(2026, 6, 3, 9, 0, tzinfo=UTC)


class LooseEndsTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.other = User.objects.create_user(
            "bob", "bob@example.com", "another secure password"
        )
        self.area = List.objects.create(owner=self.user, title="Work")

    def task(self, text, due_date=None, owner=None, area=None):
        return Item.objects.create(
            owner=owner or self.user,
            list=area if area is not None else self.area,
            text=text,
            due_date=due_date,
        )

    def capture(self, content, days_ago=10, owner=None):
        return mind_services.capture(
            owner or self.user,
            content=content,
            captured_at=NOW - timedelta(days=days_ago),
            source=NodeSource.WEB,
            actor="alice",
        )

    # -- unanswered questions ---------------------------------------------

    def test_an_unanswered_question_is_a_loose_end(self):
        question = self.capture("Which payment provider should we use?")

        ends = reads.loose_ends(self.user, today=MONDAY + timedelta(days=2))

        # Plain nodes, not wrappers: `unresolved_questions` is a view of the
        # corpus rather than a set of proposals, so there is no evidence object
        # around each one and nothing to unwrap.
        self.assertIn(question, ends.unanswered)

    def test_a_statement_is_not_a_loose_end(self):
        self.capture("Signed the venue contract this morning.")

        ends = reads.loose_ends(self.user, today=MONDAY + timedelta(days=2))

        self.assertEqual(ends.unanswered, [])

    def test_questions_are_not_redefined_here(self):
        """The same reader the knowledge core already uses.

        Asserted by behaviour rather than by inspection: a question resolved
        through an `answers` edge disappears from the review too, which can
        only be true if this is reading `unresolved_questions` and not a
        second idea of what a question is.
        """
        question = self.capture("Which payment provider should we use?")
        answer = self.capture("Settled at the meeting.", days_ago=1)
        mind_services.link(
            answer, question, relation="answers", origin="inferred",
            now=timezone.now(), actor="alice",
        )

        ends = reads.loose_ends(self.user, today=MONDAY + timedelta(days=2))

        self.assertEqual(ends.unanswered, [])

    # -- commitments proposed and never answered --------------------------

    def test_a_commitment_nobody_accepted_or_dismissed_is_a_loose_end(self):
        """The backlog nothing has ever counted.

        A proposed actionable facet is the one proposal type with no review
        window and no expiry: it sits forever, costing nothing, and until now
        appearing nowhere. `commitments_without_tasks` counts a broken
        invariant, not an unanswered question.
        """
        node = self.capture("I must ring the venue on Thursday.")
        facet = node.facets.filter(kind=FacetKind.ACTIONABLE).first()
        self.assertIsNotNone(facet, "capture should have proposed a commitment")

        ends = reads.loose_ends(self.user, today=MONDAY + timedelta(days=2))

        self.assertIn(facet, list(ends.unanswered_commitments))

    def test_a_commitment_read_out_of_a_journal_entry_is_a_loose_end(self):
        """The reader has to see both sources or it silently sees half.

        `Facet` learned to cite a `DailyEntry` in increment 2; this read was
        written a commit earlier and filters on `node__owner`, which excludes
        every entry-backed facet without failing anything. Written now, before
        a producer exists to create them, because a filter that quietly drops
        half its domain is not a bug anybody notices later -- it is a section
        that looks empty and is trusted.
        """
        from daily.models import DailyEntry
        from mind.models import Facet, InferenceOrigin

        entry = DailyEntry.objects.create(
            owner=self.user,
            date=MONDAY,
            happenings="I still need to ask Maya about the venue.",
        )
        facet = Facet.objects.create(
            entry=entry,
            kind=FacetKind.ACTIONABLE,
            origin=InferenceOrigin.INFERRED,
            reason="commitment language",
            fingerprint="journal-1",
        )

        ends = reads.loose_ends(self.user, today=MONDAY + timedelta(days=2))

        self.assertIn(facet, list(ends.unanswered_commitments))

    def test_another_person_s_journal_commitment_is_invisible(self):
        from daily.models import DailyEntry
        from mind.models import Facet, InferenceOrigin

        entry = DailyEntry.objects.create(
            owner=self.other, date=MONDAY, happenings="I must call the bank."
        )
        Facet.objects.create(
            entry=entry,
            kind=FacetKind.ACTIONABLE,
            origin=InferenceOrigin.INFERRED,
            fingerprint="theirs-1",
        )

        ends = reads.loose_ends(self.user, today=MONDAY + timedelta(days=2))

        self.assertEqual(list(ends.unanswered_commitments), [])

    def test_an_accepted_commitment_is_not_a_loose_end(self):
        node = self.capture("I must ring the venue on Thursday.")
        facet = node.facets.filter(kind=FacetKind.ACTIONABLE).first()
        mind_services.confirm_actionable(
            facet, now=timezone.now(), actor="alice",
        )

        ends = reads.loose_ends(self.user, today=MONDAY + timedelta(days=2))

        self.assertEqual(list(ends.unanswered_commitments), [])

    # -- overdue ----------------------------------------------------------

    def test_overdue_work_is_a_loose_end(self):
        late = self.task("Chase the invoice", due_date=MONDAY - timedelta(days=3))
        self.task("Not yet", due_date=MONDAY + timedelta(days=3))

        ends = reads.loose_ends(self.user, today=MONDAY)

        self.assertEqual(list(ends.overdue), [late])

    def test_a_task_due_today_is_not_overdue(self):
        """`agenda.bucket_for`'s boundary, not a second one.

        Due today is TODAY and not OVERDUE there, and a review that disagreed
        with the page it summarises would make one of the two wrong without
        saying which.
        """
        self.task("Due now", due_date=MONDAY)

        ends = reads.loose_ends(self.user, today=MONDAY)

        self.assertEqual(list(ends.overdue), [])

    # -- ownership --------------------------------------------------------

    def test_another_person_s_loose_ends_are_invisible(self):
        their_area = List.objects.create(owner=self.other, title="Theirs")
        self.task(
            "Their overdue thing",
            due_date=MONDAY - timedelta(days=3),
            owner=self.other,
            area=their_area,
        )
        self.capture("Which provider should they use?", owner=self.other)

        ends = reads.loose_ends(self.user, today=MONDAY)

        self.assertEqual(list(ends.overdue), [])
        self.assertEqual(ends.unanswered, [])


class UpcomingTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.area = List.objects.create(owner=self.user, title="Work")

    def task(self, text, due_date=None):
        return Item.objects.create(
            owner=self.user, list=self.area, text=text, due_date=due_date
        )

    def test_work_due_in_the_coming_week_is_a_constraint(self):
        soon = self.task("Send the deposit", due_date=SUNDAY + timedelta(days=2))

        upcoming = reads.upcoming_constraints(self.user, week_end=SUNDAY)

        self.assertEqual(list(upcoming.tasks), [soon])

    def test_work_beyond_the_coming_week_is_not_yet_a_constraint(self):
        """A review looks one week forward, not into the whole backlog.

        Everything with a date eventually arrives; a constraint is what
        arrives before the next review does.
        """
        self.task("Much later", due_date=SUNDAY + timedelta(days=30))

        upcoming = reads.upcoming_constraints(self.user, week_end=SUNDAY)

        self.assertEqual(list(upcoming.tasks), [])

    def test_work_already_overdue_is_not_listed_as_upcoming(self):
        """It is a loose end, and one item belongs in one section.

        The same rule the project brief follows: a thing shown twice in one
        surface makes the surface untrustworthy about its own contents.
        """
        self.task("Long late", due_date=MONDAY - timedelta(days=10))

        upcoming = reads.upcoming_constraints(self.user, week_end=SUNDAY)

        self.assertEqual(list(upcoming.tasks), [])

    def test_a_project_deadline_is_a_constraint(self):
        project = list_services.create_project(
            self.user, "Website launch", due_date=SUNDAY + timedelta(days=3)
        )

        upcoming = reads.upcoming_constraints(self.user, week_end=SUNDAY)

        self.assertEqual(list(upcoming.projects), [project])

    def test_a_completed_project_is_not_a_constraint(self):
        project = list_services.create_project(
            self.user, "Done already", due_date=SUNDAY + timedelta(days=3)
        )
        list_services.complete_project(project)

        upcoming = reads.upcoming_constraints(self.user, week_end=SUNDAY)

        self.assertEqual(list(upcoming.projects), [])


class ReadsNothingWritesTest(TestCase):
    """The review's standing rule, extended to the new reads.

    `test_reading_a_week_writes_nothing` holds this for the existing surface as
    a statement about executed SQL. These two are read-only for the same reason
    and would be the easiest place to break it, since one of them reaches into
    the knowledge core where surfacing *does* record.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )

    def test_neither_read_writes(self):
        from mind.models import ActivityEvent

        mind_services.capture(
            self.user,
            content="Which provider should we use?",
            captured_at=NOW,
            source=NodeSource.WEB,
            actor="alice",
        )
        before = ActivityEvent.objects.count()

        reads.loose_ends(self.user, today=MONDAY)
        reads.upcoming_constraints(self.user, week_end=SUNDAY)

        self.assertEqual(ActivityEvent.objects.count(), before)
