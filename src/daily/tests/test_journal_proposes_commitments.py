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
