"""What will be true by Friday — planning-assistant-v2-plan.md increment 5.

**D3, answered on August 20, 2026: outcomes and intentions are different
questions.** An intention is one sentence about what a week is *for*; an outcome
is one of two or three concrete things that will be true by the end of it, each
chosen separately and each carrying the evidence that put it on the list.

**Nothing here is generated**, which is the constraint that shaped the
proposal. The plan's sketch showed *"Make the website ready for launch review"*
— a composed sentence, and D1 defers those. What is proposed instead is a
*project* plus the facts that make it this week's, and the sentence offered is
the project's own `desired_outcome`: the person's words, which is what that
field was added for in increment 3.
"""
from datetime import date, timedelta

from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from lists import services as list_services
from lists.models import Item, List, Project
from review import reads, services
from review.models import WeeklyOutcome

MONDAY = date(2026, 6, 1)
WEDNESDAY = date(2026, 6, 3)
SUNDAY = date(2026, 6, 7)


class ChoosingAnOutcomeTest(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.bob = User.objects.create_user(
            "bob", "bob@example.com", "another secure password"
        )

    def test_a_week_starts_with_no_outcomes(self):
        self.assertEqual(reads.outcomes_for(self.alice, MONDAY), [])

    def test_choosing_one_records_it(self):
        services.choose_outcome(self.alice, MONDAY, text="The form is live.")

        found = reads.outcomes_for(self.alice, MONDAY)
        self.assertEqual([each.text for each in found], ["The form is live."])

    def test_a_week_can_hold_several(self):
        """The whole of D3. One record per owner per week could not hold
        these, which is why this is not a field on the intention."""
        services.choose_outcome(self.alice, MONDAY, text="The form is live.")
        services.choose_outcome(self.alice, WEDNESDAY, text="Billing is settled.")

        self.assertEqual(len(reads.outcomes_for(self.alice, SUNDAY)), 2)

    def test_any_day_of_the_week_addresses_the_same_week(self):
        services.choose_outcome(self.alice, SUNDAY, text="The form is live.")

        self.assertEqual(len(reads.outcomes_for(self.alice, MONDAY)), 1)

    def test_they_keep_the_order_they_were_chosen_in(self):
        """Chosen order, never a ranking. Which outcome matters more is the
        person's to say, and a number the system sorted by would become one."""
        services.choose_outcome(self.alice, MONDAY, text="First.")
        services.choose_outcome(self.alice, MONDAY, text="Second.")
        services.choose_outcome(self.alice, MONDAY, text="Third.")

        found = reads.outcomes_for(self.alice, MONDAY)
        self.assertEqual([each.text for each in found], ["First.", "Second.", "Third."])

    def test_choosing_one_from_a_project_snapshots_what_it_was_called(self):
        """Charter rule 3. An outcome that read its project's title live would
        be silently rewritten by a rename, and what somebody committed to three
        weeks ago is exactly the history that must not move."""
        project = Project.objects.create(owner=self.alice, title="Website launch")

        outcome = services.choose_outcome(
            self.alice, MONDAY, text="The form is live.", project=project
        )

        project.title = "Something else entirely"
        project.save(update_fields=["title"])

        outcome.refresh_from_db()
        self.assertEqual(outcome.project_title, "Website launch")

    def test_deleting_the_project_leaves_the_outcome_standing(self):
        """SET_NULL rather than cascade: deleting a project does not unmake
        the week somebody spent on it, and the snapshot is what keeps the row
        readable afterwards."""
        project = Project.objects.create(owner=self.alice, title="Website launch")
        services.choose_outcome(
            self.alice, MONDAY, text="The form is live.", project=project
        )

        project.delete()

        found = reads.outcomes_for(self.alice, MONDAY)
        self.assertEqual(len(found), 1)
        self.assertIsNone(found[0].project)
        self.assertEqual(found[0].project_title, "Website launch")

    def test_an_outcome_can_be_written_from_nothing(self):
        """A week can be about something that is not a project."""
        outcome = services.choose_outcome(
            self.alice, MONDAY, text="Sleep properly for five nights."
        )

        self.assertIsNone(outcome.project)
        self.assertEqual(outcome.project_title, "")

    def test_it_can_be_reworded(self):
        outcome = services.choose_outcome(
            self.alice, MONDAY, text="The form is live."
        )

        services.reword_outcome(self.alice, outcome.pk, "The form takes bookings.")

        self.assertEqual(
            reads.outcomes_for(self.alice, MONDAY)[0].text,
            "The form takes bookings.",
        )

    def test_it_can_be_dropped(self):
        """Hard delete, and the exception to the pattern around it. Choosing
        three and dropping one is ordinary editing rather than rewriting
        history -- and `PlanningSession` already records that the ritual
        happened, so this row does not have to."""
        outcome = services.choose_outcome(
            self.alice, MONDAY, text="The form is live."
        )

        services.drop_outcome(self.alice, outcome.pk)

        self.assertEqual(reads.outcomes_for(self.alice, MONDAY), [])

    def test_one_person_cannot_reword_another_s(self):
        outcome = services.choose_outcome(self.bob, MONDAY, text="Bob's week.")

        with self.assertRaises(WeeklyOutcome.DoesNotExist):
            services.reword_outcome(self.alice, outcome.pk, "Mine now.")

        outcome.refresh_from_db()
        self.assertEqual(outcome.text, "Bob's week.")

    def test_one_person_cannot_drop_another_s(self):
        outcome = services.choose_outcome(self.bob, MONDAY, text="Bob's week.")

        with self.assertRaises(WeeklyOutcome.DoesNotExist):
            services.drop_outcome(self.alice, outcome.pk)

        self.assertTrue(WeeklyOutcome.objects.filter(pk=outcome.pk).exists())

    def test_one_person_s_outcomes_are_not_another_s(self):
        services.choose_outcome(self.bob, MONDAY, text="Bob's week.")

        self.assertEqual(reads.outcomes_for(self.alice, MONDAY), [])


class WhatIsWorthProposingTest(TestCase):
    """The proposal, which is evidence rather than a suggestion.

    Each candidate is a project the week has a reason to be about, and the
    reason is stated as facts a reader can check: a deadline, work already
    dated into the week, recent movement. The sentence offered is the
    project's own, never one this composed.
    """

    def setUp(self):
        self.alice = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )

    def project(self, title, **kwargs):
        return Project.objects.create(owner=self.alice, title=title, **kwargs)

    def dated_task(self, project, text, due_date):
        area = List.objects.create(
            owner=self.alice, title=f"Area for {project.title}", project=project
        )
        return Item.objects.create(
            owner=self.alice, list=area, text=text, due_date=due_date
        )

    def test_a_project_due_in_the_week_is_worth_proposing(self):
        project = self.project("Website launch", due_date=WEDNESDAY)

        found = reads.outcomes_worth_proposing(self.alice, MONDAY)

        self.assertEqual([each.project for each in found], [project])

    def test_the_deadline_is_stated_as_the_reason(self):
        self.project("Website launch", due_date=WEDNESDAY)

        found = reads.outcomes_worth_proposing(self.alice, MONDAY)

        self.assertIn(str(WEDNESDAY), " ".join(found[0].because))

    def test_work_already_dated_into_the_week_is_a_reason(self):
        project = self.project("Billing")
        self.dated_task(project, "Pick a provider", WEDNESDAY)

        found = reads.outcomes_worth_proposing(self.alice, MONDAY)

        self.assertEqual([each.project for each in found], [project])
        self.assertIn("1", " ".join(found[0].because))

    def test_a_project_with_neither_is_not_proposed(self):
        """Not every project is this week's. A list of all of them would be
        the pile of choices the ritual exists to avoid."""
        self.project("Someday maybe")

        self.assertEqual(reads.outcomes_worth_proposing(self.alice, MONDAY), [])

    def test_the_sentence_offered_is_the_project_s_own_words(self):
        """D1 holds here. What is offered is `desired_outcome` -- written by
        the person in increment 3 -- and never a phrasing this composed."""
        self.project(
            "Website launch",
            due_date=WEDNESDAY,
            desired_outcome="The booking form is live and taking bookings.",
        )

        found = reads.outcomes_worth_proposing(self.alice, MONDAY)

        self.assertEqual(
            found[0].suggested_text, "The booking form is live and taking bookings."
        )

    def test_a_project_with_no_words_of_its_own_offers_its_title(self):
        """Still the person's words. A project nobody wrote an outcome for
        proposes its own name, which is a starting point to edit rather than
        an empty box."""
        self.project("Website launch", due_date=WEDNESDAY)

        found = reads.outcomes_worth_proposing(self.alice, MONDAY)

        self.assertEqual(found[0].suggested_text, "Website launch")

    def test_a_paused_project_is_not_proposed(self):
        project = self.project("Newsletter", due_date=WEDNESDAY)
        list_services.pause_project(project)

        self.assertEqual(reads.outcomes_worth_proposing(self.alice, MONDAY), [])

    def test_a_completed_project_is_not_proposed(self):
        project = self.project("Old site", due_date=WEDNESDAY)
        list_services.complete_project(project)

        self.assertEqual(reads.outcomes_worth_proposing(self.alice, MONDAY), [])

    def test_one_already_chosen_is_not_proposed_again(self):
        """It has been answered. Offering it a second time is the surface
        asking a question it already has the answer to."""
        project = self.project("Website launch", due_date=WEDNESDAY)
        services.choose_outcome(
            self.alice, MONDAY, text="The form is live.", project=project
        )

        self.assertEqual(reads.outcomes_worth_proposing(self.alice, MONDAY), [])

    def test_the_soonest_deadline_comes_first(self):
        later = self.project("Later", due_date=SUNDAY)
        sooner = self.project("Sooner", due_date=WEDNESDAY)

        found = reads.outcomes_worth_proposing(self.alice, MONDAY)

        self.assertEqual([each.project for each in found], [sooner, later])

    def test_no_more_than_the_cap_are_offered(self):
        """A ritual that opens with nine choices is the pile this replaces.
        The cap is on what is *shown*, never on how many somebody may choose."""
        for index in range(reads.OUTCOME_PROPOSAL_LIMIT + 3):
            self.project(f"Project {index}", due_date=WEDNESDAY)

        found = reads.outcomes_worth_proposing(self.alice, MONDAY)

        self.assertEqual(len(found), reads.OUTCOME_PROPOSAL_LIMIT)

    def test_reading_proposals_writes_nothing(self):
        self.project("Website launch", due_date=WEDNESDAY)

        reads.outcomes_worth_proposing(self.alice, MONDAY)

        self.assertFalse(WeeklyOutcome.objects.exists())

    def test_one_person_s_projects_are_not_proposed_to_another(self):
        bob = User.objects.create_user(
            "bob", "bob@example.com", "another secure password"
        )
        Project.objects.create(owner=bob, title="Bob's", due_date=WEDNESDAY)

        self.assertEqual(reads.outcomes_worth_proposing(self.alice, MONDAY), [])


