"""A task that belongs to a person rather than to a list.

`Item.list` became nullable on August 14, 2026 for the three reasons recorded on
the field itself. That was half the change and the visible half; this is the
half that makes it usable. Ownership ran through the Area
(`Item.objects.filter(list__owner=user)`) at roughly twenty call sites, so a
task with no Area had no owner and was returned by no query anybody makes -- a
row that exists, belongs to nobody, and is never seen again.

So `Item.owner` is the actual "a task can stand on its own": every task names
its owner directly, an Area is one more thing a task may have, and the filing
question stops being the price of admission.

`owner` is required. Nullable ownership would just move the orphan one field
along, and the whole point is that there is nowhere for a task to fall out of.
"""

import datetime

from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError
from django.test import TestCase

from accounts.models import User
from lists import services
from lists.models import Item, List


class TaskWithoutAnAreaTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("alice", "a@example.com", "pw")
        self.other = User.objects.create_user("bob", "b@example.com", "pw")
        self.area = List.objects.create(owner=self.user, title="Home")

    def test_a_task_can_be_created_with_no_area_at_all(self):
        task = services.create_item(None, "Dentist on the 24th", owner=self.user)

        assert task.list is None
        assert task.owner == self.user

    def test_its_owner_can_still_find_it(self):
        """The defect this field exists to prevent. Before it, the task above was
        a row nothing returned -- not lost exactly, but unreachable, which for
        somebody who wrote down an appointment is the same thing."""
        services.create_item(None, "Dentist on the 24th", owner=self.user)

        assert Item.objects.filter(owner=self.user).count() == 1

    def test_and_nobody_else_can(self):
        services.create_item(None, "Dentist on the 24th", owner=self.user)

        assert Item.objects.filter(owner=self.other).count() == 0

    def test_a_task_filed_in_an_area_takes_that_areas_owner(self):
        """Callers that pass an Area keep working unchanged -- that is what makes
        this a widening rather than a migration of every call site."""
        task = services.create_item(self.area, "Wash the car")

        assert task.owner == self.user

    def test_an_area_cannot_hold_somebody_elses_task(self):
        """Two ways to know who owns a task is two ways to disagree, so the Area
        simply wins and `owner` is derived from it.

        Written first as "the database refuses this", which it cannot: saying so
        needs a composite foreign key on `(list_id, owner_id)` and Django has no
        such field. Derivation gets the guarantee that actually matters -- a
        mismatch is unreachable rather than rejected -- and a trigger for a
        field one `save()` already keeps correct is more machinery than the risk
        earns.
        """
        task = Item.objects.create(list=self.area, owner=self.other, text="Theirs")

        task.refresh_from_db()
        assert task.owner == self.user

    def test_moving_a_task_to_another_persons_area_moves_its_ownership_too(self):
        """The drift `save()` exists to prevent: a stale `owner` would leave the
        task in one person's queries and another person's Area at once."""
        task = services.create_item(None, "Fix the tap", owner=self.user)
        theirs = List.objects.create(owner=self.other, title="Theirs")

        task.list = theirs
        task.save(update_fields=["list"])

        task.refresh_from_db()
        assert task.owner == self.other

    def test_a_task_must_have_an_owner(self):
        with self.assertRaises(IntegrityError):
            Item.objects.create(list=None, owner=None, text="Nobody's")

    def test_two_arealess_tasks_with_the_same_words_are_refused(self):
        """Duplicate protection followed the Area, so with no Area there was none:
        a phone retrying a share wrote the note twice. Ownership restores it."""
        services.create_item(None, "Dentist on the 24th", owner=self.user)

        with self.assertRaises(services.TaskConflict):
            services.create_item(None, "Dentist on the 24th", owner=self.user)

    def test_but_two_people_may_each_have_the_same_arealess_task(self):
        services.create_item(None, "Buy milk", owner=self.user)
        services.create_item(None, "Buy milk", owner=self.other)

        assert Item.objects.count() == 2

    def test_the_same_words_in_an_area_and_outside_one_do_not_collide(self):
        """Different places, so not the same task. Filing one copy is a decision
        somebody made; it should not silently block the other."""
        services.create_item(self.area, "Buy milk")
        services.create_item(None, "Buy milk", owner=self.user)

        assert Item.objects.count() == 2

    def test_a_repeating_task_with_no_area_still_gets_its_series(self):
        """`_anchor_commitment` read the owner off the Area, so a repeating
        commitment with no Area raised rather than repeating."""
        task = services.create_item(
            None, "Change the furnace filter", owner=self.user,
            recurrence=Item.Recurrence.MONTHLY,
        )

        assert task.commitment is not None
        assert task.commitment.owner == self.user


