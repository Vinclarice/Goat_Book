"""Somewhere to look at one note — Track E increment 19.

**The knowledge core had no node page.** Capture, review, concepts, search and
numbers, and no way to open a single note: forty-seven of them in production
and the only route to one was a search result that linked to a day. Everything
the graph accretes — labels, connections, what it became — existed and had
nowhere to be seen.

**It is also the caller Track A did not have.** Five increments built a time
axis and two reads over it, and nothing used either, which by `principles.md`
made the whole track a deferral wearing a completion's clothes. This page asks
both questions a person asks about an old note: *what else was going on when I
wrote this* (`around`) and *what came of it* (`since`).

**Read-only, deliberately.** Nine dark services are the undo half of a live
pair — `revise`, `delete_node`, `archive_node`, `unlink`, `reopen_question` —
and every one of them is waiting on this page. They stay dark here.
`temporal-substrate-plan.md` Track E puts the correction surface at increment
21 and person-anchoring at 20, and hanging five affordances on a page nobody
has looked at yet is how a surface gets designed twice.

**R5's visibility rule is the load-bearing one**, and it is why the page exists
in the shape it does: a deleted or archived node is not shown, and
`clarice/recall.py` already withholds their content from both reads. The rule
was written and tested before the door existed, which is the only reason this
increment does not have to invent it.
"""

from datetime import datetime, timedelta, timezone as dt_timezone

import pytest

from mind import services
from mind.models import (
    ConceptType,
    EdgeRelation,
    FacetKind,
    InferenceOrigin,
    Node,
)


WRITTEN = datetime(2026, 5, 4, 9, 0, tzinfo=dt_timezone.utc)


def later(**offset):
    return WRITTEN + timedelta(**offset)


@pytest.fixture
def signed_in(client, owner):
    client.force_login(owner)
    return client


@pytest.fixture
def note(owner):
    return services.capture(
        owner,
        content="ask Maya about the venue",
        captured_at=WRITTEN,
        source=Node.Source.WEB,
        actor="vince",
    )


def page(client, node):
    return client.get(f"/mind/notes/{node.public_id}/")


# ---------------------------------------------------------------------------
# It shows the note
# ---------------------------------------------------------------------------


def test_it_shows_what_the_note_says(signed_in, note):
    response = page(signed_in, note)

    assert response.status_code == 200
    assert "ask Maya about the venue" in response.content.decode()


def test_it_shows_the_current_body_and_not_the_original(signed_in, owner, note):
    """`current_body` is the one definition of what a node currently says, and
    a page that read `original_content` would be a second one -- disagreeing
    the moment increment 21 gives `revise` its door."""
    services.revise(note, body="ask Maya about the venue and the parking", now=later(days=1), actor="vince")

    body = page(signed_in, note).content.decode()

    assert "and the parking" in body


def test_it_shows_the_labels_a_person_confirmed(signed_in, owner, note):
    concept = services.propose_concept(
        owner,
        label="Maya",
        concept_type=ConceptType.UNKNOWN,
        now=WRITTEN,
        actor="system",
    )
    services.confirm_concept(concept, now=WRITTEN, actor="vince")
    services.propose_mention(
        note,
        concept,
        index_version="manual",
        origin=InferenceOrigin.EXPLICIT,
        now=later(hours=1),
        actor="vince",
    )

    assert "Maya" in page(signed_in, note).content.decode()


def test_it_does_not_show_a_label_nobody_confirmed(signed_in, owner, note):
    """The soft-apply rule: a guess is never presented as fact. A page that
    listed proposals beside confirmations would be the one place the
    distinction stopped being visible."""
    concept = services.propose_concept(
        owner,
        label="Guesswork",
        concept_type=ConceptType.UNKNOWN,
        now=WRITTEN,
        actor="system",
    )
    services.propose_mention(
        note, concept, index_version="fts-v1", now=later(hours=1), actor="system"
    )

    assert "Guesswork" not in page(signed_in, note).content.decode()


def test_it_shows_what_this_note_is_linked_to(signed_in, owner, note):
    other = services.capture(
        owner,
        content="the venue's phone number",
        captured_at=later(days=1),
        source=Node.Source.WEB,
        actor="vince",
    )
    services.link(
        note, other, relation=EdgeRelation.RELATES_TO, now=later(days=2), actor="vince"
    )

    assert "phone number" in page(signed_in, note).content.decode()


# ---------------------------------------------------------------------------
# The two reads Track A built, given a caller
# ---------------------------------------------------------------------------


def test_it_says_what_else_was_going_on_when_this_was_written(signed_in, owner, note):
    """`around()`, increment 4, called for the first time by anything."""
    services.capture(
        owner,
        content="book the registrar",
        captured_at=later(minutes=20),
        source=Node.Source.WEB,
        actor="vince",
    )

    assert "book the registrar" in page(signed_in, note).content.decode()


