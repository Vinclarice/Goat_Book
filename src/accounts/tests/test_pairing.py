"""Pairing a phone without carrying a secret to it — `android-login-redesign-plan.md`
Half B, increment 2.

**The requirement is stricter than "add a pairing option".** Vince: *"what I
want is to avoid having this issue where there is a need to send a token to the
phone."* That rules out the fallback as well as the main path — a flow where
the answer to *it didn't work* is still *paste a token* has not delivered it.

**The inversion is the whole design.** Today a token is minted on the laptop and
carried to the phone. Here a *request* is made on the phone and carried, as
something that grants nothing until approved, to the laptop. The token travels
back over the phone's own connection, to the device that asked for it, and is
never displayed to anybody.

## What is being defended against, written down because it is not obvious

- **Guessing a `device_code`** to steal a token somebody just approved. It is 32
  bytes from `secrets`, so this is the same non-problem as guessing a personal
  access token.
- **Guessing a `user_code`.** Approval requires an *already authenticated*
  session, so an attacker who could approve is an attacker who is already logged
  in as the victim — and would have no reason to bother. What the code space has
  to survive is therefore not an attacker but a **mistype landing on somebody
  else's live request**, which is why it is long enough that it cannot, and short
  enough to be typed.
- **Approving the wrong thing.** The real weakness of every flow shaped like
  this is social: *"type this code into your Clarice."* Nothing in this module
  fixes that; the approval page does, by saying what is being granted, and it is
  increment 3's problem.

**No failed-attempt counter, and that is a correction to the plan rather than an
omission.** The plan asked for one that destroys the request. Writing it made
clear it defends nothing here: the only caller who can attempt an approval has
already authenticated as the owner, so an attempt limit rations a person against
their own typing and stops no attack. Recorded rather than silently dropped.
"""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from accounts import pairing
from accounts.models import (
    ANDROID_DEFAULT_SCOPES,
    PairingRequest,
    PersonalAccessToken,
    User,
    hash_token,
)


class StartingAPairingTest(TestCase):
    def test_it_returns_two_different_codes(self):
        """One is shown to a person and one never is. Collapsing them into a
        single value would mean the string typed on a laptop is also the
        credential that mints a token."""
        started = pairing.start(label="Pixel")

        self.assertNotEqual(started.user_code, started.device_code)

    def test_neither_raw_code_is_stored(self):
        """The same property `PersonalAccessToken` holds: a database somebody
        can read must not yield a live pairing.

        **The user code is hashed in its normalised form, not as displayed**,
        and this test asserted the displayed one first and failed. The code
        was right and the expectation was wrong: `ABCD-EFGH` is a reading
        convenience, and hashing that instead would mean the hyphen a person
        omits changes the credential. Everything matches through
        `pairing.normalise`, which is exactly why `abcd efgh` works.
        """
        started = pairing.start()

        row = PairingRequest.objects.get()
        self.assertNotIn(started.user_code, [row.user_code_hash, row.device_code_hash])
        self.assertNotIn(started.device_code, [row.user_code_hash, row.device_code_hash])
        self.assertEqual(
            row.user_code_hash, hash_token(pairing.normalise(started.user_code))
        )
        self.assertEqual(row.device_code_hash, hash_token(started.device_code))

    def test_the_user_code_avoids_characters_people_confuse(self):
        """It is read off one screen and typed into another, so `0`/`O` and
        `1`/`I` are a mistyped code rather than a clever attack -- and a
        mistype is the failure mode this flow actually has."""
        for _ in range(25):
            code = pairing.start().user_code

            self.assertFalse(set(code) & set("O0I1L"), code)

    def test_it_has_nobody_until_somebody_approves_it(self):
        """The deliberate deviation from `architecture-trajectory.md` §4 rule
        1. A pairing request is created by an unauthenticated phone; there is
        no owner to record yet."""
        pairing.start()

        self.assertIsNone(PairingRequest.objects.get().owner)

    def test_it_expires_in_minutes_rather_than_days(self):
        started = pairing.start()

        self.assertLess(started.expires_at, timezone.now() + timedelta(minutes=30))
        self.assertGreater(started.expires_at, timezone.now())


