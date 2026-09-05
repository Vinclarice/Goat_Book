"""One box, four destinations.

`superlists-2.0-plan.md` increment 4 and its *The composer*: two questions
decide where a line goes -- *is it done?* and *is it for today?* -- so there are
four destinations and one existing service.

| Destination | `Node` | Facet and `Item` | Pin | Completed |
|---|---|---|---|---|
| **Note** | yes | no | no | -- |
| **Did** | yes | yes | below the line | yes |
| **Today** | yes | yes | below the line | no |
| **Pool** | yes | yes | no | no |

Every line is a `Node` first, which is what makes the log an intake pipe: a
line is searchable, mentionable and proposable the moment it is written.
"""
import json
import uuid

from django.test import TestCase
from django.utils import timezone

from clarice import composer, day_log
from clarice.testing import make_user
from daily import reads as daily_reads
from daily.models import DailyEntry
from lists.models import Item
from mind import services as mind_services
from mind.models import Facet, FacetKind, Node


class TheFourDestinationsTest(TestCase):
    def setUp(self):
        self.owner = make_user("alice")
        self.today = timezone.localdate()

    def write(self, text, destination):
        return composer.write_a_line(
            self.owner, text=text, destination=destination, now=timezone.now()
        )

    def closed_at(self):
        entry = DailyEntry.objects.filter(owner=self.owner, date=self.today).first()
        return entry.list_closed_at if entry else None

    def test_every_destination_writes_a_node_first(self):
        """What makes the log an intake pipe rather than a second task list."""
        for destination in composer.DESTINATIONS:
            with self.subTest(destination=destination):
                self.write(f"a line for {destination}", destination)

        self.assertEqual(
            sorted(
                Node.objects.filter(owner=self.owner).values_list(
                    "original_content", flat=True
                )
            ),
            sorted(f"a line for {each}" for each in composer.DESTINATIONS),
        )

    def test_a_note_is_only_a_note(self):
        self.write("Neighbour asked about the fence", composer.NOTE)

        self.assertEqual(Item.objects.filter(owner=self.owner).count(), 0)
        self.assertEqual(daily_reads.focus_for(self.owner, self.today), [])
        self.assertIsNone(self.closed_at())

    def test_a_note_does_not_draw_the_line(self):
        """Rule 3, and the reason D7 was answered the way it was: writing down
        something overheard at breakfast is not the start of the day's work.
        """
        self.write("Overheard at breakfast", composer.NOTE)

        self.assertIsNone(self.closed_at())

    def test_pool_makes_a_task_and_chooses_no_day_for_it(self):
        self.write("Ring the fencing people", composer.POOL)

        task = Item.objects.get(owner=self.owner)
        self.assertEqual(task.text, "Ring the fencing people")
        self.assertEqual(task.status, Item.Status.ACTIVE)
        self.assertEqual(daily_reads.focus_for(self.owner, self.today), [])
        self.assertIsNone(self.closed_at())

    def test_today_joins_the_chosen_list_on_a_day_nothing_has_happened_on(self):
        """~~"puts it below the line"~~ -- **September 4, 2026.** At eight in
        the morning on an untouched day, the first thing you add to your own
        list has to *be* your list. It drew the line and landed below it, so
        the morning's set stayed empty and every later pick joined late -- the
        exact accident rule 3 was written to prevent, through the one door it
        left open.
        """
        self.write("Call the vet back", composer.TODAY)

        bounded = daily_reads.bounded_list_for(self.owner, self.today)
        self.assertEqual([each.task_text for each in bounded.chosen], ["Call the vet back"])
        self.assertEqual(bounded.joined, [])
        self.assertIsNone(self.closed_at())
        self.assertEqual(Item.objects.get(owner=self.owner).status, Item.Status.ACTIVE)

    def test_today_joins_below_the_line_once_the_day_has_started(self):
        """And the other half, which is what makes it one rule rather than a
        special case: where a Today line lands is decided by whether the work
        has begun, not by the destination.
        """
        self.write("Fixed the fence latch", composer.DID)

        self.write("Call the vet back", composer.TODAY)

        bounded = daily_reads.bounded_list_for(self.owner, self.today)
        self.assertEqual(
            [each.task_text for each in bounded.joined],
            ["Fixed the fence latch", "Call the vet back"],
        )
        self.assertEqual(bounded.chosen, [])

    def test_did_makes_a_task_below_the_line_and_finishes_it(self):
        self.write("Fix the fence latch", composer.DID)

        bounded = daily_reads.bounded_list_for(self.owner, self.today)
        self.assertEqual(bounded.chosen, [])
        self.assertEqual([each.task_text for each in bounded.joined], ["Fix the fence latch"])
        self.assertEqual(
            Item.objects.get(owner=self.owner).status, Item.Status.COMPLETED
        )

    def test_a_did_draws_the_line_and_a_today_does_not(self):
        """Rule 3's other half, corrected. Increment 2 built the tick; a Did is
        the composer's version of it. **A Today is not** -- writing down
        something to do later today is planning, and a rule that ended the
        morning on it would be the accident rule 3 exists to prevent.
        """
        self.write("a did line", composer.DID)
        self.assertIsNotNone(self.closed_at())

        DailyEntry.objects.filter(owner=self.owner).delete()
        Item.objects.filter(owner=self.owner).delete()

        self.write("a today line", composer.TODAY)
        self.assertIsNone(self.closed_at())

    def test_a_pool_line_leaves_the_list_open(self):
        """A commitment made is not a commitment kept: filing something for
        later is not the day's work starting.
        """
        self.write("Ring the fencing people", composer.POOL)

        self.assertIsNone(self.closed_at())

    def test_the_line_a_did_draws_does_not_move_for_the_next_one(self):
        self.write("First thing", composer.DID)
        drawn = self.closed_at()

        self.write("Second thing", composer.DID)

        self.assertEqual(self.closed_at(), drawn)

    def test_a_composed_task_can_say_where_it_came_from(self):
        """The backlink is the whole reason a facet stands between them --
        `confirm_actionable` keeps the node rather than consuming it.
        """
        self.write("Ring the fencing people", composer.POOL)

        facet = Facet.objects.get(kind=FacetKind.ACTIONABLE)
        self.assertEqual(facet.task, Item.objects.get(owner=self.owner))
        self.assertEqual(facet.node, Node.objects.get(owner=self.owner))
        self.assertIsNotNone(facet.confirmed_at)

    def test_nothing_that_guessed_is_credited_for_an_explicit_line(self):
        """`Facet.producer` is blank for a facet nothing proposed, so the
        readings about which producer is worth hearing from stay honest.
        """
        self.write("Ring the fencing people", composer.POOL)

        facet = Facet.objects.get(kind=FacetKind.ACTIONABLE)
        self.assertEqual(facet.producer, "")
        self.assertEqual(facet.origin, "explicit")

    def test_a_did_line_is_in_the_days_log_twice_over(self):
        """Rule 5: a tick is a log line with a time -- and the words are a node,
        so one act leaves both a written line and a completion.
        """
        self.write("Fix the fence latch", composer.DID)

        self.assertEqual(
            [
                line.kind
                for line in day_log.lines_for(
                    self.owner, self.today, now=timezone.now()
                )
            ],
            [day_log.WRITTEN, day_log.CHOSE, day_log.COMPLETED],
        )

    def test_a_blank_line_is_refused(self):
        """`mind`'s own `EmptyNode`, not a second error meaning the same thing:
        the capture is what refuses, and the endpoint already turns that into
        the 400 a queued client reads as permanent.
        """
        with self.assertRaises(mind_services.EmptyNode):
            self.write("   ", composer.POOL)

        self.assertEqual(Node.objects.filter(owner=self.owner).count(), 0)

    def test_an_unknown_destination_is_refused(self):
        with self.assertRaises(composer.ComposerError):
            self.write("Somewhere else", "elsewhere")

        self.assertEqual(Node.objects.filter(owner=self.owner).count(), 0)


