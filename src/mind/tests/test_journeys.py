"""Whole paths a person walks, end to end, across both cores.

Every other test file here covers a layer. These cover a *journey*, and the
distinction is not academic: on 15 August 2026 the suite stood at 1007 Django
tests and 594 pytest, all green, and walking one journey by hand found three
defects in an hour.

- The agenda raised on any unfiled task, because `serialize_item` reaches
  through `item.list` and runs for every row in the payload. Accepting one
  commitment made the main page of the application 500.
- A repeating commitment with no Area could not spawn its successor: the insert
  had no owner to derive.
- Promoting a checklist step on such a task failed identically.

Each had thorough unit coverage on both sides of the seam it broke. What nobody
had done was ask *what happens next* -- and none of the three is reachable
without doing so, because each needs a task that a previous step created.

**Deliberately long, and deliberately over HTTP.** A journey assembled from
service calls would have passed while the agenda was 500ing: the serializer, the
response schema and the frontend contract are where three of those failures
actually lived. They cross `/mind/` and `/api/` in one test because that is what
one person does in one sitting.

They live in the knowledge core's suite because they *start* there, and because
this runner already reaches both cores.
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from lists.models import CadenceMode, Item
from mind.models import Facet, FacetKind, Node

pytestmark = pytest.mark.django_db


def tomorrow():
    """Computed, never written down.

    A hardcoded date compared against a live clock is a test with an expiry date
    on it -- two `lists` tests rotted into asserting a defect that way, and a
    third did it inside this very directory the same afternoon.
    """
    return timezone.localdate() + timedelta(days=1)


@pytest.fixture
def signed_in(client, owner):
    client.force_login(owner)
    return client


def capture(client, text):
    """Type into the box and press Keep, as a person does."""
    return client.post("/mind/", {"content": text})


def offered_commitment(owner):
    return Facet.objects.filter(
        node__owner=owner,
        kind=FacetKind.ACTIONABLE,
        retired_at__isnull=True,
        confirmed_at__isnull=True,
    ).first()


def accept(client, facet):
    return client.post(f"/mind/commitments/{facet.node.public_id}/")


# ---------------------------------------------------------------------------


def test_a_dated_thought_becomes_a_task_you_can_find_open_and_finish(signed_in, owner):
    """The journey that found the agenda defect.

    Every step here passed its own unit tests while step three returned a 500,
    because nothing had ever reached step three with a task that had no Area.
    """
    capture(signed_in, f"dentist on {tomorrow().isoformat()}")

    # 1. The offer is on the page, quoting what it read.
    page = signed_in.get("/mind/")
    assert b"Looks like a commitment" in page.content

    # 2. One tap, and no Area is asked for.
    facet = offered_commitment(owner)
    assert accept(signed_in, facet).status_code == 302

    task = Item.objects.get()
    assert task.list is None
    assert task.owner == owner

    # 3. The agenda still loads -- the whole page, for every task, not this row.
    agenda = signed_in.get("/api/v1/agenda")
    assert agenda.status_code == 200
    assert any(row["text"] == task.text for row in agenda.json()["items"])

    # 4. It opens. This is where the second 500 was.
    detail = signed_in.get(f"/api/v1/tasks/{task.id}")
    assert detail.status_code == 200
    assert detail.json()["area"] is None

    # 5. It can be finished, which is the point of it being a task at all.
    done = signed_in.patch(
        f"/api/items/{task.id}/",
        data={"status": "completed"},
        content_type="application/json",
    )
    assert done.status_code == 200
    task.refresh_from_db()
    assert task.status == Item.Status.COMPLETED

    # 6. And the thought is still a thought. It left the quiet tier, not the graph.
    assert Node.objects.get().deleted_at is None


def test_a_repeating_commitment_survives_its_own_first_completion(signed_in, owner):
    """The journey that found the spawn defect, which would otherwise have
    surfaced a month after the task was made, with nothing linking the two."""
    capture(signed_in, "change the furnace filter every month")

    facet = offered_commitment(owner)
    assert facet.data["recurrence"] == "monthly"
    accept(signed_in, facet)

    first = Item.objects.get()
    assert first.recurrence == Item.Recurrence.MONTHLY

    signed_in.patch(
        f"/api/items/{first.id}/",
        data={"status": "completed"},
        content_type="application/json",
    )

    # The successor exists, belongs to somebody, and is not born late.
    following = Item.objects.filter(status=Item.Status.ACTIVE).get()
    assert following.owner == owner
    assert following.list is None
    assert following.due_date > timezone.localdate()
    # And it is still one series rather than two unrelated tasks.
    assert following.commitment_id == first.commitment_id


def test_a_commitment_can_be_switched_to_counting_from_completion(signed_in, owner):
    """The setting added the same day, walked the way somebody would use it:
    accept a repeating commitment, then change how its next date is worked out."""
    capture(signed_in, "change the furnace filter every month")
    accept(signed_in, offered_commitment(owner))
    task = Item.objects.get()

    response = signed_in.patch(
        f"/api/items/{task.id}/",
        data={"cadence_mode": CadenceMode.FLOATING},
        content_type="application/json",
    )

    assert response.status_code == 200
    detail = signed_in.get(f"/api/v1/tasks/{task.id}").json()
    assert detail["cadence_mode"] == "floating"


def test_a_checklist_step_on_an_unfiled_task_becomes_its_own_task(signed_in, owner):
    """The third defect, and the one found by grep rather than by walking --
    which is exactly why it gets a journey now."""
    capture(signed_in, f"plan the trip, book it by {tomorrow().isoformat()}")
    accept(signed_in, offered_commitment(owner))
    task = Item.objects.get()

    created = signed_in.post(
        f"/api/tasks/{task.id}/checklist-steps/",
        data={"text": "Book the ferry"},
        content_type="application/json",
    )
    assert created.status_code == 201
    step_id = created.json()["data"]["id"]

    promoted = signed_in.post(f"/api/checklist-steps/{step_id}/promote/")

    assert promoted.status_code in (200, 201)
    assert Item.objects.filter(owner=owner, text="Book the ferry").exists()


def test_an_ordinary_thought_is_kept_and_asked_nothing(signed_in, owner):
    """The common case, and the one that must stay free. A capture surface that
    proposed something about every note would train somebody to ignore it."""
    capture(signed_in, "I like lucid cars, especially the Gravity")

    assert Facet.objects.count() == 0
    assert Item.objects.count() == 0
    # Still kept, and still on the page -- silence is not discarding.
    assert Node.objects.count() == 1
    assert b"lucid cars" in signed_in.get("/mind/").content


def test_declining_an_offer_leaves_the_thought_and_no_task(signed_in, owner):
    capture(signed_in, f"maybe the dentist on {tomorrow().isoformat()}")
    facet = offered_commitment(owner)

    signed_in.post(f"/mind/commitments/{facet.node.public_id}/", {"action": "dismiss"})

    assert Item.objects.count() == 0
    assert Node.objects.count() == 1
    assert b"Looks like a commitment" not in signed_in.get("/mind/").content


def test_a_tagged_capture_from_the_phone_becomes_a_tagged_task(signed_in, owner):
    """Steps 1, 2 and 4a of one-capture-surface-plan.md, walked together.

    The layers are separately tested and separately meaningless: step 1 turns a
    typed tag into a confirmed concept, step 2 carries confirmed concepts onto
    the task. What a person experiences is neither -- it is that a thought
    tagged on the phone arrives in the agenda still tagged.

    **This test used to post to `/mind/api/v1/capture` with a `mind.ApiToken`,
    and that is the endpoint the phone does not use.** The shipped APK is built
    with no `-PsecondMindBaseUrl`, so `Backends.isSplit` is false and every
    capture goes to `/api/v1/capture` on a `PersonalAccessToken`. Walking the
    wrong one is how the whole path looked covered while the live route was
    still writing a `Capture` and dropping `captured_at` on the floor.

    So it walks the real one, with the real credential, carrying the field a
    drained queue actually sends.
    """
    import json

    from accounts.models import SCOPE_CAPTURE_WRITE, PersonalAccessToken

    # Three days in the queue, which is the case the endpoint used to get wrong.
    written = timezone.now() - timedelta(days=3)
    _, raw = PersonalAccessToken.generate(
        owner, label="Android", scopes=[SCOPE_CAPTURE_WRITE]
    )
    signed_in.post(
        "/api/v1/capture",
        data=json.dumps(
            {"text": f"ring the plumber by {tomorrow().isoformat()}",
             "tags": ["boiler", "flat"],
             "captured_at": written.isoformat()}
        ),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {raw}",
        HTTP_IDEMPOTENCY_KEY="3f1b0c9e-7777-4a2b-8c3d-000000000077",
    )

    # It reached the graph, keeping the day it was typed rather than the day it
    # was delivered -- and it is on the page a person actually reads.
    assert Node.objects.get().captured_at == written
    assert b"ring the plumber" in signed_in.get("/mind/").content

    accept(signed_in, offered_commitment(owner))

    task = Item.objects.get()
    assert set(task.tags.values_list("name", flat=True)) == {"boiler", "flat"}
    # And it is on the agenda under those tags, which is the point of them.
    row = next(
        r for r in signed_in.get("/api/v1/agenda").json()["items"]
        if r["id"] == task.id
    )
    assert set(row["tags"]) == {"boiler", "flat"}
