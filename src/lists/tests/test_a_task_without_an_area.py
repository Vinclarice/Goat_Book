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
