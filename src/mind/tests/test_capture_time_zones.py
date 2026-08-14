"""A capture from the phone reads "tomorrow" as the owner's tomorrow.

The same defect as `commercial-blueprint.md` 2, in the knowledge core, and in
code written the same day the parser was. `TimeZoneMiddleware` activates a zone
from `request.user`, which is still anonymous while middleware runs on a token
request -- so `_propose_any_commitment` computed its `today` in the *server's*
zone, and a relative date parsed at capture came out wrong for anyone not
living in `settings.TIME_ZONE`.

Found by asking whether the task core's defect had a twin here rather than by
anything failing, which is the only way this one surfaces: the proposal is
plausible either way, and being a day out is invisible unless you already know
what day you meant.

The task core's fix works because both its token paths converge on one
function. This core has its own token table and its own resolver, so it needs
the same call in its own seam -- one line, in the one place an owner first
exists.
"""

import json
from datetime import date, datetime, timezone as dt_timezone
from zoneinfo import ZoneInfo

import pytest

from mind.models import ApiToken, Facet, FacetKind

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


def test_tomorrow_is_the_owners_tomorrow_not_the_servers(client, makassar, monkeypatch):
    from django.utils import timezone as dj_timezone

    monkeypatch.setattr(dj_timezone, "now", lambda: SPLIT_MOMENT)
    _, raw = ApiToken.issue(makassar, label="Android")

    client.post(
        "/mind/api/v1/capture",
        data=json.dumps({"text": "dentist tomorrow"}),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {raw}",
        HTTP_IDEMPOTENCY_KEY="3f1b0c9e-9999-4a2b-8c3d-000000000009",
    )

    facet = Facet.objects.get(kind=FacetKind.ACTIONABLE)
    assert facet.data["due_date"] == MAKASSAR_TOMORROW.isoformat()
    assert facet.data["due_date"] != SERVER_TOMORROW.isoformat()


def test_the_zone_does_not_outlive_the_request(client, makassar, monkeypatch):
    """Activating a zone mid-request means something has to undo it, and worker
    threads are reused. `TimeZoneMiddleware`'s `finally` is what does -- this
    fails if this core ever stops running behind it."""
    from django.conf import settings
    from django.utils import timezone as dj_timezone

    monkeypatch.setattr(dj_timezone, "now", lambda: SPLIT_MOMENT)
    _, raw = ApiToken.issue(makassar, label="Android")

    client.post(
        "/mind/api/v1/capture",
        data=json.dumps({"text": "hello"}),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {raw}",
        HTTP_IDEMPOTENCY_KEY="3f1b0c9e-9999-4a2b-8c3d-000000000010",
    )

    assert dj_timezone.get_current_timezone_name() == settings.TIME_ZONE
