"""Crane 1 slice 5 — the standing question, shown on every day and stored in none.

The Personal Compass is the old paper template's persistent
purpose/guiding-question block: a thing you write once and re-read daily,
not a thing you answer again each morning. `roadmap.md` is explicit that it
stays "separate from daily intentions".

So it is displayed by every day's page and written into none of them. The
acceptance condition is the negative half of that -- edit the Compass and a
day you wrote in July shows the new one, with its own record untouched.

**Where it lives, and why it is not its own model.**
architecture-trajectory.md §4 asks "does this earn a model?" and answers
that a concept earns one when it has a *different life cycle*, not a
different name. A Compass has exactly the User's: one per person, for as
long as the person exists, never created or deleted independently. So it is
two fields, next to `daily_digest`, `time_zone` and `theme`, which are
user-level settings for the same reason.
"""
from datetime import date

from django.test import Client, TestCase

from accounts.models import User
from daily import services
from daily.models import DailyEntry


PASSWORD = "correct horse battery staple 47!"
JULY_30 = date(2026, 7, 30)
PURPOSE = "Build something worth maintaining."
QUESTION = "What is the most I can do?"


class CompassOnTheDayTest(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(
            "alice", "alice@example.com", PASSWORD
        )
        self.bob = User.objects.create_user("bob", "bob@example.com", PASSWORD)
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.alice)

    def day(self, day=JULY_30):
        return self.client.get(f"/api/v1/day/{day.isoformat()}").json()

    def set_compass(self, purpose=PURPOSE, question=QUESTION):
        self.alice.compass_purpose = purpose
        self.alice.compass_question = question
        self.alice.save(update_fields=["compass_purpose", "compass_question"])

    def test_a_day_carries_the_compass(self):
        self.set_compass()

        body = self.day()

        self.assertEqual(body["compass_purpose"], PURPOSE)
        self.assertEqual(body["compass_question"], QUESTION)

    def test_a_day_nobody_has_written_still_carries_it(self):
        """It is not part of the entry, so it does not need one to exist."""
        self.set_compass()

        self.assertEqual(DailyEntry.objects.count(), 0)
        self.assertEqual(self.day()["compass_purpose"], PURPOSE)

    def test_an_unset_compass_is_empty_rather_than_missing(self):
        body = self.day()

        self.assertEqual(body["compass_purpose"], "")
        self.assertEqual(body["compass_question"], "")

    def test_editing_it_changes_a_past_day_without_touching_that_day(self):
        """Slice 5's acceptance condition, both halves.

        The past day shows the new Compass, and nothing was written into
        the record of that day to make that happen.
        """
        services.write_entry(self.alice, JULY_30, intentions="What I meant to do")
        entry = DailyEntry.objects.get()
        written_at = entry.updated_at
        self.set_compass(purpose="An older purpose")
        self.assertEqual(self.day()["compass_purpose"], "An older purpose")

        self.set_compass(purpose="A newer purpose")

        body = self.day()
        self.assertEqual(body["compass_purpose"], "A newer purpose")
        # The day's own record is exactly as it was left.
        entry.refresh_from_db()
        self.assertEqual(entry.intentions, "What I meant to do")
        self.assertEqual(entry.updated_at, written_at)

    def test_the_compass_is_not_stored_on_the_entry(self):
        """Stated as a schema fact rather than inferred from behaviour, so
        that copying it onto the day later is an obvious mistake."""
        self.set_compass()
        services.write_entry(self.alice, JULY_30, intentions="Something")

        entry_fields = {field.name for field in DailyEntry._meta.get_fields()}

        self.assertNotIn("compass_purpose", entry_fields)
        self.assertNotIn("compass_question", entry_fields)

    def test_one_person_never_sees_anothers_compass(self):
        self.bob.compass_purpose = "Bob's private purpose"
        self.bob.save(update_fields=["compass_purpose"])
        self.set_compass(purpose="Alice's purpose")

        self.assertEqual(self.day()["compass_purpose"], "Alice's purpose")