class OutcomesOverHttpTest(TestCase):
    """The HTTP half, and the isolation the id-taking routes now owe.

    Every write above these names only a date, which is a smaller surface than
    an id. Outcomes cannot do that -- a week holds several and a week key
    cannot say which -- so `principles.md`'s rule applies at its strictest:
    every owner-scoped, ID-taking surface gets a direct isolation test.
    """

    def setUp(self):
        self.alice = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.bob = User.objects.create_user(
            "bob", "bob@example.com", "another secure password"
        )
        self.client.force_login(self.alice)

    def post(self, path, body):
        import json

        return self.client.post(
            path, data=json.dumps(body), content_type="application/json"
        )

    def patch(self, path, body):
        import json

        return self.client.patch(
            path, data=json.dumps(body), content_type="application/json"
        )

    def test_choosing_one_returns_the_check_in_carrying_it(self):
        response = self.post(
            f"/api/v1/weeks/{MONDAY.isoformat()}/outcomes",
            {"text": "The form is live."},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [each["text"] for each in response.json()["outcomes"]],
            ["The form is live."],
        )

    def test_an_outcome_with_no_words_is_refused(self):
        response = self.post(
            f"/api/v1/weeks/{MONDAY.isoformat()}/outcomes", {"text": "   "}
        )

        self.assertEqual(response.status_code, 422)
        self.assertFalse(WeeklyOutcome.objects.exists())

    def test_choosing_one_from_a_project(self):
        project = Project.objects.create(owner=self.alice, title="Website launch")

        response = self.post(
            f"/api/v1/weeks/{MONDAY.isoformat()}/outcomes",
            {"text": "The form is live.", "project_id": project.pk},
        )

        self.assertEqual(response.json()["outcomes"][0]["project_title"], "Website launch")

    def test_another_person_s_project_cannot_be_named(self):
        project = Project.objects.create(owner=self.bob, title="Bob's project")

        response = self.post(
            f"/api/v1/weeks/{MONDAY.isoformat()}/outcomes",
            {"text": "Mine now.", "project_id": project.pk},
        )

        self.assertEqual(response.status_code, 404)
        self.assertFalse(WeeklyOutcome.objects.exists())

    def test_the_week_carries_what_is_worth_proposing(self):
        """Dated into the week being *drafted*, not the one on screen. The
        review shows one week and plans the next, and a proposal about the week
        under review would be asking somebody to plan a week that has already
        happened -- the same rule the draft and the check-in both follow."""
        Project.objects.create(
            owner=self.alice,
            title="Website launch",
            due_date=WEDNESDAY + timedelta(days=7),
        )

        response = self.client.get(f"/api/v1/review/{MONDAY.isoformat()}")

        proposals = response.json()["check_in"]["proposals"]
        self.assertEqual([each["project_title"] for each in proposals], ["Website launch"])
        self.assertTrue(proposals[0]["because"])

    def test_rewording_one(self):
        outcome = services.choose_outcome(
            self.alice, MONDAY, text="The form is live."
        )

        response = self.patch(
            f"/api/v1/weeks/{MONDAY.isoformat()}/outcomes/{outcome.pk}",
            {"text": "The form takes bookings."},
        )

        self.assertEqual(response.status_code, 200)
        outcome.refresh_from_db()
        self.assertEqual(outcome.text, "The form takes bookings.")

    def test_one_person_cannot_reword_another_s_over_http(self):
        outcome = services.choose_outcome(self.bob, MONDAY, text="Bob's week.")

        response = self.patch(
            f"/api/v1/weeks/{MONDAY.isoformat()}/outcomes/{outcome.pk}",
            {"text": "Mine now."},
        )

        self.assertEqual(response.status_code, 404)
        outcome.refresh_from_db()
        self.assertEqual(outcome.text, "Bob's week.")

    def test_dropping_one(self):
        outcome = services.choose_outcome(
            self.alice, MONDAY, text="The form is live."
        )

        response = self.client.delete(
            f"/api/v1/weeks/{MONDAY.isoformat()}/outcomes/{outcome.pk}"
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(WeeklyOutcome.objects.filter(pk=outcome.pk).exists())

    def test_one_person_cannot_drop_another_s_over_http(self):
        outcome = services.choose_outcome(self.bob, MONDAY, text="Bob's week.")

        response = self.client.delete(
            f"/api/v1/weeks/{MONDAY.isoformat()}/outcomes/{outcome.pk}"
        )

        self.assertEqual(response.status_code, 404)
        self.assertTrue(WeeklyOutcome.objects.filter(pk=outcome.pk).exists())

    def test_a_stranger_is_refused(self):
        self.client.logout()

        response = self.post(
            f"/api/v1/weeks/{MONDAY.isoformat()}/outcomes", {"text": "Not mine."}
        )

        self.assertEqual(response.status_code, 401)
        self.assertFalse(WeeklyOutcome.objects.exists())
