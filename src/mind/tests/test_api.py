"""The HTTP contract.

Thin layer, so these tests are mostly about the two things HTTP can get wrong that the
service layer cannot: **who is asking**, and **whether a retry costs anything**.

One endpoint deliberately breaks an HTTP convention, and it has its own test: `GET
/review` mutates. Separating read from surfacing would let a proposal be displayed
without its review window starting, and then silence would stop meaning anything.
"""

import json
import uuid as uuid_module
from datetime import datetime, timezone as dt_timezone

import pytest
from django.contrib.auth import get_user_model

from mind import services
from mind.models import ConnectionHypothesis, Edge, Node, NodeSource

pytestmark = pytest.mark.django_db

UTC = dt_timezone.utc
JAN = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)


@pytest.fixture
def signed_in(client, owner):
    owner.set_password("pw")
    owner.save()
    client.force_login(owner)
    return client


def _post(client, url, payload):
    return client.post(url, data=json.dumps(payload), content_type="application/json")


def _hypothesis(owner, *, detector="dormant_thread", confidence=0.7):
    a = services.capture(
        owner, content="first thought", captured_at=JAN,
        source=NodeSource.WEB, actor="vince",
    )
    b = services.capture(
        owner, content="second thought", captured_at=JAN,
        source=NodeSource.WEB, actor="vince",
    )
    return services.propose_hypothesis(
        owner,
        detector=detector,
        citations=[
            services.Citation(node=a, span=(0, 5), reason="the note just captured"),
            services.Citation(node=b, span=(0, 6), reason="written earlier"),
        ],
        confidence=confidence,
        label="shares: something",
        index_version="test",
        now=JAN,
    )


# ---------------------------------------------------------------------------
# Who is asking
# ---------------------------------------------------------------------------


def test_everything_requires_signing_in(client):
    for method, url in (
        ("get", "/mind/api/v1/captures"),
        ("get", "/mind/api/v1/review"),
        ("get", "/mind/api/v1/summary"),
        ("get", "/mind/api/v1/search?q=x"),
    ):
        response = getattr(client, method)(url)
        assert response.status_code in (401, 403), url


def test_another_persons_note_is_not_found_rather_than_forbidden(signed_in, other_owner):
    """Indistinguishable from a wrong id, which is what stops the API confirming
    that someone else's note exists."""
    theirs = services.capture(
        other_owner, content="theirs", captured_at=JAN,
        source=NodeSource.WEB, actor="them",
    )
    assert signed_in.get(f"/mind/api/v1/captures/{theirs.public_id}").status_code == 404


def test_listing_is_owner_scoped(signed_in, owner, other_owner):
    services.capture(
        owner, content="mine", captured_at=JAN, source=NodeSource.WEB, actor="v"
    )
    services.capture(
        other_owner, content="theirs", captured_at=JAN, source=NodeSource.WEB, actor="t"
    )

    bodies = [n["body"] for n in signed_in.get("/mind/api/v1/captures").json()]
    assert bodies == ["mine"]


# ---------------------------------------------------------------------------
# Capture, and retries
# ---------------------------------------------------------------------------


def test_capturing_returns_201_and_the_node(signed_in):
    response = _post(signed_in, "/mind/api/v1/captures", {"content": "a thought"})

    assert response.status_code == 201
    body = response.json()
    assert body["body"] == "a thought"
    assert body["source"] == NodeSource.API
    assert Node.objects.count() == 1


def test_a_retry_with_the_same_id_returns_200_and_no_second_node(signed_in):
    """The reason the column exists: a phone that never saw its request succeed
    must not create a duplicate by asking again."""
    public_id = str(uuid_module.uuid4())
    first = _post(signed_in, "/mind/api/v1/captures", {"content": "a thought", "public_id": public_id})
    second = _post(signed_in, "/mind/api/v1/captures", {"content": "a thought", "public_id": public_id})

    assert (first.status_code, second.status_code) == (201, 200)
    assert first.json()["public_id"] == second.json()["public_id"]
    assert Node.objects.count() == 1


