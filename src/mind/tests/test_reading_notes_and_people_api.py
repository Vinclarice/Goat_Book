"""The two front doors that never existed — app-overhaul-plan.md increment 2a.

`app-overhaul-audit-2026-09-06.md`'s **G3**: `/mind/notes/<uuid>/` and
`/mind/people/<uuid>/` render, and `/mind/notes/` and `/mind/people/` **do
not**. A `Note` is what capture writes and a `Person` is one of the four things
the graph is built to relate, and both are reachable only by arriving from
search, review, or another node's page.

**So these two are the one part of 2a that is not a mirror.** Everything else
in this increment copies a view; there is no view to copy here, and the audit
calls this "the counterweight to G1" — the answer to thirty surfaces is not
uniformly *fewer*, because two of the missing ones are load-bearing.

**Indexes only, and the detail pages are deliberately not here.**
`views.note`'s context has twenty keys and `views.person`'s has four joins
including commitments and a name's shape across time. Those are their own
piece; the front door is the gap the audit named and it is worth closing on
its own.

**Counted before slicing**, the way `SearchOut` is and for its reason: a
section showing thirty of six hundred and saying nothing is a surface that
lies quietly.
"""

from datetime import timedelta

import pytest
from django.test import Client
from django.utils import timezone

from accounts.models import User
from mind import services
from mind.models import ConceptCandidate, ConceptType, NodeSource

PASSWORD = "a secure password"


@pytest.fixture
def alice():
    return User.objects.create_user("alice", "alice@example.com", PASSWORD)


@pytest.fixture
def bob():
    return User.objects.create_user("bob", "bob@example.com", PASSWORD)


@pytest.fixture
def client():
    return Client()


def a_note(owner, content, *, days_ago=0):
    return services.capture(
        owner,
        content=content,
        captured_at=timezone.now() - timedelta(days=days_ago),
        source=NodeSource.WEB,
        actor=owner.get_username(),
    )


def a_person(owner, label="Maya"):
    return ConceptCandidate.objects.create(
        owner=owner,
        label=label,
        concept_type=ConceptType.PERSON,
        confirmed_at=timezone.now(),
    )


# --- notes -----------------------------------------------------------------


@pytest.mark.django_db
def test_the_notes_index_answers_newest_first(client, alice):
    """`live_nodes`' own ordering, which is what a front door on capture wants:
    the thing you wrote most recently is the thing you are most likely looking
    for."""
    a_note(alice, "The oldest thing", days_ago=10)
    a_note(alice, "The newest thing")
    client.force_login(alice)

    response = client.get("/api/v1/notes")

    assert response.status_code == 200
    bodies = [each["body"] for each in response.json()["notes"]]
    assert bodies[0] == "The newest thing"


@pytest.mark.django_db
def test_the_notes_index_is_scoped_to_its_owner(client, alice, bob):
    a_note(bob, "Bob wrote this")
    client.force_login(alice)

    response = client.get("/api/v1/notes")

    assert response.json()["notes"] == []
    assert response.json()["total"] == 0


@pytest.mark.django_db
def test_a_deleted_note_is_not_a_front_door(client, alice):
    """`live_nodes` excludes deleted and archived, and an index is not a way
    round it. This is the same rule `what_grew_from` states for a source page:
    a new surface is not an exemption from the ones that already hold."""
    note = a_note(alice, "Written then removed")
    note.deleted_at = timezone.now()
    note.save(update_fields=["deleted_at"])
    client.force_login(alice)

    response = client.get("/api/v1/notes")

    assert response.json()["notes"] == []


@pytest.mark.django_db
def test_the_notes_index_says_how_many_it_did_not_show(client, alice):
    """Counted before slicing, like `SearchOut`. A page of thirty out of six
    hundred that says nothing about the rest is worse than one that returns
    less and admits it."""
    for each in range(3):
        a_note(alice, f"Thought number {each}", days_ago=each)
    client.force_login(alice)

    response = client.get("/api/v1/notes?limit=2")

    body = response.json()
    assert len(body["notes"]) == 2
    assert body["total"] == 3


# --- people ----------------------------------------------------------------


@pytest.mark.django_db
def test_the_people_index_answers_with_confirmed_people(client, alice):
    a_person(alice, "Maya")
    client.force_login(alice)

    response = client.get("/api/v1/people")

    assert response.status_code == 200
    assert [each["label"] for each in response.json()["people"]] == ["Maya"]


@pytest.mark.django_db
def test_the_people_index_holds_only_people(client, alice):
    """A page called *people* rendering a motif would mean nothing --
    `views.person` says so, and redirects rather than showing one. The index
    is where that rule is cheapest to keep: it simply does not list them.
    """
    a_person(alice, "Maya")
    ConceptCandidate.objects.create(
        owner=alice,
        label="Indonesian",
        concept_type=ConceptType.ACTIVITY,
        confirmed_at=timezone.now(),
    )
    client.force_login(alice)

    labels = [each["label"] for each in client.get("/api/v1/people").json()["people"]]
    assert labels == ["Maya"]


@pytest.mark.django_db
def test_an_unconfirmed_name_is_not_yet_a_person(client, alice):
    """A candidate is the system's guess. The soft-apply rule is that a guess
    is never treated as fact by anything downstream, and a directory of the
    people in your life is about as downstream as it gets."""
    ConceptCandidate.objects.create(
        owner=alice, label="Maybe A Person", concept_type=ConceptType.PERSON
    )
    client.force_login(alice)

    assert client.get("/api/v1/people").json()["people"] == []


@pytest.mark.django_db
def test_the_people_index_is_scoped_to_its_owner(client, alice, bob):
    a_person(bob, "Bob's friend")
    client.force_login(alice)

    assert client.get("/api/v1/people").json()["people"] == []


@pytest.mark.django_db
def test_both_indexes_need_a_session(client, alice):
    assert client.get("/api/v1/notes").status_code == 401
    assert client.get("/api/v1/people").status_code == 401