class UnfiledSeriesContinuesTest(TestCase):
    """The second occurrence, which is where an unfiled series actually breaks.

    `_spawn_next_occurrence` builds the next task with `list=commitment.list`
    and no owner, relying on `Item.save()` deriving one from the Area. A
    commitment with no Area has nothing to derive from, so the insert violated
    NOT NULL and completing the task raised.

    Found from a real one: "change the office furnace filter on the 10th of
    each month", accepted from a capture on August 15, 2026 with no Area. It
    was created fine, listed fine, and would have failed the first time it was
    ticked off -- a month later, with nothing linking the error to the day the
    task was made.
    """

    def setUp(self):
        self.user = User.objects.create_user("alice", "a@example.com", "pw")

    def test_completing_an_unfiled_repeating_task_spawns_the_next_one(self):
        task = services.create_item(
            None, "Change the furnace filter", owner=self.user,
            recurrence=Item.Recurrence.MONTHLY, due_date=datetime.date(2026, 9, 10),
        )

        services.complete_item(task)

        following = Item.objects.filter(status=Item.Status.ACTIVE).get()
        assert following.text == "Change the furnace filter"
        assert following.due_date == datetime.date(2026, 10, 10)

    def test_the_next_occurrence_belongs_to_the_same_person(self):
        """The failure itself: no Area to inherit an owner from, so it has to
        come from the series. An occurrence owned by nobody is a row its own
        owner cannot see."""
        task = services.create_item(
            None, "Change the furnace filter", owner=self.user,
            recurrence=Item.Recurrence.MONTHLY, due_date=datetime.date(2026, 9, 10),
        )

        services.complete_item(task)

        assert Item.objects.filter(status=Item.Status.ACTIVE).get().owner == self.user

    def test_it_stays_unfiled_rather_than_acquiring_an_area(self):
        task = services.create_item(
            None, "Change the furnace filter", owner=self.user,
            recurrence=Item.Recurrence.MONTHLY, due_date=datetime.date(2026, 9, 10),
        )

        services.complete_item(task)

        assert Item.objects.filter(status=Item.Status.ACTIVE).get().list is None


class UnfiledChecklistStepPromotesTest(TestCase):
    """The same shape as the series bug, one function along.

    `promote_step` reads `step.task.list` and creates the new task from it,
    again relying on `Item.save()` to derive an owner from the Area. Found by
    grepping every `Item.objects.create` in the non-test tree after the series
    bug, rather than by tripping over it next -- the two are one mistake made
    twice, and the second was worth finding without a person hitting it.
    """

    def setUp(self):
        self.user = User.objects.create_user("alice", "a@example.com", "pw")
        self.task = services.create_item(None, "Plan the trip", owner=self.user)

    def test_a_step_on_an_unfiled_task_can_become_a_task(self):
        step = services.add_checklist_step(self.task, "Book the ferry")

        promoted = services.promote_checklist_step(step)

        assert promoted.owner == self.user
        assert promoted.list is None

    def test_the_promoted_task_is_visible_to_its_owner(self):
        step = services.add_checklist_step(self.task, "Book the ferry")

        services.promote_checklist_step(step)

        assert Item.objects.filter(owner=self.user, text="Book the ferry").exists()

    def test_it_still_refuses_a_duplicate_among_unfiled_tasks(self):
        """Dedup followed the Area too, so with no Area there was none -- the
        same gap `_duplicate_exists` already had for `create_item`."""
        services.create_item(None, "Book the ferry", owner=self.user)
        step = services.add_checklist_step(self.task, "Book the ferry")

        with self.assertRaises(services.TaskConflict):
            services.promote_checklist_step(step)
