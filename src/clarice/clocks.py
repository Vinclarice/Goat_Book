"""Whose clock a day is measured on — **D16**.

`temporal-substrate-plan.md` asked *whose clock is a morning?* and warned that
deciding it late means *"8 nights this quarter"* quietly meant UTC nights. The
answer is **the person's**, and it was already decided: `User.time_zone` has
been the single place a day boundary is stored since
`per-user-time-zones-plan.md` shipped on August 1, 2026. This module does not
add a policy. It lets the knowledge core inherit the one that exists.

**Why this is not `django.utils.timezone.localdate`.** That reads the zone the
middleware activated *for this request* — the **viewer's** zone. Which is right
for *today*, where the viewer is the owner, and wrong for the question the
knowledge core keeps asking:

> which day was this note on?

That is a property of the record, not of whoever opened it. `localdate` gives it
three different answers — the reader's zone in a request, `settings.TIME_ZONE`
in a management command, and the owner's only by coincidence — and a note that
falls on a different day depending on who is looking is not a time-zone feature.

**So the day is a function of the owner and the instant, and of nothing else.**

**Where the boundary sits.** `timezone.localdate()` stays correct and stays in
use for *today* on a request-scoped surface; the task core is full of it and
none of that is wrong. Use `day_for` when the question is which day a **stored
instant** belongs to, and `today_for` when the answer must not depend on a
request — a management command, a scheduled pass, anything running for somebody
who is not there.
"""

import datetime

from django.conf import settings
from django.utils import timezone
from zoneinfo import ZoneInfo

from accounts.models import resolve_time_zone


def zone_for(owner):
    """The owner's zone, falling back rather than raising.

    `resolve_time_zone` returns None for a key tzdata has retired, and the
    fallback is the reason it exists: in a request that would be a 500 on every
    page, and in a nightly pass it would stop the run for everyone after them.
    That argument was made for the digest and it carries here unchanged.
    """
    zone = resolve_time_zone(getattr(owner, "time_zone", "") or "")
    return zone if zone is not None else ZoneInfo(settings.TIME_ZONE)


def day_for(owner, instant) -> datetime.date:
    """The date ``instant`` fell on, on the owner's clock.

    The one question the knowledge core asks over and over -- of `captured_at`,
    of `occurred_at`, of `completed_at` -- and the one it was answering in UTC.
    """
    return instant.astimezone(zone_for(owner)).date()


def today_for(owner) -> datetime.date:
    """The owner's today, without needing anyone to be looking.

    `timezone.localdate()` where a request is in flight, and the honest answer
    where one is not.
    """
    return day_for(owner, timezone.now())
