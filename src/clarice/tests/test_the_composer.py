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

    def test_today_makes_a_task_and_puts_it_below_the_line(self):
        self.write("Call the vet back", composer.TODAY)

        bounded = daily_reads.bounded_list_for(self.owner, self.today)
        self.assertEqual(bounded.chosen, [])
        self.assertEqual([each.task_text for each in bounded.joined], ["Call the vet back"])
        self.assertEqual(Item.objects.get(owner=self.owner).status, Item.Status.ACTIVE)

    def test_did_makes_a_task_below_the_line_and_finishes_it(self):
        self.write("Fix the fence latch", composer.DID)

        bounded = daily_reads.bounded_list_for(self.owner, self.today)
        self.assertEqual(bounded.chosen, [])
        self.assertEqual([each.task_text for each in bounded.joined], ["Fix the fence latch"])
        self.assertEqual(
            Item.objects.get(owner=self.owner).status, Item.Status.COMPLETED
        )

    def test_a_did_and_a_today_both_draw_the_line(self):
        """Rule 3's other half. Increment 2 built the tick; this is the
        composer, and both are acts of execution.
        """
        for destination in (composer.DID, composer.TODAY):
            with self.subTest(destination=destination):
                DailyEntry.objects.filter(owner=self.owner).delete()
                Item.objects.filter(owner=self.owner).delete()
                self.write(f"a {destination} line", destination)
                self.assertIsNotNone(self.closed_at())

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
            [line.kind for line in day_log.lines_for(self.owner, self.today)],
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

    def test_a_today_line_lands_below_the_line(self):
        self.post({"text": "Call the vet back", "destination": "today"})

        bounded = daily_reads.bounded_list_for(self.owner, self.today)
        self.assertEqual([each.task_text for each in bounded.joined], ["Call the vet back"])

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
