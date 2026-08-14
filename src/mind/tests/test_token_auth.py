"""Bearer auth and the mobile capture contract.

These test against the shape an existing Android client already speaks, taken from its
own source rather than guessed at: `POST /login` returning `token`/`username`/`email`,
`GET /me` with a Bearer header, and `POST /capture` with `Idempotency-Key` and a body of
`text`/`tags`. Field names that look arbitrary here are that client's, and matching them
is the entire point — a mismatch fails silently, which is the worst way for this to break.

Its disposition table is the contract these status codes have to satisfy:

    200, 201 -> delivered      400 -> rejected, stop
    401, 403 -> reconnect      anything else -> retry later

The last row is why 422 and 409 were wrong: a queued client retries them forever against
a server that will never accept them.
"""

import json
from datetime import datetime, timedelta, timezone as dt_timezone

import pytest
from django.utils import timezone

from mind import services
from mind.auth import resolve_token
from mind.models import ApiToken, Node, NodeSource

pytestmark = pytest.mark.django_db

UTC = dt_timezone.utc
UUID_A = "3f1b0c9e-1111-4a2b-8c3d-000000000001"
UUID_B = "3f1b0c9e-2222-4a2b-8c3d-000000000002"


@pytest.fixture
def credentials(owner):
    owner.set_password("correct-horse")
    owner.email = "v@example.com"
    owner.save()
    return {"username": owner.get_username(), "password": "correct-horse"}


@pytest.fixture
def bearer(owner):
    _, raw = ApiToken.issue(owner, label="Android")
    return {"HTTP_AUTHORIZATION": f"Bearer {raw}"}


def _json(client, url, payload, **extra):
    return client.post(
        url, data=json.dumps(payload), content_type="application/json", **extra
    )


# ---------------------------------------------------------------------------
# The token itself
# ---------------------------------------------------------------------------


def test_only_a_hash_is_stored(owner):
    """A leaked database must yield no working credentials."""
    token, raw = ApiToken.issue(owner, label="Android")

    assert raw.startswith(ApiToken.PREFIX)
    assert raw not in json.dumps(
        {"hash": token.token_hash, "prefix": token.display_prefix}
    )
    assert token.token_hash == ApiToken.hash_token(raw)
    assert len(token.token_hash) == 64


def test_the_plaintext_is_unrecoverable_afterwards(owner):
    token, raw = ApiToken.issue(owner, label="Android")
    reloaded = ApiToken.objects.get(pk=token.pk)

    assert not hasattr(reloaded, "raw")
    assert raw not in [reloaded.token_hash, reloaded.display_prefix, reloaded.label]


def test_two_tokens_are_never_the_same(owner):
    _, first = ApiToken.issue(owner)
    _, second = ApiToken.issue(owner)
    assert first != second


def test_a_valid_token_resolves(owner):
    token, raw = ApiToken.issue(owner)
    assert resolve_token(raw) == token


@pytest.mark.parametrize("bad", ["", "sm_nonsense", "Bearer sm_x", None])
def test_nonsense_does_not_resolve(owner, bad):
    ApiToken.issue(owner)
    assert resolve_token(bad) is None


def test_a_revoked_token_stops_working(owner):
    token, raw = ApiToken.issue(owner)
    token.revoked_at = timezone.now()
    token.save()

    assert resolve_token(raw) is None


def test_a_deactivated_account_stops_working(owner):
    _, raw = ApiToken.issue(owner)
    owner.is_active = False
    owner.save()

    assert resolve_token(raw) is None


def test_last_used_is_recorded_but_not_rewritten_every_request(owner):
    """Capture is the hot path; the field only has to answer "still in use"."""
    token, raw = ApiToken.issue(owner)
    assert token.last_used_at is None

    resolve_token(raw)
    token.refresh_from_db()
    first = token.last_used_at
    assert first is not None

    resolve_token(raw)
    token.refresh_from_db()
    assert token.last_used_at == first, "a second call within the window rewrites nothing"


def test_a_stale_last_used_is_refreshed(owner):
    token, raw = ApiToken.issue(owner)
    ApiToken.objects.filter(pk=token.pk).update(
        last_used_at=timezone.now() - timedelta(hours=2)
    )

    resolve_token(raw)
    token.refresh_from_db()
    assert timezone.now() - token.last_used_at < timedelta(minutes=1)


# ---------------------------------------------------------------------------
# POST /login
# ---------------------------------------------------------------------------


def test_login_returns_the_three_fields_the_client_parses(client, credentials, owner):
    response = _json(client, "/mind/api/v1/login", credentials)

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"token", "username", "email"}
    assert body["username"] == owner.get_username()
    assert body["email"] == "v@example.com"
    assert resolve_token(body["token"]) is not None


def test_login_needs_no_existing_credential(client, credentials):
    """It is how a device gets one, so requiring one would be circular."""
    assert _json(client, "/mind/api/v1/login", credentials).status_code == 200


