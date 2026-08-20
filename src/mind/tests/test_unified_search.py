"""One search box, three sections.

Increment 3 of `design/search-plan.md`, and the first increment a person can
use. D1 and D2 were answered on August 20, 2026: the endpoint goes in
`mind/api_v1.py` beside capture, and the surface is the `/mind/search/` page
that already exists.

**Sectioned, not merged.** `SearchRank` is meaningful within one document set
and not across two, so ordering an `Item` against a `Node` in one list invents
a comparison the data does not support — and it fails silently, as a plausible
list ordered by nothing. Three lists, each ranked and counted on its own, invent
no number.

**The sections must have asked the same question.** That is what
`clarice.search.to_query` is for, and the test below that pins it is the whole
reason that module exists rather than three copies of two lines.
"""

import datetime

import pytest

from daily.models import DailyEntry
from lists.models import Item, List


@pytest.fixture
def signed_in(client, owner):
    client.force_login(owner)
    return client


@pytest.fixture
def make_task(owner):
    def _make(text, notes="", who=None):
        return Item.objects.create(owner=who or owner, text=text, notes=notes)

    return _make


@pytest.fixture
def make_day(owner):
    def _make(day, happenings="", who=None):
        return DailyEntry.objects.create(
            owner=who or owner,
            date=datetime.date(2026, 8, day),
            happenings=happenings,
        )

    return _make


def test_the_page_finds_a_task(signed_in, make_task):
    make_task("Renew passport")

    page = signed_in.get("/mind/search/", {"q": "passport"}).content.decode()

    assert "Renew passport" in page


def test_the_page_finds_a_day(signed_in, make_day):
    """The half the trigger fired on. Before this a day was reachable only by
    knowing its date, and there is no date picker."""
    make_day(3, happenings="Walked the coast path to Porthcurno")

    page = signed_in.get("/mind/search/", {"q": "Porthcurno"}).content.decode()

    assert "coast path" in page


def test_the_page_still_finds_a_note(signed_in, make_node):
    """The section that already worked. Extending this page must not cost the
    thing it was already good at."""
    make_node("The restore drill is the rollback path")

    page = signed_in.get("/mind/search/", {"q": "rollback"}).content.decode()

    assert "restore drill" in page


def test_all_three_sections_appear_for_one_query(signed_in, make_task, make_day, make_node):
    """The point of the whole increment: one box, and the person does not have
    to know which core they wrote it in."""
    make_task("Passport renewal")
    make_day(4, happenings="Sent the passport forms")
    make_node("Passport office closes at four")

    page = signed_in.get("/mind/search/", {"q": "passport"}).content.decode()

    assert "Passport renewal" in page
    assert "passport forms" in page
    assert "Passport office" in page


def test_a_section_with_no_matches_does_not_claim_the_others_failed(
    signed_in, make_task
):
    """Three empty-states stacked up would say "nothing matched" three times for
    a search that found something. The page says it once, and only when all
    three are empty."""
    make_task("Renew passport")

    page = signed_in.get("/mind/search/", {"q": "passport"}).content.decode()

    assert page.count("Nothing matched") == 0


def test_nothing_anywhere_says_so_once(signed_in, make_task):
    make_task("Renew passport")

    page = signed_in.get("/mind/search/", {"q": "bicycle"}).content.decode()

    assert page.count("Nothing matched") == 1


def test_another_owners_material_is_in_no_section(
    signed_in, other_owner, make_task, make_day
):
    """Charter rule 1, across all three sections at once. This is the test that
    would have to fail for the feature to be worth reverting."""
    make_task("Renew passport", who=other_owner)
    make_day(5, happenings="Walked the coast path", who=other_owner)

    page = signed_in.get("/mind/search/", {"q": "passport coast"}).content.decode()

    assert "Renew passport" not in page
    assert "coast path" not in page


def test_an_empty_query_returns_no_sections_at_all(signed_in, make_task, make_day):
    """A blank box must not hand back the person's entire diary."""
    make_task("Renew passport")
    make_day(6, happenings="Walked the coast path")

    page = signed_in.get("/mind/search/", {"q": ""}).content.decode()

    assert "Renew passport" not in page
    assert "coast path" not in page


def test_every_section_parses_the_query_the_same_way(
    signed_in, make_task, make_day, make_node
):
    """The quiet dependency `clarice.search` exists for.

    A two-word query narrows in every section or in none. If one section ANDs
    its terms while another ORs them, the person sees three lists that disagree
    and is never told they were asked different questions -- which looks like a
    ranking bug and is not one.
    """
    make_task("Renew passport", notes="")
    make_task("Renew licence", notes="")
    make_day(7, happenings="Renew passport reminder")
    make_day(8, happenings="Renew licence reminder")
    make_node("Renew passport at the office")
    make_node("Renew licence at the office")

    page = signed_in.get("/mind/search/", {"q": "renew passport"}).content.decode()

    assert "licence" not in page.lower()


def test_the_miss_button_survives(signed_in, make_task):
    """The page's most valuable control, and the one an extension could quietly
    push below three sections of results and out of mind. D3 is still open --
    a miss recorded here cannot yet resolve to a task -- but the button
    recording *that a search failed* does not depend on that."""
    make_task("Renew passport")

    page = signed_in.get("/mind/search/", {"q": "bicycle"}).content.decode()

    assert "can’t find it" in page


def test_searching_requires_signing_in(client):
    assert client.get("/mind/search/", {"q": "passport"}).status_code == 302


class TestTheEndpoint:
    """`GET /api/v1/search`, D1's answer: in `mind/api_v1.py` beside capture."""

    def test_it_returns_all_three_sections(self, signed_in, make_task, make_day, make_node):
        make_task("Passport renewal")
        make_day(9, happenings="Sent the passport forms")
        make_node("Passport office closes at four")

        body = signed_in.get("/api/v1/search", {"q": "passport"}).json()

        assert [r["text"] for r in body["tasks"]] == ["Passport renewal"]
        assert [r["date"] for r in body["days"]] == ["2026-08-09"]
        assert "Passport office" in body["notes"][0]["body"]

    def test_each_section_carries_its_own_total(self, signed_in, make_task):
        """Counted before slicing, for the reason the notes section already
        does it: a section that shows three of thirty and says nothing invites
        the miss button to be pressed for something it simply did not show."""
        for n in range(3):
            make_task(f"Passport thing {n}")

        body = signed_in.get("/api/v1/search", {"q": "passport"}).json()

        assert body["tasks_total"] == 3

    def test_an_empty_query_returns_empty_sections(self, signed_in, make_task):
        make_task("Renew passport")

        body = signed_in.get("/api/v1/search", {"q": ""}).json()

        assert body["tasks"] == []
        assert body["days"] == []
        assert body["notes"] == []

    def test_it_is_scoped_to_one_owner(self, signed_in, other_owner, make_task):
        make_task("Renew passport", who=other_owner)

        body = signed_in.get("/api/v1/search", {"q": "passport"}).json()

        assert body["tasks"] == []

    def test_a_stranger_gets_no_results(self, client):
        assert client.get("/api/v1/search", {"q": "passport"}).status_code == 401

    def test_a_task_result_carries_what_a_surface_needs_to_show_it(
        self, signed_in, make_task
    ):
        """Including `status`, which is the price of returning every status --
        a completed task in a result list with nothing saying so is worse than
        not returning it."""
        task = make_task("Renew passport")

        result = signed_in.get("/api/v1/search", {"q": "passport"}).json()["tasks"][0]

        assert result["id"] == task.pk
        assert result["status"] == "active"
