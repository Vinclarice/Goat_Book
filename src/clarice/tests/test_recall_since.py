"""What developed out of this, afterwards -- `since()`, Track A increment 5.

The last of Track A, and the one the brief said might correctly never ship.
**D4** is why: *what makes a later event bear on an earlier node?* The wide
answer -- anything similar, anything sharing a concept -- is the one that
cannot be given honestly, because "bears on" would be a similarity score
wearing a causal word. Increment 5's *"stopping at four is the correct
outcome"* was written for that version.

**The narrow answer ships instead, and invents nothing.** The merger already
records one true development chain, in columns:

    Node → Facet (confirmed actionable) → Item → that task's later life events

Every hop is a row somebody wrote, with a date on it. `since()` follows it and
stops. **What it refuses is the interesting part**: two notes about the same
subject, a shared concept, a close embedding -- none of those are development,
and a read that presented them as *"what came of this"* would be inventing a
history the log never recorded.

**Uniform with `around()` on purpose.** Same `Neighbour` shape, same
person-not-machine line, same chronological-never-ranked rule, same
counted-not-flagged cap. Increment 4 answers *what else was going on*, this
answers *what came of it*; a caller putting them side by side should not have
to reconcile two vocabularies.

**Edges reach forward and not backward**, which is the same refusal in a
smaller place. An edge drawn *from* this note is something that grew out of it.
An edge drawn *toward* it, from somewhere else, is a development of that other
note -- and following it would quietly make *"what developed from X"* and
*"what has since mentioned X"* the same question, which is the similarity slide
D4 exists to stop.
"""

import datetime

from django.utils import timezone

from clarice import recall
from clarice.testing import CrossCoreTestCase, make_node
from lists import services as list_services
from mind import services as mind_services
from mind.models import EventType, FacetKind, InferenceOrigin


WRITTEN = datetime.datetime(2026, 5, 4, 9, 0, tzinfo=datetime.timezone.utc)


def after(**offset):
    return WRITTEN + datetime.timedelta(**offset)


