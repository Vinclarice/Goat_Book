"""Three ways in, one kind of row.

Crane 1 slice 3 asserted this of the Inbox: a thought typed on the Daily Page
must be "indistinguishable in the triage flow from one typed on the Inbox's own
form". Heron 4a moves the guarantee rather than retiring it — there is no triage
now, but there is still one graph, and a thought must not carry a different shape
depending on which surface it arrived through.

**The pair being compared has changed, and that is the point.** The old version
of this test compared the Day page's route to the Inbox form, both writing a
`Capture`. 4a made the first write a `Node` while the second still wrote a
`Capture`, so the two deliberately diverged and this test correctly failed; 4b
then deleted the Inbox form outright. It was the right test throughout — what it
guards has moved, twice, and it is still the only thing comparing the surfaces.

The three surfaces that must agree now:

* `POST /api/v1/capture` with a bearer token — the phone.
* `POST /api/v1/capture` with a session — the SPA's Day page quick-capture box,
  which is the third capture surface `one-capture-surface-plan.md` did not count.
* `POST /mind/` — the knowledge core's own page.

**One property did not survive the move, deliberately.** The Inbox normalised
text; the graph does not, because `original_content` is meant to be what was
first written. Both graph surfaces agree in *not* normalising, so the invariant
this file exists for holds — but it is recorded here rather than quietly dropped,
because a test that stops asserting something is indistinguishable from a
behaviour that stopped happening.
"""

import json
import uuid

import pytest
from django.test import Client

from accounts.models import SCOPE_CAPTURE_WRITE, PersonalAccessToken, User
from mind.models import Node, NodeSource

pytestmark = pytest.mark.django_db

PASSWORD = "correct horse battery staple 47!"

# Everything a reader, a detector or the review surface takes off a node.
# Deliberately spelled out rather than compared with a blanket __dict__, so a new
# field is a decision somebody makes about all three paths rather than something
# a loose assertion absorbs.
#
# `source` is not here, and must not be: WEB and MOBILE differing is the one
# difference between these paths that is true.
SHARED_FIELDS = (
    "owner_id",
    "original_content",
    "archived_at",
    "deleted_at",
    "import_key",
)


@pytest.fixture
def alice():
    return User.objects.create_user("alice", "alice@example.com", PASSWORD)


@pytest.fixture
def client(alice):
    client = Client()
    client.force_login(alice)
    return client


def snapshot(node):
    return {field: getattr(node, field) for field in SHARED_FIELDS}


def through_the_api(client, text, *, token=None):
    extra = {"HTTP_AUTHORIZATION": f"Bearer {token}"} if token else {}
    client.post(
        "/api/v1/capture",
        data=json.dumps({"text": text}),
        content_type="application/json",
        **extra,
    )
    return Node.objects.get(original_content=text)


def test_the_phone_and_the_day_page_write_the_same_row(client, alice):
    _, token = PersonalAccessToken.generate(alice, scopes=[SCOPE_CAPTURE_WRITE])

    # No session on this one: a phone cannot hold a cookie, and the whole reason
    # the endpoint carries two auth classes is that both must reach the same code.
    from_phone = through_the_api(Client(), "A thought from the phone", token=token)
    from_day_page = through_the_api(client, "A thought from the Day page")

    phone, day_page = snapshot(from_phone), snapshot(from_day_page)
    # The text differs by construction; everything else must not.
    phone.pop("original_content")
    day_page.pop("original_content")
    assert phone == day_page


def test_the_api_and_the_capture_page_write_the_same_row(client):
    from_api = through_the_api(client, "A thought from the API")

    client.post("/mind/", {"content": "A thought from the page"})
    from_page = Node.objects.get(original_content="A thought from the page")

    api, page = snapshot(from_api), snapshot(from_page)
    api.pop("original_content")
    page.pop("original_content")
    assert api == page


def test_the_source_is_the_one_thing_that_differs(client, alice):
    _, token = PersonalAccessToken.generate(alice, scopes=[SCOPE_CAPTURE_WRITE])

    from_phone = through_the_api(Client(), "From the phone", token=token)
    client.post("/mind/", {"content": "From the page"})

    assert from_phone.source == NodeSource.MOBILE
    assert Node.objects.get(original_content="From the page").source == NodeSource.WEB


def test_all_three_refuse_an_empty_capture(client, alice):
    _, token = PersonalAccessToken.generate(alice, scopes=[SCOPE_CAPTURE_WRITE])

    bearer = Client().post(
        "/api/v1/capture",
        data=json.dumps({"text": "   "}),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )
    session = client.post(
        "/api/v1/capture",
        data=json.dumps({"text": "   "}),
        content_type="application/json",
    )
    client.post("/mind/", {"content": "   "})

    assert bearer.status_code == 400
    assert session.status_code == 400
    assert not Node.objects.exists()


def test_a_thought_from_the_phone_appears_on_the_capture_page(client, alice):
    """The whole point of the step: it shows up where the thinking happens.

    Before 4a this landed in the Inbox at `/capture/`, which the crossover is
    deleting, and never reached the graph at all.
    """
    _, token = PersonalAccessToken.generate(alice, scopes=[SCOPE_CAPTURE_WRITE])
    through_the_api(Client(), "Ship Heron 4a", token=token)

    assert "Ship Heron 4a" in client.get("/mind/").content.decode()


def test_a_browser_capture_carries_no_retry_identity_it_was_not_given(client):
    """The mobile client's key is mobile-only. A browser capture that arrived
    with one would be the one visible difference between the paths."""
    node = through_the_api(client, "From the Day page")

    # A server-minted UUID4, not the client's -- there was no Idempotency-Key.
    assert node.public_id is not None
    assert node.public_id.version == uuid.uuid4().version
