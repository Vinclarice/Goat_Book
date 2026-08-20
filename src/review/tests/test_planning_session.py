"""Sitting down to plan a week — planning-assistant-v2-plan.md increment 4.

Two different claims are asserted here. That the ritual is **recorded**, so "I
planned and had little to change" stays distinguishable from "I never opened
it" — without which nothing can say whether v2 worked. And that the check-in
**arrives with an opinion** rather than a questionnaire: the plan's rule is that
a session asking what the system already knows makes the ritual longer and the
answers worse.
"""
from datetime import date, timedelta

from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from lists import services as list_services
from lists.models import Item, List, Project
from review import reads, services
from review.models import PlanningSession, WeeklyIntention

MONDAY = date(2026, 6, 1)
WEDNESDAY = date(2026, 6, 3)
NEXT_MONDAY = date(2026, 6, 8)


class OpeningASessionTest(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.bob = User.objects.create_user(
            "bob", "bob@example.com", "another secure password"
        )

    def test_a_week_starts_with_no_session(self):
        """A blank page, not a missing one — and "nobody has sat down yet" is
        precisely the fact this model exists to be able to state."""
        self.assertIsNone(reads.planning_session_for(self.alice, MONDAY))

    def test_opening_one_records_that_it_happened(self):
        services.open_planning_session(self.alice, MONDAY)

        self.assertIsNotNone(reads.planning_session_for(self.alice, MONDAY))

    def test_any_day_of_the_week_addresses_the_same_session(self):
        services.open_planning_session(self.alice, MONDAY)
        services.open_planning_session(self.alice, WEDNESDAY)

        self.assertEqual(
            PlanningSession.objects.filter(owner=self.alice).count(), 1
        )

    def test_reopening_does_not_restart_it(self):
        """When somebody first sat down is the fact worth keeping. A second
        open that re-stamped it would rewrite that, which is the only thing
        this timestamp could ever answer."""
        first = services.open_planning_session(self.alice, MONDAY)

        again = services.open_planning_session(self.alice, WEDNESDAY)

        self.assertEqual(again.pk, first.pk)
        self.assertEqual(again.created_at, first.created_at)

    def test_reading_one_writes_nothing(self):
        """The trap this model is most likely to fall into. A session created
        by loading the review would make every refresh a planning session and
        destroy the only number it exists to produce."""
        reads.planning_session_for(self.alice, MONDAY)

        self.assertFalse(PlanningSession.objects.exists())

    def test_opening_one_invents_no_intention(self):
        """Three records key on (owner, week) and each means a different
        thing. Planning a week is not writing an intention for it."""
        services.open_planning_session(self.alice, MONDAY)

        self.assertFalse(WeeklyIntention.objects.exists())

    def test_one_person_s_session_is_not_another_s(self):
        services.open_planning_session(self.bob, MONDAY)

        self.assertIsNone(reads.planning_session_for(self.alice, MONDAY))


class SayingTheWeekIsUnusualTest(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )

    def test_a_new_session_assumes_a_usual_week(self):
        session = services.open_planning_session(self.alice, MONDAY)

        self.assertEqual(session.unusual, PlanningSession.Unusual.USUAL)

    def test_a_person_can_say_they_have_less_time(self):
        services.open_planning_session(self.alice, MONDAY)

        services.set_week_unusual(
            self.alice, MONDAY, PlanningSession.Unusual.LESS_TIME
        )

        self.assertEqual(
            reads.planning_session_for(self.alice, MONDAY).unusual,
            PlanningSession.Unusual.LESS_TIME,
        )

    def test_saying_so_opens_a_session_if_none_was_open(self):
        """Correcting what the system believes *is* planning, so this must not
        need a separate open first — otherwise a correction could be recorded
        against a week nobody sat down with."""
        services.set_week_unusual(
            self.alice, MONDAY, PlanningSession.Unusual.MORE_TIME
        )

        self.assertIsNotNone(reads.planning_session_for(self.alice, MONDAY))

    def test_it_can_be_taken_back(self):
        services.set_week_unusual(
            self.alice, MONDAY, PlanningSession.Unusual.LESS_TIME
        )

        services.set_week_unusual(
            self.alice, MONDAY, PlanningSession.Unusual.USUAL
        )

        self.assertEqual(
            reads.planning_session_for(self.alice, MONDAY).unusual,
            PlanningSession.Unusual.USUAL,
        )


class ProjectsWorthConfirmingTest(TestCase):
    """What the check-in *believes*, so it can confirm rather than ask.

    The plan's own example: *"Website Launch and Billing look active.
    Newsletter has not moved in five weeks — still going?"* A session that
    opened by asking which projects are active would be asking for something
    the system can work out, which is the failure this read exists to avoid.
    """

    def setUp(self):
        self.alice = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )

    def project(self, title, **kwargs):
        return Project.objects.create(owner=self.alice, title=title, **kwargs)

    def task_in(self, project, text, *, made_days_ago=0, finished_days_ago=None):
        area = List.objects.create(
            owner=self.alice, title=f"Area for {project.title}", project=project
        )
        task = list_services.create_item(area, text)
        Item.objects.filter(pk=task.pk).update(
            created_at=timezone.now() - timedelta(days=made_days_ago)
        )
        if finished_days_ago is not None:
            list_services.complete_item(task)
            Item.objects.filter(pk=task.pk).update(
                completed_at=timezone.now() - timedelta(days=finished_days_ago)
            )
        return task

    def test_a_project_worked_on_recently_looks_active(self):
        project = self.project("Website launch")
        self.task_in(project, "Write the copy", made_days_ago=2)

        found = reads.projects_to_confirm(self.alice)

        self.assertEqual([each.project for each in found], [project])
        self.assertTrue(found[0].looks_active)

    def test_a_project_nothing_has_moved_in_looks_quiet(self):
        project = self.project("Newsletter")
        self.task_in(project, "Draft issue one", made_days_ago=40)

        found = reads.projects_to_confirm(self.alice)

        self.assertFalse(found[0].looks_active)
        self.assertEqual(found[0].quiet_for_days, 40)

    def test_finishing_something_counts_as_movement(self):
        """Activity is not only new work. A project whose last act was
        finishing something is one somebody was working on."""
        project = self.project("Billing")
        self.task_in(
            project, "Pick a provider", made_days_ago=40, finished_days_ago=3
        )

        found = reads.projects_to_confirm(self.alice)

        self.assertTrue(found[0].looks_active)

    def test_a_paused_project_is_not_asked_about(self):
        """It has already been answered. Asking again would make the pause
        worth nothing — the same reason the review stopped counting its
        deadline."""
        project = self.project("Newsletter")
        self.task_in(project, "Draft issue one", made_days_ago=40)
        list_services.pause_project(project)

        self.assertEqual(reads.projects_to_confirm(self.alice), [])

    def test_a_completed_project_is_not_asked_about(self):
        project = self.project("Old site")
        self.task_in(project, "Ship it", made_days_ago=40)
        list_services.complete_project(project)

        self.assertEqual(reads.projects_to_confirm(self.alice), [])

    def test_a_project_with_no_work_in_it_is_judged_by_its_own_age(self):
        """An empty project made this morning is not stale, and one made two
        months ago and never filled is exactly what this should ask about.
        With no tasks to read, the project's own creation is the only evidence
        there is."""
        self.project("Just started")

        found = reads.projects_to_confirm(self.alice)

        self.assertTrue(found[0].looks_active)

    def test_an_empty_project_left_for_months_is_asked_about(self):
        project = self.project("Someday maybe")
        Project.objects.filter(pk=project.pk).update(
            created_at=timezone.now() - timedelta(days=60)
        )

        found = reads.projects_to_confirm(self.alice)

        self.assertFalse(found[0].looks_active)

    def test_the_quiet_ones_come_first(self):
        """The list is a question, and the projects worth asking about are the
        ones that have not moved. Sorting the active ones to the top would
        bury the only rows that need an answer."""
        active = self.project("Website launch")
        self.task_in(active, "Write the copy", made_days_ago=1)
        quiet = self.project("Newsletter")
        self.task_in(quiet, "Draft issue one", made_days_ago=40)

        found = reads.projects_to_confirm(self.alice)

        self.assertEqual([each.project for each in found], [quiet, active])

    def test_one_person_s_projects_are_not_another_s(self):
        bob = User.objects.create_user(
            "bob", "bob@example.com", "another secure password"
        )
        Project.objects.create(owner=bob, title="Bob's project")

        self.assertEqual(reads.projects_to_confirm(self.alice), [])


