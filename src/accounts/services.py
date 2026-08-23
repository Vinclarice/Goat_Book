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
from django.utils import timezone

from accounts import emails
from mind.models import ActivityEvent

# Long enough to survive a change of mind, a holiday, and an account somebody
# else deleted in anger on their behalf. Short enough to be a real promise.
ACCOUNT_DELETION_GRACE = timedelta(days=30)


@transaction.atomic
def request_deletion(user, *, now):
    """Schedule an account for erasure. Reversible until the grace period ends.

    Idempotent: asking twice does not move the date further out, because that
    would let a repeated click quietly extend the very window somebody is
    waiting on — and it does not send a second email either, for the same
    reason a doubled click is not a second decision.

    **The email is the half that protects somebody who did not do this.** The
    password re-entry on the form stops a passer-by at an unlocked screen; it
    does nothing against someone who has the password. A message to the address
    on the account is what makes the thirty days a real window rather than one
    that only helps if you happen to sign in and read a banner.
    """
    if user.deletion_requested_at is not None:
        return user

    # The whole body is one unit: the timestamp must not outlive the warning
    # it depends on. A send that failed used to leave the account scheduled
    # with nobody told -- and the guard above then made that permanent,
    # because the retry took the early return and sent nothing. The guard is
    # right; what was missing is its precondition, that the message went out
    # when the timestamp was written.
    #
    # Sending inside the transaction puts an SMTP round trip between BEGIN and
    # COMMIT, which is why settings.py sets EMAIL_TIMEOUT: unbounded, a hung
    # relay would hold this open for as long as it liked.
    #
    # The `except` restores the *instance*, which the rollback cannot reach.
    # It is provably None here given the guard above, and named rather than
    # written as None so that removing the guard cannot silently make this
    # wrong. Without it the caller's user goes on claiming a timestamp the
    # database no longer has, and the retry takes the early return again --
    # the very defect being fixed. The same divergence bit `pause_routine`
    # during D9.
    previously_requested_at = user.deletion_requested_at
    try:
        user.deletion_requested_at = now
        user.save(update_fields=["deletion_requested_at"])
        emails.confirm_deletion_scheduled(user, purge_at=purge_at(user))
    except Exception:
        user.deletion_requested_at = previously_requested_at
        raise
    return user


def cancel_deletion(user):
    """Change your mind. Nothing has been touched, so nothing is restored.

    **Deliberately not atomic, unlike `request_deletion` above**, and the
    asymmetry is the point rather than an oversight. There the email *is* the
    protection, so a timestamp without one is a silent loss and rolling back is
    correct. Here the person is at the screen having just asked to keep their
    account: rolling the cancellation back because its receipt bounced would
    leave the account scheduled for erasure, trading a missing confirmation for
    exactly the outcome the confirmation was about.

    So the cancellation stands and the send may fail loudly on top of it.
    `test_cancelling_survives_a_failed_confirmation` pins this.
    """
    if user.deletion_requested_at is None:
        return user

    user.deletion_requested_at = None
    user.save(update_fields=["deletion_requested_at"])
    emails.confirm_deletion_cancelled(user)
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
    # Read before anything is destroyed, and sent before the transaction that
    # destroys it. A receipt that depends on the record whose destruction it is
    # confirming is a receipt that does not send.
    username, address = user.get_username(), user.email
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

    # After the deletes, inside the transaction. If anything above raises, the
    # rollback takes the account back and this never ran -- which is the right
    # way round: a receipt for an erasure that did not happen is worse than no
    # receipt. Django's locmem and SMTP backends both send immediately rather
    # than on commit, so the narrow reverse risk is a message sent for a
    # transaction that then fails; that is the failure worth having.
    if address:
        emails.confirm_account_erased(username=username, email=address)
    return removed


@transaction.atomic
def redeem_invitation(invitation, form):
    """Create the invited account and spend the invitation, together — **S1**.

    **One transaction, and that is the whole reason this is a service rather
    than four lines in the view.** An account created against an invitation that
    was not marked spent is a second way in; an invitation marked spent with no
    account behind it is a link somebody paid for and cannot use. Neither is
    recoverable by hand from the outside.

    `is_active` is set here rather than in `SignUpForm.save`, which stays the
    public form's behaviour: a stranger with no invitation still waits.
    """
    user = form.save(commit=False)
    user.is_active = True
    user.save()

    invitation.redeemed_at = timezone.now()
    invitation.redeemed_by = user
    invitation.save(update_fields=["redeemed_at", "redeemed_by"])
    return user
