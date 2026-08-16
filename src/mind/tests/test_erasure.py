"""Erasing an account, against an append-only log that refuses to be erased.

`ActivityEvent` is append-only by database trigger, not by intention — the whole
point being that folded projections are only trustworthy if the log genuinely
cannot be edited. The trigger fires `BEFORE UPDATE OR DELETE`.

**So deleting a `User` was impossible.** `ActivityEvent.owner` is
`on_delete=CASCADE`, so `User.delete()` issues a `DELETE` against the log and the
trigger raises. The model had reasoned this through for the *node* reference and
made it non-constraining — "CASCADE, SET_NULL and SET_DEFAULT are each a
*mutation* of the log, which the append-only trigger refuses" — and the `owner`
reference never got the same treatment. Nothing had noticed because nothing had
ever deleted an account.

**The line taken: append-only means history cannot be rewritten *within a live
account*.** It was never a promise to outlive the account's own erasure. When the
owner goes, their log goes with them — and it has to, because the log is not
content-free: concept events carry the labels somebody typed, which on real
material include other people's names, and every event carries the username as
`actor`.

The exemption is deliberately narrow. It is not a boolean "allow deletes now";
it names **one owner id**, inside **one transaction**, so an erasure in flight
cannot take another account's log with it. Everything below exists to hold that
boundary in place.
"""

import pytest
from django.contrib.auth import get_user_model
from django.db import DatabaseError, connection, transaction

from accounts import services as account_services
from mind import services
from mind.models import ActivityEvent, Node, NodeSource

pytestmark = pytest.mark.django_db(transaction=True)

NOW = None  # set per-test from the fixtures below


@pytest.fixture
def when():
    from datetime import datetime, timezone as dt_timezone

    return datetime(2026, 6, 10, 9, 0, tzinfo=dt_timezone.utc)


def a_thought(owner, text, *, when):
    return services.capture(
        owner, content=text, captured_at=when,
        source=NodeSource.WEB, actor=owner.get_username(),
    )


# ---------------------------------------------------------------------------
# The guard
# ---------------------------------------------------------------------------


def test_a_bare_user_delete_is_refused(owner, when):
    """A regression guard, and it passes on the day it is written.

    This is the behaviour that made account deletion impossible, and it stays
    the behaviour: erasure must go through `purge_account`, which is the only
    thing that sets the exemption. If somebody later loosens the trigger into a
    general "allow deletes", this is the test that goes red.
    """
    a_thought(owner, "the boiler again", when=when)
    assert ActivityEvent.objects.filter(owner=owner).exists()

    with pytest.raises(DatabaseError):
        with transaction.atomic():
            owner.delete()


def test_the_log_still_refuses_an_ordinary_update(owner, when):
    a_thought(owner, "the boiler again", when=when)
    event = ActivityEvent.objects.filter(owner=owner).first()

    with pytest.raises(DatabaseError):
        with transaction.atomic():
            ActivityEvent.objects.filter(pk=event.pk).update(actor="somebody else")


def test_the_log_still_refuses_an_ordinary_delete(owner, when):
    """The exemption is for erasure, not for deletion in general."""
    a_thought(owner, "the boiler again", when=when)
    event = ActivityEvent.objects.filter(owner=owner).first()

    with pytest.raises(DatabaseError):
        with transaction.atomic():
            ActivityEvent.objects.filter(pk=event.pk).delete()


# ---------------------------------------------------------------------------
# The erasure
# ---------------------------------------------------------------------------


def test_purging_an_account_takes_its_log_with_it(owner, when):
    a_thought(owner, "the boiler again", when=when)
    a_thought(owner, "ring the plumber", when=when)
    assert ActivityEvent.objects.filter(owner=owner).count() >= 2

    account_services.purge_account(owner, now=when)

    assert not ActivityEvent.objects.exists()
    assert not Node.objects.exists()
    assert not get_user_model().objects.filter(username="vince").exists()


def test_it_does_not_reach_another_persons_log(owner, other_owner, when):
    """What the owner-scoped setting is for. A boolean exemption would pass the
    test above and fail this one."""
    a_thought(owner, "mine", when=when)
    a_thought(other_owner, "theirs", when=when)

    account_services.purge_account(owner, now=when)

    assert ActivityEvent.objects.filter(owner=other_owner).exists()
    assert Node.objects.get().owner == other_owner


def test_the_exemption_does_not_outlive_the_transaction(owner, other_owner, when):
    """`SET LOCAL`, not `SET`. A connection is reused across requests, so an
    exemption that survived the transaction would leave the log erasable by
    whatever ran next on the same connection."""
    a_thought(owner, "mine", when=when)
    a_thought(other_owner, "theirs", when=when)
    account_services.purge_account(owner, now=when)

    with connection.cursor() as cursor:
        cursor.execute("SELECT current_setting('mind.erasing_owner', true)")
        assert cursor.fetchone()[0] in (None, "")

    survivor = ActivityEvent.objects.filter(owner=other_owner).first()
    with pytest.raises(DatabaseError):
        with transaction.atomic():
            ActivityEvent.objects.filter(pk=survivor.pk).delete()