class TheCheckInOverHttpTest(TestCase):
    """What a client can read and write — the HTTP half of increment 4."""

    def setUp(self):
        self.alice = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.bob = User.objects.create_user(
            "bob", "bob@example.com", "another secure password"
        )
        self.client.force_login(self.alice)

    def start(self, on):
        return self.client.post(f"/api/v1/weeks/{on.isoformat()}/planning-session")

    def correct(self, on, unusual):
        return self.client.patch(
            f"/api/v1/weeks/{on.isoformat()}/planning-session",
            data=f'{{"unusual": "{unusual}"}}',
            content_type="application/json",
        )

    def test_starting_a_session_says_it_started(self):
        response = self.start(MONDAY)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["started"])

    def test_reading_the_week_does_not_start_one(self):
        """The whole reason this is a POST. A session recorded by a page load
        would make every refresh a planning session and destroy the number the
        record exists to produce."""
        self.client.get(f"/api/v1/review/{MONDAY.isoformat()}")

        self.assertFalse(PlanningSession.objects.exists())

    def test_the_week_reports_whether_one_was_started(self):
        response = self.client.get(f"/api/v1/review/{MONDAY.isoformat()}")

        self.assertFalse(response.json()["check_in"]["started"])

    def test_the_check_in_is_about_the_week_being_drafted(self):
        """The review shows one week and drafts the next, and the check-in
        belongs to the one being planned. A check-in on the week under review
        would be asking somebody to plan a week that has already happened."""
        self.start(NEXT_MONDAY)

        response = self.client.get(f"/api/v1/review/{MONDAY.isoformat()}")

        self.assertTrue(response.json()["check_in"]["started"])

    def test_a_person_can_say_the_week_is_unusual(self):
        response = self.correct(MONDAY, "less_time")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["unusual"], "less_time")

    def test_a_shape_nobody_defined_is_refused(self):
        response = self.correct(MONDAY, "extremely_busy")

        self.assertEqual(response.status_code, 422)
        self.assertFalse(PlanningSession.objects.exists())

    def test_a_week_with_no_session_reports_the_usual_shape(self):
        """The default rather than null: "nobody has said otherwise" and
        "somebody said it is usual" render identically, and a nullable enum
        would make every client handle both."""
        response = self.client.get(f"/api/v1/review/{MONDAY.isoformat()}")

        self.assertEqual(response.json()["check_in"]["unusual"], "usual")

    def test_the_check_in_names_the_projects_it_believes_are_active(self):
        Project.objects.create(owner=self.alice, title="Website launch")

        response = self.client.get(f"/api/v1/review/{MONDAY.isoformat()}")

        projects = response.json()["check_in"]["projects"]
        self.assertEqual([each["title"] for each in projects], ["Website launch"])
        self.assertTrue(projects[0]["looks_active"])

    def test_it_names_no_one_else_s_projects(self):
        Project.objects.create(owner=self.bob, title="Bob's project")

        response = self.client.get(f"/api/v1/review/{MONDAY.isoformat()}")

        self.assertEqual(response.json()["check_in"]["projects"], [])

    def test_a_stranger_is_refused(self):
        self.client.logout()

        response = self.start(MONDAY)

        self.assertEqual(response.status_code, 401)
        self.assertFalse(PlanningSession.objects.exists())