class ApprovingAPairingTest(TestCase):
    def setUp(self):
        self.vince = User.objects.create_user("vince", "v@example.com", "pw")

    def test_approving_attaches_the_person_who_approved(self):
        started = pairing.start()

        pairing.approve(self.vince, started.user_code)

        self.assertEqual(PairingRequest.objects.get().owner, self.vince)

    def test_approving_snapshots_the_scopes_it_granted(self):
        """§4 rule 3. Without the snapshot, editing `ANDROID_DEFAULT_SCOPES`
        would retroactively change what an approved-but-unredeemed request
        hands out."""
        started = pairing.start()

        pairing.approve(self.vince, started.user_code)

        self.assertEqual(
            PairingRequest.objects.get().scope_set, set(ANDROID_DEFAULT_SCOPES)
        )

    def test_a_code_nobody_issued_approves_nothing(self):
        self.assertIsNone(pairing.approve(self.vince, "ZZZZ-ZZZZ"))

    def test_an_expired_request_cannot_be_approved(self):
        started = pairing.start()
        PairingRequest.objects.update(expires_at=timezone.now() - timedelta(minutes=1))

        self.assertIsNone(pairing.approve(self.vince, started.user_code))
        self.assertIsNone(PairingRequest.objects.get().owner)

    def test_the_code_is_matched_however_it_was_typed(self):
        """Somebody reading eight characters off a screen will type them in
        the case and spacing they feel like. Rejecting `abcd efgh` for a code
        displayed as `ABCD-EFGH` would be this flow failing at the one thing
        it asks a person to do."""
        started = pairing.start()
        typed = started.user_code.lower().replace("-", " ")

        self.assertIsNotNone(pairing.approve(self.vince, typed))


class RedeemingAPairingTest(TestCase):
    def setUp(self):
        self.vince = User.objects.create_user("vince", "v@example.com", "pw")

    def test_an_unapproved_request_yields_nothing_yet(self):
        started = pairing.start()

        self.assertIsNone(pairing.redeem(started.device_code))
        self.assertFalse(PersonalAccessToken.objects.exists())

    def test_an_approved_request_yields_a_token(self):
        started = pairing.start()
        pairing.approve(self.vince, started.user_code)

        raw = pairing.redeem(started.device_code)

        self.assertIsNotNone(raw)
        self.assertEqual(
            PersonalAccessToken.objects.get().token_hash, hash_token(raw)
        )

    def test_the_token_belongs_to_whoever_approved_it(self):
        priya = User.objects.create_user("priya", "p@example.com", "pw")
        started = pairing.start()
        pairing.approve(priya, started.user_code)

        pairing.redeem(started.device_code)

        self.assertEqual(PersonalAccessToken.objects.get().owner, priya)

    def test_the_token_carries_the_scopes_that_were_approved(self):
        started = pairing.start()
        pairing.approve(self.vince, started.user_code)

        pairing.redeem(started.device_code)

        self.assertEqual(
            PersonalAccessToken.objects.get().scope_set, set(ANDROID_DEFAULT_SCOPES)
        )

    def test_the_token_expires_like_every_other_android_token(self):
        """Pairing changes how a phone gets a token, not what a token is. A
        pairing-minted credential that outlived a login-minted one would be a
        second policy nobody chose."""
        started = pairing.start()
        pairing.approve(self.vince, started.user_code)

        pairing.redeem(started.device_code)

        self.assertIsNotNone(PersonalAccessToken.objects.get().expires_at)

    def test_redeeming_spends_the_request(self):
        """Single use, and hard-deleted -- §4 rule 6, decided at creation. A
        replayed poll must not mint a second ninety-day token."""
        started = pairing.start()
        pairing.approve(self.vince, started.user_code)

        pairing.redeem(started.device_code)

        self.assertFalse(PairingRequest.objects.exists())
        self.assertIsNone(pairing.redeem(started.device_code))
        self.assertEqual(PersonalAccessToken.objects.count(), 1)

    def test_a_device_code_nobody_issued_is_answered_like_one_still_waiting(self):
        """**No oracle.** Unknown, expired and not-yet-approved are one
        answer, so polling cannot be used to discover which codes are live."""
        self.assertIsNone(pairing.redeem("not-a-real-device-code"))

    def test_an_expired_request_yields_nothing_even_once_approved(self):
        """Approval does not extend the window. Somebody who approved and then
        left the phone in a drawer for an hour reconnects rather than finding a
        token waiting."""
        started = pairing.start()
        pairing.approve(self.vince, started.user_code)
        PairingRequest.objects.update(expires_at=timezone.now() - timedelta(minutes=1))

        self.assertIsNone(pairing.redeem(started.device_code))
        self.assertFalse(PersonalAccessToken.objects.exists())


