"""What today could hold — the day's own draft.

The weekly loop got fourteen increments of assistant and the daily loop got a
form: `write_entry`, `pin_task`, `unpin_task` and nothing that proposes. Daily
runs seven times as often, so the manual cost was highest exactly where the
automation was absent.

**Not a new planner.** `typical_day_for`'s own docstring settles the shape:
*"D2 is explicit that the daily grain is the same computation as the weekly one
and that two definitions of 'what I got through' would drift."* The selection
is `action_items_for` -- the agenda's own query and bucketing, late then due --
and the capacity is `typical_day_for`. Nothing here counts, buckets or dates
anything of its own.

**It proposes; it never pins.** Vince's call, August 20, 2026, and it is what
`draft_week` already does: *"Writes nothing. A draft is a proposal: nothing is
pinned, nothing is re-dated, and opening the planner twice changes nothing
either time."* The moat is that `DailyFocus` records what a person *chose*, and
a focus pinned by the system would quietly change what the finish rate
measures -- which is not reconstructible afterwards.

**No capacity, no proposal.** `typical_day_for` returns `None` below its
evidence floor rather than zero, because *"no evidence yet"* and *"you have
room"* call for opposite responses. A draft that proposed a number it could not
justify would be the second wearing the first's clothes.

**It does not truncate what has a claim on the day.** The full list is still
the Day page's action items; the draft says how many of them a typical day
holds and which it would choose. Bounding the *proposal* is not hiding the
*work*.
"""

from datetime import date, datetime, timedelta

from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from daily import reads, services
from daily.models import DailyFocus
from lists import services as list_services
from lists.models import Item, List


# A Tuesday, because S3's is.
TUESDAY = date(2026, 8, 4)


class DraftDayTest(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.list_ = List.objects.create(owner=self.alice, title="Home")

    def with_capacity_of(self, finished, *, days=6):
        """Enough planned days before TUESDAY for `typical_day_for` to answer.

        Its floor is five planned days in the previous thirty, and the figure
        is the median finished -- so every day finishes the same number and the
        median is that number, with no arithmetic for this file to get wrong.
        """
        for offset in range(1, days + 1):
            day = TUESDAY - timedelta(days=offset)
            for index in range(finished):
                task = list_services.create_item(self.list_, f"{day} #{index}")
                services.pin_task(self.alice, day, task)
                list_services.complete_item(task)
                Item.objects.filter(pk=task.pk).update(
                    completed_at=timezone.make_aware(
                        datetime.combine(day, datetime.min.time())
                        + timedelta(hours=9)
                    )
                )

    def due(self, text, on=TUESDAY):
        return list_services.create_item(self.list_, text, due_date=on)

    def test_without_enough_history_it_proposes_nothing_rather_than_guessing(self):
        self.due("Pay rent")

        draft = reads.draft_day(self.alice, TUESDAY, today=TUESDAY)

        assert draft.typical is None
        assert draft.proposed == []

    def test_it_proposes_as_many_as_a_typical_day_finishes(self):
        self.with_capacity_of(2)
        self.due("First")
        self.due("Second")
        self.due("Third")

        draft = reads.draft_day(self.alice, TUESDAY, today=TUESDAY)

        assert draft.typical == 2
        assert [task.text for task in draft.proposed] == ["First", "Second"]

    def test_the_late_ones_come_first_because_the_agenda_says_so(self):
        """Borrowed, not re-decided: `action_items_for` is "late, then due",
        and a draft that re-sorted would be a second answer to the same
        question."""
        self.with_capacity_of(1)
        self.due("Due today")
        self.due("Late", on=TUESDAY - timedelta(days=3))

        draft = reads.draft_day(self.alice, TUESDAY, today=TUESDAY)

        assert [task.text for task in draft.proposed] == ["Late"]

    def test_it_says_how_much_has_a_claim_on_the_day_even_when_it_proposes_less(self):
        """Bounding the proposal is not hiding the work. The number is what
        lets the page say "three of nine" rather than quietly showing three."""
        self.with_capacity_of(2)
        for index in range(5):
            self.due(f"Task {index}")

        draft = reads.draft_day(self.alice, TUESDAY, today=TUESDAY)

        assert draft.available == 5
        assert len(draft.proposed) == 2

    def test_what_is_already_pinned_is_not_proposed_again(self):
        self.with_capacity_of(3)
        already = self.due("Already chosen")
        services.pin_task(self.alice, TUESDAY, already)
        self.due("Not yet chosen")

        draft = reads.draft_day(self.alice, TUESDAY, today=TUESDAY)

        assert [task.text for task in draft.proposed] == ["Not yet chosen"]

    def test_a_day_already_at_capacity_is_proposed_nothing_more(self):
        """The half that makes the number mean something. Proposing on top of
        what somebody already chose would make the draft an argument for
        over-committing rather than a check on it."""
        self.with_capacity_of(1)
        already = self.due("Already chosen")
        services.pin_task(self.alice, TUESDAY, already)
        self.due("Not yet chosen")

        draft = reads.draft_day(self.alice, TUESDAY, today=TUESDAY)

        assert draft.proposed == []

    def test_drafting_writes_nothing(self):
        """`draft_week`'s own rule: opening the planner twice changes nothing
        either time. The moat is that DailyFocus records what a person chose."""
        self.with_capacity_of(2)
        self.due("Pay rent")

        reads.draft_day(self.alice, TUESDAY, today=TUESDAY)
        reads.draft_day(self.alice, TUESDAY, today=TUESDAY)

        assert DailyFocus.objects.filter(entry__date=TUESDAY).count() == 0

    def test_a_day_that_has_been_lived_is_not_drafted(self):
        """Absent on a past day, the same refusal `typical_day_for` makes:
        proposing what somebody should have done is a verdict, not a plan."""
        self.with_capacity_of(2)
        self.due("Pay rent")

        draft = reads.draft_day(
            self.alice, TUESDAY, today=TUESDAY + timedelta(days=1)
        )

        assert draft.proposed == []
