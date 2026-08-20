"""A drafted week, and whether it fits — increment 6.

`planning-assistant-plan.md` increment 6, the last of the six. Two prerequisites
had to land first and both now have: S9's weekly intention, and D2's decision
that capacity comes from what already happened rather than from estimates
nobody would enter.

**Deterministic, by an explicit trade.** `design-concept.md` chose predictable
and unit-testable over adaptive and opaque for exactly this: cadence math and
rule-based selection, no model. D1 settled that the assistant ships no
generation at all, and a planner is the place that would have been most tempting.

**A draft that cannot say "this is more than your week holds" is a list, and
the product has lists.** So capacity is the point rather than a garnish, and it
comes from `DailyFocus` history — what was pinned against what was finished,
the denominator the vision document insists is recorded at the moment of
choosing because it cannot be reconstructed afterwards.

**It states capacity and never performance.** "You have finished four in a
typical week" is a fact about the weeks; "you only finish four" is a verdict
about the person, and `daily-operating-system-vision.md` asks that history be
useful without making missed work feel like punishment. The wording is not
decoration — it is the difference between a signal somebody keeps opening and
one they learn to avoid.

**No evidence is not "you are fine".** With too few weeks behind it the draft
reports no capacity at all rather than a comforting number, the same call
`accept_rate` makes returning None rather than zero.
"""
from datetime import date, timedelta

from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from daily import reads as daily_reads, services as daily_services
from lists.models import Item, List, Project
from review import reads, services

# A Monday, and the week the draft is for.
THIS_MONDAY = date(2026, 6, 1)
NEXT_MONDAY = date(2026, 6, 8)
NEXT_SUNDAY = date(2026, 6, 14)


