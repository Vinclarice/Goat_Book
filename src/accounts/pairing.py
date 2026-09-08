"""Connecting a phone by approving it, rather than by carrying a token to it.

`android-login-redesign-plan.md` Half B. Three transitions, each of which
enforces something, which is why they are all here rather than split across a
read module: `start` mints, `approve` grants, `redeem` spends.

**The shape.** The phone calls [start] and shows the `user_code`. A person
types that into the web, where they are already logged in and have already
passed the second factor, and [approve] attaches them to the request. The
phone, polling [redeem], gets a token over its own connection.

**What crosses between the two devices is the `user_code` alone**, and it
grants nothing by itself — it names a request awaiting a decision. The token
goes back the way the request came.
"""
import secrets
from dataclasses import dataclass
from datetime import datetime

from django.db import IntegrityError, transaction
from django.utils import timezone

from accounts.models import (
    ANDROID_DEFAULT_SCOPES,
    ANDROID_TOKEN_LIFETIME,
    PairingRequest,
    PersonalAccessToken,
    _encode_scopes,
    hash_token,
)


#: Deliberately missing `O`, `0`, `I`, `1` and `L`. This code is read off one
#: screen and typed into another, so the failure it has to survive is a person
#: confusing two glyphs -- not an attacker, who cannot approve anything without
#: already being logged in as the victim.
ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"

#: Eight characters of a 31-symbol alphabet is a little over 39 bits. That is
#: far short of a token and is not trying to be one: what it has to guarantee
#: is that a mistype cannot land on somebody else's live request, against a
#: population of live requests that is realistically one.
CODE_LENGTH = 8

#: How often the phone should ask. Slow enough not to be a self-inflicted
#: flood, fast enough that approving feels like it did something -- and the
#: number the nginx zone for the poll endpoint is sized from, rather than the
#: other way round.
POLL_INTERVAL_SECONDS = 5


@dataclass(frozen=True)
class StartedPairing:
    """What the phone needs to keep and what it needs to show.

    Two values, and only one of them is ever displayed. Collapsing them would
    make the string on a laptop screen into the credential that mints a token.
    """

    #: Shown to a person. Formatted with a hyphen for reading; matched without.
    user_code: str
    #: Kept by the phone and never shown. The real credential of this flow.
    device_code: str
    expires_at: datetime
    interval: int = POLL_INTERVAL_SECONDS


def _readable(code: str) -> str:
    """`ABCD-EFGH`. Grouped because eight characters in one run is where people
    lose their place, and the hyphen is stripped before matching so it costs
    nothing to type or to omit."""
    half = CODE_LENGTH // 2
    return f"{code[:half]}-{code[half:]}"


def normalise(typed: str) -> str:
    """What somebody typed, reduced to what was generated.

    Upper-cased and stripped of anything outside the alphabet, so `abcd efgh`,
    `ABCD-EFGH` and `abcdefgh` are one code. Rejecting the spacing a person
    chose would be this flow failing at the only thing it asks them to do.
    """
    return "".join(c for c in typed.upper() if c in ALPHABET)


def start(label: str = "Android") -> StartedPairing:
    """A request nobody owns yet, waiting for somebody to say yes."""
    device_code = secrets.token_urlsafe(32)
    # Retried rather than made unique at the database level: two live codes
    # colliding is possible in principle, and a unique constraint would answer
    # it with a 500 at the moment somebody was trying to connect a phone.
    for _ in range(5):
        user_code = "".join(secrets.choice(ALPHABET) for _ in range(CODE_LENGTH))
        if PairingRequest.objects.filter(
            user_code_hash=hash_token(user_code), expires_at__gt=timezone.now()
        ).exists():
            continue
        try:
            row = PairingRequest.objects.create(
                label=label,
                user_code_hash=hash_token(user_code),
                device_code_hash=hash_token(device_code),
            )
        except IntegrityError:  # pragma: no cover - the device code colliding
            continue
        return StartedPairing(
            user_code=_readable(user_code),
            device_code=device_code,
            expires_at=row.expires_at,
        )
    raise RuntimeError("could not mint a free pairing code")  # pragma: no cover


# ~~DARK: no production caller.~~ **Live since September 7, 2026**, called by
# `accounts.views.pair` -- the page at `/pair/`, which was this declaration's
# named trigger and fired within the session that wrote it.
def approve(user, typed_code: str) -> PairingRequest | None:
    """Attach a person to a waiting request, or None if there is no live one.

    **Returns None for both "no such code" and "expired"**, and the caller
    shows one message for the two. A person who has mistyped and a person whose
    code has aged out both need the same thing -- start again on the phone --
    and distinguishing them would only be telling somebody which of their two
    guesses was closer.
    """
    code = normalise(typed_code)
    if not code:
        return None
    row = PairingRequest.objects.filter(
        user_code_hash=hash_token(code),
        expires_at__gt=timezone.now(),
        approved_at__isnull=True,
    ).first()
    if row is None:
        return None
    row.owner = user
    row.approved_at = timezone.now()
    # Snapshotted here, not read at redemption -- §4 rule 3. What was approved
    # is what gets granted, whatever the default becomes afterwards.
    row.scopes = _encode_scopes(ANDROID_DEFAULT_SCOPES)
    row.save(update_fields=["owner", "approved_at", "scopes"])
    return row


def redeem(device_code: str) -> str | None:
    """The raw token, once, or None.

    **None is deliberately three answers in one**: not approved yet, never
    existed, and expired. A poll that could tell them apart would let anybody
    enumerate live codes, and the phone has nothing useful to do differently in
    any of the three -- it keeps asking until its own window closes.

    Hard-deletes the request on success, so a replayed poll cannot mint a
    second ninety-day token.
    """
    with transaction.atomic():
        row = (
            PairingRequest.objects.select_for_update()
            .filter(
                device_code_hash=hash_token(device_code),
                expires_at__gt=timezone.now(),
                approved_at__isnull=False,
                owner__isnull=False,
            )
            .first()
        )
        if row is None:
            return None
        _, raw = PersonalAccessToken.generate(
            row.owner,
            label=row.label,
            # The snapshot, not the current default.
            scopes=row.scope_set,
            expires_at=timezone.now() + ANDROID_TOKEN_LIFETIME,
        )
        # §4 rule 6, and the reason redeeming is single-use at all.
        row.delete()
    return raw


# **There is no sweeper, and that is a refusal rather than an oversight.**
# One was written and deleted the same hour, because
# `test_dark_services_declare_their_deferral` found it had no caller and
# `principles.md` says a trigger that cannot fire is a refusal to be recorded
# as one. Nothing here needs it: an expired request is already inert, since
# `approve` and `redeem` both filter on `expires_at`, so a leftover row is a
# dead sixty bytes rather than a live credential. At roughly one pairing per
# phone per year, a cron to collect them would be more machinery than the rows
# it removes.
#
# **What would change the answer** is pairing becoming something done often, or
# by more than one person -- at which point this is four lines and a management
# command, and the argument above is the thing to re-read rather than repeat.
