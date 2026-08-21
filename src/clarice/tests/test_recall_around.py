"""What else was in the log near an instant -- the first read that crosses.

`temporal-substrate-plan.md` Track A increment 4. Increments 1-3 taught the log
to hold a life and gave it the history the task core already had; nothing read
it temporally, and until something does the substrate is a write-only table.

`mind/queries.py` holds twenty-one reads and **every one is adjacency in
meaning** -- similarity, concepts, mentions, threads. This is adjacency in
**time**, and it is the *"what was nearby"* of the recollection surface
`clarice-v3-plan.md` describes.

Three decisions that plan does not make, taken here and stated so they are easy
to overturn:

**Only what a person did.** `MACHINE_EVENTS` is the excluded set and
`recall.py` owns the reasoning. The line is *whose act was it*, not *which
core* -- so an import, a confirmation and a dismissal are all in.

**Chronological, never ranked.** A merged ordering over a task completion and a
captured note is `SearchRank` across two document sets again -- a number that
does not exist, presented as relevance, failing silently. Time is the one
ordering both sides genuinely share.

**Nothing is dropped in silence.** A day with thirty-one events and a day with
one are both real, so the cap is per side and the result says how many it left
out rather than quietly returning a round number.

**This file could not run when it was written**, and that is the whole of
`code-review-2026-08-21.md` R1: `a_node()` built a `Node` with `title` and
`body`, which live on `Revision`, so eleven of eighteen tests raised
`TypeError` at construction and nothing here had ever been executed. The
factory now comes from `clarice.testing`, where nobody hand-rolls one. R3's
three green mutations -- the after-side cap, the at-instant tie-break and the
upper window edge -- have tests below for the same reason.
"""

import datetime

from django.utils import timezone

from clarice import life_log, recall
from clarice.testing import CrossCoreTestCase
from lists.models import Item
from mind.models import EventType


NOON = datetime.datetime(2026, 8, 11, 12, 0, tzinfo=datetime.timezone.utc)


def at(**offset):
    return NOON + datetime.timedelta(**offset)