class WeekDraftTest(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.other = User.objects.create_user(
            "bob", "bob@example.com", "another secure password"
        )
        self.area = List.objects.create(owner=self.alice, title="Work")

    def task(self, text, due_date=None, owner=None):
        return Item.objects.create(
            owner=owner or self.alice,
            list=self.area if owner is None else None,
            text=text,
            due_date=due_date,
        )

    def draft(self):
        return reads.draft_week(self.alice, NEXT_MONDAY, today=THIS_MONDAY)

    def finish_a_week(self, monday, *, planned, met):
        """A week of real history: `planned` pinned, `met` of them completed."""
        for index in range(planned):
            task = self.task(f"{monday} task {index}")
            daily_services.pin_task(self.alice, monday, task)
            if index < met:
                task.status = Item.Status.COMPLETED
                task.completed_at = timezone.make_aware(
                    timezone.datetime.combine(monday, timezone.datetime.min.time())
                ) + timedelta(hours=12)
                task.save(update_fields=["status", "completed_at"])

    # -- what it proposes -------------------------------------------------

    def test_it_carries_the_week_s_intention(self):
        services.set_intention(self.alice, NEXT_MONDAY, "Ship the booking form.")

        self.assertEqual(self.draft().intention, "Ship the booking form.")

    def test_a_week_with_no_intention_still_drafts(self):
        """The intention is context, not a gate.

        Refusing to draft without one would make the planner useless in exactly
        the week somebody most needs it -- the one they have not thought about.
        """
        self.task("Chase the invoice", due_date=THIS_MONDAY - timedelta(days=3))

        draft = self.draft()

        self.assertEqual(draft.intention, "")
        self.assertEqual([t.text for t in draft.proposed], ["Chase the invoice"])

    def test_overdue_work_is_proposed(self):
        late = self.task("Chase the invoice", due_date=THIS_MONDAY - timedelta(days=3))

        self.assertEqual(list(self.draft().proposed), [late])

    def test_work_already_dated_into_the_week_is_proposed(self):
        due = self.task("Send the deposit", due_date=NEXT_MONDAY + timedelta(days=2))

        self.assertEqual(list(self.draft().proposed), [due])

    def test_work_beyond_the_week_is_left_alone(self):
        """A draft for one week, not a backlog with a heading."""
        self.task("Much later", due_date=NEXT_SUNDAY + timedelta(days=30))

        self.assertEqual(list(self.draft().proposed), [])

    def test_undated_work_is_not_conscripted(self):
        """The someday pile is not a plan, and pulling from it would be the
        planner deciding something the person did not."""
        self.task("Someday idea", due_date=None)

        self.assertEqual(list(self.draft().proposed), [])

    def test_overdue_comes_before_merely_due(self):
        due = self.task("Send the deposit", due_date=NEXT_MONDAY + timedelta(days=2))
        late = self.task("Chase the invoice", due_date=THIS_MONDAY - timedelta(days=3))

        self.assertEqual(list(self.draft().proposed), [late, due])

    def test_routines_are_named_separately_from_tasks(self):
        """Two different life cycles, kept apart on the page as in the schema.

        A routine is measured toward a quantity over a period and never spawns
        a task; folding it into the same list would be the misuse
        `daily-operating-system-vision.md` names outright.
        """
        from routines.models import Routine

        Routine.objects.create(
            owner=self.alice, title="Five lessons", cadence=Routine.Cadence.DAILY,
            target_quantity=5, unit="lessons",
        )

        self.assertEqual([r.title for r in self.draft().routines], ["Five lessons"])

    # -- whether it fits ---------------------------------------------------

    def test_with_no_history_it_offers_no_capacity(self):
        """None, never a comforting number.

        "No evidence yet" and "you have plenty of room" call for opposite
        responses, which is the same reason `accept_rate` returns None.
        """
        self.task("Chase the invoice", due_date=THIS_MONDAY - timedelta(days=3))

        draft = self.draft()

        self.assertIsNone(draft.typical_week)
        self.assertFalse(draft.over_committed)

    def test_history_gives_a_typical_week(self):
        for week in range(4):
            self.finish_a_week(
                THIS_MONDAY - timedelta(weeks=week + 1), planned=5, met=3
            )

        self.assertEqual(self.draft().typical_week, 3)

    def test_it_says_when_the_week_holds_less_than_this(self):
        for week in range(4):
            self.finish_a_week(
                THIS_MONDAY - timedelta(weeks=week + 1), planned=5, met=3
            )
        for index in range(6):
            self.task(f"Due {index}", due_date=NEXT_MONDAY + timedelta(days=1))

        draft = self.draft()

        self.assertTrue(draft.over_committed)
        self.assertEqual(draft.typical_week, 3)

    def test_a_week_that_fits_is_not_flagged(self):
        for week in range(4):
            self.finish_a_week(
                THIS_MONDAY - timedelta(weeks=week + 1), planned=5, met=3
            )
        self.task("Just one", due_date=NEXT_MONDAY + timedelta(days=1))

        self.assertFalse(self.draft().over_committed)

    def test_a_week_nobody_planned_does_not_count_as_a_zero(self):
        """Null, not zero -- the discipline `review/reads.py` already holds.

        A week with no plan is not a week that finished nothing, and averaging
        it in would drag the typical week toward a number nobody lived.
        """
        self.finish_a_week(THIS_MONDAY - timedelta(weeks=1), planned=4, met=4)
        self.finish_a_week(THIS_MONDAY - timedelta(weeks=3), planned=4, met=4)

        self.assertEqual(self.draft().typical_week, 4)

    # -- ownership and writes ---------------------------------------------

    def test_another_person_s_work_is_never_drafted(self):
        self.task(
            "Theirs", due_date=NEXT_MONDAY + timedelta(days=1), owner=self.other
        )

        self.assertEqual(list(self.draft().proposed), [])

    def test_drafting_writes_nothing(self):
        """A proposal, not a commitment. Nothing is pinned, nothing is dated,
        and opening the planner twice changes nothing either time."""
        from daily.models import DailyFocus

        self.task("Chase the invoice", due_date=THIS_MONDAY - timedelta(days=3))
        before = DailyFocus.objects.count()

        self.draft()

        self.assertEqual(DailyFocus.objects.count(), before)


class TheDraftIsScopedAndStressTestedTest(TestCase):
    """The draft, arranged and questioned — v2 increment 7.

    Three things happen to a proposal here and none of them is a decision.
    Dated work is **arranged onto the day it is already due**, never re-dated;
    each row says whether it serves something the week is *for*, which
    increment 5 made answerable; and each day is measured against what a
    typical day of this person's actually holds, which increment 2 built.

    **Nothing is cut.** Work connected to no chosen outcome is listed and
    marked, because a draft that quietly dropped it would be deciding, and
    `draft_week`'s whole discipline is that it writes nothing and decides
    nothing.
    """

    def setUp(self):
        self.alice = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.project = Project.objects.create(
            owner=self.alice, title="Website launch"
        )
        self.area = List.objects.create(
            owner=self.alice, title="Site", project=self.project
        )
        self.elsewhere = List.objects.create(owner=self.alice, title="Home")

    def task(self, text, due_date, area=None):
        return Item.objects.create(
            owner=self.alice,
            list=area if area is not None else self.area,
            text=text,
            due_date=due_date,
        )

    def draft(self):
        return reads.draft_week(self.alice, NEXT_MONDAY, today=THIS_MONDAY)

    def a_typical_day_of(self, met):
        """Enough planned days behind `today` for a typical-day figure."""
        for offset in range(1, 6):
            day = THIS_MONDAY - timedelta(days=offset)
            for index in range(met + 2):
                task = Item.objects.create(
                    owner=self.alice, list=self.elsewhere, text=f"{day}-{index}"
                )
                daily_services.pin_task(self.alice, day, task)
                if index < met:
                    task.status = Item.Status.COMPLETED
                    task.completed_at = timezone.make_aware(
                        timezone.datetime.combine(
                            day, timezone.datetime.min.time()
                        )
                    ) + timedelta(hours=9)
                    task.save(update_fields=["status", "completed_at"])

    def test_dated_work_is_arranged_onto_the_day_it_is_already_due(self):
        wednesday = NEXT_MONDAY + timedelta(days=2)
        self.task("Write the copy", wednesday)

        days = {each.date: each for each in self.draft().days}

        self.assertEqual([t.text for t in days[wednesday].tasks], ["Write the copy"])

    def test_overdue_work_is_not_given_a_day(self):
        """The line this feature could most easily cross. A draft that placed
        a late task onto Tuesday would be re-dating it, which is the one thing
        `draft_week` promises it never does."""
        self.task("Call the bank", THIS_MONDAY - timedelta(days=3))

        draft = self.draft()

        placed = [t.text for day in draft.days for t in day.tasks]
        self.assertEqual(placed, [])
        self.assertIn("Call the bank", [t.text for t in draft.proposed])

    def test_every_day_of_the_week_is_present_even_when_empty(self):
        """A week is seven days and the empty ones are information: they are
        where anything being moved would go."""
        draft = self.draft()

        self.assertEqual(len(draft.days), 7)
        self.assertEqual(draft.days[0].date, NEXT_MONDAY)

    def test_work_serving_a_chosen_outcome_is_marked(self):
        wednesday = NEXT_MONDAY + timedelta(days=2)
        self.task("Write the copy", wednesday)
        services.choose_outcome(
            self.alice, NEXT_MONDAY, text="The form is live.", project=self.project
        )

        days = {each.date: each for each in self.draft().days}

        self.assertTrue(days[wednesday].tasks[0].serves_an_outcome)

    def test_work_serving_nothing_chosen_is_listed_and_marked(self):
        wednesday = NEXT_MONDAY + timedelta(days=2)
        self.task("Fix the gate", wednesday, area=self.elsewhere)
        services.choose_outcome(
            self.alice, NEXT_MONDAY, text="The form is live.", project=self.project
        )

        days = {each.date: each for each in self.draft().days}

        self.assertEqual([t.text for t in days[wednesday].tasks], ["Fix the gate"])
        self.assertFalse(days[wednesday].tasks[0].serves_an_outcome)

    def test_a_day_holding_more_than_a_typical_one_is_named(self):
        self.a_typical_day_of(2)
        wednesday = NEXT_MONDAY + timedelta(days=2)
        for index in range(4):
            self.task(f"Thing {index}", wednesday)

        days = {each.date: each for each in self.draft().days}

        self.assertTrue(days[wednesday].over_committed)

    def test_a_day_that_fits_is_not_named(self):
        self.a_typical_day_of(4)
        wednesday = NEXT_MONDAY + timedelta(days=2)
        self.task("Write the copy", wednesday)

        days = {each.date: each for each in self.draft().days}

        self.assertFalse(days[wednesday].over_committed)

    def test_with_too_little_history_no_day_is_named(self):
        """Null is not zero. Without a typical day there is nothing to exceed,
        and flagging every day would be a verdict drawn from no evidence."""
        wednesday = NEXT_MONDAY + timedelta(days=2)
        for index in range(9):
            self.task(f"Thing {index}", wednesday)

        draft = self.draft()

        self.assertIsNone(draft.typical_day)
        self.assertFalse(any(day.over_committed for day in draft.days))

    def test_the_typical_day_is_measured_once_for_the_week(self):
        """Seven days do not mean seven measurements. What a typical day holds
        is a fact about the person, not about a date in the future, and asking
        per day would cost thirty queries seven times over on the surface that
        can least afford it."""
        self.a_typical_day_of(3)

        draft = self.draft()

        self.assertEqual(
            draft.typical_day,
            daily_reads.typical_day_for(self.alice, THIS_MONDAY),
        )
