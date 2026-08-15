"""`POST /api/v1/capture` — the one endpoint a non-browser client gets.

Step 4a of `design/one-capture-surface-plan.md`, and the step the plan did not
know it needed. Step 4 said to *check first that nothing on the phone still uses
the task-core capture scope*. The check says it does, and decisively: the shipped
APK is built with no `-PsecondMindBaseUrl`, so `Backends.isSplit` is false and
`capture` is the same object as `workspace`. Every thought typed on the phone
posts to this URL, not to `/mind/api/v1/capture`. Deleting it would have drained
the offline queue into 404s.

So the endpoint keeps its URL, its token and its `capture:write` scope, and
changes what it writes: a `Node` rather than a `Capture`. Nothing on the phone
is rebuilt, nobody logs in twice, and `Capture` becomes deletable.

**This is what `mind/urls.py` already predicted.** Two cores defining
`/api/v1/capture` was "the dual-write question arriving early, and it is answered
when facets land — one capture endpoint that writes a node and optionally a
task." Facets landed.

Ported from `capture/tests/test_api_v1.py` rather than written fresh: the auth,
CSRF and idempotency behaviour of this endpoint is unchanged and is exactly the
part a rewrite is most likely to lose. What changed is the row it writes.
"""

import json
import uuid
from datetime import datetime, timedelta, timezone as dt_timezone

import pytest
from django.test import Client
from django.utils import timezone

from accounts.models import SCOPE_CAPTURE_WRITE, PersonalAccessToken, User
from capture.models import Capture
from mind.models import ConceptCandidate, Mention, Node, NodeSource
from mind.services import TYPED_TAG_REASON

pytestmark = pytest.mark.django_db

PASSWORD = "correct horse battery staple 47!"
URL = "/api/v1/capture"
UTC = dt_timezone.utc


@pytest.fixture
def alice():
    return User.objects.create_user("alice", "alice@example.com", PASSWORD)


@pytest.fixture
def token(alice):
    _, raw = PersonalAccessToken.generate(
        alice, label="Phone", scopes=[SCOPE_CAPTURE_WRITE]
    )
    return raw


@pytest.fixture
def client():
    # enforce_csrf_checks, because the default client silently disables CSRF and
    # that is precisely what hid a real bug on this endpoint once: a bad token
    # fell through to session auth and answered "403 CSRF check Failed" instead
    # of 401. Only curl could see it.
    return Client(enforce_csrf_checks=True)


