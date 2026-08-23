"""Fixtures for tests that cross both cores.

**Here rather than under `clarice/tests/`** so that `mind`'s pytest suite can
import it too without reaching into another app's test package. `clarice` is
already where the rules that outrank one app live (`search.py`, `life_log.py`,
`recall.py`); the fixtures for those rules belong beside them.

`code-review-2026-08-21.md` R10: three files in `clarice/tests/` had grown the
same user-and-area `setUp`, and one had built a `Node` by hand with fields the
model does not have -- which is R1, and the reason eleven tests could never run.
**A factory nobody hand-rolls is the repair for both.**
"""

import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone


PASSWORD = "a secure password"


def make_user(username="alice", **fields):
    return get_user_model().objects.create_user(
        username, f"{username}@example.com", PASSWORD, **fields
    )


def make_area(owner, title="Home"):
    from lists.models import List

    return List.objects.create(owner=owner, title=title)


def make_task(area, text="Call the plumber", **fields):
    """Through the service, not the model.

    `create_item` positions the row and anchors a commitment; a task built with
    `Item.objects.create` is a shape the application never produces, which is
    the sort of test that passes while the thing it stands for is broken.
    """
    from lists import services as list_services

    return list_services.create_item(area, text, **fields)


def make_node(owner, content="the boiler is making that noise again", *, when=None):
    """A captured note, through `mind.services.capture`.

    `Node` holds `original_content`, `captured_at` and `source`; `title` and
    `body` belong to `Revision` and never existed here. Hand-building one is
    how eleven of eighteen increment-4 tests came to raise `TypeError` at
    construction without anybody noticing -- so this is the only way these
    suites make one.
    """
    from mind import services as mind_services
    from mind.models import NodeSource

    return mind_services.capture(
        owner,
        content=content,
        captured_at=when if when is not None else timezone.now(),
        source=NodeSource.WEB,
        actor=owner.get_username(),
    )


def make_event(owner, event_type, when, **subjects):
    """One row in the log, written directly.

    Deliberately not through `clarice.life_log.record`: that module guards the
    life vocabulary and raises on the knowledge-core events these tests need to
    place beside a task completion. The guard is right, and a test of what the
    log *contains* is not the caller it is guarding against.
    """
    from mind.models import ActivityEvent

    return ActivityEvent.objects.create(
        owner=owner,
        event_type=event_type,
        occurred_at=when,
        actor=owner.get_username(),
        **subjects,
    )


class CrossCoreTestCase(TestCase):
    """One owner and one area, which every suite over the log needs first.

    The third byte-for-byte copy of this `setUp` was what R10 named; `since()`
    would have made a fourth.
    """

    def setUp(self):
        self.alice = make_user("alice")
        self.area = make_area(self.alice)

    def a_task(self, text="Call the plumber", **fields):
        return make_task(self.area, text, **fields)

    def a_node(self, content="the boiler is making that noise again", *, when=None):
        return make_node(self.alice, content, when=when)

    def an_entry(self, day):
        from daily.models import DailyEntry

        entry, _ = DailyEntry.objects.get_or_create(owner=self.alice, date=day)
        return entry

    def someone_else(self, username="bob"):
        return make_user(username)


def days(n):
    return datetime.timedelta(days=n)


def sign_into_the_admin(client, user):
    """Log in *and* verify — what reaching `/admin/` costs since August 23, 2026.

    `admin-mfa-plan.md` increment 4 made `is_verified()` part of
    `AdminSite.has_permission`, so `force_login` alone no longer opens the
    admin. Six existing tests found that out at once, which is the gate working:
    the meaning of *signed in as an admin* genuinely changed, and a helper is
    better than six copies of the same two extra lines.

    A confirmed device and `otp_login` rather than a code round trip: what these
    tests are about is the page they are asking for, and TOTP itself is proved
    in `accounts/tests/test_admin_second_factor.py`.
    """
    from django_otp import login as otp_login
    from django_otp.plugins.otp_totp.models import TOTPDevice

    device = TOTPDevice.objects.create(user=user, name="test phone", confirmed=True)
    client.force_login(user)
    # `otp_login` writes the device into the session, which is what
    # `is_verified()` reads. It needs a request-shaped object; the test client's
    # session is reachable through this dance and nothing simpler works.
    session = client.session
    session["otp_device_id"] = device.persistent_id
    session.save()
    return device