class ThePairingEndpointsTest(TestCase):
    """The two doors, over HTTP, with no credential of any kind.

    Both are in `test_api_auth_surface.py`'s `UNAUTHENTICATED` set and both
    carry an nginx rate limit, which
    `test_unauthenticated_endpoints_are_throttled` holds against the real
    template. Those two guards are the ones that make an `auth=None` endpoint
    a deliberate act; these assert it behaves.
    """

    def start(self, **body):
        return self.client.post(
            "/api/v1/pair/start", body, content_type="application/json"
        )

    def poll(self, device_code):
        return self.client.post(
            "/api/v1/pair/poll",
            {"device_code": device_code},
            content_type="application/json",
        )

    def test_a_phone_with_no_credential_can_start_one(self):
        response = self.start(label="Pixel")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["user_code"])
        self.assertTrue(body["device_code"])
        self.assertEqual(body["interval"], pairing.POLL_INTERVAL_SECONDS)

    def test_polling_before_approval_says_nothing_yet(self):
        device_code = self.start().json()["device_code"]

        response = self.poll(device_code)

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["token"])

    def test_polling_after_approval_hands_over_the_token(self):
        vince = User.objects.create_user("vince", "v@example.com", "pw")
        started = self.start().json()
        pairing.approve(vince, started["user_code"])

        token = self.poll(started["device_code"]).json()["token"]

        self.assertIsNotNone(token)
        self.assertEqual(
            PersonalAccessToken.objects.get().token_hash, hash_token(token)
        )

    def test_the_token_it_hands_over_actually_works(self):
        """End to end, and the point of the whole flow: what the phone gets is
        a credential it can use, without anybody having carried one to it."""
        vince = User.objects.create_user("vince", "v@example.com", "pw")
        started = self.start().json()
        pairing.approve(vince, started["user_code"])
        token = self.poll(started["device_code"]).json()["token"]

        me = self.client.get("/api/v1/me", HTTP_AUTHORIZATION=f"Bearer {token}")

        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["username"], "vince")
        # Increment 1's fields, reporting what pairing granted.
        self.assertEqual(sorted(ANDROID_DEFAULT_SCOPES), me.json()["scopes"])

    def test_an_invented_device_code_is_answered_like_one_still_waiting(self):
        """**200 with a null token, not a 404.** A status code is as much of an
        oracle as a body, and distinguishing "never existed" from "not yet"
        would let anybody enumerate live codes."""
        response = self.poll("not-a-real-device-code")

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["token"])

    def test_starting_one_grants_nothing_on_its_own(self):
        """The property that makes an unauthenticated endpoint safe here: a
        request exists, and it can do nothing until a logged-in person says
        so."""
        self.start()

        self.assertFalse(PersonalAccessToken.objects.exists())
        self.assertIsNone(PairingRequest.objects.get().owner)
