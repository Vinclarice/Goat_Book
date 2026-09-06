"""Reading the concept layer over `/api/v1/` — app-overhaul-plan.md increment 2a.

The plan's rule 2 is that detail *opens* rather than navigates, and increment 2
turns the knowledge core's ten browsing surfaces into panels. Splitting it in
two was forced by what `mind/api_v1.py` actually is: **one GET and seven
POSTs**, the GET being search. Every one of those surfaces is a Django view
reading models directly, so there was nothing for a panel to consume.

2a is the reads, and this is the first pair. **Pure addition** — `/mind/concepts/`
and `/mind/concepts/<id>/` keep their templates and keep working, and nothing
in the SPA consumes these yet. That is deliberate: an increment that only adds
cannot break what is running.

**Session-only.** `mind/api_v1.py` is create-only for a bearer token and stays
that way, which `test_api_auth_surface.py` holds. A phone has no concept
browser and a token in an Android keystore outlives a session by ninety days.

**The endpoints mirror the views rather than improving on them.** Where the
page reads `queries.concept_candidates` and attaches three sentences of
evidence, so does this — the point of 2a is that 2b can retire a template
without anybody having to ask whether the panel shows the same thing.
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


def a_confirmed_name(owner, label="Indonesian", kind=ConceptType.ACTIVITY):
    return ConceptCandidate.objects.create(
        owner=owner,
        label=label,
        concept_type=kind,
        confirmed_at=timezone.now(),
    )


def a_note(owner, content, *, days_ago=0):
    return services.capture(
        owner,
        content=content,
        captured_at=timezone.now() - timedelta(days=days_ago),
        source=NodeSource.WEB,
        actor=owner.get_username(),
    )


def a_mention(node, concept, *, confirmed=True):
    """The row that makes a note *about* a concept.

    Built explicitly rather than left to extraction, because the gravity gate
    is what this reads through: `queries.concept_candidates` wants three
    mentions over more than a day, and a test that relied on the extractor
    finding a word would be testing the extractor.
    """
    return Mention.objects.create(
        node=node,
        concept=concept,
        origin=InferenceOrigin.EXPLICIT,
        index_version="rules-v1",
        confirmed_at=timezone.now() if confirmed else None,
    )


def a_name_with_gravity(owner, label="Indonesian"):
    """An unconfirmed candidate that has earned its way onto the queue.

    Three mentions across sixty days -- `MIN_MENTIONS_TO_ASK` is 3 and
    `MIN_SPAN_TO_ASK` is a day, and the span is measured as a stretch rather
    than as distinct calendar dates on purpose.
    """
    concept = ConceptCandidate.objects.create(
        owner=owner, label=label, concept_type=ConceptType.UNKNOWN
    )
    for days_ago in (60, 50, 40):
        a_mention(
            a_note(owner, f"{label} again, and more of it.", days_ago=days_ago),
            concept,
        )
    return concept


@pytest.mark.django_db
def test_the_index_answers_with_the_names_already_confirmed(client, alice):
    a_confirmed_name(alice, "Indonesian")
    client.force_login(alice)

    response = client.get("/api/v1/concepts")

    assert response.status_code == 200
    labels = [each["label"] for each in response.json()["confirmed"]]
    assert "Indonesian" in labels


@pytest.mark.django_db
def test_the_index_is_scoped_to_its_owner(client, alice, bob):
    """The same scoping the page has, asserted rather than assumed.

    Every lookup in this module is owner-filtered in the query rather than
    checked afterwards -- `_concept_or_404` is the existing example -- and a
    read endpoint is where that stops being visible in a template's context.
    """
    a_confirmed_name(bob, "Bob's private topic")
    client.force_login(alice)

    response = client.get("/api/v1/concepts")

    labels = [each["label"] for each in response.json()["confirmed"]]
    assert "Bob's private topic" not in labels


@pytest.mark.django_db
def test_a_candidate_carries_the_evidence_for_it(client, alice):
    """"Indonesian, 4 mentions" asks somebody to take the system's word for it.

    The page attaches three sentences to every candidate for exactly that
    reason, and the docstring on `views.concepts` calls it the same rule the
    review's span citations follow. A panel that showed the count without the
    sentences would be a quieter surface, not the same one.
    """
    a_name_with_gravity(alice)
    client.force_login(alice)

    response = client.get("/api/v1/concepts")

    candidates = response.json()["candidates"]
    assert candidates, "a name with gravity did not reach the queue"
    assert any(each["evidence"] for each in candidates)


@pytest.mark.django_db
def test_one_concept_answers_with_the_material_it_gathered(client, alice):
    """The payoff the concept layer exists for, per `views.concept`: not a
    search result but the material itself, gathered without anybody having
    filed it anywhere."""
    concept = a_confirmed_name(alice, "Indonesian")
    a_mention(a_note(alice, "Practised Indonesian again this morning."), concept)
    client.force_login(alice)

    response = client.get(f"/api/v1/concepts/{concept.public_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["concept"]["label"] == "Indonesian"
    assert any("Indonesian" in node["body"] for node in body["nodes"])


@pytest.mark.django_db
def test_one_concept_offers_every_kind_it_could_be(client, alice):
    """All seven, not a curated four.

    `views.concept` is explicit: the set is small and closed, and offering four
    of seven leaves three unreachable in exactly the way all seven were until
    somebody noticed.
    """
    concept = a_confirmed_name(alice)
    client.force_login(alice)

    response = client.get(f"/api/v1/concepts/{concept.public_id}")

    assert len(response.json()["kinds"]) == len(ConceptType.choices)


@pytest.mark.django_db
def test_a_person_says_so(client, alice):
    """`is_a_person` is a separate flag on the page rather than a comparison
    the template makes, because a person's page offers different things."""
    concept = a_confirmed_name(alice, "Maya", kind=ConceptType.PERSON)
    client.force_login(alice)

    response = client.get(f"/api/v1/concepts/{concept.public_id}")

    assert response.json()["is_a_person"] is True


@pytest.mark.django_db
def test_another_owners_concept_is_not_found(client, alice, bob):
    concept = a_confirmed_name(bob)
    client.force_login(alice)

    response = client.get(f"/api/v1/concepts/{concept.public_id}")

    assert response.status_code == 404


@pytest.mark.django_db
def test_reading_concepts_needs_a_session(client, alice):
    """Not a bearer token, and this is the assertion that keeps it that way
    if somebody widens the router's default later."""
    concept = a_confirmed_name(alice)

    assert client.get("/api/v1/concepts").status_code == 401
    assert (
        client.get(f"/api/v1/concepts/{concept.public_id}").status_code == 401
    )
