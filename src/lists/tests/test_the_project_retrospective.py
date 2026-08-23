"""A project ends and explains itself — **S12**.

> A project completes. Vince wants a retrospective he did not have to write from
> memory.

**Done means:** closing a project with eleven weeks of history shows **what was
planned versus met across its life**, **what he deliberately set aside**, and
**the notes and decisions made along the way** — and he adds **what he would do
differently, kept for next time**.

**Why this was impossible until now, and what actually unblocked it.** The
verdict's own words: *"nothing computes planned-versus-met across a project's
life, and `services.complete_project` still sets two fields and writes no
record. There is nowhere to put what he would do differently either."* All three
are true statements about yesterday.

**Planned versus met is not read from outcomes**, which is the first thing that
had to be settled. `WeeklyOutcome` carries no met state — it records what was
chosen, never what became of it — so a retrospective built on outcomes would
have had to invent the judgement. `DailyFocus` already carries it, and
`planned_in_week` already makes it: **met, unfinished, deliberately set aside**,
judged *at each week's end* so a past week's figure cannot move.

**So the judgement was extracted rather than copied.** `review.reads.
what_became_of` is now one function with two callers — the weekly review and
this. A second copy would have drifted the first time either changed, and
silently, because both would have gone on returning plausible numbers.

**Notes and decisions come from recorded provenance, not from retrieval**, and
this is the line between a brief and a retrospective. The brief asks *what bears
on this?* and answers topically, because a running project wants prompting. A
retrospective is a **record**, so it follows `Node → Facet → Item → List →
Project` — notes that actually became work here — and the decisions citing them.
Nothing is guessed, which is what makes it something he *did not have to write
from memory* rather than something he has to check.
"""

from datetime import date, datetime, timedelta, timezone as dt_timezone

from django.test import TestCase

from accounts.models import User
from daily import services as daily_services
from lists import projects as project_reader
from lists import services
from lists.models import Item, List
from mind import services as mind_services
from mind.models import Facet, FacetKind, InferenceOrigin, NodeSource


UTC = dt_timezone.utc

#: Monday. Eleven weeks is the story's own number, and the fixtures below use
#: three — enough to prove the per-week judgement without eleven weeks of setup.
WEEK_ONE = date(2026, 3, 2)
NOW = datetime(2026, 6, 1, 9, 0, tzinfo=UTC)


def at(day, hour=15):
    return datetime(day.year, day.month, day.day, hour, 0, tzinfo=UTC)


class TheProjectRetrospectiveTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.project = services.create_project(
            self.user, "Website launch", purpose="Stop losing bookings to email."
        )
        self.area = List.objects.create(
            owner=self.user, title="Site", project=self.project
        )
        self.elsewhere = List.objects.create(owner=self.user, title="Home")

    # -- fixtures ------------------------------------------------------------

    def pin(self, text, *, day, area=None, finished_on=None, released_on=None):
        """A task pinned to a day, and what became of it.

        Through the services, so the shapes are ones the application produces.
        """
        task = services.create_item(area if area is not None else self.area, text)
        daily_services.pin_task(self.user, day, task)
        if finished_on is not None:
            services.complete_item(task)
            Item.objects.filter(pk=task.pk).update(completed_at=at(finished_on))
        if released_on is not None:
            daily_services.unpin_task(self.user, day, task)
            from daily.models import DailyFocus

            DailyFocus.objects.filter(task=task).update(released_at=at(released_on))
        return task

    def retrospective(self):
        return project_reader.retrospective_for(self.user, self.project)

    # -- planned versus met --------------------------------------------------

    def test_it_counts_what_was_planned_and_met(self):
        self.pin("Draft the form", day=WEEK_ONE, finished_on=WEEK_ONE)
        self.pin("Wire the form", day=WEEK_ONE + timedelta(days=1))

        looking_back = self.retrospective()

        self.assertEqual(looking_back.met, 1)
        self.assertEqual(looking_back.unfinished, 1)

    def test_it_counts_what_was_deliberately_set_aside(self):
        """*What he deliberately set aside* is its own clause in the done-means,
        and it is not a failure. A pin dropped on purpose is a decision, and
        folding it into *unfinished* would report a choice as a shortfall."""
        self.pin("The newsletter idea", day=WEEK_ONE, released_on=WEEK_ONE + timedelta(days=2))

        looking_back = self.retrospective()

        self.assertEqual(looking_back.set_aside, 1)
        self.assertEqual(looking_back.unfinished, 0)

    def test_a_task_finished_after_the_week_closed_was_unfinished_that_week(self):
        """**The rule the whole read hangs on.** A task finished the following
        Tuesday was unfinished when the week closed, and a retrospective that
        judged at read time would quietly rewrite every past week into a
        success."""
        self.pin("Slipped", day=WEEK_ONE, finished_on=WEEK_ONE + timedelta(days=9))

        looking_back = self.retrospective()

        self.assertEqual(looking_back.met, 0)
        self.assertEqual(looking_back.unfinished, 1)

    def test_it_reports_week_by_week_and_not_only_a_total(self):
        """*Across its life* — a single pair of numbers cannot show a project
        that started well and stalled, which is the shape a retrospective exists
        to make visible."""
        self.pin("Week one", day=WEEK_ONE, finished_on=WEEK_ONE)
        self.pin("Week three", day=WEEK_ONE + timedelta(days=14))

        weeks = self.retrospective().weeks

        self.assertEqual([week.week_start for week in weeks][0], WEEK_ONE)
        self.assertEqual(len(weeks), 3)

    def test_a_week_with_nothing_pinned_is_still_a_week(self):
        """Eleven weeks of history includes the quiet ones. Dropping them would
        make a project that ran for a quarter look like a fortnight of work."""
        self.pin("Week one", day=WEEK_ONE, finished_on=WEEK_ONE)
        self.pin("Week three", day=WEEK_ONE + timedelta(days=14))

        middle = self.retrospective().weeks[1]

        self.assertEqual(middle.met, 0)
        self.assertEqual(middle.unfinished, 0)
        self.assertFalse(middle.has_anything)

    def test_a_long_silence_before_closing_is_one_line_not_twenty_rows(self):
        """**Found in a browser, and the first version had it wrong.**

        Empty weeks *between* work are the most legible thing a retrospective
        shows — a fortnight of silence mid-quarter is the finding. Empty weeks
        *after* the work stopped are not: they are the gap before somebody got
        round to closing it, and rendering twenty-two of them made a three-week
        project look like a six-month one. Which is worse than untidy; it is the
        page telling him something untrue about his own year.

        Counted and said in a sentence instead, which is the same *no silent
        caps* discipline the rest of this codebase keeps — do not drop it, and
        do not pad with it either.
        """
        self.pin("Week one", day=WEEK_ONE, finished_on=WEEK_ONE)
        services.complete_project(self.project)
        from lists.models import Project

        Project.objects.filter(pk=self.project.pk).update(
            completed_at=at(WEEK_ONE + timedelta(days=140))
        )
        self.project.refresh_from_db()

        looking_back = self.retrospective()

        self.assertEqual(len(looking_back.weeks), 1)
        self.assertEqual(looking_back.quiet_weeks_before_closing, 20)
        self.assertIn("20 weeks", looking_back.quiet_says)

    def test_silence_inside_the_work_is_still_shown_week_by_week(self):
        """The other half, and the reason this is not simply *drop empty
        weeks*: a gap between two bursts of work is the finding."""
        self.pin("Week one", day=WEEK_ONE, finished_on=WEEK_ONE)
        self.pin("Week three", day=WEEK_ONE + timedelta(days=14))

        looking_back = self.retrospective()

        self.assertEqual(len(looking_back.weeks), 3)
        self.assertEqual(looking_back.quiet_weeks_before_closing, 0)

    def test_work_in_another_area_is_not_this_project(self):
        self.pin("Nothing to do with it", day=WEEK_ONE, area=self.elsewhere,
                 finished_on=WEEK_ONE)

        looking_back = self.retrospective()

        self.assertEqual(looking_back.met, 0)
        self.assertEqual(looking_back.unfinished, 0)

    def test_it_does_not_read_another_persons_project(self):
        bob = User.objects.create_user("bob", "bob@example.com", "another password")

        self.assertIsNone(project_reader.retrospective_for(bob, self.project))

    # -- notes and decisions made along the way ------------------------------

    def note_that_became_work(self, content, *, day):
        node = mind_services.capture(
            self.user, content=content, captured_at=at(day),
            source=NodeSource.WEB, actor="alice",
        )
        task = services.create_item(self.area, content[:40])
        Facet.objects.create(
            node=node, kind=FacetKind.ACTIONABLE, origin=InferenceOrigin.EXPLICIT,
            task=task, confirmed_at=at(day), data={},
        )
        return node

    def test_it_shows_the_notes_that_became_work_here(self):
        """**Recorded provenance, not retrieval**, and that is the line between
        a brief and a retrospective. A brief prompts a running project and may
        be topical; a retrospective is a record, so every item in it is a row
        somebody wrote."""
        node = self.note_that_became_work("The form needs a deposit field", day=WEEK_ONE)

        self.assertEqual(list(self.retrospective().notes), [node])

    def test_a_note_that_never_became_work_here_is_not_in_the_record(self):
        mind_services.capture(
            self.user, content="A thought about the form that went nowhere",
            captured_at=at(WEEK_ONE), source=NodeSource.WEB, actor="alice",
        )

        self.assertEqual(list(self.retrospective().notes), [])

    def test_it_shows_the_decisions_taken_on_those_notes(self):
        node = self.note_that_became_work("The form needs a deposit field", day=WEEK_ONE)
        decision = mind_services.record_decision(
            self.user, question="Deposit up front?", chose="Yes, 20%",
            considered="Invoice afterwards", cites=node, now=at(WEEK_ONE, 16),
        )

        self.assertEqual(list(self.retrospective().decisions), [decision])

    # -- what he would do differently ----------------------------------------

    def test_he_can_record_what_he_would_do_differently(self):
        services.record_what_was_learned(
            self.project, "Start with the deposit rules, not the form layout."
        )

        self.project.refresh_from_db()
        self.assertEqual(
            self.project.learned, "Start with the deposit rules, not the form layout."
        )

    def test_it_starts_empty(self):
        self.assertEqual(self.project.learned, "")

    def test_the_retrospective_carries_it(self):
        services.record_what_was_learned(self.project, "Start with the deposit rules.")

        self.assertEqual(
            self.retrospective().learned, "Start with the deposit rules."
        )

    def test_it_survives_the_project_being_completed(self):
        """*Kept for next time* — a retrospective written and then lost at the
        next state change would be worse than none, because he would stop
        writing them."""
        services.record_what_was_learned(self.project, "Deposit rules first.")

        services.complete_project(self.project)

        self.project.refresh_from_db()
        self.assertEqual(self.project.learned, "Deposit rules first.")