def test_it_says_what_came_of_the_note(signed_in, owner, note):
    """`since()`, increment 5. The hop across the cores: this note became a
    task, and the task was completed, and neither fact lives on the node."""
    from lists import services as list_services
    from lists.models import List

    area = List.objects.create(owner=owner, title="Home")
    facet = services.propose_facet(
        note,
        kind=FacetKind.ACTIONABLE,
        data={},
        now=later(hours=1),
        actor="vince",
        reason="looks like a commitment",
    )
    confirmed = services.confirm_actionable(
        facet, area=area, now=later(hours=1), actor="vince"
    )
    list_services.complete_item(confirmed.task)

    body = page(signed_in, note).content.decode()

    # Phrased, not named. The raw `task_completed` this used to accept is the
    # log's vocabulary, and putting it in front of a person is the bend
    # `test_it_says_what_happened_in_words` now guards against.
    assert "the task finished" in body


def test_the_note_itself_is_not_something_else_that_was_going_on(signed_in, note):
    """It listed its own capture. "What else" means else, and a section whose
    first entry is the thing you are already looking at teaches a reader that
    the section means nothing."""
    body = page(signed_in, note).content.decode()

    assert "Nothing else is recorded" in body


def test_a_quiet_note_says_so_rather_than_showing_nothing(signed_in, note):
    """The failure this project has shipped twice: a section that renders
    empty is indistinguishable from one that is broken, to somebody who has
    never seen it full."""
    body = page(signed_in, note).content.decode()

    assert "Nothing" in body or "nothing" in body


# ---------------------------------------------------------------------------
# R5's visibility rule, given its door
# ---------------------------------------------------------------------------


def test_a_deleted_note_is_not_shown(signed_in, note):
    """`delete_node`'s promise, which `clarice/recall.py` already keeps in both
    its reads. This is the surface that would have broken it."""
    services.delete_node(note, now=later(days=1), actor="vince")

    assert page(signed_in, note).status_code == 404


def test_an_archived_note_is_not_shown(signed_in, note):
    """`queries.live_nodes` excludes archived nodes from everything else, and
    a page that ignored that would be the exception."""
    services.archive_node(note, now=later(days=1), actor="vince")

    assert page(signed_in, note).status_code == 404


def test_one_person_cannot_open_anothers_note(client, other_owner, note):
    """404 rather than 403: whether a note exists is itself the person's."""
    client.force_login(other_owner)

    assert page(client, note).status_code == 404


def test_signing_in_is_required(client, note):
    response = page(client, note)

    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


def test_a_note_that_does_not_exist_is_a_404(signed_in, owner):
    import uuid

    response = signed_in.get(f"/mind/notes/{uuid.uuid4()}/")

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Findable, which is the whole reason it exists
# ---------------------------------------------------------------------------


def test_a_search_result_links_to_the_note(signed_in, note):
    """The gap this closes. Search could find a note and offer nowhere to go
    -- the same failure as the calendar and bills pages, which shipped
    reachable only from one link nobody found."""
    response = signed_in.get("/mind/search/", {"q": "venue"})

    assert f"/mind/notes/{note.public_id}/" in response.content.decode()


# ---------------------------------------------------------------------------
# It reads like a sentence, not like a table of event names
# ---------------------------------------------------------------------------


def test_it_says_what_happened_in_words(signed_in, owner, note):
    """The first render showed `facet_confirmed`, `mention_confirmed`,
    `edge_created` and `task_completed` -- the log's own vocabulary, put in
    front of a person.

    `principles.md` calls that a bend, and the log's vocabulary is exactly the
    kind that should never surface: it is chosen for what a *reading* can
    filter on, which is a different job from what a person can read.
    """
    from lists import services as list_services
    from lists.models import List

    area = List.objects.create(owner=owner, title="Home")
    facet = services.propose_facet(
        note,
        kind=FacetKind.ACTIONABLE,
        data={},
        now=later(hours=1),
        actor="vince",
        reason="looks like a commitment",
    )
    confirmed = services.confirm_actionable(
        facet, area=area, now=later(hours=1), actor="vince"
    )
    list_services.complete_item(confirmed.task)

    body = page(signed_in, note).content.decode()

    assert "became a task" in body
    assert "finished" in body.lower()
    assert "facet_confirmed" not in body
    assert "task_completed" not in body


def test_a_link_says_how_two_notes_relate_in_words(signed_in, owner, note):
    other = services.capture(
        owner,
        content="the venue phone number",
        captured_at=later(days=1),
        source=Node.Source.WEB,
        actor="vince",
    )
    services.link(
        note, other, relation=EdgeRelation.RELATES_TO, now=later(days=2), actor="vince"
    )

    body = page(signed_in, note).content.decode()

    assert "relates_to" not in body


def test_an_event_with_no_phrase_still_says_something(signed_in, owner, note):
    """The fallback matters more than the phrases. `EventType` is open by
    design -- new kinds are new values -- so a mapping that returned nothing
    for an unmapped one would blank a row rather than degrade to the name.
    """
    from mind.views import phrase_for

    assert phrase_for("something_nobody_has_written_yet")
