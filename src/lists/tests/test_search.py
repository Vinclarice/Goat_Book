"""Finding a task by what it says.

Slice 1 of `design/search-plan.md`. The task core has never been searchable by
any means -- the knowledge core has had generated `tsvector` columns and a
ranked read since before the merger, and nothing on this side of the tree did.

The mechanism is inherited rather than designed, including the expensive part:
a plain `models.Index` on a tsvector is created as btree, which cannot serve
`@@` at all and caps index entries at 2704 bytes, so a long task note would
fail to *insert*. `mind/models.py:113` records what that cost. `GinIndex`, and
a test below that a long note still saves.
"""

from django.contrib.postgres.search import SearchQuery
from django.test import TestCase

from accounts.models import User
from lists import search
from lists.models import Item, List


def q(text):
    return SearchQuery(text, config="english")


class TaskSearchIndexTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("alice", "a@example.com", "pw")
        self.other = User.objects.create_user("bob", "b@example.com", "pw")
        self.area = List.objects.create(owner=self.user, title="Home")

    def test_a_task_is_found_by_a_word_in_its_text(self):
        Item.objects.create(owner=self.user, list=self.area, text="Renew passport")

        found = Item.objects.filter(owner=self.user, search_document=q("passport"))

        assert [i.text for i in found] == ["Renew passport"]

    def test_a_task_is_found_by_a_word_in_its_notes(self):
        """Notes are indexed too, which is the difference between finding the
        task you named well and finding the one where the detail is in the
        body."""
        Item.objects.create(
            owner=self.user,
            list=self.area,
            text="Admin",
            notes="Passport renewal form needs two photographs",
        )

        found = Item.objects.filter(owner=self.user, search_document=q("photographs"))

        assert [i.text for i in found] == ["Admin"]

    def test_the_index_stems_so_a_different_ending_still_matches(self):
        """`config="english"` is doing the work here. Without a stemmer this is
        a `LIKE` query wearing a hat, and searching for what you actually wrote
        three weeks ago is exactly the case where the ending has changed."""
        Item.objects.create(owner=self.user, list=self.area, text="Running the drill")

        found = Item.objects.filter(owner=self.user, search_document=q("run"))

        assert [i.text for i in found] == ["Running the drill"]

    def test_another_owners_task_is_not_found(self):
        """Charter rule 1, and the reason every read here takes an owner. A
        search that leaks is worse than no search -- it leaks whatever the other
        person happened to write down."""
        Item.objects.create(owner=self.other, list=None, text="Renew passport")

        found = Item.objects.filter(owner=self.user, search_document=q("passport"))

        assert list(found) == []

    def test_a_task_with_no_area_is_searchable(self):
        """`Item.list` is nullable and `Item.owner` is the spine. A task that
        stands on its own was the whole point of that change, and it would be a
        poor joke for it to be the one task nothing can find."""
        Item.objects.create(owner=self.user, list=None, text="Dentist on the 24th")

        found = Item.objects.filter(owner=self.user, search_document=q("dentist"))

        assert [i.text for i in found] == ["Dentist on the 24th"]

    def test_a_task_with_a_very_long_note_can_still_be_saved(self):
        """The btree failure, held open deliberately.

        This is a write-path test wearing a search test's clothes. With the
        wrong index class this raises on `create()` -- the note is never
        stored, and the person who typed it loses it. It asserts nothing about
        searching on purpose: the claim is that indexing this material did not
        make it unwritable.
        """
        many_distinct_words = " ".join(f"lexeme{n}" for n in range(2000))

        item = Item.objects.create(
            owner=self.user, list=self.area, text="Long", notes=many_distinct_words
        )

        assert Item.objects.filter(pk=item.pk).exists()

    def test_the_vector_follows_an_edit(self):
        """Generated, not maintained. The column cannot drift from its source
        because nothing updates it -- which is the argument for the generated
        column over a worker, and is worth one test rather than a comment."""
        item = Item.objects.create(owner=self.user, list=self.area, text="Renew licence")

        item.text = "Renew passport"
        item.save()

        assert Item.objects.filter(owner=self.user, search_document=q("passport")).exists()
        assert not Item.objects.filter(owner=self.user, search_document=q("licence")).exists()


class RankedTaskSearchTest(TestCase):
    """Increment 2: best first, rather than whatever order the table gives.

    `mind`'s search was a recency truncation before it was ranked, and the
    lesson recorded at `queries.py:78` is that this is not a refinement -- it
    decided *which* thirty results you saw, so which note you found depended on
    when you wrote it. Starting ranked rather than arriving at it later.
    """

    def setUp(self):
        self.user = User.objects.create_user("alice", "a@example.com", "pw")
        self.other = User.objects.create_user("bob", "b@example.com", "pw")
        self.area = List.objects.create(owner=self.user, title="Home")

    def task(self, text, notes="", owner=None, status=Item.Status.ACTIVE, **kw):
        return Item.objects.create(
            owner=owner or self.user,
            list=self.area if (owner or self.user) == self.user else None,
            text=text,
            notes=notes,
            status=status,
            **kw,
        )

    def test_a_match_in_the_text_outranks_a_match_in_the_notes(self):
        """The weighting on the column, proved through the read that uses it.
        A task called "Passport" is a better answer than one that mentions a
        passport in its notes, and the person searching almost always means the
        first."""
        self.task("Admin", notes="Ring the passport office")
        self.task("Passport renewal")

        found = search.search_tasks(self.user, "passport")

        assert [i.text for i in found] == ["Passport renewal", "Admin"]

    def test_it_returns_nothing_for_a_query_that_matches_nothing(self):
        self.task("Renew passport")

        assert list(search.search_tasks(self.user, "bicycle")) == []

    def test_an_empty_query_returns_nothing_rather_than_everything(self):
        """A blank search box is the most likely input on a search page, and
        returning the entire table for it is the classic version of this bug."""
        self.task("Renew passport")

        assert list(search.search_tasks(self.user, "")) == []
        assert list(search.search_tasks(self.user, "   ")) == []

    def test_it_is_scoped_to_one_owner(self):
        self.task("Renew passport", owner=self.other)

        assert list(search.search_tasks(self.user, "passport")) == []

    def test_completed_and_archived_tasks_are_found(self):
        """Deliberate, and the opposite of what the agenda does.

        The agenda hides finished work because it is a plan for today. Search
        answers "I know I wrote this down", and the older a thing is the more
        likely it is both finished *and* the thing being looked for -- so
        excluding them would recreate the exact complaint this exists to fix,
        on precisely the material most affected by it. The status travels with
        the result so a surface can say which it is.
        """
        import datetime

        from django.utils import timezone

        self.task("Renew passport", status=Item.Status.ACTIVE)
        self.task(
            "Passport photos",
            status=Item.Status.COMPLETED,
            completed_at=timezone.now(),
        )
        self.task(
            "Passport forms",
            status=Item.Status.ARCHIVED,
            archived_at=timezone.now(),
        )

        found = search.search_tasks(self.user, "passport")

        assert {i.text for i in found} == {
            "Renew passport",
            "Passport photos",
            "Passport forms",
        }

    def test_a_multi_word_query_requires_both_words(self):
        """`websearch` parsing, so two words narrow rather than widen. A search
        that ORs its terms gets steadily less useful as the person types, which
        is backwards."""
        self.task("Renew passport")
        self.task("Renew licence")

        found = search.search_tasks(self.user, "renew passport")

        assert [i.text for i in found] == ["Renew passport"]
