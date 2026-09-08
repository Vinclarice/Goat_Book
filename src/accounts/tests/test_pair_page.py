"""Saying yes to a phone — `android-login-redesign-plan.md` Half B, increment 3.

**This is the page the whole flow is built around, and the only dangerous verb
in it.** `pair/start` and `pair/poll` are unauthenticated because they grant
nothing; this is where a person, already logged in and already past their second
factor, turns an inert request into a ninety-day credential.

**It is also the only place the flow's real weakness can be addressed.** Every
design shaped like this shares one: the attack is not cryptographic, it is
*"type this code into your Clarice"*. Nothing in `pairing.py` can help — by the
time a code is typed, the person has already been persuaded. What a page can do
is make the decision legible: say what is being granted, in the words the token
page already uses, so *approve* is a decision rather than a reflex.

**The second factor is not re-proved here, it is required to have been proved.**
An account with a confirmed device reaches this page only on a verified session
— which is what makes pairing something other than a way around the door it
stands next to. Not a new gate: `/admin/` has taken exactly this since
`admin-mfa-plan.md` increment 4.
"""
from django.test import TestCase
from django.urls import reverse

from accounts import pairing
from accounts.models import PairingRequest, PersonalAccessToken, User
from clarice.testing import sign_into_the_admin


PASSWORD = "a rather secure password"


class ReachingThePageTest(TestCase):
    def setUp(self):
        self.vince = User.objects.create_user("vince", "v@example.com", PASSWORD)

    def test_a_stranger_is_sent_to_log_in(self):
        """The page grants a credential. Nobody reaches it without a session."""
        response = self.client.get("/pair/")

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response["Location"])

    def test_somebody_logged_in_can_open_it(self):
        self.client.force_login(self.vince)

        self.assertEqual(self.client.get("/pair/").status_code, 200)

    def test_an_account_with_a_second_factor_must_have_proved_it(self):
        """**The property that keeps this from being a way around the door it
        stands beside.** A password alone must not mint a ninety-day token on an
        account with a factor -- which is what `/api/v1/login` enforces for the
        credential path, and this is the same rule for the pairing path.
        """
        from django_otp.plugins.otp_totp.models import TOTPDevice

        TOTPDevice.objects.create(user=self.vince, name="phone", confirmed=True)
        self.client.force_login(self.vince)

        response = self.client.get("/pair/")

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("verify"), response["Location"])

    def test_it_comes_back_here_after_verifying(self):
        """Sent to prove it is you, then returned to what you were doing.
        Dropping somebody on the admin index instead would leave them to find
        this page again with a code expiring on a phone in their hand."""
        from django_otp.plugins.otp_totp.models import TOTPDevice

        TOTPDevice.objects.create(user=self.vince, name="phone", confirmed=True)
        self.client.force_login(self.vince)

        response = self.client.get("/pair/")

        self.assertIn("next=/pair/", response["Location"])

    def test_a_verified_session_reaches_it(self):
        sign_into_the_admin(self.client, self.vince)

        self.assertEqual(self.client.get("/pair/").status_code, 200)

    def test_an_account_with_no_factor_is_not_asked_to_prove_one(self):
        """There is nothing to verify, and sending somebody to a page that
        cannot help them would be a lock with no key."""
        self.client.force_login(self.vince)

        self.assertEqual(self.client.get("/pair/").status_code, 200)


class WhatThePageSaysTest(TestCase):
    """**The page's actual job.** An approval screen that does not say what it
    approves is a click-through, and a click-through is what the social attack
    on this flow needs."""

    def setUp(self):
        self.vince = User.objects.create_user("vince", "v@example.com", PASSWORD)
        self.client.force_login(self.vince)

    def test_it_names_what_a_paired_phone_will_be_able_to_do(self):
        page = self.client.get("/pair/").content.decode()

        self.assertIn("Daily Page", page)
        self.assertIn("Agenda", page)
        self.assertIn("captures", page)

    def test_it_says_the_credential_expires(self):
        """Ninety days is a property of the thing being granted, so it belongs
        on the screen where it is granted rather than only in a docstring."""
        self.assertIn("90 days", self.client.get("/pair/").content.decode())

    def test_it_uses_the_same_words_as_the_token_page(self):
        """One vocabulary for scopes, not two. `TokenForm.SCOPE_CHOICES` is the
        authority for what a scope means to a person -- `principles.md`'s *one
        rule, one authoritative definition* -- and this page reads it rather
        than describing the same seven capabilities in its own words."""
        from accounts.forms import TokenForm

        page = self.client.get("/pair/").content.decode()

        label = dict(TokenForm.SCOPE_CHOICES)["day:read"]
        self.assertIn(label.split("—")[0].strip(), page)


