"""The brief a project page can offer, in three sections.

`planning-assistant-plan.md` increment 4. Assembled here rather than in
`mind.queries` because this is the half that knows what a Project is: the
knowledge core stays text-anchored and answers "what bears on this statement",
and the caller supplies the statement. That direction is deliberate and is what
lets `mind` remain ignorant of the task core -- the same shape `review/reads.py`
already uses when it reads nodes for a week.

Three sections, and they are three because a loose end, a piece of prior
thinking and a dated commitment are three different things to do something
about:

* **Material** -- prior notes bearing on the purpose, each citing the terms
  that selected it.
* **Questions** -- unresolved questions bearing on the purpose. A *partition*
  of the same retrieval rather than a second query, so nothing appears twice
  and "this is still open" wins over "this is related" when a note is both.
* **Commitments** -- open tasks in the project due on or before its own date.
  Pure task core, no retrieval, and the only section that can be complete
  rather than merely plausible.

**A brief is opened, never pushed**, and it writes nothing. It also proposes
nothing: there is no confirm gate here because there is nothing to confirm --
every item already exists and already belongs to the person. That is what makes
it a briefing rather than a queue.
"""
from datetime import date, datetime, timedelta, timezone as dt_timezone

from django.test import TestCase

from accounts.models import User
from lists import projects as project_reader
from lists import services
from lists.models import Item, List
from mind import services as mind_services
from mind.models import ActivityEvent, NodeSource

UTC = dt_timezone.utc
NOW = datetime(2026, 6, 1, 9, 0, tzinfo=UTC)
TODAY = date(2026, 6, 1)

PURPOSE = (
    "Replace the enquiries inbox with a booking form so the venue stops "
    "losing bookings to email."
)


class ProjectBriefTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.other = User.objects.create_user(
            "bob", "bob@example.com", "another secure password"
        )
        self.project = services.create_project(
            self.user, "Website launch", due_date=TODAY + timedelta(days=30),
            purpose=PURPOSE,
        )
        self.area = List.objects.create(
            owner=self.user, title="Site", project=self.project
        )

    def capture(self, content, days_ago=30, owner=None):
        return mind_services.capture(
            owner or self.user,
            content=content,
            captured_at=NOW - timedelta(days=days_ago),
            source=NodeSource.WEB,
            actor="alice",
        )

    def task(self, text, due_date=None, status=Item.Status.ACTIVE, area=None):
        # `valid_item_status_timestamps` pairs each status with its stamp, so a
        # fixture that sets one without the other is rejected by the database
        # rather than quietly creating a row the application could not.
        stamps = {
            Item.Status.COMPLETED: {"completed_at": NOW},
            Item.Status.ARCHIVED: {"archived_at": NOW},
        }
        return Item.objects.create(
            owner=self.user,
            list=area if area is not None else self.area,
            text=text,
            due_date=due_date,
            status=status,
            **stamps.get(status, {}),
        )

    # -- material ----------------------------------------------------------

    def test_prior_notes_bearing_on_the_purpose_are_material(self):
        note = self.capture(
            "The booking form should collect the venue and the enquiries contact."
        )
        self.capture("Bought milk and walked to the park this afternoon.")

        brief = project_reader.brief_for(self.user, self.project)

        self.assertEqual([each.node for each in brief.material], [note])

    def test_every_piece_of_material_says_why_it_surfaced(self):
        self.capture(
            "The booking form should collect the venue and the enquiries contact."
        )

        brief = project_reader.brief_for(self.user, self.project)

        self.assertTrue(brief.material[0].reason)

    def test_a_project_with_no_purpose_offers_no_material(self):
        """The anchor is the whole permission to retrieve.

        Without one this would be `precision.md`'s Tier 3 -- the corpus sorted
        by coincidence -- which is the panel `detectors/__init__` rejects.
        """
        blank = services.create_project(self.user, "Unnamed intent")
        self.capture("The booking form should collect the venue and enquiries.")

        brief = project_reader.brief_for(self.user, blank)

        self.assertEqual(brief.material, [])
        self.assertEqual(brief.questions, [])

    # -- questions ---------------------------------------------------------

    def test_an_unresolved_question_bearing_on_the_purpose_is_a_loose_end(self):
        question = self.capture(
            "Which booking form should the venue use for enquiries?"
        )

        brief = project_reader.brief_for(self.user, self.project)

        self.assertEqual([each.node for each in brief.questions], [question])

    def test_a_question_is_not_also_listed_as_material(self):
        """The two sections partition one retrieval; they do not overlap.

        A loose end shown twice is the same failure as a proposal counted
        twice in one review -- the brief stops being trustworthy about its own
        contents.
        """
        question = self.capture(
            "Which booking form should the venue use for enquiries?"
        )

        brief = project_reader.brief_for(self.user, self.project)

        self.assertNotIn(question, [each.node for each in brief.material])

    def test_an_answered_question_is_material_rather_than_a_loose_end(self):
        """Answered means resolved, and resolved means it is not a loose end.

        It stays in the brief -- prior thinking about this project is still
        worth having -- but it moves sections, which is the whole reason the
        questions half reuses `unresolved_questions` rather than testing for a
        question mark.
        """
        question = self.capture(
            "Which booking form should the venue use for enquiries?"
        )
        # Deliberately shares none of the question's distinctive vocabulary.
        # An answer written in the same words would raise those terms' document
        # frequency and the rare-term gate would then filter *both* notes out,
        # leaving this test unable to see the behaviour it is about. The
        # `answers` edge is explicit, so matching prose was never required.
        answer = self.capture("Settled at yesterday's meeting.", days_ago=2)
        mind_services.link(
            answer,
            question,
            relation="answers",
            origin="inferred",
            now=NOW,
            actor="alice",
        )

        brief = project_reader.brief_for(self.user, self.project)

        self.assertNotIn(question, [each.node for each in brief.questions])
        self.assertIn(question, [each.node for each in brief.material])

    # -- commitments -------------------------------------------------------

    def test_open_tasks_due_before_the_project_are_commitments(self):
        due = self.task("Draft the booking form copy", due_date=TODAY + timedelta(days=7))

        brief = project_reader.brief_for(self.user, self.project)

        self.assertEqual(list(brief.commitments), [due])

    def test_a_task_due_after_the_project_is_not_yet_a_constraint(self):
        self.task("Later polish", due_date=TODAY + timedelta(days=90))

        brief = project_reader.brief_for(self.user, self.project)

        self.assertEqual(list(brief.commitments), [])

    def test_a_task_with_no_due_date_is_not_a_constraint(self):
        """A commitment without a date cannot be due before anything.

        Included as its own case because `due_date__lte` silently drops NULLs,
        so the behaviour is correct by accident and would survive a rewrite
        that made it wrong.
        """
        self.task("Someday idea", due_date=None)

        brief = project_reader.brief_for(self.user, self.project)

        self.assertEqual(list(brief.commitments), [])

    def test_completed_and_archived_tasks_are_not_constraints(self):
        self.task(
            "Done already",
            due_date=TODAY + timedelta(days=3),
            status=Item.Status.COMPLETED,
        )
        self.task(
            "Filed away",
            due_date=TODAY + timedelta(days=3),
            status=Item.Status.ARCHIVED,
        )

        brief = project_reader.brief_for(self.user, self.project)

        self.assertEqual(list(brief.commitments), [])

    def test_a_task_in_another_project_is_not_a_constraint(self):
        elsewhere = services.create_project(self.user, "Other work")
        other_area = List.objects.create(
            owner=self.user, title="Elsewhere", project=elsewhere
        )
        self.task(
            "Not this project's",
            due_date=TODAY + timedelta(days=3),
            area=other_area,
        )

        brief = project_reader.brief_for(self.user, self.project)

        self.assertEqual(list(brief.commitments), [])

    def test_a_project_with_no_due_date_still_lists_its_open_work(self):
        """No date means no horizon to filter against, not an empty section.

        Filtering `due_date__lte=None` would return nothing and read as "no
        commitments", which is a different claim from "this project has no
        deadline".
        """
        undated = services.create_project(self.user, "Open-ended", purpose=PURPOSE)
        area = List.objects.create(
            owner=self.user, title="Open-ended area", project=undated
        )
        task = self.task(
            "Still a commitment", due_date=TODAY + timedelta(days=5), area=area
        )

        brief = project_reader.brief_for(self.user, undated)

        self.assertEqual(list(brief.commitments), [task])

    # -- ownership and writes ---------------------------------------------

    def test_another_person_s_notes_and_tasks_never_reach_a_brief(self):
        self.capture(
            "The booking form should collect the venue and enquiries.",
            owner=self.other,
        )
        their_area = List.objects.create(owner=self.other, title="Theirs")
        Item.objects.create(
            owner=self.other,
            list=their_area,
            text="Their task",
            due_date=TODAY + timedelta(days=3),
        )

        brief = project_reader.brief_for(self.user, self.project)

        self.assertEqual(brief.material, [])
        self.assertEqual(brief.questions, [])
        self.assertEqual(list(brief.commitments), [])

    def test_reading_a_brief_writes_nothing(self):
        """Charter rule 4, and the sharper version of it.

        `/mind/review/` records being loaded on purpose, because a proposal
        shown without starting its window makes silence meaningless. A brief
        proposes nothing, so there is no window to start -- and the two must
        not be confused for each other.
        """
        self.capture("The booking form collects the venue and enquiries.")
        self.task("Draft copy", due_date=TODAY + timedelta(days=7))
        before = ActivityEvent.objects.count()

        project_reader.brief_for(self.user, self.project)

        self.assertEqual(ActivityEvent.objects.count(), before)
