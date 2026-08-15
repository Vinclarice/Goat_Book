"""Capture reads a commitment, and one tap accepts it.

The two halves that make a facet reachable. Without the parser nothing ever
proposes an actionable facet, and without the surface nothing can confirm one --
either alone leaves the merger's payoff sitting behind a management command.

**Capture is unchanged as an experience.** Still one box, still nothing to
classify, still no decision at the moment of entry. The proposal appears
*afterwards*, on the way back, where ignoring it is free and accepting it is one
tap. A parser that opened a dialogue would have broken the product's first
principle to save somebody four seconds.
"""

from datetime import date, datetime, timezone as dt_timezone

import pytest
from django.urls import reverse

from lists.models import Item, List
from mind import services
from mind.models import Facet, FacetKind, InferenceOrigin, NodeSource

pytestmark = pytest.mark.django_db

UTC = dt_timezone.utc
NOW = datetime(2026, 6, 10, 9, 0, tzinfo=UTC)  # a Wednesday


# ---------------------------------------------------------------------------
# The proposal, made at capture
# ---------------------------------------------------------------------------


def test_capturing_something_with_a_date_in_it_proposes_a_commitment(owner):
    node = services.capture(owner, content="Dentist on 2026-06-24", captured_at=NOW,
                            source=NodeSource.WEB, actor="vince")

    facet = Facet.objects.get(node=node, kind=FacetKind.ACTIONABLE)
    assert facet.data["due_date"] == "2026-06-24"


def test_the_proposal_is_only_a_proposal(owner):
    """No task yet. The whole reason the actionable facet is exempt from
    soft-apply is that a commitment nobody agreed to is worse than none."""
    services.capture(owner, content="Dentist on 2026-06-24", captured_at=NOW,
                     source=NodeSource.WEB, actor="vince")

    assert Item.objects.count() == 0


def test_it_is_inferred_rather_than_explicit(owner):
    node = services.capture(owner, content="Dentist on 2026-06-24", captured_at=NOW,
                            source=NodeSource.WEB, actor="vince")

    assert Facet.objects.get(node=node).origin == InferenceOrigin.INFERRED


def test_the_proposal_quotes_what_it_read(owner):
    node = services.capture(owner, content="pay rent on Friday", captured_at=NOW,
                            source=NodeSource.WEB, actor="vince")

    assert "friday" in Facet.objects.get(node=node).reason.lower()


def test_a_recurrence_is_carried_into_the_proposal(owner):
    node = services.capture(owner, content="change the furnace filter every month",
                            captured_at=NOW, source=NodeSource.WEB, actor="vince")

    assert Facet.objects.get(node=node).data["recurrence"] == "monthly"


def test_an_ordinary_thought_proposes_nothing(owner):
    """Silence is the common case and has to stay free. A capture surface that
    guessed at every note would train people to ignore it."""
    services.capture(owner, content="I like lucid cars", captured_at=NOW,
                     source=NodeSource.WEB, actor="vince")

    assert Facet.objects.count() == 0


def test_the_date_is_read_against_when_it_was_captured(owner):
    """Not against now. An import carries its original timestamp, and reading
    "tomorrow" in a 2019 note as tomorrow-from-today would put a date nobody
    ever meant into next week."""
    node = services.capture(owner, content="dentist tomorrow", captured_at=NOW,
                            source=NodeSource.WEB, actor="vince")

    assert Facet.objects.get(node=node).data["due_date"] == "2026-06-11"


def test_a_retried_capture_does_not_propose_twice(owner):
    """Same node, so the same facet -- `propose_facet` is get_or_create on the
    live one. A retry that doubled the proposal would show the same suggestion
    twice on the way back."""
    first = services.capture(owner, content="Dentist on 2026-06-24", captured_at=NOW,
                             source=NodeSource.WEB, actor="vince")
    services.capture(owner, content="Dentist on 2026-06-24", captured_at=NOW,
                     source=NodeSource.WEB, actor="vince", public_id=first.public_id)

    assert Facet.objects.count() == 1


# ---------------------------------------------------------------------------
# The tap
# ---------------------------------------------------------------------------


@pytest.fixture
def client_in(client, owner):
    client.force_login(owner)
    return client


@pytest.fixture
def proposed(owner):
    return services.capture(owner, content="Dentist on 2026-06-24", captured_at=NOW,
                            source=NodeSource.WEB, actor="vince")


def test_the_capture_page_offers_what_it_read(client_in, proposed):
    response = client_in.get(reverse("capture"))

    assert b"Looks like a commitment" in response.content
    assert b"due 2026-06-24" in response.content


def test_accepting_makes_the_task(client_in, owner, proposed):
    facet = Facet.objects.get(node=proposed)

    client_in.post(reverse("accept_commitment", args=[facet.node.public_id]))

    task = Item.objects.get()
    assert task.text == "Dentist on 2026-06-24"
    assert task.due_date == date(2026, 6, 24)
    assert task.list is None
    assert task.owner == owner


def test_accepting_asks_no_second_question(client_in, proposed):
    """One tap, and the redirect goes back to capture rather than to a form.
    Being sent somewhere to choose an Area is the toll this removes."""
    response = client_in.post(
        reverse("accept_commitment", args=[proposed.public_id])
    )

    assert response.status_code == 302
    assert response["Location"] == reverse("capture")


def test_declining_retires_the_proposal_without_making_anything(client_in, proposed):
    client_in.post(
        reverse("accept_commitment", args=[proposed.public_id]), {"action": "dismiss"}
    )

    assert Item.objects.count() == 0
    assert Facet.objects.get(node=proposed).retired_at is not None


def test_a_declined_proposal_stops_being_offered(client_in, proposed):
    client_in.post(
        reverse("accept_commitment", args=[proposed.public_id]), {"action": "dismiss"}
    )

    response = client_in.get(reverse("capture"))
    # Not the date, which stays visible in the note itself forever -- the offer.
    assert b"Looks like a commitment" not in response.content


def test_an_accepted_proposal_stops_being_offered(client_in, proposed):
    client_in.post(reverse("accept_commitment", args=[proposed.public_id]))

    response = client_in.get(reverse("capture"))
    # Not the date, which stays visible in the note itself forever -- the offer.
    assert b"Looks like a commitment" not in response.content


def test_somebody_elses_proposal_cannot_be_accepted(client, other_owner, proposed):
    client.force_login(other_owner)

    client.post(reverse("accept_commitment", args=[proposed.public_id]))

    assert Item.objects.count() == 0


def test_tapping_twice_does_not_make_two_tasks(client_in, proposed):
    """A double tap on a phone, or a back-button re-post."""
    client_in.post(reverse("accept_commitment", args=[proposed.public_id]))
    client_in.post(reverse("accept_commitment", args=[proposed.public_id]))

    assert Item.objects.count() == 1
