"""Answering a question from the other core's review — increment 6.

The weekly planning session shows questions that bear on the outcomes somebody
chose, and the plan's whole complaint about v1's review is that it could only
point at them: *"Decide them in Second Mind"*. These two endpoints are how it
stops pointing.

**They call this core's own services**, so the epistemic facet, the activity
event and the actor are recorded exactly as when the same decision is made from
`/mind/review/`. Two surfaces, one decision path — which is what stops "act in
place" becoming a second, quieter way for the graph to change.

**Session-only.** `mind/api_v1.py` is create-only for a bearer token and stays
that way; a phone exists to get a thought out of your head, not to triage.
`clarice/tests/test_api_auth_surface.py` is what holds that, and it passed
unchanged when these were added.

**Safe from a second surface because a question has no review window.** A
proposal is stamped with `first_surfaced_at` when it is shown, so *where* it is
shown is a real question; a question has nothing that expires or ripens, and
leaving it alone is a permanent and costless answer. That asymmetry is why
increment 6 did not have to settle where the ritual lives.
"""

import uuid

import pytest
from django.test import Client
from django.utils import timezone

from accounts.models import User
from mind import services
from mind.models import FacetKind, NodeSource

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


def a_question(owner, content="Which booking form should the venue use?"):
    return services.capture(
        owner,
        content=content,
        captured_at=timezone.now(),
        source=NodeSource.WEB,
        actor=owner.get_username(),
    )


def epistemic(node):
    return node.facets.filter(kind=FacetKind.EPISTEMIC, retired_at__isnull=True)


@pytest.mark.django_db
def test_answering_one_records_it_the_way_the_other_surface_does(client, alice):
    node = a_question(alice)
    client.force_login(alice)

    response = client.post(f"/api/v1/questions/{node.public_id}/answered")

    assert response.status_code == 200
    assert epistemic(node).count() == 1


@pytest.mark.django_db
def test_saying_it_was_never_a_question_is_a_different_fact(client, alice):
    """Deliberately not the same call. This is the only correction the
    question heuristic will ever get, and collapsing the two would spend that
    signal to save a status value."""
    node = a_question(alice)
    client.force_login(alice)

    client.post(f"/api/v1/questions/{node.public_id}/not-a-question")

    statuses = [facet.data["status"] for facet in epistemic(node)]
    assert statuses == [services.NOT_A_QUESTION]


@pytest.mark.django_db
def test_answering_and_dismissing_do_not_produce_the_same_record(client, alice):
    answered = a_question(alice, "Which form?")
    never = a_question(alice, "Why does anybody bother?")
    client.force_login(alice)

    client.post(f"/api/v1/questions/{answered.public_id}/answered")
    client.post(f"/api/v1/questions/{never.public_id}/not-a-question")

    assert [f.data["status"] for f in epistemic(answered)] != [
        f.data["status"] for f in epistemic(never)
    ]


@pytest.mark.django_db
def test_one_person_cannot_answer_another_s_question(client, alice, bob):
    node = a_question(bob)
    client.force_login(alice)

    response = client.post(f"/api/v1/questions/{node.public_id}/answered")

    assert response.status_code == 404
    assert not epistemic(node).exists()


@pytest.mark.django_db
def test_a_question_that_does_not_exist_is_a_404(client, alice):
    client.force_login(alice)

    response = client.post(f"/api/v1/questions/{uuid.uuid4()}/answered")

    assert response.status_code == 404


@pytest.mark.django_db
def test_a_deleted_note_cannot_be_answered(client, alice):
    """The lookup asks for a live node. Answering something already gone would
    write a facet nothing can reach."""
    node = a_question(alice)
    node.deleted_at = timezone.now()
    node.save(update_fields=["deleted_at"])
    client.force_login(alice)

    response = client.post(f"/api/v1/questions/{node.public_id}/answered")

    assert response.status_code == 404


@pytest.mark.django_db
def test_a_stranger_is_refused(client, alice):
    node = a_question(alice)

    response = client.post(f"/api/v1/questions/{node.public_id}/answered")

    assert response.status_code == 401
    assert not epistemic(node).exists()