class SinceTest(CrossCoreTestCase):
    def a_written_note(self, content="ask Maya about the venue"):
        return make_node(self.alice, content, when=WRITTEN)

    def an_actionable_facet(self, node, *, confirmed_at=None, area=None):
        """The one hop that turns a thought into a commitment."""
        facet = mind_services.propose_facet(
            node,
            kind=FacetKind.ACTIONABLE,
            data={},
            now=confirmed_at or after(hours=1),
            actor="alice",
            reason="looks like a commitment",
        )
        return mind_services.confirm_actionable(
            facet,
            area=area or self.area,
            now=confirmed_at or after(hours=1),
            actor="alice",
        )

    def since(self, node, **kwargs):
        return recall.since(self.alice, node, **kwargs)

    def kinds(self, result):
        return [d.event_type for d in result.developments]

    # -- the chain the merger already records ----------------------------

    def test_a_note_that_became_a_task_says_so(self):
        node = self.a_written_note()
        self.an_actionable_facet(node)

        self.assertIn(EventType.FACET_CONFIRMED, self.kinds(self.since(node)))

    def test_and_what_became_of_that_task(self):
        """The hop nothing could make before increment 1. The task's
        completion is not on the node, is not near it in time, and is the
        single most load-bearing thing that can happen to a thought."""
        node = self.a_written_note()
        facet = self.an_actionable_facet(node)
        list_services.complete_item(facet.task)

        self.assertIn(EventType.TASK_COMPLETED, self.kinds(self.since(node)))

    def test_the_task_it_became_is_reachable_from_the_development(self):
        node = self.a_written_note()
        facet = self.an_actionable_facet(node)
        list_services.complete_item(facet.task)

        completion = [
            d
            for d in self.since(node).developments
            if d.event_type == EventType.TASK_COMPLETED
        ][0]
        self.assertEqual(completion.task.pk, facet.task_id)

    def test_a_link_drawn_from_this_note_is_a_development(self):
        node = self.a_written_note()
        other = make_node(self.alice, "the venue's number", when=after(days=1))
        mind_services.link(
            node, other, relation="relates_to", now=after(days=2), actor="alice"
        )

        self.assertIn(EventType.EDGE_CREATED, self.kinds(self.since(node)))

    # -- what it refuses -------------------------------------------------

    def test_a_note_about_the_same_thing_is_not_a_development(self):
        """The whole of D4 in one test. Written later, about the venue, with
        every word in common -- and nothing records that one came out of the
        other, so `since()` says nothing about it. A read that included this
        would be presenting a similarity score as a causal claim."""
        node = self.a_written_note()
        make_node(self.alice, "ask Maya about the venue again", when=after(days=3))

        self.assertFalse(self.since(node).has_anything)

    def test_a_link_drawn_toward_this_note_is_the_other_notes_development(self):
        """The same refusal in a smaller place: following it backwards would
        make "what developed from X" and "what has since mentioned X" one
        question."""
        node = self.a_written_note()
        other = make_node(self.alice, "the venue's number", when=after(days=1))
        mind_services.link(
            other, node, relation="relates_to", now=after(days=2), actor="alice"
        )

        self.assertFalse(self.since(node).has_anything)

    def test_a_facet_nobody_confirmed_is_a_suggestion_not_a_development(self):
        """Consistent with `around()`'s line: the machine proposing something
        is not the person doing something."""
        node = self.a_written_note()
        mind_services.propose_facet(
            node,
            kind=FacetKind.ACTIONABLE,
            data={},
            origin=InferenceOrigin.INFERRED,
            now=after(hours=1),
            actor="system",
            reason="looks like a commitment",
        )

        self.assertFalse(self.since(node).has_anything)

    def test_another_persons_note_develops_on_its_own(self):
        bob = self.someone_else()
        theirs = make_node(bob, "their note", when=WRITTEN)

        self.assertFalse(self.since(theirs).has_anything)

    # -- when developments are counted from ------------------------------

    def test_it_counts_from_when_the_note_was_written_by_default(self):
        """The honest default for *"what came of this"*: everything after the
        thought existed."""
        node = self.a_written_note()
        self.an_actionable_facet(node, confirmed_at=after(days=10))

        self.assertTrue(self.since(node).has_anything)

    def test_it_can_be_asked_from_a_later_moment(self):
        """Which is what *"what changed since I last looked"* needs."""
        node = self.a_written_note()
        self.an_actionable_facet(node, confirmed_at=after(days=1))

        result = self.since(node, from_moment=after(days=5))

        self.assertFalse(result.has_anything)

    def test_the_capture_itself_is_not_a_development_of_the_note(self):
        """A note is not something that came out of itself, and `CAPTURED`
        landing inside `since()` would make every note look like it had
        developed the moment it was written."""
        node = self.a_written_note()

        self.assertEqual(self.kinds(self.since(node)), [])

    # -- shape, shared with around() -------------------------------------

    def test_developments_are_chronological_and_ranked_by_nothing(self):
        node = self.a_written_note()
        facet = self.an_actionable_facet(node, confirmed_at=after(hours=1))
        list_services.complete_item(facet.task)

        result = self.since(node)

        self.assertEqual(
            [d.occurred_at for d in result.developments],
            sorted(d.occurred_at for d in result.developments),
        )

    def test_nothing_developed_is_said_rather_than_left_blank(self):
        """The base of D5. *"Since then, nothing has been recorded"* is a real
        answer, and it is only honest if the read can tell it from not having
        looked."""
        node = self.a_written_note()

        result = self.since(node)

        self.assertEqual(result.developments, [])
        self.assertFalse(result.has_anything)
        self.assertEqual(result.omitted, 0)

    def test_it_says_how_many_it_left_out(self):
        node = self.a_written_note()
        facet = self.an_actionable_facet(node, confirmed_at=after(hours=1))
        for _ in range(4):
            list_services.complete_item(facet.task)
            list_services.reopen_item(facet.task)

        result = self.since(node, limit=3)

        self.assertEqual(len(result.developments), 3)
        self.assertEqual(result.omitted, 6)

    def test_the_cap_keeps_the_earliest_developments(self):
        """The opposite end from `around()`, and deliberately: a neighbourhood
        is read outward from an instant, and a development chain is read
        forward from a beginning."""
        node = self.a_written_note()
        facet = self.an_actionable_facet(node, confirmed_at=after(hours=1))
        list_services.complete_item(facet.task)

        result = self.since(node, limit=1)

        self.assertEqual(self.kinds(result), [EventType.FACET_CONFIRMED])

    def test_a_naive_moment_is_refused_like_it_is_next_door(self):
        node = self.a_written_note()

        with self.assertRaises(ValueError):
            self.since(node, from_moment=datetime.datetime(2026, 5, 4, 9, 0))

    def test_a_note_the_person_deleted_develops_no_further(self):
        """`delete_node`'s promise, kept here as it is in `around()`."""
        node = self.a_written_note()
        self.an_actionable_facet(node)
        node.deleted_at = timezone.now()
        node.save(update_fields=["deleted_at"])

        self.assertFalse(self.since(node).has_anything)