class ApprovingTest(TestCase):
    def setUp(self):
        self.vince = User.objects.create_user("vince", "v@example.com", PASSWORD)
        self.client.force_login(self.vince)

    def approve(self, code):
        return self.client.post("/pair/", {"code": code})

    def test_a_correct_code_approves_the_waiting_request(self):
        started = pairing.start(label="Pixel")

        response = self.approve(started.user_code)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(PairingRequest.objects.get().owner, self.vince)

    def test_approving_does_not_itself_mint_a_token(self):
        """The token is minted when the *phone* redeems, over its own
        connection. If approving minted one here it would have to be carried,
        which is the thing this flow exists to stop."""
        started = pairing.start()

        self.approve(started.user_code)

        self.assertFalse(PersonalAccessToken.objects.exists())

    def test_the_phone_can_then_collect_it(self):
        """End to end through the page: nothing secret crossed between the two
        devices except a code that granted nothing until this moment."""
        started = pairing.start()
        self.approve(started.user_code)

        token = self.client.post(
            "/api/v1/pair/poll",
            {"device_code": started.device_code},
            content_type="application/json",
        ).json()["token"]

        self.assertIsNotNone(token)
        self.assertEqual(PersonalAccessToken.objects.get().owner, self.vince)

    def test_a_wrong_code_says_so_and_grants_nothing(self):
        pairing.start()

        response = self.approve("ZZZZ-ZZZZ")

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(PairingRequest.objects.get().owner)
        self.assertIn("didn", response.content.decode().lower())

    def test_a_code_typed_in_any_shape_is_accepted(self):
        """Somebody reading eight characters off a phone will type them how
        they like. This is the one thing the page asks a person to do."""
        started = pairing.start()

        self.approve(started.user_code.lower().replace("-", " "))

        self.assertEqual(PairingRequest.objects.get().owner, self.vince)

    def test_approving_tells_you_which_phone_it_was(self):
        """So the answer to *did that work* is on the screen, rather than
        being inferred from the phone stopping asking."""
        started = pairing.start(label="Pixel 9")

        page = self.approve(started.user_code).content.decode()

        self.assertIn("Pixel 9", page)

    def test_it_grants_to_whoever_approved_rather_than_whoever_asked(self):
        """A pairing request has no owner until this moment -- the §4 rule 1
        deviation -- so *who this becomes* is decided here and nowhere else."""
        priya = User.objects.create_user("priya", "p@example.com", PASSWORD)
        started = pairing.start()
        self.client.force_login(priya)

        self.approve(started.user_code)

        self.assertEqual(PairingRequest.objects.get().owner, priya)


class TheTwoCodesAreNotConfusedTest(TestCase):
    """**The defect a real attempt found, September 7, 2026.**

    Vince tapped *Connect this phone*, took the pairing code to the web, and
    got back *"That code didn't work. Try the next one your app shows."* —
    which is `verify`'s message, not `pair`'s. He had never reached the pairing
    page at all.

    **The flow put two different codes in front of one box.** `/pair/` redirects
    an account with a second factor to *Confirm it's you*, which asks for "the
    code from your authenticator app" — at the exact moment the person is
    holding a pairing code on the phone in their other hand. Typing it there is
    not a mistake; it is the obvious reading of the screen.

    **Nothing about the gate is wrong and it is not being weakened.** What was
    wrong is that the page said the same thing whether you arrived from
    `/admin/` or mid-pairing. It now says which code it wants when it knows.
    """

    def setUp(self):
        self.vince = User.objects.create_user("vince", "v@example.com", PASSWORD)
        from django_otp.plugins.otp_totp.models import TOTPDevice

        TOTPDevice.objects.create(user=self.vince, name="phone", confirmed=True)
        self.client.force_login(self.vince)

    def test_verifying_on_the_way_to_pairing_says_which_code_it_wants(self):
        page = self.client.get(f"{reverse('verify')}?next=/pair/").content.decode()

        self.assertIn("authenticator", page.lower())
        # The distinguishing sentence: it has to name the *other* code to rule
        # it out, because naming only the one it wants is what the page already
        # did and is what somebody read straight past.
        self.assertIn("not the code", page.lower())

    def test_verifying_on_the_way_anywhere_else_is_unchanged(self):
        """The admin path is the one this page was built for and it gains
        nothing from a sentence about phones."""
        page = self.client.get(reverse("verify")).content.decode()

        self.assertNotIn("not the code", page.lower())

    def test_the_wrong_code_message_says_which_code_when_pairing(self):
        """The message Vince actually saw. On the way to pairing it now names
        the confusion outright rather than sending somebody to fetch another
        code of the wrong kind."""
        response = self.client.post(f"{reverse('verify')}?next=/pair/", {"code": "000000"})

        self.assertIn("authenticator", response.content.decode().lower())

    def test_it_still_lets_a_real_code_through_to_pairing(self):
        """The gate is unchanged: a correct second factor still arrives at the
        page it was going to."""
        from django_otp.oath import TOTP
        from django_otp.plugins.otp_totp.models import TOTPDevice

        device = TOTPDevice.objects.get(user=self.vince)
        totp = TOTP(device.bin_key, device.step, device.t0, device.digits)
        code = str(totp.token()).zfill(device.digits)

        response = self.client.post(f"{reverse('verify')}?next=/pair/", {"code": code})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/pair/")