class KeptForNextTimeTest(TestCase):
    """*...kept for next time.*

    **The clause that makes it worth writing.** A learning stored where only its
    own finished project can show it has been filed, not kept — and the moment
    it would matter is the next project, which is what the brief is for.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.done = services.create_project(self.user, "Last one", purpose="A purpose.")
        services.record_what_was_learned(self.done, "Start with the deposit rules.")
        services.complete_project(self.done)

        self.next_one = services.create_project(
            self.user, "The next one", purpose="Another purpose."
        )
        List.objects.create(owner=self.user, title="Site", project=self.next_one)

    def test_a_new_project_s_brief_carries_what_earlier_ones_taught(self):
        brief = project_reader.brief_for(self.user, self.next_one)

        self.assertEqual(
            [each.learned for each in brief.learned_before],
            ["Start with the deposit rules."],
        )

    def test_it_says_which_project_taught_it(self):
        """A lesson with no source is an aphorism. Naming the project it came
        from is what lets him decide whether it still applies."""
        brief = project_reader.brief_for(self.user, self.next_one)

        self.assertEqual(brief.learned_before[0].project.title, "Last one")

    def test_a_project_still_running_has_not_taught_anything_yet(self):
        """Only completed projects. A learning recorded mid-flight is a note to
        self about work still in progress, and offering it as a lesson would be
        the project advising itself."""
        running = services.create_project(self.user, "In flight", purpose="A purpose.")
        services.record_what_was_learned(running, "Too early to say.")

        brief = project_reader.brief_for(self.user, self.next_one)

        self.assertEqual(len(brief.learned_before), 1)

    def test_a_project_does_not_quote_its_own_lesson_back(self):
        services.record_what_was_learned(self.next_one, "Mine.")
        services.complete_project(self.next_one)

        brief = project_reader.brief_for(self.user, self.next_one)

        self.assertNotIn("Mine.", [each.learned for each in brief.learned_before])

    def test_it_does_not_carry_another_persons_lessons(self):
        bob = User.objects.create_user("bob", "bob@example.com", "another password")
        theirs = services.create_project(bob, "Theirs", purpose="A purpose.")
        services.record_what_was_learned(theirs, "Not yours.")
        services.complete_project(theirs)

        brief = project_reader.brief_for(self.user, self.next_one)

        self.assertEqual(len(brief.learned_before), 1)


class TheRetrospectiveHasItsOwnRouteTest(TestCase):
    """**Its own route rather than part of the brief**, and the split is the
    point: a brief prompts a project that is *running* and may answer topically;
    a retrospective is a record of one that is over, and every item in it is a
    row somebody wrote."""

    def setUp(self):
        self.user = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.project = services.create_project(
            self.user, "Website launch", purpose="Stop losing bookings."
        )
        self.area = List.objects.create(
            owner=self.user, title="Site", project=self.project
        )
        self.client.force_login(self.user)

    def test_it_reports_the_weeks(self):
        task = services.create_item(self.area, "Draft the form")
        daily_services.pin_task(self.user, WEEK_ONE, task)
        services.complete_item(task)
        Item.objects.filter(pk=task.pk).update(completed_at=at(WEEK_ONE))

        payload = self.client.get(
            f"/api/v1/projects/{self.project.id}/retrospective"
        ).json()

        self.assertEqual(payload["met"], 1)
        self.assertEqual(payload["weeks"][0]["week_start"], WEEK_ONE.isoformat())

    def test_it_carries_what_he_would_do_differently(self):
        services.record_what_was_learned(self.project, "Deposit rules first.")

        payload = self.client.get(
            f"/api/v1/projects/{self.project.id}/retrospective"
        ).json()

        self.assertEqual(payload["learned"], "Deposit rules first.")

    def test_it_can_be_written_through_the_project_endpoint(self):
        response = self.client.patch(
            f"/api/v1/projects/{self.project.id}",
            {"learned": "Deposit rules first."},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.project.refresh_from_db()
        self.assertEqual(self.project.learned, "Deposit rules first.")

    def test_one_person_cannot_read_anothers(self):
        bob = User.objects.create_user("bob", "bob@example.com", "another password")
        self.client.force_login(bob)

        response = self.client.get(
            f"/api/v1/projects/{self.project.id}/retrospective"
        )

        self.assertEqual(response.status_code, 404)
