"""Finding a day by what was written in it.

Slice 1 of `design/search-plan.md`, and the half the trigger actually fired on:
daily entries are already written, already numerous, and reachable only by
knowing the date. There is no date picker either, so a journal entry from three
weeks ago is, in practice, gone.

All three fields are indexed as peers. `intentions`, `gratitude` and
`happenings` are what one person wrote about one day and no one of them is the
day's title -- unlike a task, which has a name and a body. So no weights here,
where `Item` has them.
"""

import datetime

from django.contrib.postgres.search import SearchQuery
from django.test import TestCase

from accounts.models import User
from daily import reads
from daily.models import DailyEntry


def q(text):
    return SearchQuery(text, config="english")


class DailyEntrySearchIndexTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("alice", "a@example.com", "pw")
        self.other = User.objects.create_user("bob", "b@example.com", "pw")
        self.date = datetime.date(2026, 8, 20)

    def entry(self, owner=None, date=None, **fields):
        return DailyEntry.objects.create(
            owner=owner or self.user, date=date or self.date, **fields
        )

    def test_a_day_is_found_by_a_word_in_its_happenings(self):
        self.entry(happenings="Walked the coast path to Porthcurno")

        found = DailyEntry.objects.filter(owner=self.user, search_document=q("coast"))

        assert [e.date for e in found] == [self.date]

    def test_all_three_fields_are_searched(self):
        """Three separate one-field indexes would mean three searches and a
        merge, and a person does not know which box they typed it in."""
        self.entry(date=datetime.date(2026, 8, 1), intentions="Finish the restore drill")
        self.entry(date=datetime.date(2026, 8, 2), gratitude="Quiet morning, no alerts")
        self.entry(date=datetime.date(2026, 8, 3), happenings="Deployed the mail fix")

        assert DailyEntry.objects.filter(owner=self.user, search_document=q("drill")).count() == 1
        assert DailyEntry.objects.filter(owner=self.user, search_document=q("alerts")).count() == 1
        assert DailyEntry.objects.filter(owner=self.user, search_document=q("deployed")).count() == 1

    def test_the_index_stems(self):
        self.entry(happenings="Deploying the fix took all afternoon")

        found = DailyEntry.objects.filter(owner=self.user, search_document=q("deploy"))

        assert found.count() == 1

    def test_another_owners_day_is_not_found(self):
        """A journal is the most private material in this application. Charter
        rule 1 is not a formality here."""
        self.entry(owner=self.other, happenings="Walked the coast path")

        found = DailyEntry.objects.filter(owner=self.user, search_document=q("coast"))

        assert list(found) == []

    def test_an_empty_day_matches_nothing_rather_than_everything(self):
        """All three fields blank is a real and common row -- a day opened and
        not written in. `coalesce` inside the vector is what keeps that from
        becoming NULL, and a NULL tsvector matching a query would be a quiet
        disaster in the other direction."""
        self.entry()

        assert not DailyEntry.objects.filter(owner=self.user, search_document=q("anything")).exists()

    def test_a_very_long_entry_can_still_be_saved(self):
        """The btree write-path failure, held open here as well. A journal entry
        is precisely the long, lexically varied text that trips the 2704-byte
        index-entry cap -- see `mind/models.py:113`."""
        many_distinct_words = " ".join(f"lexeme{n}" for n in range(2000))

        written = self.entry(happenings=many_distinct_words)

        assert DailyEntry.objects.filter(pk=written.pk).exists()

    def test_the_vector_follows_an_edit(self):
        written = self.entry(happenings="Walked the coast path")

        written.happenings = "Stayed in and read"
        written.save()

        assert DailyEntry.objects.filter(owner=self.user, search_document=q("read")).exists()
        assert not DailyEntry.objects.filter(owner=self.user, search_document=q("coast")).exists()


class RankedDailyEntrySearchTest(TestCase):
    """Increment 2 for the journal half."""

    def setUp(self):
        self.user = User.objects.create_user("alice", "a@example.com", "pw")
        self.other = User.objects.create_user("bob", "b@example.com", "pw")

    def entry(self, day, owner=None, **fields):
        return DailyEntry.objects.create(
            owner=owner or self.user, date=datetime.date(2026, 8, day), **fields
        )

    def test_a_denser_match_ranks_above_a_passing_mention(self):
        self.entry(1, happenings="Mentioned the restore drill in passing")
        self.entry(2, happenings="Restore drill, restore drill, the whole restore drill day")

        found = reads.search_entries(self.user, "restore drill")

        assert [e.date.day for e in found] == [2, 1]

    def test_an_empty_query_returns_nothing_rather_than_every_day(self):
        """On a journal this is the difference between a blank search box and
        handing back the person's entire diary."""
        self.entry(1, happenings="Walked the coast path")

        assert list(reads.search_entries(self.user, "")) == []
        assert list(reads.search_entries(self.user, "  ")) == []

    def test_it_is_scoped_to_one_owner(self):
        self.entry(1, owner=self.other, happenings="Walked the coast path")

        assert list(reads.search_entries(self.user, "coast")) == []

    def test_ties_are_broken_by_recency(self):
        """Equal matches are common in a journal -- the same phrase on two days
        -- and an unstable order there means the same search puts a different
        day first each time it is run."""
        self.entry(1, happenings="Walked the coast path")
        self.entry(3, happenings="Walked the coast path")
        self.entry(2, happenings="Walked the coast path")

        found = reads.search_entries(self.user, "coast path")

        assert [e.date.day for e in found] == [3, 2, 1]

    def test_a_multi_word_query_requires_both_words(self):
        self.entry(1, happenings="Walked the coast path")
        self.entry(2, happenings="Walked the dog")

        found = reads.search_entries(self.user, "walked coast")

        assert [e.date.day for e in found] == [1]
