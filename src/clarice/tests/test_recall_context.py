"""The context of a *thing*, which is plural — **D19**.

`around()` takes one instant, and a thing does not have one. A note has its
writing, its confirmation as a commitment, the completion of the task it
became; asking *what was going on around this note* with a single timestamp
answers about the morning it was written and silently drops the rest of its
life.

**So: both, and the subject read is built on the instant one.** `around()`
stays the primitive and this unions it over the subject's own moments. The
decision's own words are *"without it every caller re-derives that resolution
ad hoc"* — and the note page had already done exactly that, anchoring on
`captured_at` because that was the one timestamp to hand.

**The hard part is overlap, which is why this is a read and not a loop in a
view.** Two of a subject's moments twenty minutes apart produce two
neighbourhoods that are nearly the same set, and a caller unioning them naively
either shows everything twice or loses which moment each thing belonged to.
Both failures are silent. So moments within reach of each other are **one
occasion**, and an event that would appear in two of them appears once, in the
earlier.

**An occasion keeps its moments.** *What else was going on* is only answerable
if you can say *going on when* — and after a merge that is a set of moments
rather than a timestamp, which is precisely the resolution the decision says
nobody should re-derive.
"""

import datetime

from django.utils import timezone

from clarice import recall
from clarice.testing import CrossCoreTestCase, make_node
from lists import services as list_services
from mind import services as mind_services
from mind.models import EventType, FacetKind, Node


WRITTEN = datetime.datetime(2026, 5, 4, 9, 0, tzinfo=datetime.timezone.utc)


def at(**offset):
    return WRITTEN + datetime.timedelta(**offset)


