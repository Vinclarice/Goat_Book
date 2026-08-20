"""Answering the *rest* of the review's pile in place — S7's remaining half.

Increment 6 gave the questions two verbs and stopped the review pointing at
`/mind/` for them. It left the other two rows: a commitment proposed from a
capture and never accepted, and a name that has recurred enough to be worth
asking about. `product-stories.md` S7 says the remaining half "needs no new
decision, only the same treatment", and it was right — but the reason it is
right is worth checking rather than assuming.

**The asymmetry that made increment 6 safe holds here too.** Its argument was
that a question carries no review window — nothing expires, nothing ripens —
where a *proposal* is stamped when it is shown, so answering one elsewhere
cannot disturb the machinery that interprets silence. Checked at the schema
rather than inferred: `first_surfaced_at` belongs to `ConnectionHypothesis`
alone. `Facet` has no window (the actionable facet is, in the review payload's
own words, "the one proposal type with no expiry") and neither does
`ConceptCandidate`. So D6 — where the ritual lives — stays undisturbed by
these two as well.

**They call this core's own services**, so the facet, the concept, the activity
event and the actor are recorded exactly as when the same decision is made from
`/mind/`. Two surfaces, one decision path.

**Session-only**, like the question verbs: `mind/api_v1.py` is create-only for
a bearer token and stays that way.
"""

import pytest
from django.test import Client
from django.utils import timezone

from accounts.models import User
from mind import services
from mind.models import ConceptCandidate, ConceptType, FacetKind, NodeSource

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


def a_proposed_commitment(owner, content="Call the dentist tomorrow"):
    """A capture the commitment parser reads an actionable facet out of.

    Through `capture` rather than by building the facet by hand, so the test
    exercises the same row the review actually shows -- `_propose_any_commitment`
    runs on the live path.
    """
    node = services.capture(
        owner,
        content=content,
        captured_at=timezone.now(),
        source=NodeSource.WEB,
        actor=owner.get_username(),
    )
    return node.facets.filter(kind=FacetKind.ACTIONABLE).first()


def a_name_worth_confirming(owner, label="Maya"):
    return ConceptCandidate.objects.create(
        owner=owner, label=label, concept_type=ConceptType.UNKNOWN
    )


@pytest.mark.django_db
def test_accepting_a_commitment_makes_a_task_the_way_the_other_surface_does(
    client, alice
):
    facet = a_proposed_commitment(alice)
    client.force_login(alice)

    response = client.post(f"/api/v1/commitments/{facet.id}/accept")

    assert response.status_code == 200
    facet.refresh_from_db()
    assert facet.task_id is not None


@pytest.mark.django_db
def test_accepting_asks_no_filing_question(client, alice):
    """`confirm_actionable`'s whole point, inherited rather than re-decided:
    requiring an Area puts a filing decision at the moment somebody has
    already made a different one. The task is real without one."""
    facet = a_proposed_commitment(alice)
    client.force_login(alice)

    client.post(f"/api/v1/commitments/{facet.id}/accept")

    facet.refresh_from_db()
    assert facet.task.list_id is None
    assert facet.task.owner == alice


@pytest.mark.django_db
def test_dismissing_a_commitment_is_a_different_record_from_accepting_it(
    client, alice
):
    accepted = a_proposed_commitment(alice, "Call the dentist tomorrow")
    dismissed = a_proposed_commitment(alice, "Book the hotel tomorrow")
    client.force_login(alice)

    client.post(f"/api/v1/commitments/{accepted.id}/accept")
    client.post(f"/api/v1/commitments/{dismissed.id}/dismiss")

    accepted.refresh_from_db()
    dismissed.refresh_from_db()
    assert accepted.task_id is not None
    assert dismissed.task_id is None
    assert dismissed.retired_at is not None


@pytest.mark.django_db
def test_one_person_cannot_answer_anothers_commitment(client, alice, bob):
    """The isolation test principles.md asks of every owner-scoped,
    id-taking surface."""
    facet = a_proposed_commitment(bob)
    client.force_login(alice)

    response = client.post(f"/api/v1/commitments/{facet.id}/accept")

    assert response.status_code == 404
    facet.refresh_from_db()
    assert facet.task_id is None


@pytest.mark.django_db
def test_confirming_a_name_admits_it_to_the_trusted_corpus(client, alice):
    concept = a_name_worth_confirming(alice)
    client.force_login(alice)

    response = client.post(f"/api/v1/concepts/{concept.public_id}/confirm")

    assert response.status_code == 200
    concept.refresh_from_db()
    assert concept.confirmed_at is not None


@pytest.mark.django_db
def test_retiring_a_name_stops_it_being_proposed_again(client, alice):
    """Extraction runs after every batch of captures, so without a permanent
    record a rejected name would be re-proposed forever -- and answering it
    would be the ritual somebody stops trusting."""
    concept = a_name_worth_confirming(alice)
    client.force_login(alice)

    client.post(f"/api/v1/concepts/{concept.public_id}/retire")

    concept.refresh_from_db()
    assert concept.confirmed_at is None
    assert concept.retired_at is not None


@pytest.mark.django_db
def test_one_person_cannot_confirm_anothers_name(client, alice, bob):
    concept = a_name_worth_confirming(bob)
    client.force_login(alice)

    response = client.post(f"/api/v1/concepts/{concept.public_id}/confirm")

    assert response.status_code == 404
    concept.refresh_from_db()
    assert concept.confirmed_at is None


@pytest.mark.django_db
def test_all_four_refuse_a_signed_out_caller(client, alice):
    facet = a_proposed_commitment(alice)
    concept = a_name_worth_confirming(alice)

    for path in (
        f"/api/v1/commitments/{facet.id}/accept",
        f"/api/v1/commitments/{facet.id}/dismiss",
        f"/api/v1/concepts/{concept.public_id}/confirm",
        f"/api/v1/concepts/{concept.public_id}/retire",
    ):
        assert client.post(path).status_code == 401, path