class AroundTest(CrossCoreTestCase):
    def event(self, event_type, when, *, owner=None, **subjects):
        from clarice.testing import make_event

        return make_event(owner or self.alice, event_type, when, **subjects)

    def around(self, instant=NOON, **kwargs):
        return recall.around(self.alice, instant, **kwargs)

    def types(self, result):
        return [n.event_type for n in result.before + result.after]

    # -- it crosses ------------------------------------------------------

    def test_it_answers_from_both_cores_at_once(self):
        """The whole point of the increment. Before this, one read saw notes
        and another saw tasks and nothing saw a morning."""
        self.event(EventType.CAPTURED, at(minutes=-30), node=self.a_node())
        self.event(EventType.TASK_COMPLETED, at(minutes=20), task=self.a_task())

        self.assertEqual(
            self.types(self.around()),
            [EventType.CAPTURED, EventType.TASK_COMPLETED],
        )

    def test_it_reads_in_time_order_and_ranks_nothing(self):
        self.event(EventType.TASK_COMPLETED, at(minutes=-10), task=self.a_task())
        self.event(EventType.CAPTURED, at(minutes=-50), node=self.a_node())
        self.event(
            EventType.FOCUS_PINNED, at(minutes=-30), task=self.a_task("Other")
        )

        self.assertEqual(
            self.types(self.around()),
            [EventType.CAPTURED, EventType.FOCUS_PINNED, EventType.TASK_COMPLETED],
        )

    def test_before_and_after_are_kept_apart(self):
        """A neighbourhood is not a list -- what led up to this and what
        followed it are different questions, and one merged list makes the
        caller re-derive the split from timestamps."""
        self.event(EventType.CAPTURED, at(minutes=-5), node=self.a_node())
        self.event(EventType.TASK_COMPLETED, at(minutes=5), task=self.a_task())

        result = self.around()

        self.assertEqual([n.event_type for n in result.before], [EventType.CAPTURED])
        self.assertEqual(
            [n.event_type for n in result.after], [EventType.TASK_COMPLETED]
        )

    def test_something_at_the_instant_itself_counts_as_after(self):
        """R3's second green mutation. `accept_draft` pins a whole set inside
        one transaction, so an event landing exactly on the instant is the
        ordinary case -- and the tie-break has to be documented behaviour
        rather than whichever comparison got typed."""
        self.event(EventType.TASK_COMPLETED, NOON, task=self.a_task())

        result = self.around()

        self.assertEqual(result.before, [])
        self.assertEqual(
            [n.event_type for n in result.after], [EventType.TASK_COMPLETED]
        )

    # -- whose act was it ------------------------------------------------

    def test_what_the_machine_proposed_is_not_what_was_nearby(self):
        """A neighbourhood full of the detectors' output describes their
        evening, not the person's."""
        for machine in recall.MACHINE_EVENTS:
            self.event(machine, at(minutes=-1), node=self.a_node())

        self.assertEqual(self.types(self.around()), [])

    def test_what_the_person_did_in_the_knowledge_core_counts(self):
        """The line is whose act it was, not which core it came from --
        confirming and dismissing are decisions, and an import is something
        somebody ran."""
        for person in (
            EventType.CONCEPT_CONFIRMED,
            EventType.FACET_DISMISSED,
            EventType.IMPORTED,
            EventType.REVIEWED,
        ):
            self.event(person, at(minutes=-10), node=self.a_node())

        self.assertEqual(len(self.types(self.around())), 4)

    def test_every_event_type_is_classified_one_way_or_the_other(self):
        """R8: a denylist over an open enum admits the next value by default.
        `life_log.py` solved the same problem with an allowlist and a raise;
        this asserts the partition instead, so a new `EventType` cannot be
        added without somebody answering the question."""
        self.assertEqual(
            recall.MACHINE_EVENTS | recall.PERSON_EVENTS,
            set(EventType.values),
        )
        self.assertEqual(recall.MACHINE_EVENTS & recall.PERSON_EVENTS, set())

    def test_a_reconstructed_event_is_still_something_that_happened(self):
        """`origin` says how the log knows, not whether it is true. Filtering
        reconstructions out here would make every backfilled morning invisible
        -- which is most of them, on the day increment 3 shipped."""
        life_log.record(
            self.alice,
            life_log.TASK_COMPLETED,
            task=self.a_task(),
            occurred_at=at(minutes=-15),
            origin=life_log.RECONSTRUCTED,
        )

        self.assertEqual(self.types(self.around()), [EventType.TASK_COMPLETED])

    # -- the window ------------------------------------------------------

    def test_something_outside_the_window_is_not_nearby(self):
        self.event(EventType.CAPTURED, at(hours=-30), node=self.a_node())

        self.assertEqual(self.types(self.around()), [])

    def test_the_window_can_be_widened_by_the_caller(self):
        self.event(EventType.CAPTURED, at(hours=-30), node=self.a_node())

        result = self.around(window=datetime.timedelta(days=2))

        self.assertEqual(self.types(result), [EventType.CAPTURED])

    def test_the_earlier_edge_of_the_window_is_included(self):
        self.event(
            EventType.CAPTURED, NOON - recall.DEFAULT_WINDOW, node=self.a_node()
        )

        self.assertEqual(self.types(self.around()), [EventType.CAPTURED])

    def test_the_later_edge_of_the_window_is_included(self):
        """R3's third green mutation: narrowing the upper bound to `lt` passed
        the whole suite, because every window test used a negative offset."""
        self.event(
            EventType.CAPTURED, NOON + recall.DEFAULT_WINDOW, node=self.a_node()
        )

        self.assertEqual(self.types(self.around()), [EventType.CAPTURED])

    def test_a_naive_instant_is_refused_rather_than_reinterpreted(self):
        """`USE_TZ` is on, so the ORM merely warns and guesses at a naive
        datetime and the split then raises `TypeError` comparing it to an aware
        one -- but only when the window holds a row, so it would have looked
        like an intermittent bug. The most natural day-scoped call,
        `datetime.combine(entry.date, time(9))`, is exactly the naive one."""
        with self.assertRaises(ValueError):
            self.around(instant=datetime.datetime(2026, 8, 11, 12, 0))

    # -- nothing dropped in silence --------------------------------------

    def test_it_says_how_many_it_left_out_rather_than_just_stopping(self):
        """August 15 has thirty-one events in production and August 4 has one.
        A cap that returned a round number without saying so would make the
        busy day and the quiet day look alike."""
        for minute in range(1, 8):
            self.event(EventType.CAPTURED, at(minutes=-minute), node=self.a_node())

        result = self.around(limit_each_side=3)

        self.assertEqual(len(result.before), 3)
        self.assertEqual(result.omitted_before, 4)
        self.assertEqual(result.omitted_after, 0)

    def test_the_after_side_is_capped_and_counted_too(self):
        """R3's first green mutation: every cap test used negative offsets, so
        inverting the after-slice to keep the *farthest* events passed."""
        for minute in range(1, 8):
            self.event(EventType.CAPTURED, at(minutes=minute), node=self.a_node())

        result = self.around(limit_each_side=3)

        self.assertEqual(len(result.after), 3)
        self.assertEqual(result.omitted_after, 4)
        self.assertEqual(result.omitted_before, 0)

    def test_the_cap_keeps_what_is_closest_to_the_instant(self):
        """Truncating from the far end: the nearest neighbours are the ones
        that make a moment legible."""
        for minute in (5, 10, 60, 120):
            self.event(
                EventType.CAPTURED,
                at(minutes=-minute),
                node=self.a_node(f"note {minute}"),
            )

        result = self.around(limit_each_side=2)

        self.assertEqual(
            [n.node.original_content for n in result.before], ["note 10", "note 5"]
        )

    def test_the_after_cap_also_keeps_what_is_closest(self):
        for minute in (5, 10, 60, 120):
            self.event(
                EventType.CAPTURED,
                at(minutes=minute),
                node=self.a_node(f"note {minute}"),
            )

        result = self.around(limit_each_side=2)

        self.assertEqual(
            [n.node.original_content for n in result.after], ["note 5", "note 10"]
        )

    def test_a_cap_of_zero_does_not_claim_the_neighbourhood_was_empty(self):
        """R9. `has_anything` is the one flag a caller branches on, and with
        everything capped away it read False beside non-zero omitted counts --
        "nothing is dropped in silence", inverted."""
        for minute in range(1, 4):
            self.event(EventType.CAPTURED, at(minutes=-minute), node=self.a_node())

        result = self.around(limit_each_side=0)

        self.assertEqual(result.omitted_before, 3)
        self.assertTrue(result.has_anything)

    def test_a_quiet_neighbourhood_is_empty_rather_than_absent(self):
        result = self.around()

        self.assertEqual(result.before, [])
        self.assertEqual(result.after, [])
        self.assertFalse(result.has_anything)

    # -- what a neighbour carries ----------------------------------------

    def test_a_neighbour_carries_what_it_was_about(self):
        """Resolved here rather than left to the caller: a surface that has to
        issue a query per row to render a morning will issue thirty."""
        self.event(
            EventType.TASK_COMPLETED,
            at(minutes=-5),
            task=self.a_task("Call the plumber"),
        )

        neighbour = self.around().before[0]

        self.assertEqual(neighbour.task.text, "Call the plumber")
        self.assertIsNone(neighbour.node)

    def test_a_neighbour_whose_subject_is_gone_is_still_a_neighbour(self):
        """The log keeps the event after the row it named is deleted -- which
        is why `DailyFocus.task_text` is snapshotted -- so a read that assumed
        otherwise would raise on exactly the oldest history."""
        task = self.a_task()
        self.event(EventType.TASK_COMPLETED, at(minutes=-5), task=task)
        Item.objects.filter(pk=task.pk).delete()

        neighbour = self.around().before[0]

        self.assertIsNone(neighbour.task)
        self.assertEqual(neighbour.event_type, EventType.TASK_COMPLETED)

    def test_a_note_the_person_deleted_is_not_handed_back(self):
        """R5. The event stays -- capturing it was a real act -- but the
        content is withheld, which is `delete_node`'s whole promise and the
        same shape the dangling-task path already returns. Latent today only
        because no surface calls `delete_node`; the day one does, this read
        would have rendered the note somebody erased."""
        node = self.a_node("something regretted")
        self.event(EventType.CAPTURED, at(minutes=-5), node=node)
        node.deleted_at = timezone.now()
        node.save(update_fields=["deleted_at"])

        neighbour = self.around().before[0]

        self.assertIsNone(neighbour.node)
        self.assertEqual(neighbour.event_type, EventType.CAPTURED)

    def test_a_note_the_person_archived_is_withheld_too(self):
        """`queries.live_nodes` excludes archived nodes from everything, and
        this agrees with that rule rather than inventing a second one."""
        node = self.a_node("put away")
        self.event(EventType.CAPTURED, at(minutes=-5), node=node)
        node.archived_at = timezone.now()
        node.save(update_fields=["archived_at"])

        self.assertIsNone(self.around().before[0].node)

    def test_an_archived_task_is_still_handed_back(self):
        """The asymmetry with an archived node, asserted rather than assumed:
        the task core has an archive somebody browses, so an archived task is
        finished rather than hidden. Withholding it would also make
        `TASK_ARCHIVED` the one event in the log that can never name its own
        subject."""
        task = self.a_task("Old paperwork")
        self.event(EventType.TASK_ARCHIVED, at(minutes=-5), task=task)
        Item.objects.filter(pk=task.pk).update(
            status=Item.Status.ARCHIVED, archived_at=timezone.now()
        )

        self.assertEqual(self.around().before[0].task.text, "Old paperwork")

    def test_a_day_is_a_subject_like_any_other(self):
        entry = self.an_entry(NOON.date())
        self.event(
            EventType.FOCUS_PINNED, at(minutes=-5), entry=entry, task=self.a_task()
        )

        self.assertEqual(self.around().before[0].entry_id, entry.pk)

    # -- asking around an event ------------------------------------------

    def test_an_event_is_not_its_own_neighbour(self):
        """Asking what was around a completion should not answer "that
        completion"."""
        anchor = self.event(EventType.TASK_COMPLETED, NOON, task=self.a_task())

        self.assertEqual(self.types(self.around(excluding=anchor)), [])

    def test_it_can_be_told_which_event_by_its_id(self):
        anchor = self.event(EventType.TASK_COMPLETED, NOON, task=self.a_task())

        self.assertEqual(self.types(self.around(excluding=anchor.pk)), [])

    def test_it_refuses_something_that_is_not_an_event(self):
        """R6. `getattr(x, "pk", x)` took anything: a `Neighbour` -- this
        module's own return type, which has `event_id` and no `pk` -- went
        into the query whole and raised deep in `AutoField`, and any other
        model instance silently excluded an unrelated event that happened to
        share its integer id."""
        self.event(EventType.CAPTURED, at(minutes=-5), node=self.a_node())
        not_an_event = self.a_task()

        with self.assertRaises(TypeError):
            self.around(excluding=not_an_event)

    def test_two_things_at_the_same_instant_are_both_nearby(self):
        entry = self.an_entry(NOON.date())
        for text in ("One", "Two", "Three"):
            self.event(
                EventType.FOCUS_PINNED,
                at(minutes=-5),
                entry=entry,
                task=self.a_task(text),
            )

        self.assertEqual(len(self.around().before), 3)

    # -- isolation -------------------------------------------------------

    def test_it_does_not_reach_into_another_persons_morning(self):
        from clarice.testing import make_node

        bob = self.someone_else()
        self.event(
            EventType.CAPTURED,
            at(minutes=-5),
            owner=bob,
            node=make_node(bob, "theirs"),
        )

        self.assertEqual(self.types(self.around()), [])
