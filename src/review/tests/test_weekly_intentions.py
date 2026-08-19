"""What a week is for — S9, and increment 6's one prerequisite.

`product-stories.md` S9: *"On Sunday she decides what the week is about. On
Wednesday the day knows."* Planning existed only at day scale, which the story
calls a hole in a product whose pitch is "design the future".

**Its own model, and `WeeklyReview` is why.** That row is keyed identically —
one per owner per week — so a field on it looks like the cheap answer. But
`WeeklyReview`'s *existence* is itself a fact: it has no delete path precisely
so that "I reviewed that week and had little to say" stays distinguishable from
"I never reviewed that week". Writing an intention would create rows for weeks
nobody reviewed, and the model would stop being able to say whether the practice
is happening at all — which is the thing it exists to say.

The life cycles differ too, which is `architecture-trajectory.md` §4's actual
test: an intention is written *before* a week and a review *after* it. One is a
commitment, the other a conclusion.

**Kept in the `review` app** because that app already owns what a week is —
`review/weeks.py` and `week_start_for`. A second home would mean a second
definition of when a week starts, and two answers to that is the drift
`crane-plan.md` §6 warns about.
"""
from datetime import date

from django.test import TestCase

from accounts.models import User
from review import reads, services
from review.models import WeeklyIntention, WeeklyReview

MONDAY = date(2026, 6, 1)
WEDNESDAY = date(2026, 6, 3)
SUNDAY = date(2026, 6, 7)
NEXT_MONDAY = date(2026, 6, 8)


