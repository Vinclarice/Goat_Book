"""Naming something after the fact, on a note that already exists.

The capture-page tags box only helps notes written from now on, which left the
case that produced it unsolved: four notes about films, already captured, and no
way to say "these are films". A thought is often only recognisable as part of
something once the something exists.

**How this is expected to be used, from Vince, August 15, 2026:** obvious
categories — movies, books, a particular project — and not much else. Most
capture is random and will stay untagged, which is the point rather than a
shortfall. The field is flexibility for the cases that repeat, not a filing
system waiting to be filled in.

That expectation is why this is a one-line form on a card rather than a tag
manager: it should cost nothing to ignore thirty times and be there the once it
is wanted.
"""

import pytest

from mind import services
from mind.models import ConceptCandidate, Mention, NodeSource

pytestmark = pytest.mark.django_db

from datetime import datetime, timezone as dt_timezone

NOW = datetime(2026, 6, 10, 9, 0, tzinfo=dt_timezone.utc)


@pytest.fixture
def signed_in(client, owner):
    client.force_login(owner)
    return client


@pytest.fixture
def note(owner):
    return services.capture(
        owner, content="the invention of lying", captured_at=NOW,
        source=NodeSource.WEB, actor="vince",
    )


def add_tags(client, node, tags):
    return client.post(f"/mind/{node.public_id}/tags/", {"tags": tags})


def test_a_note_can_be_named_after_it_was_written(signed_in, owner, note):
    add_tags(signed_in, note, "movie")

    concept = ConceptCandidate.objects.get(label="movie")
    assert concept.confirmed_at is not None
    assert Mention.objects.filter(node=note, concept=concept).exists()


def test_the_same_name_across_old_notes_gathers_them(signed_in, owner, note):
    """The case this exists for: material already captured, recognised as one
    concern only afterwards."""
    second = services.capture(
        owner, content="down periscope", captured_at=NOW,
        source=NodeSource.WEB, actor="vince",
    )

    add_tags(signed_in, note, "movie")
    add_tags(signed_in, second, "movie")

    concept = ConceptCandidate.objects.get(label="movie")
    assert Mention.objects.filter(concept=concept).count() == 2


def test_the_page_shows_what_a_note_is_already_named(signed_in, owner, note):
    """Otherwise there is no way to tell a tagged note from an untagged one,
    and no way to notice you have used two spellings for one thing."""
    add_tags(signed_in, note, "movie")

    page = signed_in.get("/mind/")

    assert b"movie" in page.content


def test_the_form_is_on_every_note(signed_in, owner, note):
    page = signed_in.get("/mind/")

    assert f"/mind/{note.public_id}/tags/".encode() in page.content


def test_it_goes_back_to_the_page_it_came_from(signed_in, owner, note):
    response = add_tags(signed_in, note, "movie")

    assert response.status_code == 302
    assert response["Location"] == "/mind/"


def test_an_empty_submission_does_nothing(signed_in, owner, note):
    """A stray press of return should not be an error, and should not record
    an empty name."""
    response = add_tags(signed_in, note, "   ")

    assert response.status_code == 302
    assert ConceptCandidate.objects.count() == 0


def test_somebody_elses_note_cannot_be_named(signed_in, other_owner):
    theirs = services.capture(
        other_owner, content="their thought", captured_at=NOW,
        source=NodeSource.WEB, actor="them",
    )

    add_tags(signed_in, theirs, "movie")

    assert Mention.objects.count() == 0


def test_naming_it_twice_does_not_deepen_the_evidence(signed_in, owner, note):
    add_tags(signed_in, note, "movie")
    add_tags(signed_in, note, "movie")

    assert Mention.objects.count() == 1
