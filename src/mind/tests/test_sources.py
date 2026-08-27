"""Something you read, and what grew out of it — S15, and `Source`.

> Sam reads an article. Two ideas and one task come out of it, and six months
> later he can still tell where they came from.

**Done means:** the task remembers the external source it came from, and the
source shows everything that grew out of it.

**Impossible until now for exactly one reason**, and S15 names it: *there is
nothing to attach an article to.* `NodeSource` is a capture-channel label —
mobile, web — not external material. **The backlink half already existed**:
`Facet.task` carries `related_name="mind_facets"`, so from a task you could
already reach the thought it came from. Only the source end was absent.

**It earns a model on `architecture-trajectory.md` §4's test**, which the v3
plan's table did not cover:

- **Its life cycle is unlike anything here.** A source **exists before any note
  about it**, produces notes over years, and **outlives every one of them** — a
  `Node` is captured, revised, archived, deleted; a `Facet` is proposed,
  confirmed, retired; an `Item` is open then done. None of those is *a thing in
  the world that you keep returning to*.
- **A `Node` with a kind is the tempting answer and it is wrong.** A node is
  something *you wrote*. S15 is explicit that this is the gap: *the material is
  his own, and this story starts with an article somebody else wrote.*
- **Unlike `MoneyLine` it is not a sidecar**, because there is no existing row for it
  to hang off.

**The URL is text and is never fetched**, which is D7's answer already made:
storing one is most of the value and fetching reopens SSRF surface on a
one-host deployment.
"""

import datetime

import pytest

from lists.models import List
from mind import services
from mind.models import Facet, FacetKind, Node, Source


NOW = datetime.datetime(2026, 5, 4, 9, 0, tzinfo=datetime.timezone.utc)


def later(**offset):
    return NOW + datetime.timedelta(**offset)


@pytest.fixture
def signed_in(client, owner):
    client.force_login(owner)
    return client


@pytest.fixture
def article(owner):
    return services.record_source(
        owner,
        title="The Cost of Context Switching",
        url="https://example.com/context",
        author="A Writer",
        now=NOW,
    )


def a_note_from(owner, source, content, *, when=NOW):
    return services.capture(
        owner,
        content=content,
        captured_at=when,
        source=Node.Source.WEB,
        actor="vince",
        came_from=source,
    )


# ---------------------------------------------------------------------------
# The thing that did not exist
# ---------------------------------------------------------------------------


def test_something_you_read_can_be_recorded(db, article):
    assert Source.objects.count() == 1
    assert article.title == "The Cost of Context Switching"


def test_it_keeps_the_url_as_text_and_fetches_nothing(db, article):
    """D7's answer, already made: storing a URL is most of the value, and
    fetching reopens SSRF surface on a one-host deployment where the
    interesting targets are that host and the metadata endpoint."""
    assert article.url == "https://example.com/context"


def test_a_source_needs_a_title(db, owner):
    """A row with a URL and no title is a bookmark. What this records is
    something you read, which you can name."""
    with pytest.raises(services.MindError):
        services.record_source(owner, title="   ", url="https://example.com", now=NOW)


def test_recording_the_same_thing_twice_is_one_source(db, owner):
    """A person reads an article, notes something, comes back a week later and
    notes something else. Two rows would split what grew out of it in half."""
    services.record_source(owner, title="A", url="https://example.com/x", now=NOW)
    services.record_source(owner, title="A", url="https://example.com/x", now=later(days=7))

    assert Source.objects.count() == 1


def test_two_people_reading_the_same_article_have_their_own(db, owner, other_owner):
    services.record_source(owner, title="A", url="https://example.com/x", now=NOW)
    services.record_source(other_owner, title="A", url="https://example.com/x", now=NOW)

    assert Source.objects.count() == 2


# ---------------------------------------------------------------------------
# What grew out of it
# ---------------------------------------------------------------------------


def test_a_note_can_say_what_it_came_from(db, owner, article):
    node = a_note_from(owner, article, "the switching cost is the meeting after")

    assert node.came_from == article


def test_the_source_shows_what_grew_out_of_it(db, owner, article):
    a_note_from(owner, article, "one idea")
    a_note_from(owner, article, "another idea", when=later(days=3))

    grew = services.what_grew_from(article)

    assert [n.original_content for n in grew.notes] == ["one idea", "another idea"]


def test_it_shows_the_tasks_those_notes_became(db, owner, article):
    """The half S15's done-means turns on -- *two ideas and one task come out
    of it*. The task is not on the source; it is reached along the chain the
    merger already records."""
    node = a_note_from(owner, article, "email the author")
    area = List.objects.create(owner=owner, title="Home")
    facet = services.propose_facet(
        node,
        kind=FacetKind.ACTIONABLE,
        data={},
        now=later(hours=1),
        actor="vince",
        reason="looks like a commitment",
    )
    services.confirm_actionable(facet, area=area, now=later(hours=1), actor="vince")

    grew = services.what_grew_from(article)

    assert [t.text for t in grew.tasks] == ["email the author"]


