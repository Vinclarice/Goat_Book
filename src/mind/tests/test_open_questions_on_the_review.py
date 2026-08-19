"""Open questions on the review page — increment 1, finished.

The read shipped in `a302dee`, both decisions in `6196b99`, the context in
`4093610`. This is the surface, and it is the last piece.

**Loose ends sit above proposals, and that is not a layout preference.** A
proposal asks *is this connection real?* — the system claiming something. A
loose end asks *did you settle this?* — a fact about the person's own corpus
with no claim in it at all. The second is cheaper to answer and more often
worth answering, and burying it under a queue of guesses is how it goes unread.

**Showing a question surfaces nothing.** `/mind/review/` stamps
`first_surfaced_at` on the proposals it displays, because a proposal shown
without starting its window makes silence meaningless. A question is not a
proposal: nothing expires, nothing ripens, and leaving it alone is a permanent
and costless answer. So this section must not touch that machinery, and a test
holds it — the two live on one page and would be easy to conflate.
"""

from datetime import datetime, timedelta, timezone as dt_timezone

import pytest
from django.utils import timezone

from mind import services
from mind.models import ConnectionHypothesis, Facet, FacetKind, NodeSource

pytestmark = pytest.mark.django_db

UTC = dt_timezone.utc
QUESTION = "Which payment provider should we use for the booking form?"


@pytest.fixture
def signed_in(client, owner):
    client.force_login(owner)
    return client


def _capture(owner, content, days_ago):
    return services.capture(
        owner,
        content=content,
        captured_at=timezone.now() - timedelta(days=days_ago),
        source=NodeSource.WEB,
        actor="v",
    )


@pytest.fixture
def question(owner):
    for index in range(8):
        _capture(owner, f"Note {index}: the garden, the weather, a walk.", 40 + index)
    return _capture(owner, QUESTION, 12)


def test_an_open_question_appears_on_the_review(signed_in, question):
    body = signed_in.get("/mind/review/").content.decode()

    assert QUESTION in body


def test_it_says_how_long_it_has_been_open(signed_in, question):
    body = signed_in.get("/mind/review/").content.decode()

    assert "12 days" in body


def test_it_says_when_a_question_came_back(signed_in, owner, question):
    _capture(owner, "Still undecided on the payment provider for the booking form.", 4)

    body = signed_in.get("/mind/review/").content.decode()

    assert "1 later note" in body


def test_a_returning_question_shows_the_words_that_matched(signed_in, owner, question):
    """The evidence, not just the count.

    "Mentioned again once" is a claim; the terms underneath are what let
    somebody disagree with it, which is the same rule every proposal on this
    page already follows.
    """
    _capture(owner, "Still undecided on the payment provider for the booking form.", 4)

    body = signed_in.get("/mind/review/").content.decode()

    assert "appear in almost none of your other notes" in body


def test_a_question_nobody_returned_to_says_nothing_about_mentions(
    signed_in, question
):
    """Silence rather than "0 later notes".

    A zero invites a conclusion from nothing, and most questions will have one
    -- a page that renders it for every row is a page of noughts.
    """
    body = signed_in.get("/mind/review/").content.decode()

    assert "later note" not in body


def test_settling_it_takes_it_off_the_page(signed_in, question):
    signed_in.post(f"/mind/questions/{question.public_id}/resolve/")

    assert QUESTION not in signed_in.get("/mind/review/").content.decode()


def test_settling_it_records_an_explicit_decision(signed_in, question):
    signed_in.post(f"/mind/questions/{question.public_id}/resolve/")

    facet = question.facets.get(kind=FacetKind.EPISTEMIC)
    assert facet.data["status"] == "resolved"


def test_saying_it_was_never_a_question_takes_it_off_too(signed_in, question):
    signed_in.post(f"/mind/questions/{question.public_id}/dismiss/")

    facet = question.facets.get(kind=FacetKind.EPISTEMIC)
    assert facet.data["status"] == "not_a_question"


def test_showing_a_question_surfaces_no_proposal(signed_in, owner, question):
    """The two mechanics share a page and must not share behaviour.

    Loading this page starts the review window on every *proposal* it shows,
    deliberately. A question has no window to start, and a section that
    accidentally marked one would make silence mean something it does not.
    """
    a = _capture(owner, "The venue was lovely in April.", 30)
    b = _capture(owner, "We saw the venue again in April.", 25)
    hypothesis = services.propose_hypothesis(
        owner,
        detector="dormant_thread",
        citations=[
            services.Citation(node=a, reason="shares venue"),
            services.Citation(node=b, reason="shares venue"),
        ],
        confidence=0.5,
        label="shares: venue",
        index_version="fts-v1",
        now=timezone.now(),
        actor="v",
    )
    signed_in.post(f"/mind/questions/{question.public_id}/dismiss/")

    hypothesis.refresh_from_db()
    assert hypothesis.first_surfaced_at is None


def test_a_question_that_is_not_yours_is_not_answerable(
    signed_in, other_owner
):
    theirs = services.capture(
        other_owner,
        content=QUESTION,
        captured_at=timezone.now() - timedelta(days=12),
        source=NodeSource.WEB,
        actor="someone-else",
    )

    response = signed_in.post(f"/mind/questions/{theirs.public_id}/resolve/")

    assert response.status_code in (302, 404)
    assert not theirs.facets.filter(kind=FacetKind.EPISTEMIC).exists()


def test_an_empty_review_says_so_without_a_question_heading(signed_in, owner):
    """No heading over nothing.

    The proposals half already refuses this -- an empty review is the normal
    state, not a failure -- and a loose-ends heading with nothing under it
    would teach somebody to skip that part of the page permanently.
    """
    body = signed_in.get("/mind/review/").content.decode()

    assert "Still unanswered" not in body