def test_the_label_names_the_device(client, credentials, owner):
    _json(client, "/mind/api/v1/login", credentials | {"label": "Pixel"})
    assert owner.api_tokens.get().label == "Pixel"


@pytest.mark.parametrize(
    "payload,why",
    [
        ({"username": "vince", "password": "wrong"}, "wrong password"),
        ({"username": "nobody", "password": "correct-horse"}, "unknown username"),
    ],
)
def test_every_login_failure_looks_identical(client, credentials, payload, why):
    """Telling them apart confirms which usernames exist, and helps nobody
    legitimate."""
    response = _json(client, "/mind/api/v1/login", payload)

    assert response.status_code == 401, why
    assert response.json()["detail"] == "Those details did not work."


def test_a_deactivated_account_cannot_log_in(client, credentials, owner):
    owner.is_active = False
    owner.save()

    assert _json(client, "/mind/api/v1/login", credentials).status_code == 401
    assert ApiToken.objects.count() == 0


def test_login_is_throttled(client, credentials):
    """An unlimited password endpoint is an invitation.

    429 also happens to be correct for the client: not 400 and not 401, so it retries
    later rather than discarding the queue or asking the person to reconnect.
    """
    codes = [
        _json(client, "/mind/api/v1/login", {"username": "vince", "password": "no"}).status_code
        for _ in range(12)
    ]
    assert 429 in codes


# ---------------------------------------------------------------------------
# GET /me
# ---------------------------------------------------------------------------


def test_me_identifies_the_bearer(client, bearer, owner):
    """How a client validates a token before storing it — a refused token sitting in
    storage produces an app where every capture fails and nothing says why."""
    response = client.get("/mind/api/v1/me", **bearer)

    assert response.status_code == 200
    assert response.json() == {"username": owner.get_username(), "email": owner.email}


def test_me_refuses_a_bad_token(client, owner):
    ApiToken.issue(owner)
    response = client.get("/mind/api/v1/me", HTTP_AUTHORIZATION="Bearer sm_wrong")

    assert response.status_code in (401, 403), "the client reads this as reconnect"


def test_me_refuses_no_token(client):
    assert client.get("/mind/api/v1/me").status_code in (401, 403)


# ---------------------------------------------------------------------------
# POST /capture — the mobile contract
# ---------------------------------------------------------------------------


def test_capture_with_a_bearer_token_needs_no_csrf_token(client, bearer, owner):
    """There is no cookie to be tricked into using, so there is nothing for CSRF to
    defend — and a native client has no token to send."""
    response = _json(
        client,
        "/mind/api/v1/capture",
        {"text": "a thought from the train", "tags": []},
        HTTP_IDEMPOTENCY_KEY=UUID_A,
        **bearer,
    )

    assert response.status_code == 201
    node = Node.objects.get()
    assert node.original_content == "a thought from the train"
    assert node.owner == owner
    assert node.source == NodeSource.MOBILE
    assert str(node.public_id) == UUID_A


def test_a_queued_capture_keeps_the_time_it_was_written(client, bearer):
    """The thought's own time, not the moment the queue finally drained.

    Found on a device, August 14, 2026: six captures typed minutes apart while offline
    all arrived stamped to the same second, because the mobile contract had no field for
    when they were written and this endpoint passed `captured_at=None`. Node.captured_at
    is defined as when the thought happened precisely so temporal detectors mean
    something, and dormancy is measured *between* notes — so a queue that collapses its
    contents onto one delivery instant destroys spread on exactly the material a
    phone-first client produces most of.
    """
    written = datetime(2026, 3, 14, 9, 30, tzinfo=dt_timezone.utc)

    response = _json(
        client,
        "/mind/api/v1/capture",
        {"text": "typed on a train", "tags": [], "captured_at": written.isoformat()},
        HTTP_IDEMPOTENCY_KEY=UUID_A,
        **bearer,
    )

    assert response.status_code == 201
    assert Node.objects.get().captured_at == written


def test_a_capture_with_no_stated_time_still_arrives(client, bearer):
    """The field is optional, so an older client that does not send it is unchanged and
    falls back to now -- which is correct for anything captured while connected."""
    before = timezone.now()

    response = _json(
        client, "/mind/api/v1/capture", {"text": "no time given", "tags": []},
        HTTP_IDEMPOTENCY_KEY=UUID_B, **bearer,
    )

    assert response.status_code == 201
    assert Node.objects.get().captured_at >= before


def test_a_replayed_key_returns_200_and_no_second_note(client, bearer):
    """The client treats 200 and 201 alike on purpose: 200 means an earlier request
    with this key already stored it, so the thought is safe either way."""
    first = _json(
        client, "/mind/api/v1/capture", {"text": "same thought", "tags": []},
        HTTP_IDEMPOTENCY_KEY=UUID_A, **bearer,
    )
    second = _json(
        client, "/mind/api/v1/capture", {"text": "same thought", "tags": []},
        HTTP_IDEMPOTENCY_KEY=UUID_A, **bearer,
    )

    assert (first.status_code, second.status_code) == (201, 200)
    assert Node.objects.count() == 1