def test_claiming_another_persons_public_id_is_a_permanent_fault(signed_in, other_owner):
    """400 rather than 409, and the reason is the offline client.

    A queued client treats anything that is not 400/401/403 as "retry later", so 409 —
    correct as HTTP semantics — meant a capture the server will never accept and a phone
    that keeps asking. 400 tells it to stop.
    """
    theirs = services.capture(
        other_owner, content="theirs", captured_at=JAN,
        source=NodeSource.WEB, actor="them",
    )
    response = _post(
        signed_in, "/mind/api/v1/captures", {"content": "mine", "public_id": str(theirs.public_id)}
    )
    assert response.status_code == 400


def test_an_offline_capture_keeps_the_time_it_happened(signed_in):
    """Without this every queued capture arrives stamped with the moment the network
    came back, which is exactly the error the import path exists to prevent."""
    response = _post(
        signed_in,
        "/mind/api/v1/captures",
        {"content": "written on the train", "captured_at": "2026-02-03T08:15:00+00:00"},
    )
    assert response.status_code == 201
    assert response.json()["captured_at"].startswith("2026-02-03T08:15")


def test_an_empty_capture_is_refused(signed_in):
    """400, not 422 — see the test above. An empty body is never going to be accepted,
    so the client has to be told to stop rather than to try again."""
    assert _post(signed_in, "/mind/api/v1/captures", {"content": "   "}).status_code == 400


def test_revising_keeps_the_original(signed_in):
    created = _post(signed_in, "/mind/api/v1/captures", {"content": "as first written"}).json()
    revised = _post(
        signed_in,
        f"/mind/api/v1/captures/{created['public_id']}/revisions",
        {"body": "rewritten"},
    ).json()

    assert revised["body"] == "rewritten"
    assert revised["original_content"] == "as first written"
    assert revised["revisions"] == 1


def test_deleting_removes_it_from_listings(signed_in):
    created = _post(signed_in, "/mind/api/v1/captures", {"content": "a thought"}).json()
    assert signed_in.delete(f"/mind/api/v1/captures/{created['public_id']}").status_code == 204
    assert signed_in.get("/mind/api/v1/captures").json() == []


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------


def test_search_finds_the_original_wording_after_a_revision(signed_in):
    """A thought stays findable by the words it was first written in."""
    created = _post(signed_in, "/mind/api/v1/captures", {"content": "the furnace filter"}).json()
    _post(
        signed_in,
        f"/mind/api/v1/captures/{created['public_id']}/revisions",
        {"body": "the dusty air upstairs"},
    )

    assert len(signed_in.get("/mind/api/v1/search?q=furnace").json()) == 1
    assert len(signed_in.get("/mind/api/v1/search?q=dusty").json()) == 1


def test_an_empty_query_returns_nothing_rather_than_everything(signed_in):
    _post(signed_in, "/mind/api/v1/captures", {"content": "a thought"})
    assert signed_in.get("/mind/api/v1/search?q=%20").json() == []


def test_a_recorded_miss_is_the_strongest_retrieval_signal(signed_in, owner):
    response = _post(signed_in, "/mind/api/v1/misses", {"query_text": "that thing about delay"})
    assert response.status_code == 201
    assert owner.misses.count() == 1


# ---------------------------------------------------------------------------
# Review — where the HTTP idiom loses to the invariant
# ---------------------------------------------------------------------------


def test_getting_the_review_marks_what_it_returns_as_shown(signed_in, owner):
    """A pure read here would let a proposal be displayed while `first_surfaced_at`
    stayed null, after which inaction is indistinguishable from never having seen it."""
    hypothesis = _hypothesis(owner)
    assert hypothesis.first_surfaced_at is None

    body = signed_in.get("/mind/api/v1/review").json()

    hypothesis.refresh_from_db()
    assert [p["public_id"] for p in body] == [str(hypothesis.public_id)]
    assert hypothesis.first_surfaced_at is not None
    assert hypothesis.review_window_expires_at is not None


