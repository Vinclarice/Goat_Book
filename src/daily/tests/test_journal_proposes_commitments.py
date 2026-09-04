"""Writing in the journal offers the commitments it reads — increment 2, slice B.

The producer is the knowledge core's (`mind.services.propose_journal_commitments`);
this is only about it being *invoked*, which is the half that has gone missing
before. `run_detectors` was written, green and uninvoked for weeks, and the
lesson recorded twice in `CLAUDE.md` is that a seam nothing calls is not a seam.

**On save, deliberately.** The parser is a regex over a few sentences — no
model, no network, no per-call cost — which is the same argument that lets
capture propose on its live path. So the suggestion is ready when the page comes
back, and nothing was asked at the moment of writing.
"""
from datetime import date

from django.test import TestCase

from accounts.models import User
from daily import services
from mind.models import Facet, FacetKind

AUGUST_3 = date(2026, 8, 3)


class WritingProposesCommitmentsTest(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )

    def commitments(self, entry):
        return list(Facet.objects.filter(entry=entry, kind=FacetKind.ACTIONABLE))

    def test_writing_a_promise_offers_it(self):
        entry = services.write_entry(
            self.alice,
            AUGUST_3,
            happenings="I still need to ask Maya about the venue.",
        )

        self.assertEqual(len(self.commitments(entry)), 1)

    def test_writing_ordinary_prose_offers_nothing(self):
        entry = services.write_entry(
            self.alice, AUGUST_3, happenings="A good day. Nothing else today."
        )

        self.assertEqual(self.commitments(entry), [])

    def test_saving_again_does_not_duplicate_the_offer(self):
        """A day is saved on every pause in typing.

        Without idempotence the surface would carry a dozen copies of one
        sentence by lunchtime, which is the failure that makes a suggestion
        panel worth ignoring.
        """
        services.write_entry(
            self.alice, AUGUST_3, happenings="I must call the bank."
        )
        entry = services.write_entry(
            self.alice,
            AUGUST_3,
            happenings="I must call the bank. Also it rained.",
        )

        self.assertEqual(len(self.commitments(entry)), 1)

    def test_a_write_that_mentions_no_field_proposes_nothing_new(self):
        """Pinning a task saves the row without touching the writing.

        `write_entry` is also how an entry comes into existence for a pin, and
        re-reading unchanged prose on every such call would be work nobody
        asked for -- harmless because of the fingerprint, but pointless, and
        the kind of pointless that shows up in a query count later.
        """
        services.write_entry(
            self.alice, AUGUST_3, happenings="I must call the bank."
        )

        entry = services.write_entry(self.alice, AUGUST_3)

        self.assertEqual(len(self.commitments(entry)), 1)

    def test_the_proposal_belongs_to_the_person_who_wrote_it(self):
        entry = services.write_entry(
            self.alice, AUGUST_3, happenings="I need to post the form."
        )

        self.assertEqual(self.commitments(entry)[0].owner, self.alice)


class ItReadsWhatHappenedAndNothingElseTest(TestCase):
    """**D5, answered.** `superlists-2.0-plan.md` increment 9.

    *With the log carrying what happened line by line, `happenings` is either
    retired or kept as end-of-day reflection. Kept, and the journal producer
    reads it alone, so the two commitment producers keep two signals as
    `Facet.producer`'s own comment intends.*

    The three fields say different things. `intentions` is a plan for the day,
    and the morning pick is what makes a plan real -- reading commitments out
    of it would propose a task for something already chosen, or for something
    deliberately not. `gratitude` is not about undertakings at all. What is
    left is the field that records what actually happened, which is where a
    promise made in passing turns up.
    """

    def setUp(self):
        self.alice = User.objects.create_user(
            "alice", "alice@example.com", "a secure password"
        )

    def commitments(self):
        return Facet.objects.filter(kind=FacetKind.ACTIONABLE)

    def test_a_promise_in_what_happened_is_offered(self):
        services.write_entry(
            self.alice, AUGUST_3, happenings="I still need to ask Maya about the venue."
        )

        self.assertEqual(self.commitments().count(), 1)

    def test_a_promise_in_the_intentions_is_not(self):
        services.write_entry(
            self.alice, AUGUST_3, intentions="I still need to ask Maya about the venue."
        )

        self.assertEqual(self.commitments().count(), 0)

    def test_a_promise_in_the_gratitude_is_not(self):
        services.write_entry(
            self.alice, AUGUST_3, gratitude="I still need to ask Maya about the venue."
        )

        self.assertEqual(self.commitments().count(), 0)

    def test_the_quote_still_points_at_the_words_that_caused_it(self):
        """The alignment contract, which is the reason this narrows by *span*
        rather than by reading a different string. `entry_body` stays the one
        definition offsets index into -- a producer reading `happenings` alone
        would have shifted every existing facet's quote by the length of
        whatever was above it, and it would have looked like a parser bug.
        """
        entry = services.write_entry(
            self.alice,
            AUGUST_3,
            intentions="Ship the slice.",
            gratitude="Rain.",
            happenings="I still need to ask Maya about the venue.",
        )

        facet = self.commitments().get()
        self.assertEqual(facet.cited_text, "I still need to ask Maya about the venue.")
        self.assertEqual(entry.happenings, "I still need to ask Maya about the venue.")

