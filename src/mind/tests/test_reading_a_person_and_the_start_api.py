"""One person, and where somebody starts — app-overhaul-plan.md increment 2a.

**Person detail is the half that makes G3's front door worth having.** The
index landed on September 6 and lists confirmed people; this is what opening
one gives you, and `views.person` is explicit that the value is the two joins a
concept page cannot make — *the commitments that grew out of those notes*, and
*the shape of a name across time*.

**Start is the smallest surface in the core** and the answer to
`commercial-blueprint.md`'s long-open *explain the six invented concepts
somewhere in the product, once*. A tour was the obvious answer and the plan
refuses it: a concept explained before it exists is a word attached to nothing.
So it reads what the person's own material has earned, and nothing else.

Both session-only, both mirroring their views, both pure addition — the pages
keep working until 2b.
"""

from datetime import timedelta

import pytest
from django.test import Client
from django.utils import timezone

from accounts.models import User
from mind import services
from mind.models import (
    ConceptCandidate,
    ConceptType,
    InferenceOrigin,
    Mention,
    NodeSource,
)

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


def mentioning(node, concept):
    return Mention.objects.create(
        node=node,
        concept=concept,
        origin=InferenceOrigin.EXPLICIT,
        index_version="rules-v1",
        confirmed_at=timezone.now(),
    )


# --- one person ------------------------------------------------------------


@pytest.mark.django_db
def test_a_person_gathers_the_notes_that_mention_them(client, alice):
    person = a_person(alice)
    mentioning(a_note(alice, "Coffee with Maya, she is moving."), person)
    client.force_login(alice)

    response = client.get(f"/api/v1/people/{person.public_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["person"]["label"] == "Maya"
    assert any("Maya" in note["body"] for note in body["nodes"])


@pytest.mark.django_db
def test_a_person_carries_the_shape_of_their_name_across_time(client, alice):
    """The second join increment 20 names, and the one a flat list cannot
    give: twenty notes in one week and twenty across two years read
    identically until you count by month."""
    person = a_person(alice)
    mentioning(a_note(alice, "Maya, today"), person)
    mentioning(a_note(alice, "Maya, months ago", days_ago=70), person)
    client.force_login(alice)

    response = client.get(f"/api/v1/people/{person.public_id}")

    months = response.json()["months"]
    assert len(months) == 2
    assert all(each["seen"] == 1 for each in months)


@pytest.mark.django_db
def test_a_motif_is_not_a_person(client, alice):
    """`views.person` redirects rather than rendering one, because a page
    called *people* showing a motif would mean nothing. An API cannot redirect
    usefully into a panel, so it says 404 -- the same divergence the concept
    endpoint makes and for the same reason: a panel has to know it asked for
    something that is not there.
    """
    motif = ConceptCandidate.objects.create(
        owner=alice,
        label="Indonesian",
        concept_type=ConceptType.ACTIVITY,
        confirmed_at=timezone.now(),
    )
    client.force_login(alice)

    assert client.get(f"/api/v1/people/{motif.public_id}").status_code == 404


@pytest.mark.django_db
def test_another_owners_person_is_not_found(client, alice, bob):
    person = a_person(bob)
    client.force_login(alice)

    assert client.get(f"/api/v1/people/{person.public_id}").status_code == 404


# --- where somebody starts -------------------------------------------------


@pytest.mark.django_db
def test_start_says_when_somebody_is_new_here(client, alice):
    """Not a stored flag, deliberately: a flag says *has been shown the tour*
    and this asks *has anything happened*. Somebody who signed up, wrote
    nothing and came back a month later is new here again, which is true."""
    client.force_login(alice)

    response = client.get("/api/v1/start")

    assert response.status_code == 200
    assert response.json()["new_here"] is True


@pytest.mark.django_db
def test_start_explains_only_what_the_material_has_earned(client, alice):
    """A concept explained before it exists is a word attached to nothing, so
    a fresh account is told about nothing at all."""
    client.force_login(alice)

    assert client.get("/api/v1/start").json()["concepts"] == []


@pytest.mark.django_db
def test_a_concept_arrives_with_the_evidence_for_it(client, alice):
    """`Concept.evidence` is the reason this is a read rather than static
    copy: a concept with no evidence is not explained at all.

    An Area rather than a note, because the six invented words are the *task*
    core's -- Area, Project, checklist step, focus, week reviewed. Capturing a
    node earns none of them, which this test asserted by accident first and is
    worth stating on purpose: `/mind/start/` explains Clarice's vocabulary,
    not the knowledge core's.
    """
    from lists.models import List

    List.objects.create(owner=alice, title="Programming")
    client.force_login(alice)

    concepts = client.get("/api/v1/start").json()["concepts"]

    assert concepts, "writing something earned no concept at all"
    assert all(each["name"] and each["means"] and each["evidence"] for each in concepts)


@pytest.mark.django_db
def test_both_need_a_session(client, alice):
    person = a_person(alice)

    assert client.get("/api/v1/start").status_code == 401
    assert client.get(f"/api/v1/people/{person.public_id}").status_code == 401
