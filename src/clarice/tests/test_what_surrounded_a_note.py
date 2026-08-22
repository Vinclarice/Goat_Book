"""What a note was written into — S14's missing relationship, as a read.

v3's *Unify* lists this as **"typed links from a node into the day and project
domain objects"**, and S14 has said *one relationship short* for weeks. The
story's own done-means is the specification:

> the note carries the day it belongs to, the project it was inside and what
> she had committed to that week — and she reached it without having filed it
> anywhere by hand.

**Built as a read rather than as stored links, which is a deviation from the
require's wording and is deliberate.** The same plan's Part 1 says
*"facts, not derivations — nothing may write a row a read could have
produced"*, and every one of the three is derivable:

- **The day** is `captured_at`'s date. A stored link would be a second answer
  to a question the timestamp already settles, free to disagree with it.
- **The project** comes along the chain the merger already records in columns:
  `Node` → confirmed actionable `Facet` → `Item` → `List` → `Project`. That is
  provenance, and a stored link would be a copy of it.
- **The week's commitments** are `WeeklyIntention` and `WeeklyOutcome` for the
  week containing `captured_at`.

**So the differentiator survives and the rows do not.** *A graph that accretes
from what you were already doing* is exactly what a read over existing columns
gives; writing the links would accrete rows instead, which is the opposite
claim wearing the same words.

**What a read cannot do, and what would change the answer:** if a note should
carry a project it never became a task in — one written *during* a project,
about it, that never produced a commitment — no column records that and only a
stored link could. That is a real question, and it is S14's to answer rather
than this file's.
"""

import datetime

from clarice import recall
from clarice.testing import CrossCoreTestCase, make_node
from daily import services as daily_services
from lists.models import List, Project
from mind import services as mind_services
from mind.models import FacetKind
from review import services as review_services


WRITTEN = datetime.datetime(2026, 5, 6, 9, 0, tzinfo=datetime.timezone.utc)
ITS_DAY = datetime.date(2026, 5, 6)
ITS_MONDAY = datetime.date(2026, 5, 4)


class WhatSurroundedTest(CrossCoreTestCase):
    def a_note(self, content="ask Maya about the venue"):
        return make_node(self.alice, content, when=WRITTEN)

    def surrounding(self, node):
        return recall.what_surrounded(self.alice, node)

    def became_a_task_in(self, node, area):
        facet = mind_services.propose_facet(
            node,
            kind=FacetKind.ACTIONABLE,
            data={},
            now=WRITTEN,
            actor="alice",
            reason="looks like a commitment",
        )
        return mind_services.confirm_actionable(
            facet, area=area, now=WRITTEN, actor="alice"
        )

    # -- the day it belongs to -------------------------------------------

    def test_it_knows_the_day_the_note_was_written_into(self):
        note = self.a_note()
        daily_services.write_entry(self.alice, ITS_DAY, happenings="a hard week")

        self.assertEqual(self.surrounding(note).day.date, ITS_DAY)

    def test_a_day_nobody_wrote_in_is_absent_rather_than_invented(self):
        """A `DailyEntry` is created by writing in one. No entry means the day
        was not written in, which is a fact about the day rather than a gap in
        this read -- the same absence discipline as everywhere else here."""
        note = self.a_note()

        self.assertIsNone(self.surrounding(note).day)

    def test_the_day_comes_from_the_notes_own_time(self):
        """`captured_at`, not `created_at`. An imported note belongs to the day
        it was written, and the whole point of keeping the two apart is that
        importing does not move a memory to today."""
        note = make_node(
            self.alice,
            "written long ago",
            when=datetime.datetime(2024, 3, 1, 9, 0, tzinfo=datetime.timezone.utc),
        )
        daily_services.write_entry(
            self.alice, datetime.date(2024, 3, 1), happenings="then"
        )

        self.assertEqual(self.surrounding(note).day.date, datetime.date(2024, 3, 1))

    # -- the project it was inside ---------------------------------------

    def test_it_knows_the_project_the_note_ended_up_in(self):
        """Along the chain the merger already records: node, confirmed
        actionable facet, item, area, project."""
        project = Project.objects.create(owner=self.alice, title="The wedding")
        area = List.objects.create(owner=self.alice, title="Venue", project=project)
        note = self.a_note()
        self.became_a_task_in(note, area)

        self.assertEqual(self.surrounding(note).project, project)

    def test_a_note_that_became_nothing_is_inside_no_project(self):
        note = self.a_note()

        self.assertIsNone(self.surrounding(note).project)

    def test_a_task_in_an_area_with_no_project_is_inside_no_project(self):
        """An Area need not belong to one, and inventing a project for a
        note that landed in a loose area would be the derivation this read
        exists to avoid."""
        note = self.a_note()
        self.became_a_task_in(note, self.area)

        self.assertIsNone(self.surrounding(note).project)

    # -- what was committed to that week ---------------------------------

    def test_it_knows_what_was_intended_that_week(self):
        note = self.a_note()
        review_services.set_intention(self.alice, ITS_DAY, "Finish the chapter")

        self.assertEqual(self.surrounding(note).intention, "Finish the chapter")

    def test_it_knows_what_was_committed_to_that_week(self):
        note = self.a_note()
        review_services.choose_outcome(self.alice, ITS_DAY, text="Chapter three")

        self.assertEqual(
            [o.text for o in self.surrounding(note).outcomes], ["Chapter three"]
        )

    def test_a_week_with_no_intention_says_nothing(self):
        note = self.a_note()

        surrounding = self.surrounding(note)

        self.assertEqual(surrounding.intention, "")
        self.assertEqual(surrounding.outcomes, [])

    def test_the_week_is_the_notes_week_and_not_this_one(self):
        note = self.a_note()
        review_services.set_intention(self.alice, ITS_DAY, "the right week")
        review_services.set_intention(
            self.alice, ITS_DAY + datetime.timedelta(days=14), "a fortnight later"
        )

        self.assertEqual(self.surrounding(note).intention, "the right week")

    # -- the shape it shares with the rest --------------------------------

    def test_a_note_with_nothing_around_it_says_so(self):
        note = self.a_note()

        self.assertFalse(self.surrounding(note).has_anything)

    def test_a_note_with_something_around_it_says_that(self):
        note = self.a_note()
        review_services.set_intention(self.alice, ITS_DAY, "Finish the chapter")

        self.assertTrue(self.surrounding(note).has_anything)

    def test_it_does_not_read_another_persons_week(self):
        note = self.a_note()
        bob = self.someone_else()
        review_services.set_intention(bob, ITS_DAY, "theirs")

        self.assertEqual(self.surrounding(note).intention, "")
