"""The pool -- every open line the owner has, in one list.

`superlists-2.0-plan.md` increment 1, and its rule 1: *every open line the
owner has, in one list, with no Area. Two kinds of line: **floating**, which
has no date and cannot be overdue because nothing was promised, and **fixed**,
which has a due date. Age is shown as a fact -- added 40 days ago -- never as
debt.*
"""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from lists import agenda
from daily import services as daily_services
from lists.models import Item, List
from money.models import Bill, Direction


def backdate(item, days):
    """`created_at` is `auto_now_add`, so age has to be written after the fact."""
    stamp = timezone.now() - timedelta(days=days)
    Item.objects.filter(pk=item.pk).update(created_at=stamp)
    item.refresh_from_db()
    return item


class PoolReadTest(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.today = timezone.localdate()

    def pool(self, **kwargs):
        return agenda.pool_for(self.owner, self.today, **kwargs)

    def test_holds_a_filed_line_and_an_unfiled_one_alike(self):
        area = List.objects.create(owner=self.owner, title="Programming")
        Item.objects.create(list=area, text="Ship the migration")
        Item.objects.create(owner=self.owner, text="Book dentist")

        texts = [row["task"]["text"] for row in self.pool()["floating"]]

        self.assertCountEqual(texts, ["Ship the migration", "Book dentist"])

    def test_a_dated_line_is_fixed_and_an_undated_one_floats(self):
        Item.objects.create(
            owner=self.owner, text="Send Sam the export", due_date=self.today
        )
        Item.objects.create(owner=self.owner, text="Book dentist")

        pool = self.pool()

        self.assertEqual(
            [row["task"]["text"] for row in pool["fixed"]], ["Send Sam the export"]
        )
        self.assertEqual(
            [row["task"]["text"] for row in pool["floating"]], ["Book dentist"]
        )

    def test_bills_interleave_with_dated_tasks_by_date(self):
        Item.objects.create(
            owner=self.owner,
            text="Send Sam the export",
            due_date=self.today + timedelta(days=2),
        )
        Bill.objects.create(
            owner=self.owner, payee="Rent", due_date=self.today + timedelta(days=1)
        )
        Bill.objects.create(
            owner=self.owner,
            payee="Car insurance",
            due_date=self.today + timedelta(days=5),
        )

        fixed = self.pool()["fixed"]

        self.assertEqual(
            [
                (
                    row["kind"],
                    row["task"]["text"] if row["task"] else row["bill"]["payee"],
                )
                for row in fixed
            ],
            [
                ("bill", "Rent"),
                ("task", "Send Sam the export"),
                ("bill", "Car insurance"),
            ],
        )

    def test_a_fixed_line_says_how_many_days_until_it_is_due(self):
        Item.objects.create(
            owner=self.owner, text="Late one", due_date=self.today - timedelta(days=3)
        )
        Item.objects.create(
            owner=self.owner, text="Soon one", due_date=self.today + timedelta(days=2)
        )

        fixed = self.pool()["fixed"]

        self.assertEqual([row["days_until"] for row in fixed], [-3, 2])

    def test_floating_lines_are_oldest_first_and_carry_their_age(self):
        backdate(Item.objects.create(owner=self.owner, text="Middling"), 9)
        backdate(Item.objects.create(owner=self.owner, text="Oldest"), 24)
        Item.objects.create(owner=self.owner, text="Newest")

        floating = self.pool()["floating"]

        self.assertEqual(
            [(row["task"]["text"], row["age_in_days"]) for row in floating],
            [("Oldest", 24), ("Middling", 9), ("Newest", 0)],
        )

    def test_leaves_out_a_completed_or_archived_line(self):
        # The timestamps are not decoration: `valid_item_status_timestamps`
        # refuses a completed row with no `completed_at`.
        Item.objects.create(
            owner=self.owner,
            text="Done",
            status=Item.Status.COMPLETED,
            completed_at=timezone.now(),
        )
        Item.objects.create(
            owner=self.owner,
            text="Gone",
            status=Item.Status.ARCHIVED,
            archived_at=timezone.now(),
        )
        Item.objects.create(owner=self.owner, text="Open")

        pool = self.pool()

        self.assertEqual([row["task"]["text"] for row in pool["floating"]], ["Open"])
        self.assertEqual(pool["open_count"], 1)

    def test_leaves_out_a_paid_bill_and_money_coming_in(self):
        Bill.objects.create(
            owner=self.owner,
            payee="Rent",
            due_date=self.today,
            paid_at=timezone.now(),
            paid_amount=10,
        )
        Bill.objects.create(
            owner=self.owner,
            payee="Salary",
            due_date=self.today,
            direction=Direction.IN,
        )
        Bill.objects.create(owner=self.owner, payee="Electricity", due_date=self.today)

        fixed = self.pool()["fixed"]

        self.assertEqual([row["bill"]["payee"] for row in fixed], ["Electricity"])

    def test_holds_only_this_owners_lines(self):
        intruder = User.objects.create_user(
            "mallory", "mallory@example.com", "another secure password"
        )
        Item.objects.create(owner=intruder, text="Not mine")
        Bill.objects.create(owner=intruder, payee="Not my rent", due_date=self.today)
        Item.objects.create(owner=self.owner, text="Mine")

        pool = self.pool()

        self.assertEqual([row["task"]["text"] for row in pool["floating"]], ["Mine"])
        self.assertEqual(pool["fixed"], [])
        self.assertEqual(pool["open_count"], 1)

    def test_search_narrows_both_halves_and_keeps_the_pools_order(self):
        backdate(Item.objects.create(owner=self.owner, text="Fence latch"), 3)
        backdate(
            Item.objects.create(owner=self.owner, text="Ring the fencing people"), 30
        )
        Item.objects.create(owner=self.owner, text="Book dentist")
        Bill.objects.create(owner=self.owner, payee="Fence panels", due_date=self.today)
        Bill.objects.create(owner=self.owner, payee="Rent", due_date=self.today)

        pool = self.pool(query="fenc")

        self.assertEqual([row["bill"]["payee"] for row in pool["fixed"]], ["Fence panels"])
        self.assertEqual(
            [row["task"]["text"] for row in pool["floating"]],
            ["Ring the fencing people", "Fence latch"],
        )

    def test_the_open_count_is_the_whole_pool_not_the_search(self):
        Item.objects.create(owner=self.owner, text="Book dentist")
        Item.objects.create(owner=self.owner, text="Fence latch")
        Bill.objects.create(owner=self.owner, payee="Rent", due_date=self.today)

        self.assertEqual(self.pool(query="fenc")["open_count"], 3)

    def test_a_search_matching_nothing_is_an_empty_pool_not_the_whole_one(self):
        Item.objects.create(owner=self.owner, text="Book dentist")

        pool = self.pool(query="zzz")

        self.assertEqual(pool["fixed"], [])
        self.assertEqual(pool["floating"], [])


class PoolEndpointTest(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.today = timezone.localdate()

    def test_rejects_anonymous_requests(self):
        self.assertEqual(self.client.get("/api/v1/pool").status_code, 401)

    def test_serves_the_owners_pool(self):
        Item.objects.create(owner=self.owner, text="Book dentist")
        Bill.objects.create(owner=self.owner, payee="Rent", due_date=self.today)
        self.client.force_login(self.owner)

        response = self.client.get("/api/v1/pool")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["today"], self.today.isoformat())
        self.assertEqual(payload["open_count"], 2)
        self.assertEqual(payload["fixed"][0]["bill"]["payee"], "Rent")
        self.assertEqual(payload["floating"][0]["task"]["text"], "Book dentist")
        self.assertEqual(payload["floating"][0]["age_in_days"], 0)

    def test_narrows_to_a_search(self):
        Item.objects.create(owner=self.owner, text="Book dentist")
        Item.objects.create(owner=self.owner, text="Fence latch")
        self.client.force_login(self.owner)

        payload = self.client.get("/api/v1/pool?q=fenc").json()

        self.assertEqual(
            [row["task"]["text"] for row in payload["floating"]], ["Fence latch"]
        )
        self.assertEqual(payload["open_count"], 2)

    def test_does_not_leak_another_owners_pool(self):
        intruder = User.objects.create_user(
            "mallory", "mallory@example.com", "another secure password"
        )
        Item.objects.create(owner=intruder, text="Not mine")
        self.client.force_login(self.owner)

        payload = self.client.get("/api/v1/pool").json()

        self.assertEqual(payload["floating"], [])
        self.assertEqual(payload["open_count"], 0)


class WhatIsAlreadyPickedTest(TestCase):
    """A pool row says whether it has already been chosen, and for which day.

    `superlists-2.0-plan.md` increment 2: the pool is where tomorrow's list is
    made and where a line joins today below the line. Without this the button
    is one that appears to do nothing -- and picking twice is idempotent on the
    server, so nothing would ever say otherwise.

    Today and tomorrow only, because those are the two days the page offers.
    """

    def setUp(self):
        self.owner = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.today = timezone.localdate()
        self.tomorrow = self.today + timedelta(days=1)

    def rows(self):
        pool = agenda.pool_for(self.owner, self.today)
        return {row["task"]["text"]: row["picked_for"] for row in pool["floating"]}

    def test_an_unpicked_line_is_picked_for_nothing(self):
        Item.objects.create(owner=self.owner, text="Book dentist")

        self.assertEqual(self.rows()["Book dentist"], [])

    def test_a_line_picked_for_today_says_so(self):
        task = Item.objects.create(owner=self.owner, text="Book dentist")
        daily_services.pin_task(self.owner, self.today, task)

        self.assertEqual(self.rows()["Book dentist"], [self.today.isoformat()])

    def test_a_line_picked_for_tomorrow_says_so(self):
        task = Item.objects.create(owner=self.owner, text="Book dentist")
        daily_services.pin_task(self.owner, self.tomorrow, task)

        self.assertEqual(self.rows()["Book dentist"], [self.tomorrow.isoformat()])

    def test_a_released_pin_is_not_a_pick(self):
        task = Item.objects.create(owner=self.owner, text="Book dentist")
        daily_services.pin_task(self.owner, self.today, task)
        daily_services.unpin_task(self.owner, self.today, task)

        self.assertEqual(self.rows()["Book dentist"], [])

    def test_a_pick_on_a_day_the_page_does_not_offer_is_not_reported(self):
        """Yesterday's pin is history, not a state of the line today."""
        task = Item.objects.create(owner=self.owner, text="Book dentist")
        daily_services.pin_task(self.owner, self.today - timedelta(days=1), task)

        self.assertEqual(self.rows()["Book dentist"], [])

    def test_a_fixed_line_carries_it_too(self):
        task = Item.objects.create(
            owner=self.owner, text="Send Sam the export", due_date=self.today
        )
        daily_services.pin_task(self.owner, self.today, task)

        fixed = agenda.pool_for(self.owner, self.today)["fixed"]

        self.assertEqual(fixed[0]["picked_for"], [self.today.isoformat()])

    def test_a_bill_is_picked_for_nothing_because_it_cannot_be_picked(self):
        """A bill is not an `Item`, so `DailyFocus` cannot point at one. The
        field is empty rather than absent, so the client reads one shape.
        """
        Bill.objects.create(owner=self.owner, payee="Rent", due_date=self.today)

        fixed = agenda.pool_for(self.owner, self.today)["fixed"]

        self.assertEqual(fixed[0]["picked_for"], [])


class TheHeadOfThePoolTest(TestCase):
    """The panel beside the day -- the same rows, narrowed to a column.

    `superlists-2.0-plan.md`: *the pool is a panel **and** a page. Both read the
    same query, so neither is a copy of the other.*
    """

    def setUp(self):
        self.owner = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.today = timezone.localdate()

    def head(self):
        return agenda.pool_for(self.owner, self.today, head=True)

    def test_fixed_lines_stop_at_the_week(self):
        Item.objects.create(
            owner=self.owner, text="This week", due_date=self.today + timedelta(days=3)
        )
        Item.objects.create(
            owner=self.owner, text="Next month", due_date=self.today + timedelta(days=40)
        )

        self.assertEqual(
            [row["task"]["text"] for row in self.head()["fixed"]], ["This week"]
        )

    def test_an_overdue_line_is_still_in_the_head(self):
        """More urgent than next Tuesday, not less."""
        Item.objects.create(
            owner=self.owner, text="Late", due_date=self.today - timedelta(days=9)
        )

        self.assertEqual([row["task"]["text"] for row in self.head()["fixed"]], ["Late"])

    def test_the_oldest_few_floating_lines_and_nothing_after_them(self):
        for age in range(agenda.POOL_HEAD_FLOATING + 3):
            backdate(
                Item.objects.create(owner=self.owner, text=f"Line {age}"), age + 1
            )

        self.assertEqual(
            len(self.head()["floating"]), agenda.POOL_HEAD_FLOATING
        )

    def test_what_arrived_today_is_in_the_head_however_deep_it_falls(self):
        """A panel that showed only the oldest would never show the thing
        somebody wrote ten minutes ago, which is the one they are looking for.
        """
        for age in range(agenda.POOL_HEAD_FLOATING + 3):
            backdate(
                Item.objects.create(owner=self.owner, text=f"Line {age}"), age + 1
            )
        Item.objects.create(owner=self.owner, text="Just now")

        self.assertIn(
            "Just now", [row["task"]["text"] for row in self.head()["floating"]]
        )

    def test_the_count_is_still_the_whole_pool(self):
        """Which is what lets the link beside the panel say how many there
        really are.
        """
        for age in range(agenda.POOL_HEAD_FLOATING + 3):
            backdate(
                Item.objects.create(owner=self.owner, text=f"Line {age}"), age + 1
            )

        self.assertEqual(self.head()["open_count"], agenda.POOL_HEAD_FLOATING + 3)

    def test_the_page_is_not_narrowed(self):
        for age in range(agenda.POOL_HEAD_FLOATING + 3):
            backdate(
                Item.objects.create(owner=self.owner, text=f"Line {age}"), age + 1
            )

        whole = agenda.pool_for(self.owner, self.today)

        self.assertEqual(len(whole["floating"]), agenda.POOL_HEAD_FLOATING + 3)

    def test_the_endpoint_takes_it(self):
        Item.objects.create(
            owner=self.owner, text="Next month", due_date=self.today + timedelta(days=40)
        )
        self.client.force_login(self.owner)

        payload = self.client.get("/api/v1/pool?head=true").json()

        self.assertEqual(payload["fixed"], [])
        self.assertEqual(payload["open_count"], 1)

