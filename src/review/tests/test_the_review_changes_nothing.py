"""Crane 3 slice 5 — the review proposes; nothing here decides.

**These are regression guards and they passed on their first run**, which
`CLAUDE.md` asks be said out loud rather than presented as new behaviour
proven. Nothing in the review app writes to a task today, and the point of
the guards is that nothing in it ever starts to. Each was made to fail
deliberately once, by having `complete_review` clear a due date, before
being left as it stands.

They exist because this is precisely the surface where the temptation
lives. A weekly review that can see five unfinished commitments is one
small helpful step from rolling them forward, and both
`daily-operating-system-vision.md` ("never automatically reschedule
everything left incomplete") and `principles.md` ("automations propose;
people decide") forbid exactly that step. Slice 5's answer is that acting
on an unfinished commitment goes through the day's own pin service, one
item at a time, from a control a person presses -- so there is no
review-shaped write path for a later convenience to grow out of.
"""
import json
from datetime import date, datetime, timedelta

from django.test import Client, TestCase
from django.utils import timezone

from accounts.models import User
from daily import services as daily_services
from daily.models import DailyFocus
from lists import services as list_services
from lists.models import Item, List


PASSWORD = "correct horse battery staple 47!"

JULY_27 = date(2026, 7, 27)
JULY_29 = date(2026, 7, 29)


class TheReviewDecidesNothingTest(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(
            "alice", "alice@example.com", PASSWORD
        )
        self.alices_list = List.objects.create(owner=self.alice, title="Home")
        self.client = Client()
        self.client.force_login(self.alice)
        self.unfinished = list_services.create_item(
            self.alices_list, "Call the bank", due_date=JULY_29
        )
        daily_services.pin_task(self.alice, JULY_27, self.unfinished)
        self.finished = list_services.create_item(self.alices_list, "Pay rent")
        daily_services.pin_task(self.alice, JULY_27, self.finished)
        list_services.complete_item(self.finished)
        Item.objects.filter(pk=self.finished.pk).update(
            completed_at=timezone.make_aware(
                datetime.combine(JULY_29, datetime.min.time()) + timedelta(hours=9)
            )
        )

    def task_state(self):
        return sorted(
            (
                item.id,
                item.text,
                item.status,
                item.due_date,
                item.list_id,
                item.completed_at,
            )
            for item in Item.objects.filter(list__owner=self.alice)
        )

    def test_reading_and_reviewing_a_week_changes_no_task(self):
        before = self.task_state()

        self.client.get(f"/api/v1/review/{JULY_27}")
        self.client.patch(
            f"/api/v1/review/{JULY_27}",
            data=json.dumps({"plan": "Next week is for the review"}),
            content_type="application/json",
        )
        self.client.post(f"/api/v1/review/{JULY_27}/complete")
        self.client.post(f"/api/v1/review/{JULY_27}/reopen")

        self.assertEqual(self.task_state(), before)

    def test_reviewing_a_week_moves_nothing_onto_another_day(self):
        """The forbidden convenience, stated as a test. An unfinished
        commitment stays where it was chosen until a person moves it."""
        before = set(
            DailyFocus.objects.filter(owner=self.alice).values_list(
                "entry__date", "task_id", "released_at"
            )
        )

        self.client.post(f"/api/v1/review/{JULY_27}/complete")

        self.assertEqual(
            set(
                DailyFocus.objects.filter(owner=self.alice).values_list(
                    "entry__date", "task_id", "released_at"
                )
            ),
            before,
        )

    def test_putting_one_commitment_on_today_moves_only_that_one(self):
        """Acting on the review goes through the day's own endpoint, so the
        service that owns pinning still owns it -- there is no
        review-shaped write path at all, which is what stops a bulk one
        appearing later beside it."""
        today = timezone.localdate()

        response = self.client.post(
            f"/api/v1/day/{today}/focus",
            data=json.dumps({"task_id": self.unfinished.pk}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            sorted(
                DailyFocus.objects.filter(
                    owner=self.alice, entry__date=today
                ).values_list("task_id", flat=True)
            ),
            [self.unfinished.pk],
        )
        # And the task itself is untouched: pinning is a statement about a
        # day, not about the task's own dates or state.
        self.unfinished.refresh_from_db()
        self.assertEqual(self.unfinished.due_date, JULY_29)
        self.assertEqual(self.unfinished.status, Item.Status.ACTIVE)

    def test_the_review_offers_no_endpoint_that_touches_more_than_one_thing(self):
        """A structural guard rather than a behavioural one: the routes
        this app serves are two reads and four writes, and every write
        addresses one week's own record. If a bulk route is ever added this
        fails, which is the point.

        **It fired when S9's write path was added, and the list was widened
        deliberately.** `PUT /weeks/{day}/intention` is the fourth write, and
        it meets this guard's actual criterion rather than being excused from
        it: it addresses one week's own `WeeklyIntention` by the requesting
        owner and the week containing a date, touches no task, and cannot
        name a record belonging to anyone else. The guard is doing its job
        here -- a route arrived and a person had to say why -- which is
        exactly the transaction it exists for.

        Its path is `/weeks/` and not `/review/` on purpose. An intention is
        not part of the review record; writing one must not invent a
        `WeeklyReview`, whose existence is the only evidence of whether
        reviewing is happening at all.

        **It fired again for the planning session**, which added the fifth and
        sixth writes. Both address one week's own `PlanningSession` by owner
        and date, and neither touches a task — the POST records that somebody
        sat down, the PATCH records that they corrected what the system
        believed about the week. Same criterion, same answer, and the guard
        made somebody say so twice rather than letting a route arrive quietly.
        """
        from review.api_v1 import router

        paths = sorted(
            f"{list(operation.methods)[0]} {path}"
            for path, view in router.path_operations.items()
            for operation in view.operations
        )
        self.assertEqual(
            paths,
            [
                "GET /review",
                "GET /review/{day}",
                "PATCH /review/{day}",
                "PATCH /weeks/{day}/planning-session",
                "POST /review/{day}/complete",
                "POST /review/{day}/reopen",
                "POST /weeks/{day}/planning-session",
                "PUT /weeks/{day}/intention",
            ],
        )
