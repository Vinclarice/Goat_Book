"""A capture from the phone reads "tomorrow" as the owner's tomorrow.

The same defect as `commercial-blueprint.md` 2, reaching the knowledge core's
parser. `TimeZoneMiddleware` activates a zone from `request.user`, which is
still anonymous while middleware runs on a token request — so
`_propose_any_commitment` would compute its `today` in the *server's* zone, and
a relative date parsed at capture would come out wrong for anyone not living in
`settings.TIME_ZONE`.

Found by asking whether the task core's defect had a twin here rather than by
anything failing, which is the only way this one surfaces: the proposal is
plausible either way, and being a day out is invisible unless you already know
what day you meant.

**This used to go through `/mind/api/v1/capture` and a `mind.ApiToken`**, which
had its own resolver and so needed its own `activate_for` call. That API is
deleted — nothing ever called it — and the surviving path is the task core's
`/api/v1/capture` on a `PersonalAccessToken`, where `_resolve_scoped_token` makes
the same call in the one place both of its token paths converge.

So the seam moved and the defect did not. Rewritten rather than deleted, because
deleting it would have removed the only coverage of a live behaviour on the
grounds that an unused endpoint went away.
"""

import json
from datetime import date, datetime, timezone as dt_timezone

import pytest

from accounts.models import SCOPE_CAPTURE_WRITE, PersonalAccessToken
from mind.models import Facet, FacetKind

pytestmark = pytest.mark.django_db

# 23:30 UTC on August 1st, the instant the task core's own time-zone tests use.
# In Makassar (+8) it is already 07:30 on the 2nd, so "tomorrow" means the 3rd.
# In America/New_York -- which is settings.TIME_ZONE, and so what this computed
# before -- it is still 19:30 on the 1st, and "tomorrow" means the 2nd.
SPLIT_MOMENT = datetime(2026, 8, 1, 23, 30, tzinfo=dt_timezone.utc)

MAKASSAR_TOMORROW = date(2026, 8, 3)
SERVER_TOMORROW = date(2026, 8, 2)


@pytest.fixture
def makassar(owner):
    owner.time_zone = "Asia/Makassar"
    owner.save(update_fields=["time_zone"])
    return owner


def capture(client, makassar, text, key):
    _, raw = PersonalAccessToken.generate(
        makassar, label="Android", scopes=[SCOPE_CAPTURE_WRITE]
    )
    return client.post(
        "/api/v1/capture",
        data=json.dumps({"text": text}),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {raw}",
        HTTP_IDEMPOTENCY_KEY=key,
    )


def test_tomorrow_is_the_owners_tomorrow_not_the_servers(client, makassar, monkeypatch):
    from django.utils import timezone as dj_timezone

    monkeypatch.setattr(dj_timezone, "now", lambda: SPLIT_MOMENT)

    capture(client, makassar, "dentist tomorrow",
            "3f1b0c9e-9999-4a2b-8c3d-000000000009")

    facet = Facet.objects.get(kind=FacetKind.ACTIONABLE)
    assert facet.data["due_date"] == MAKASSAR_TOMORROW.isoformat()
    assert facet.data["due_date"] != SERVER_TOMORROW.isoformat()


def test_the_zone_does_not_outlive_the_request(client, makassar, monkeypatch):
    """Activating a zone mid-request means something has to undo it, and worker
    threads are reused. `TimeZoneMiddleware`'s `finally` is what does -- this
    fails if this endpoint ever stops running behind it."""
    from django.conf import settings
    from django.utils import timezone as dj_timezone

    monkeypatch.setattr(dj_timezone, "now", lambda: SPLIT_MOMENT)

    capture(client, makassar, "hello", "3f1b0c9e-9999-4a2b-8c3d-000000000010")

    assert dj_timezone.get_current_timezone_name() == settings.TIME_ZONE