class ContextTest(CrossCoreTestCase):
    def a_note(self, content="ask Maya about the venue", when=WRITTEN):
        return make_node(self.alice, content, when=when)

    def event(self, event_type, when, *, owner=None, **subjects):
        from clarice.testing import make_event

        return make_event(owner or self.alice, event_type, when, **subjects)

    def became_a_task(self, node, *, when):
        """The real chain, not a faked event.

        `_moments_of` follows `Facet.task`, so a `FACET_CONFIRMED` row with a
        task on it and no facet behind it reaches nothing -- which is the
        provenance rule working, and was this test being wrong about how a note
        becomes a task.
        """
        facet = mind_services.propose_facet(
            node,
            kind=FacetKind.ACTIONABLE,
            data={},
            now=when,
            actor="alice",
            reason="looks like a commitment",
        )
        return mind_services.confirm_actionable(
            facet, area=self.area, now=when, actor="alice"
        )

    def context(self, node, **kwargs):
        return recall.context_of(self.alice, node, **kwargs)

    def moments_of(self, occasion):
        return [m.event_type for m in occasion.moments]

    def neighbours_of(self, occasion):
        return [n.event_type for n in occasion.neighbours]

    # -- the subject's own moments ---------------------------------------

    def test_writing_it_is_one_of_its_moments(self):
        note = self.a_note()

        occasions = self.context(note).occasions

        self.assertEqual(len(occasions), 1)
        self.assertEqual(self.moments_of(occasions[0]), [EventType.CAPTURED])

    def test_what_happened_to_the_task_it_became_is_also_its_moment(self):
        """The hop D19 names: *the completion of the task it became*. That
        event is not on the node, is months from its capture, and is the single
        most load-bearing thing that can happen to a thought."""
        note = self.a_note()
        confirmed = self.became_a_task(note, when=at(hours=1))
        from lists.models import Item

        Item.objects.filter(pk=confirmed.task_id).update(
            status=Item.Status.COMPLETED, completed_at=at(days=30)
        )
        self.event(EventType.TASK_COMPLETED, at(days=30), task=confirmed.task)

        occasions = self.context(note).occasions

        self.assertEqual(len(occasions), 2)
        self.assertEqual(
            self.moments_of(occasions[1]), [EventType.TASK_COMPLETED]
        )

    def test_a_task_the_note_never_became_is_not_its_moment(self):
        """The same refusal `since()` makes: provenance, not coincidence."""
        note = self.a_note()
        list_services.complete_item(self.a_task("Unrelated"))

        self.assertEqual(len(self.context(note).occasions), 1)

    # -- occasions, which is the resolution D19 asks for -----------------

    def test_moments_close_together_are_one_occasion(self):
        """Twenty minutes apart is one sitting, and two occasions would show
        nearly the same neighbourhood twice under two headings."""
        note = self.a_note()
        self.event(EventType.FACET_CONFIRMED, at(minutes=20), node=note)

        occasions = self.context(note).occasions

        self.assertEqual(len(occasions), 1)
        self.assertEqual(
            self.moments_of(occasions[0]),
            [EventType.CAPTURED, EventType.FACET_CONFIRMED],
        )

    def test_moments_far_apart_are_separate_occasions(self):
        note = self.a_note()
        self.event(EventType.REVISED, at(days=30), node=note)

        self.assertEqual(len(self.context(note).occasions), 2)

    def test_an_occasion_knows_when_it_began_and_ended(self):
        """A merged occasion has no single timestamp, which is the whole reason
        this cannot be left to each caller."""
        note = self.a_note()
        self.event(EventType.FACET_CONFIRMED, at(minutes=20), node=note)

        occasion = self.context(note).occasions[0]

        self.assertEqual(occasion.began, WRITTEN)
        self.assertEqual(occasion.ended, at(minutes=20))

    def test_occasions_are_chronological(self):
        note = self.a_note()
        self.event(EventType.REVISED, at(days=60), node=note)
        self.event(EventType.FACET_CONFIRMED, at(days=30), node=note)

        began = [o.began for o in self.context(note).occasions]

        self.assertEqual(began, sorted(began))

    # -- what else was going on, without saying it twice -----------------

    def test_it_says_what_else_was_going_on_around_each_occasion(self):
        note = self.a_note()
        # `a_note` goes through `capture`, which writes the event itself. Adding
        # one on top gave this note two capture events and the assertion two.
        self.a_note("something else", at(minutes=30))

        neighbours = self.neighbours_of(self.context(note).occasions[0])

        self.assertEqual(neighbours, [EventType.CAPTURED])

    def test_something_near_two_moments_is_reported_once(self):
        """The overlap failure, which is silent in both directions: shown twice
        it reads as two happenings, and deduped without care the later occasion
        loses it entirely."""
        note = self.a_note()
        # Far enough apart to be two occasions, with a bystander close to both.
        self.event(EventType.FACET_CONFIRMED, at(hours=11), node=note)
        self.a_note("the bystander", at(hours=6))

        occasions = self.context(note).occasions

        self.assertEqual(len(occasions), 2)
        appearances = sum(
            1
            for occasion in occasions
            for neighbour in occasion.neighbours
            if neighbour.node and neighbour.node.original_content == "the bystander"
        )
        self.assertEqual(appearances, 1)

    def test_the_subject_is_never_its_own_neighbour(self):
        """Its own events are the moments. Repeating them as neighbours is the
        note page's first defect, generalised."""
        note = self.a_note()
        self.event(EventType.FACET_CONFIRMED, at(minutes=20), node=note)

        self.assertEqual(self.neighbours_of(self.context(note).occasions[0]), [])

    def test_the_task_it_became_is_not_its_own_neighbour_either(self):
        note = self.a_note()
        confirmed = self.became_a_task(note, when=at(hours=1))
        self.event(EventType.TASK_COMPLETED, at(hours=2), task=confirmed.task)

        for occasion in self.context(note).occasions:
            self.assertEqual(self.neighbours_of(occasion), [])

    # -- the shape it shares with the other two reads --------------------

    def test_a_note_with_no_life_at_all_says_so(self):
        """A node with not even a capture event -- imported rows exist that way
        -- is not an error and not a blank. `has_anything` is the flag every
        caller branches on, and it has to be honest for the empty case."""
        # Built without `capture`, which writes the event. The log is
        # append-only by trigger, so deleting one is not available and should
        # not be -- an imported row with no event is the real shape of this.
        note = Node.objects.create(
            owner=self.alice,
            original_content="a note with no recorded life",
            captured_at=WRITTEN,
            source=Node.Source.IMPORT,
        )

        result = self.context(note)

        self.assertEqual(result.occasions, [])
        self.assertFalse(result.has_anything)

    def test_a_deleted_note_has_no_context(self):
        note = self.a_note()
        note.deleted_at = timezone.now()
        note.save(update_fields=["deleted_at"])

        self.assertFalse(self.context(note).has_anything)

    def test_it_does_not_reach_into_another_persons_day(self):
        note = self.a_note()
        bob = self.someone_else()
        self.event(
            EventType.CAPTURED,
            at(minutes=10),
            owner=bob,
            node=make_node(bob, "theirs", when=at(minutes=10)),
        )

        self.assertEqual(self.neighbours_of(self.context(note).occasions[0]), [])

    def test_a_naive_window_is_refused_like_it_is_next_door(self):
        note = self.a_note()

        with self.assertRaises(ValueError):
            self.context(note, window=None)