class WeeklyIntentionTest(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.bob = User.objects.create_user(
            "bob", "bob@example.com", "another secure password"
        )

    def test_a_week_starts_with_no_intention(self):
        """A blank page, not a missing one. Nothing to have found, so nothing
        is an error."""
        self.assertIsNone(reads.intention_for(self.alice, MONDAY))

    def test_setting_one_makes_it_readable(self):
        services.set_intention(self.alice, MONDAY, "Get the booking form shipped.")

        found = reads.intention_for(self.alice, MONDAY)
        self.assertEqual(found.text, "Get the booking form shipped.")

    def test_any_day_of_the_week_addresses_the_same_intention(self):
        """S9's whole point: Wednesday knows what Sunday decided.

        Two links to one week must not make two rows -- the same call
        `WeeklyReview` makes, and for the reason `crane-plan.md` §6 gives about
        a second definition of "this week" being wrong in a way nobody sees.
        """
        services.set_intention(self.alice, MONDAY, "Get the booking form shipped.")

        self.assertEqual(
            reads.intention_for(self.alice, WEDNESDAY).text,
            "Get the booking form shipped.",
        )
        self.assertEqual(
            reads.intention_for(self.alice, SUNDAY).text,
            "Get the booking form shipped.",
        )

    def test_a_new_week_has_its_own_intention(self):
        services.set_intention(self.alice, MONDAY, "This week.")

        self.assertIsNone(reads.intention_for(self.alice, NEXT_MONDAY))

    def test_rewriting_it_updates_rather_than_accumulates(self):
        services.set_intention(self.alice, MONDAY, "First thought.")
        services.set_intention(self.alice, WEDNESDAY, "Second thought.")

        self.assertEqual(WeeklyIntention.objects.filter(owner=self.alice).count(), 1)
        self.assertEqual(reads.intention_for(self.alice, MONDAY).text, "Second thought.")

    def test_clearing_it_leaves_the_row(self):
        """"I set no intention this week" and "I never opened it" are different
        facts, and only one of them says the practice lapsed.

        The same call `DailyEntry` and `WeeklyReview` both make, and the reason
        neither has a delete path.
        """
        services.set_intention(self.alice, MONDAY, "Something.")
        services.set_intention(self.alice, MONDAY, "")

        self.assertEqual(reads.intention_for(self.alice, MONDAY).text, "")
        self.assertTrue(WeeklyIntention.objects.filter(owner=self.alice).exists())

    def test_setting_one_does_not_invent_a_review(self):
        """The reason this is not a field on `WeeklyReview`.

        That row's existence means "I reviewed that week". If writing an
        intention created one, the review model could no longer say whether the
        practice was happening -- which is the only thing its row-presence is
        for.
        """
        services.set_intention(self.alice, MONDAY, "Get the booking form shipped.")

        self.assertFalse(WeeklyReview.objects.filter(owner=self.alice).exists())

    def test_one_person_s_intention_is_not_another_s(self):
        services.set_intention(self.bob, MONDAY, "Bob's week.")

        self.assertIsNone(reads.intention_for(self.alice, MONDAY))

    def test_two_people_may_hold_the_same_week(self):
        services.set_intention(self.alice, MONDAY, "Alice's week.")
        services.set_intention(self.bob, MONDAY, "Bob's week.")

        self.assertEqual(reads.intention_for(self.alice, MONDAY).text, "Alice's week.")
        self.assertEqual(reads.intention_for(self.bob, MONDAY).text, "Bob's week.")

    def test_reading_one_writes_nothing(self):
        """`review.reads` must not write, and this is the easiest place to
        forget: a get_or_create here would look like a convenience."""
        reads.intention_for(self.alice, MONDAY)

        self.assertFalse(WeeklyIntention.objects.exists())


class WednesdayKnowsTest(TestCase):
    """S9's sentence, asserted through the surface that has to carry it.

    "On Sunday she decides what the week is about. On Wednesday the day knows."
    The model and the read are only half of that; the claim is about what a day
    shows, and nothing above this reaches the Day page.
    """

    def setUp(self):
        self.alice = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.client.force_login(self.alice)

    def day(self, on):
        return self.client.get(f"/api/v1/day/{on.isoformat()}").json()

    def test_wednesday_shows_what_the_week_is_for(self):
        services.set_intention(self.alice, SUNDAY, "Get the booking form shipped.")

        self.assertEqual(
            self.day(WEDNESDAY)["week_intention"], "Get the booking form shipped."
        )

    def test_a_day_in_another_week_does_not(self):
        services.set_intention(self.alice, MONDAY, "This week only.")

        self.assertEqual(self.day(NEXT_MONDAY)["week_intention"], "")

    def test_a_week_with_no_intention_sends_an_empty_string(self):
        """Never null over the wire, so the client renders text either way and
        has one representation of "nothing set" rather than two."""
        self.assertEqual(self.day(WEDNESDAY)["week_intention"], "")


class SundayDecidesTest(TestCase):
    """The other half of S9's sentence, and the half that was missing.

    Everything above this could be exercised only from a Django shell:
    `services.set_intention` had no caller outside these tests, no endpoint,
    and no form, so *"on Sunday she decides what the week is about"* could not
    happen from any client. `product-stories.md` scored S9 impossible on
    exactly that -- a feature otherwise finished, held up by an absence.

    **Its own path rather than a field on the review's PATCH.** The model is
    deliberately not the review's, and a write addressed to `/review/{day}`
    would put that confusion in the contract -- where the next person to add a
    field has to rediscover why an intention must not create a review row.
    """

    def setUp(self):
        self.alice = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )
        self.bob = User.objects.create_user(
            "bob", "bob@example.com", "another secure password"
        )
        self.client.force_login(self.alice)

    def put(self, on, text):
        return self.client.put(
            f"/api/v1/weeks/{on.isoformat()}/intention",
            data={"text": text},
            content_type="application/json",
        )

    def test_a_person_can_say_what_the_week_is_for(self):
        response = self.put(SUNDAY, "Get the booking form shipped.")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            reads.intention_for(self.alice, SUNDAY).text,
            "Get the booking form shipped.",
        )

    def test_the_response_names_the_week_it_wrote(self):
        """A Sunday addresses the week containing it, and the client is told
        which one rather than resolving a Monday of its own -- the second
        definition of "this week" that `crane-plan.md` §6 warns about."""
        response = self.put(WEDNESDAY, "Ship it.")

        self.assertEqual(
            response.json(), {"week_start": MONDAY.isoformat(), "text": "Ship it."}
        )

    def test_any_day_of_the_week_writes_the_same_intention(self):
        self.put(MONDAY, "First thought.")
        self.put(WEDNESDAY, "Second thought.")

        self.assertEqual(WeeklyIntention.objects.filter(owner=self.alice).count(), 1)
        self.assertEqual(reads.intention_for(self.alice, SUNDAY).text, "Second thought.")

    def test_writing_one_invents_no_review(self):
        """The invariant the model exists for, asserted at the new caller.

        It is already true of the service; a second way in is a second way to
        break it, and this is the one that would be reached by a client.
        """
        self.put(MONDAY, "Get the booking form shipped.")

        self.assertFalse(WeeklyReview.objects.filter(owner=self.alice).exists())

    def test_blank_is_a_value_and_not_a_delete(self):
        """"I set none this week" and "I never opened it" stay different
        facts, which is the same call `DailyEntry` and `WeeklyReview` make."""
        self.put(MONDAY, "Something.")
        self.put(MONDAY, "")

        self.assertEqual(reads.intention_for(self.alice, MONDAY).text, "")

    def test_one_person_cannot_write_another_s_week(self):
        """There is no id to forge -- the record is addressed by (requesting
        user, the week containing day) -- and this proves the path carries no
        way to name someone else's."""
        self.put(MONDAY, "Alice's week.")

        self.assertIsNone(reads.intention_for(self.bob, MONDAY))

    def test_a_stranger_is_refused(self):
        self.client.logout()

        response = self.put(MONDAY, "Not mine.")

        self.assertEqual(response.status_code, 401)
        self.assertFalse(WeeklyIntention.objects.exists())