def test_a_deleted_note_did_not_grow_out_of_anything(db, owner, article):
    """`live_nodes` is the one visibility rule and a source page is not a way
    round it."""
    node = a_note_from(owner, article, "something regretted")
    services.delete_node(node, now=later(days=1), actor="vince")

    assert services.what_grew_from(article).notes == []


def test_a_source_nothing_grew_from_says_so(db, article):
    grew = services.what_grew_from(article)

    assert not grew.has_anything


# ---------------------------------------------------------------------------
# And from the other end — the task remembers
# ---------------------------------------------------------------------------


def test_a_task_remembers_what_it_was_read_in(db, owner, article):
    """*Six months later he can still tell where they came from.* Read along
    task, facet, node, source rather than stored on the task -- the chain
    exists and a copy would be free to disagree with it."""
    node = a_note_from(owner, article, "email the author")
    area = List.objects.create(owner=owner, title="Home")
    facet = services.propose_facet(
        node,
        kind=FacetKind.ACTIONABLE,
        data={},
        now=later(hours=1),
        actor="vince",
        reason="looks like a commitment",
    )
    confirmed = services.confirm_actionable(
        facet, area=area, now=later(hours=1), actor="vince"
    )

    assert services.what_a_task_was_read_in(confirmed.task) == article


def test_a_task_from_nothing_read_remembers_nothing(db, owner):
    from lists import services as list_services

    area = List.objects.create(owner=owner, title="Home")

    assert services.what_a_task_was_read_in(
        list_services.create_item(area, "a task somebody typed")
    ) is None


# ---------------------------------------------------------------------------
# The surface
# ---------------------------------------------------------------------------


def test_the_source_has_a_page(signed_in, owner, article):
    a_note_from(owner, article, "the switching cost is the meeting after")

    response = signed_in.get(f"/mind/sources/{article.public_id}/")

    assert response.status_code == 200
    assert "the switching cost" in response.content.decode()


def test_the_page_links_to_what_you_read(signed_in, article):
    body = signed_in.get(f"/mind/sources/{article.public_id}/").content.decode()

    assert "https://example.com/context" in body


def test_one_person_cannot_open_anothers_source(client, other_owner, article):
    client.force_login(other_owner)

    assert client.get(f"/mind/sources/{article.public_id}/").status_code == 404


def test_the_note_page_says_what_it_was_read_in(signed_in, owner, article):
    node = a_note_from(owner, article, "an idea")

    body = signed_in.get(f"/mind/notes/{node.public_id}/").content.decode()

    assert "The Cost of Context Switching" in body
    assert f"/mind/sources/{article.public_id}/" in body


def test_sources_are_listed_somewhere(signed_in, article):
    """Findability, which this sequence has now got wrong twice."""
    body = signed_in.get("/mind/sources/").content.decode()

    assert "The Cost of Context Switching" in body


def test_a_source_is_in_the_export(db, owner, article):
    """An owned model, so `test_every_owned_model_is_named_somewhere_in_the_export`
    would catch this anyway -- asserted here too because a person's archive
    losing what they read is the kind of gap nobody checks."""
    from accounts import export
    from django.utils import timezone

    payload = export._payload(owner, now=timezone.now())

    assert payload["knowledge"]["sources"]


# ---------------------------------------------------------------------------
# Getting a note into one, which nothing could do until now
# ---------------------------------------------------------------------------


def test_you_can_write_a_note_from_the_source_page(signed_in, owner, article):
    """**The half that would have left this a seam.** `came_from` existed and
    no surface could set it, which is the state `principles.md` now calls a
    deferral wearing a completion's clothes.

    The box is on the source page rather than a picker on the capture page,
    because that is the shape of the act: you are reading the thing, and notes
    come out of it while you are there.
    """
    signed_in.post(
        f"/mind/sources/{article.public_id}/",
        {"content": "the switching cost is the meeting after"},
    )

    node = Node.objects.get(original_content="the switching cost is the meeting after")
    assert node.came_from == article


def test_a_note_written_there_shows_up_there(signed_in, owner, article):
    signed_in.post(
        f"/mind/sources/{article.public_id}/", {"content": "an idea"}
    )

    body = signed_in.get(f"/mind/sources/{article.public_id}/").content.decode()

    assert "an idea" in body


def test_an_empty_note_writes_nothing(signed_in, owner, article):
    signed_in.post(f"/mind/sources/{article.public_id}/", {"content": "   "})

    assert not Node.objects.filter(came_from=article).exists()


def test_you_cannot_write_into_another_persons_source(client, other_owner, article):
    client.force_login(other_owner)
    client.post(f"/mind/sources/{article.public_id}/", {"content": "not mine"})

    assert not Node.objects.filter(came_from=article).exists()


def test_a_note_written_from_a_source_still_proposes_a_commitment(signed_in, owner, article):
    """Capture's own behaviour is unchanged by arriving through a source --
    this is a different door into the same act, not a different act."""
    signed_in.post(
        f"/mind/sources/{article.public_id}/",
        {"content": "email the author by Friday"},
    )

    assert Facet.objects.filter(kind=FacetKind.ACTIONABLE).exists()