class TheSecondFactorSaysWhyItRefusedTest(TestCase):
    """**The compounding failure, found by the second real attempt.**

    Vince typed the pairing code here, was told which code the page wanted,
    typed his authenticator code — and was refused again with the same message.

    **`ThrottlingMixin` is why, and nothing said so.** Every failed
    verification increments a per-device counter and `verify_token` refuses
    *before checking* while the backoff runs — 1, 2, 4, 8, 16, 32 seconds. So a
    handful of attempts with the wrong kind of code locks out the right one,
    and a TOTP code lives about thirty seconds, which means somebody in a
    32-second backoff is chasing codes that expire before the door reopens.
    Each attempt makes it worse.

    **This is `admin-mfa-plan.md` §2.4 read from the other side.** That section
    established the device's own backoff as the *whole* protection here,
    because `django-axes` cannot see this step. Correct — and it means this page
    is the only place that can explain it.

    **And the message I added made it worse before it made it better.** It
    asserted *"that is not the code this page wants"* for every failure on the
    pairing path, including a correct code refused by the backoff. A message
    that names what somebody typed has to be right about it.
    """

    def setUp(self):
        from django_otp.plugins.otp_totp.models import TOTPDevice

        self.vince = User.objects.create_user("vince", "v@example.com", PASSWORD)
        self.device = TOTPDevice.objects.create(
            user=self.vince, name="phone", confirmed=True
        )
        self.client.force_login(self.vince)

    def verify(self, code, pairing_path=True):
        url = f"{reverse('verify')}?next=/pair/" if pairing_path else reverse("verify")
        return self.client.post(url, {"code": code})

    def test_a_throttled_attempt_says_to_wait_rather_than_to_try_again(self):
        """*Try the next one your app shows* is the worst possible advice
        during a backoff: the next one is refused too, and asking for it
        lengthens the lock."""
        self.verify("000000")

        page = self.verify("000001").content.decode().lower()

        self.assertIn("too many", page)
        self.assertNotIn("try the next one", page)

    def test_it_says_roughly_how_long_to_wait(self):
        """A wait with no number is indistinguishable from a refusal."""
        self.verify("000000")

        self.assertIn("second", self.verify("000001").content.decode().lower())

    def test_the_wait_is_explained_off_the_pairing_path_too(self):
        """The backoff is a property of the device, not of where somebody was
        going. Explaining it only on one route would leave the admin path with
        the advice that makes things worse."""
        self.verify("000000", pairing_path=False)

        page = self.verify("000001", pairing_path=False).content.decode().lower()

        self.assertIn("too many", page)

    def test_an_untrottled_wrong_code_on_the_pairing_path_mentions_both_codes(self):
        """**Without asserting which one was typed.** A recovery code is also
        eight characters of letters and digits, so this page cannot tell one
        from a pairing code by looking — and telling somebody using a recovery
        code that they typed the wrong kind would be wrong."""
        page = self.verify("000000").content.decode().lower()

        self.assertIn("authenticator", page)
        self.assertIn("phone", page)
        # The claim that was too strong to keep.
        self.assertNotIn("that is not the code this page wants", page)

    def test_an_untrottled_wrong_code_elsewhere_is_unchanged(self):
        page = self.verify("000000", pairing_path=False).content.decode().lower()

        # "try the next one" rather than "didn't work": Django escapes the
        # apostrophe to `&#x27;`, so asserting the human spelling matches
        # nothing. Written the other way first and it failed on exactly that,
        # with the page rendering correctly the whole time.
        self.assertIn("try the next one", page)
        self.assertNotIn("phone", page)