def test_the_pending_count_does_not_surface_anything(signed_in, owner):
    """Safe to poll precisely because it returns a number and no content."""
    hypothesis = _hypothesis(owner)
    assert signed_in.get("/mind/api/v1/review/pending").json() == {"pending": 1}

    hypothesis.refresh_from_db()
    assert hypothesis.first_surfaced_at is None


def test_a_proposal_cites_the_span_not_the_whole_note(signed_in, owner):
    _hypothesis(owner)
    [proposal] = signed_in.get("/mind/api/v1/review").json()

    quotes = [c["quote"] for c in proposal["citations"]]
    assert "first" in quotes or "second" in quotes
    assert all(len(q) <= len("second thought") for q in quotes)
    assert sum(1 for c in proposal["citations"] if c["is_source"]) == 1


def test_confirming_creates_the_edge(signed_in, owner):
    hypothesis = _hypothesis(owner)
    response = signed_in.post(f"/mind/api/v1/review/{hypothesis.public_id}/confirm")

    assert response.status_code == 200
    assert response.json() == {"confirmed": True, "edges": 1}
    assert Edge.objects.count() == 1


def test_confirming_twice_conflicts_rather_than_double_promoting(signed_in, owner):
    hypothesis = _hypothesis(owner)
    signed_in.post(f"/mind/api/v1/review/{hypothesis.public_id}/confirm")
    again = signed_in.post(f"/mind/api/v1/review/{hypothesis.public_id}/confirm")

    assert again.status_code == 409
    assert Edge.objects.count() == 1


def test_dismissing_is_permanent(signed_in, owner):
    hypothesis = _hypothesis(owner)
    assert signed_in.post(f"/mind/api/v1/review/{hypothesis.public_id}/dismiss").status_code == 200
    assert signed_in.get("/mind/api/v1/review").json() == []
    assert Edge.objects.count() == 0


def test_another_persons_proposal_is_not_found(signed_in, other_owner):
    theirs = _hypothesis(other_owner)
    assert signed_in.post(f"/mind/api/v1/review/{theirs.public_id}/confirm").status_code == 404


def test_marking_a_note_reviewed_returns_its_new_schedule(signed_in):
    created = _post(signed_in, "/mind/api/v1/captures", {"content": "worth keeping around"}).json()
    body = signed_in.post(f"/mind/api/v1/captures/{created['public_id']}/reviewed").json()

    assert body["reviewed"] is True
    assert body["reviews"] == 1
    assert body["due_at"] is not None


def test_burying_stretches_the_schedule_harder_than_keeping(signed_in):
    kept = _post(signed_in, "/mind/api/v1/captures", {"content": "note one here"}).json()
    buried = _post(signed_in, "/mind/api/v1/captures", {"content": "note two here"}).json()

    a = signed_in.post(f"/mind/api/v1/captures/{kept['public_id']}/reviewed").json()
    b = signed_in.post(
        f"/mind/api/v1/captures/{buried['public_id']}/reviewed?buried=true"
    ).json()

    assert b["due_at"] > a["due_at"]


# ---------------------------------------------------------------------------
# Measurement
# ---------------------------------------------------------------------------


def test_the_summary_reports_no_evidence_as_null_not_zero(signed_in, owner):
    """Zero would read as "wrong every time"; the two call for opposite responses."""
    _hypothesis(owner)
    body = signed_in.get("/mind/api/v1/summary").json()

    [detector] = body["detectors"]
    assert detector["proposed"] == 1
    assert detector["accept_rate"] is None
    assert len(body["gate"]) == 3


def test_the_openapi_schema_is_generated(signed_in):
    """The typed contract a client would be generated from."""
    schema = signed_in.get("/mind/api/v1/openapi.json").json()
    assert schema["info"]["title"] == "Second Mind"
    assert "/mind/api/v1/captures" in schema["paths"]
    assert "/mind/api/v1/review" in schema["paths"]
