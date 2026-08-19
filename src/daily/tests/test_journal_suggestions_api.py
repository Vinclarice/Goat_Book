"""Suggestions beside the entry, and the two ways to answer one — slice D.

`planning-assistant-plan.md` increment 2, the last slice. The card the person
sees answers five questions, and the fourth had no implementation anywhere until
this endpoint:

| Proposal | the sentence read as a commitment |
| Evidence | the passage it was read out of |
| Reason | why it was proposed |
| **Effect** | **what confirming will do** |
| Decision | confirm, or dismiss |

**Effect is the new one and it earns its place immediately.** "Creates a task"
and "creates a task due 4 June" are different things to agree to, and slice C
decided a promise with no date makes a task with none — so a person who cannot
see which they are getting is being asked to approve something they were not
told.

Carried on the day payload rather than fetched separately, because the
suggestion belongs beside the writing that caused it and a second request would
let the two arrive apart.
"""
import json
from datetime import date

from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from daily import services
from lists.models import Item
from mind.models import Facet, FacetKind

AUGUST_3 = date(2026, 8, 3)


class JournalSuggestionsTest(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.bob = User.objects.create_user(
            "bob", "bob@example.com", "another secure password"
        )
        self.client.force_login(self.alice)

    def write(self, text, owner=None, day=AUGUST_3):
        return services.write_entry(owner or self.alice, day, happenings=text)

    def suggestion_for(self, entry):
        return Facet.objects.get(entry=entry, kind=FacetKind.ACTIONABLE)

    def get_day(self, day=AUGUST_3):
        return self.client.get(f"/api/v1/day/{day.isoformat()}").json()

    def post(self, path, body=None):
        return self.client.post(
            path, data=json.dumps(body or {}), content_type="application/json"
        )

    # -- the card ---------------------------------------------------------

    def test_a_suggestion_appears_beside_the_day_it_was_read_from(self):
        self.write("I still need to ask Maya about the venue.")

        body = self.get_day()

        self.assertEqual(len(body["suggestions"]), 1)

    def test_the_card_carries_its_evidence_and_its_reason(self):
        self.write("A quiet morning. I still need to ask Maya about the venue.")

        card = self.get_day()["suggestions"][0]

        self.assertEqual(card["text"], "I still need to ask Maya about the venue.")
        self.assertTrue(card["reason"])

    def test_the_card_says_what_confirming_will_do(self):
        """The Effect field, and the reason it exists.

        Slice C decided a dateless promise makes a dateless task. Somebody
        approving one should be told that rather than discovering it in their
        agenda.
        """
        self.write("I still need to ask Maya about the venue.")

        card = self.get_day()["suggestions"][0]

        self.assertEqual(card["effect"], "Creates a task with no due date")

    def test_the_effect_names_the_date_when_there_is_one(self):
        """That a date is named, not which one.

        Which date "4 June" means from an August entry is the parser's
        roll-forward rule, tested where that rule lives. Asserting it again
        here would couple this endpoint to a semantic it does not own -- and
        the first version of this test did exactly that, hard-coding a year
        the parser was right to move.
        """
        self.write("I need to ring the venue on 4 September.")

        card = self.get_day()["suggestions"][0]

        self.assertRegex(card["effect"], r"^Creates a task due \d{4}-\d{2}-\d{2}$")

    def test_ordinary_writing_offers_no_card(self):
        self.write("A good day. Nothing else today.")

        self.assertEqual(self.get_day()["suggestions"], [])

    def test_an_answered_suggestion_stops_being_offered(self):
        entry = self.write("I still need to ask Maya about the venue.")
        self.post(f"/api/v1/suggestions/{self.suggestion_for(entry).id}/confirm")

        self.assertEqual(self.get_day()["suggestions"], [])

    # -- confirming -------------------------------------------------------

    def test_confirming_makes_the_task(self):
        entry = self.write("I still need to ask Maya about the venue.")

        response = self.post(
            f"/api/v1/suggestions/{self.suggestion_for(entry).id}/confirm"
        )

        self.assertEqual(response.status_code, 200)
        task = Item.objects.get(owner=self.alice)
        self.assertEqual(task.text, "I still need to ask Maya about the venue.")
        self.assertIsNone(task.due_date)

    def test_confirming_answers_with_the_day(self):
        """The whole day back, so the card disappears without a second fetch.

        Every other write on this surface returns `DayOut` for the same
        reason -- a client reconciling its own state after a decision is a
        client that can disagree with the server about what just happened.
        """
        entry = self.write("I still need to ask Maya about the venue.")

        body = self.post(
            f"/api/v1/suggestions/{self.suggestion_for(entry).id}/confirm"
        ).json()

        self.assertEqual(body["date"], AUGUST_3.isoformat())
        self.assertEqual(body["suggestions"], [])

    # -- dismissing -------------------------------------------------------

    def test_dismissing_makes_no_task_and_removes_the_card(self):
        entry = self.write("I still need to ask Maya about the venue.")

        body = self.post(
            f"/api/v1/suggestions/{self.suggestion_for(entry).id}/dismiss"
        ).json()

        self.assertEqual(body["suggestions"], [])
        self.assertEqual(Item.objects.filter(owner=self.alice).count(), 0)

    def test_a_dismissed_suggestion_does_not_return_on_the_next_save(self):
        """The fingerprint doing its job through the whole loop.

        Dismissing and then typing another word is the ordinary case, not an
        edge one -- and a suggestion that came back would make the dismiss
        button meaningless.
        """
        entry = self.write("I still need to ask Maya about the venue.")
        self.post(f"/api/v1/suggestions/{self.suggestion_for(entry).id}/dismiss")

        self.write("I still need to ask Maya about the venue. It rained.")

        self.assertEqual(self.get_day()["suggestions"], [])

    # -- ownership --------------------------------------------------------

    def test_cannot_answer_somebody_else_s_suggestion(self):
        entry = self.write(
            "I still need to ask Maya about the venue.", owner=self.bob
        )
        facet = self.suggestion_for(entry)

        response = self.post(f"/api/v1/suggestions/{facet.id}/confirm")

        self.assertEqual(response.status_code, 404)
        facet.refresh_from_db()
        self.assertIsNone(facet.task)

    def test_another_person_s_suggestions_are_not_on_my_day(self):
        self.write("I still need to ask Maya about the venue.", owner=self.bob)

        self.assertEqual(self.get_day()["suggestions"], [])

    def test_rejects_anonymous_requests(self):
        self.client.logout()

        self.assertEqual(
            self.client.get(f"/api/v1/day/{AUGUST_3.isoformat()}").status_code, 401
        )
