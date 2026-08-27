"""The review stopped asking what next week is for. The intention asks it.

**`planning-assistant-v2-plan.md` D7, answered August 26, 2026: collapse to the
intention.** The review page carried two free-text boxes about the coming week a
few hundred pixels apart -- *"What is next week for?"*, which writes a
`WeeklyIntention`, and *"Next week"*, which wrote `WeeklyReview.plan`. The plan's
own test decided it: **if the distinction cannot be written on the page in a
sentence, there is one field here and not two**, and nobody wrote the sentence in
the six days both boxes were on screen.

**The intention won because it is the one with a life cycle.** The Day page reads
it through the week; nothing read `plan` but the form that wrote it.

**What is retired is the write path, and only the write path.** The column stays
and so does the read: *what I said on that Sunday* is history, and
`architecture-trajectory.md` §4 rule 6 keeps a row whose existence answers
whether something happened. **Removing the read would have made every plan ever
written invisible**, which is not what collapsing two controls into one is
supposed to cost -- so an existing plan still renders, and renders read-only.

**This file is the guard on that pair of claims**, because they pull in opposite
directions and a later tidy-up could satisfy either one alone: no new plans, and
no lost ones.
"""
from datetime import date

from django.test import Client, TestCase

from accounts.models import User
from review.models import WeeklyReview

PASSWORD = "correct horse battery staple 47!"
JULY_27 = date(2026, 7, 27)


class ThePlanFieldIsRetiredTest(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(
            username="alice", email="alice@example.com", password=PASSWORD
        )
        self.client = Client()
        self.client.force_login(self.alice)

    def patch(self, payload, week=JULY_27):
        return self.client.patch(
            f"/api/v1/review/{week}",
            data=payload,
            content_type="application/json",
        )

    def test_the_endpoint_will_not_write_a_plan(self):
        """The retirement, stated as the thing a client can no longer do.

        Asserted through the API rather than by checking the schema object,
        because the schema is a means: what matters is that a request carrying
        a plan does not result in one being stored.
        """
        self.patch({"reflections": "Quieter than last week", "plan": "Two mornings"})

        review = WeeklyReview.objects.get(owner=self.alice, week_start=JULY_27)
        self.assertEqual(review.reflections, "Quieter than last week")
        self.assertEqual(
            review.plan,
            "",
            "A plan reached the database through the review endpoint. The "
            "field is retired: `WeeklyIntention` is where 'what next week is "
            "for' lives, and two records answering one question is the drift "
            "architecture-trajectory.md §4 exists to prevent.",
        )

    def test_a_plan_already_written_is_still_returned(self):
        """The other half, and the one a tidy-up is most likely to break.

        Nothing writes this column any more, so it looks unused -- and it is
        not. Rows written before August 26, 2026 hold a person's own sentence
        about a week, and the read is the only thing keeping them reachable.
        """
        WeeklyReview.objects.create(
            owner=self.alice, week_start=JULY_27, plan="Two mornings on the review"
        )

        payload = self.client.get(f"/api/v1/review/{JULY_27}").json()

        self.assertEqual(
            payload["review"]["plan"],
            "Two mornings on the review",
            "A plan written before the field was retired is no longer "
            "readable. Retiring the write path was not supposed to cost the "
            "history -- see this module's docstring.",
        )

    def test_saving_a_review_does_not_blank_an_existing_plan(self):
        """The partial-write contract, which now has to hold in one direction
        only. A page that saves reflections must not quietly erase a sentence
        somebody wrote in August and can no longer rewrite."""
        WeeklyReview.objects.create(
            owner=self.alice, week_start=JULY_27, plan="Two mornings on the review"
        )

        self.patch({"reflections": "Quieter than last week"})

        review = WeeklyReview.objects.get(owner=self.alice, week_start=JULY_27)
        self.assertEqual(review.plan, "Two mornings on the review")