class TheComposerOverTheApiTest(TestCase):
    """`/api/v1/capture`, which the phone already calls, with one more field."""

    def setUp(self):
        self.owner = make_user("alice")
        self.today = timezone.localdate()
        self.client.force_login(self.owner)

    def post(self, body):
        return self.client.post(
            "/api/v1/capture",
            data=json.dumps(body),
            content_type="application/json",
            headers={"Idempotency-Key": str(uuid.uuid4())},
        )

    def test_a_body_with_no_destination_is_a_note(self):
        """The phone sends exactly this and needs no change; its offline queue
        is untouched.
        """
        response = self.post({"text": "Neighbour asked about the fence"})

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Item.objects.filter(owner=self.owner).count(), 0)

    def test_a_did_line_arrives_finished(self):
        response = self.post({"text": "Fix the fence latch", "destination": "did"})

        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            Item.objects.get(owner=self.owner).status, Item.Status.COMPLETED
        )

    def test_a_today_line_joins_the_list_wherever_the_day_already_is(self):
        """~~"lands below the line"~~ -- September 4, 2026. A Today line pins
        and draws nothing, so on an untouched day it is part of the set you
        chose, and after the first tick it joins below it.
        """
        self.post({"text": "Call the vet back", "destination": "today"})

        bounded = daily_reads.bounded_list_for(self.owner, self.today)
        self.assertEqual([each.task_text for each in bounded.chosen], ["Call the vet back"])

        self.post({"text": "Fixed the fence latch", "destination": "did"})
        self.post({"text": "Ring the fencing people", "destination": "today"})

        bounded = daily_reads.bounded_list_for(self.owner, self.today)
        self.assertEqual(
            [each.task_text for each in bounded.joined],
            ["Fixed the fence latch", "Ring the fencing people"],
        )

    def test_an_unknown_destination_is_a_bad_request_not_a_silent_note(self):
        """A queued client treats 400 as permanent, which this is: the server
        must not invent or silently ignore a field it cannot use.
        """
        response = self.post({"text": "Somewhere else", "destination": "elsewhere"})

        self.assertEqual(response.status_code, 422)
        self.assertEqual(Node.objects.filter(owner=self.owner).count(), 0)

    def test_a_replayed_key_does_not_do_the_work_twice(self):
        """Idempotency is the graph's own mechanism, and a composed line must
        inherit it -- two taps on Did must not make two completed tasks.
        """
        key = str(uuid.uuid4())
        body = json.dumps({"text": "Fix the fence latch", "destination": "did"})
        first = self.client.post(
            "/api/v1/capture",
            data=body,
            content_type="application/json",
            headers={"Idempotency-Key": key},
        )
        second = self.client.post(
            "/api/v1/capture",
            data=body,
            content_type="application/json",
            headers={"Idempotency-Key": key},
        )

        self.assertEqual((first.status_code, second.status_code), (201, 200))
        self.assertEqual(Item.objects.filter(owner=self.owner).count(), 1)

    def test_a_line_never_reaches_another_persons_day(self):
        bob = make_user("bob")

        self.post({"text": "Mine", "destination": "did"})

        self.assertEqual(Item.objects.filter(owner=bob).count(), 0)
        self.assertEqual(Node.objects.filter(owner=bob).count(), 0)