def test_different_keys_are_different_thoughts(client, bearer):
    for key in (UUID_A, UUID_B):
        _json(client, "/mind/api/v1/capture", {"text": "a thought here", "tags": []},
              HTTP_IDEMPOTENCY_KEY=key, **bearer)
    assert Node.objects.count() == 2


def test_a_permanent_fault_returns_400_so_the_client_stops(client, bearer):
    """Anything that is not 400/401/403 is retried forever by a queued client.

    An empty body will never be accepted, so returning 422 would have meant a note the
    server refuses and a phone that keeps asking.
    """
    response = _json(
        client, "/mind/api/v1/capture", {"text": "   ", "tags": []},
        HTTP_IDEMPOTENCY_KEY=UUID_A, **bearer,
    )
    assert response.status_code == 400


def test_a_non_uuid_key_is_rejected_rather_than_retried(client, bearer):
    response = _json(
        client, "/mind/api/v1/capture", {"text": "a thought here", "tags": []},
        HTTP_IDEMPOTENCY_KEY="not-a-uuid", **bearer,
    )
    assert response.status_code == 400


def test_claiming_another_persons_id_is_a_permanent_fault(client, bearer, other_owner):
    theirs = services.capture(
        other_owner, content="theirs", captured_at=timezone.now(),
        source=NodeSource.WEB, actor="them",
    )
    response = _json(
        client, "/mind/api/v1/capture", {"text": "mine", "tags": []},
        HTTP_IDEMPOTENCY_KEY=str(theirs.public_id), **bearer,
    )
    assert response.status_code == 400, "409 would be retried forever"


def test_tags_are_kept_rather_than_discarded(client, bearer, owner):
    """No tag table exists and structure is meant to emerge — but a person typed these,
    so they are recorded rather than dropped in silence."""
    _json(
        client, "/mind/api/v1/capture",
        {"text": "a thought about the boiler", "tags": ["house", "repairs"]},
        HTTP_IDEMPOTENCY_KEY=UUID_A, **bearer,
    )

    payloads = [e.payload for e in owner.events.all()]
    assert any(p.get("tags") == ["house", "repairs"] for p in payloads)


def test_a_bad_token_gives_the_client_reconnect_not_rejection(client, owner):
    """A queue is never emptied because a credential expired."""
    response = _json(
        client, "/mind/api/v1/capture", {"text": "a thought here", "tags": []},
        HTTP_IDEMPOTENCY_KEY=UUID_A, HTTP_AUTHORIZATION="Bearer sm_expired",
    )
    assert response.status_code in (401, 403)
    assert Node.objects.count() == 0


# ---------------------------------------------------------------------------
# Both auth paths coexist
# ---------------------------------------------------------------------------


def test_session_auth_still_works_alongside_bearer(client, owner):
    client.force_login(owner)
    assert client.get("/mind/api/v1/captures").status_code == 200


def test_a_token_reaches_the_ordinary_endpoints_too(client, bearer):
    assert client.get("/mind/api/v1/captures", **bearer).status_code == 200
    assert client.get("/mind/api/v1/summary", **bearer).status_code == 200


def test_one_persons_token_cannot_see_another_persons_notes(client, bearer, other_owner):
    services.capture(
        other_owner, content="theirs", captured_at=timezone.now(),
        source=NodeSource.WEB, actor="them",
    )
    assert client.get("/mind/api/v1/captures", **bearer).json() == []


# ---------------------------------------------------------------------------
# Revocation — the lost-phone case
# ---------------------------------------------------------------------------


def test_devices_can_be_listed_and_told_apart(client, bearer, owner):
    ApiToken.issue(owner, label="Old tablet")
    listed = client.get("/mind/api/v1/tokens", **bearer).json()

    assert {t["label"] for t in listed} == {"Android", "Old tablet"}
    assert all(t["prefix"].startswith(ApiToken.PREFIX) for t in listed)


def test_revoking_takes_effect_immediately(client, bearer, owner):
    token, raw = ApiToken.issue(owner, label="Lost phone")

    assert client.delete(f"/mind/api/v1/tokens/{token.pk}", **bearer).status_code == 204
    assert resolve_token(raw) is None
    assert client.get("/mind/api/v1/me", HTTP_AUTHORIZATION=f"Bearer {raw}").status_code in (
        401,
        403,
    )


def test_another_persons_token_cannot_be_revoked(client, bearer, other_owner):
    theirs, raw = ApiToken.issue(other_owner)

    assert client.delete(f"/mind/api/v1/tokens/{theirs.pk}", **bearer).status_code == 404
    assert resolve_token(raw) is not None
