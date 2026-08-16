"""Leaving: requesting deletion, changing your mind, and the erasure itself.

`commercial-blueprint.md` calls account deletion and data export a legal blocker
rather than a feature gap — Sentry and Resend already process other people's
data. This is the deletion half.

**Three states, and `is_active` is deliberately not one of them.** That flag
already means "pending admin approval", and overloading it would make two
unrelated situations indistinguishable in the admin and in every login path. A
departing account keeps working normally during its grace period, which is also
what keeps *cancel* reachable: they log in and press the button, and no
signed-link email flow has to exist.
"""

from datetime import timedelta

from django.db import connection, transaction

from mind.models import ActivityEvent

# Long enough to survive a change of mind, a holiday, and an account somebody
# else deleted in anger on their behalf. Short enough to be a real promise.
ACCOUNT_DELETION_GRACE = timedelta(days=30)


def request_deletion(user, *, now):
    """Schedule an account for erasure. Reversible until the grace period ends.

    Idempotent: asking twice does not move the date further out, because that
    would let a repeated click quietly extend the very window somebody is
    waiting on.
    """
    if user.deletion_requested_at is None:
        user.deletion_requested_at = now
        user.save(update_fields=["deletion_requested_at"])
    return user


def cancel_deletion(user):
    """Change your mind. Nothing has been touched, so nothing is restored."""
    if user.deletion_requested_at is not None:
        user.deletion_requested_at = None
        user.save(update_fields=["deletion_requested_at"])
    return user


def purge_at(user):
    """When this account becomes eligible, or None if it is not leaving."""
    if user.deletion_requested_at is None:
        return None
    return user.deletion_requested_at + ACCOUNT_DELETION_GRACE


def due_for_purge(now):
    """Accounts whose grace period has run out."""
    from django.contrib.auth import get_user_model

    return get_user_model().objects.filter(
        deletion_requested_at__isnull=False,
        deletion_requested_at__lte=now - ACCOUNT_DELETION_GRACE,
    )


@transaction.atomic
def purge_account(user, *, now):
    """Erase an account and everything it owns. Irreversible, and immediate.

    **The append-only log has to be deleted explicitly, and cannot be reached by
    cascade.** `ActivityEvent` is append-only by database trigger, so a plain
    `user.delete()` issues a `DELETE` against it and is refused — which is why
    account deletion was impossible before this existed, and why it stays
    impossible by any route other than this function.

    The exemption is a transaction-local setting naming **this owner**, so an
    erasure in flight cannot take another account's log with it, and `SET LOCAL`
    means it dies with the transaction rather than lingering on a reused
    connection. `mind/migrations/0015` carries the matching trigger.

    Returns what it removed, per model, so the command that calls this can say
    what it did rather than what existed.
    """
    owner_id = user.pk
    with connection.cursor() as cursor:
        # Parameterised through `set_config` rather than interpolated into a
        # `SET LOCAL` statement: SET does not take bind parameters, and building
        # that string by hand is the one place in this codebase that would need
        # to. `true` is the is_local flag.
        cursor.execute("SELECT set_config('mind.erasing_owner', %s, true)",
                       [str(owner_id)])

    removed = {}
    removed["mind.ActivityEvent"] = ActivityEvent.objects.filter(
        owner=user
    ).delete()[0]

    # Everything else is an ordinary cascade -- lists, daily, routines, review,
    # the rest of mind, and the access tokens.
    _, per_model = user.delete()
    removed.update(per_model)
    return removed