class ALogLineProposesNothingTest(TestCase):
    """**D2, answered.** `superlists-2.0-plan.md` increment 9.

    *Forty nodes a day will drown concept proposal and hypothesis detection if
    each is treated as a considered note.* So a line written into the day's log
    is a `Node` from the first keystroke -- searchable, mentionable, in the
    graph -- and proposes nothing at capture.

    **The attention tier was never the lever**, which the decision says in as
    many words: `attention_tier` is computed at read time and already places a
    node with no confirmed actionable facet in quiet knowledge. What is
    suppressed here is the one producer that runs on the live path.
    """

    def setUp(self):
        self.owner = make_user("alice")

    def write(self, text, destination=None, **fields):
        return composer.write_a_line(
            self.owner,
            text=text,
            destination=destination or composer.NOTE,
            now=timezone.now(),
            **fields,
        )

    def proposals(self):
        return Facet.objects.filter(
            kind=FacetKind.ACTIONABLE, confirmed_at__isnull=True
        )

    def test_a_note_that_reads_like_a_commitment_proposes_nothing(self):
        """The exact sentence the capture producer exists for, written into the
        log instead. It is still a node, still searchable; what it does not do
        is interrupt.
        """
        self.write("Call the dentist by Friday")

        self.assertEqual(self.proposals().count(), 0)
        self.assertEqual(Node.objects.filter(owner=self.owner).count(), 1)

    def test_the_same_words_from_a_phone_still_propose(self):
        """**The phone is the exception and not an oversight.** A capture
        client exists to get one considered thought out of your head in three
        seconds, which is the volume the producer was designed for and what
        `bittern` validated. The day's composer is the other thing -- forty
        lines as they happen -- and it is the only browser caller of this
        endpoint.
        """
        self.write("Call the dentist by Friday", from_a_phone=True)

        self.assertEqual(self.proposals().count(), 1)

    def test_a_pool_line_proposes_nothing_either_and_confirms_instead(self):
        """Proposing a commitment on top of one somebody just made explicitly
        would be the system asking whether they meant what they said.
        """
        self.write("Ring the fencing people", composer.POOL)

        self.assertEqual(self.proposals().count(), 0)
        self.assertEqual(
            Facet.objects.filter(
                kind=FacetKind.ACTIONABLE, confirmed_at__isnull=False
            ).count(),
            1,
        )

    def test_a_log_line_is_in_the_graph_from_the_first_keystroke(self):
        """*Searchable, mentionable and proposable the moment it is written* --
        what is deferred is the proposal, not the node.
        """
        from mind import queries

        self.write("Neighbour asked about the fence")

        node = Node.objects.get(owner=self.owner)
        self.assertIn(node, queries.live_nodes(self.owner))