def post(client, payload, *, token=None, idempotency_key=None, **extra):
    if token is not None:
        extra["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    if idempotency_key is not None:
        extra["HTTP_IDEMPOTENCY_KEY"] = str(idempotency_key)
    return client.post(
        URL, data=json.dumps(payload), content_type="application/json", **extra
    )


# ---------------------------------------------------------------------------
# What it writes
# ---------------------------------------------------------------------------


def test_a_valid_token_writes_a_node(client, alice, token):
    response = post(client, {"text": "Call the vet"}, token=token)

    assert response.status_code == 201
    node = Node.objects.get()
    assert node.owner == alice
    assert node.original_content == "Call the vet"
    assert response.json()["public_id"] == str(node.public_id)


def test_it_no_longer_writes_a_capture(client, token):
    """The whole point of the step. `Capture` stops growing here, which is what
    makes it deletable in 4b."""
    post(client, {"text": "Call the vet"}, token=token)

    assert not Capture.objects.exists()


def test_the_source_says_it_came_from_a_phone(client, token):
    post(client, {"text": "Call the vet"}, token=token)

    assert Node.objects.get().source == NodeSource.MOBILE


def test_the_thought_is_visible_on_the_capture_page(client, alice, token):
    """The read half. A capture that lands somewhere nobody looks is not a
    capture, and this endpoint's whole justification is that `/mind/` is now
    where the phone's thoughts go."""
    post(client, {"text": "Call the vet"}, token=token)

    client.force_login(alice)
    assert "Call the vet" in client.get("/mind/").content.decode()


# ---------------------------------------------------------------------------
# The thought's own time
# ---------------------------------------------------------------------------


def test_a_queued_capture_keeps_the_time_it_was_written(client, token):
    """The live defect this step fixes.

    A capture can sit in the encrypted queue for hours. Both Android call sites
    send `captured_at` — `CaptureViewModel.deliver` and `QueueDrainer.drain`,
    each passing the queued item's own `createdAt` — but this endpoint's schema
    was `text` and `tags` only, so Ninja dropped the field silently and every
    queued thought was stamped with the moment the network came back.

    It was fixed once already, on `/mind/api/v1/capture`, which nothing calls.
    Six captures landing on the same second during the August 14 device pass is
    how it was first found; they are still in the graph with the wrong times.

    Dormancy is measured *between* notes, so collapsing a queue onto one instant
    destroys temporal spread on precisely the material a phone-first client
    produces most of.
    """
    written = timezone.now() - timedelta(days=3)

    post(
        client,
        {"text": "the boiler again", "captured_at": written.isoformat()},
        token=token,
    )

    assert Node.objects.get().captured_at == written


def test_a_capture_that_never_waited_is_stamped_now(client, token):
    """Omitted rather than guessed is the client's contract, and now is the
    honest answer for anything captured while connected."""
    before = timezone.now()

    post(client, {"text": "the boiler again"}, token=token)

    assert Node.objects.get().captured_at >= before


def test_a_time_the_server_cannot_read_is_rejected_not_guessed(client, token):
    response = post(
        client, {"text": "the boiler again", "captured_at": "last Tuesday"},
        token=token,
    )

    assert response.status_code == 422
    assert not Node.objects.exists()


# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------


def test_a_typed_tag_arrives_as_a_confirmed_concept(client, token):
    """Step 1's rule reaching the surface it was always meant for. Until now the
    phone's tags became `lists.Tag` rows on a `Capture` — real, and invisible to
    the concept layer."""
    post(client, {"text": "watched Down Periscope", "tags": ["movie"]}, token=token)

    concept = ConceptCandidate.objects.get(label="movie")
    assert concept.confirmed_at is not None
    assert concept.reason == TYPED_TAG_REASON


def test_tags_are_optional(client, token):
    post(client, {"text": "Call the vet"}, token=token)

    assert not ConceptCandidate.objects.exists()


def test_a_replay_does_not_deepen_the_evidence(client, token):
    """A retry is the same thought arriving twice, not two mentions of it. The
    gravity gate counts mentions, so a queue that retried six times would
    manufacture a recurrence that never happened."""
    key = uuid.uuid4()
    post(client, {"text": "watched Down Periscope", "tags": ["movie"]},
         token=token, idempotency_key=key)

    post(client, {"text": "watched Down Periscope", "tags": ["movie"]},
         token=token, idempotency_key=key)

    assert Mention.objects.count() == 1


# ---------------------------------------------------------------------------
# Retry identity
# ---------------------------------------------------------------------------


def test_a_keyed_request_names_the_node(client, token):
    """`Idempotency-Key` is a UUID from the client, which is precisely what
    `public_id` already is — so retry safety is the same mechanism the graph
    already has, not a parallel one."""
    key = uuid.uuid4()

    response = post(client, {"text": "Call the vet"}, token=token, idempotency_key=key)

    assert response.status_code == 201
    assert Node.objects.get().public_id == key


def test_repeating_a_key_returns_the_original_and_creates_nothing(client, token):
    key = uuid.uuid4()
    post(client, {"text": "Call the vet"}, token=token, idempotency_key=key)

    # Different text on purpose: a lost-response retry sends the same request,
    # but even if it didn't, the first successful write is the one of record.
    retry = post(client, {"text": "Call the vet (retry)"},
                 token=token, idempotency_key=key)

    assert retry.status_code == 200
    assert Node.objects.count() == 1
    assert Node.objects.get().original_content == "Call the vet"


def test_a_key_already_used_by_someone_else_is_refused(client, token):
    """A `Capture` key was unique per owner; a node's `public_id` is unique
    outright, so this now refuses instead of writing a second row.

    Refused with 400, which the client reads as a permanent rejection — right,
    because retrying cannot help. In practice unreachable: these are client-side
    UUID4s. It is tested because the *status* matters, not the odds; a 500 here
    would be retried against a server that will never accept it.
    """
    bob = User.objects.create_user("bob", "bob@example.com", PASSWORD)
    _, bobs = PersonalAccessToken.generate(bob, scopes=[SCOPE_CAPTURE_WRITE])
    key = uuid.uuid4()
    post(client, {"text": "Mine"}, token=token, idempotency_key=key)

    response = post(client, {"text": "Theirs"}, token=bobs, idempotency_key=key)

    assert response.status_code == 400
    assert Node.objects.count() == 1


def test_a_malformed_key_is_rejected_and_creates_nothing(client, token):
    response = post(client, {"text": "Call the vet"},
                    token=token, idempotency_key="not-a-uuid")

    assert response.status_code == 400
    assert not Node.objects.exists()


def test_two_keyless_requests_never_collide(client, token):
    post(client, {"text": "One"}, token=token)

    response = post(client, {"text": "Two"}, token=token)

    assert response.status_code == 201
    assert Node.objects.count() == 2


# ---------------------------------------------------------------------------
# Credentials
# ---------------------------------------------------------------------------


def test_no_credential_at_all_is_401(client):
    response = post(client, {"text": "Call the vet"})

    assert response.status_code == 401
    assert not Node.objects.exists()


def test_a_made_up_token_is_401(client):
    response = post(client, {"text": "Call the vet"}, token="not-a-real-token")

    assert response.status_code == 401
    assert not Node.objects.exists()


def test_a_deleted_token_is_401(client, token):
    # Deleting the row is the whole of revocation, so this is the test that
    # revocation works.
    PersonalAccessToken.objects.all().delete()

    assert post(client, {"text": "Call the vet"}, token=token).status_code == 401


def test_a_token_on_a_deactivated_account_is_401(client, alice, token):
    alice.is_active = False
    alice.save()

    assert post(client, {"text": "Call the vet"}, token=token).status_code == 401


def test_a_token_without_capture_write_is_401(client, alice):
    # Valid, unexpired, wrong capability.
    _, read_only = PersonalAccessToken.generate(alice, scopes=["identity:read"])

    response = post(client, {"text": "Call the vet"}, token=read_only)

    assert response.status_code == 401
    assert not Node.objects.exists()


def test_using_a_token_stamps_last_used_at(client, alice, token):
    post(client, {"text": "Call the vet"}, token=token)

    assert PersonalAccessToken.objects.get(owner=alice).last_used_at is not None


def test_a_node_belongs_to_the_token_holder_not_whoever_asks(client):
    bob = User.objects.create_user("bob", "bob@example.com", PASSWORD)
    _, bobs = PersonalAccessToken.generate(bob, scopes=[SCOPE_CAPTURE_WRITE])

    post(client, {"text": "Bob's thought"}, token=bobs)

    assert Node.objects.get().owner == bob


# ---------------------------------------------------------------------------
# The browser on the same endpoint
# ---------------------------------------------------------------------------


def test_a_logged_in_browser_can_still_use_it(client, alice):
    """The Day page's quick-capture box, which posts here on session auth. It is
    the third capture surface, and it was not in the plan's count of two."""
    client.force_login(alice)
    csrf = client.get("/accounts/password/change/").cookies["csrftoken"].value

    response = client.post(
        URL,
        data=json.dumps({"text": "From the browser"}),
        content_type="application/json",
        HTTP_X_CSRFTOKEN=csrf,
    )

    assert response.status_code == 201
    assert Node.objects.get().owner == alice


def test_a_logged_in_browser_still_needs_its_csrf_token(client, alice):
    # Declining to CSRF-check a caller with no session must not stop checking
    # one that has a session, which is the only request the check protected.
    client.force_login(alice)

    response = client.post(
        URL, data=json.dumps({"text": "Forged"}), content_type="application/json"
    )

    assert response.status_code == 403
    assert not Node.objects.exists()


# ---------------------------------------------------------------------------
# Refusals
# ---------------------------------------------------------------------------


def test_empty_text_is_rejected_and_creates_nothing(client, token):
    """400, not 422. A queued client treats anything but 400/401/403 as "retry
    later", so an unprocessable body returned as 422 would be retried forever
    against a server that will never accept it."""
    response = post(client, {"text": "   "}, token=token)

    assert response.status_code == 400
    assert not Node.objects.exists()
