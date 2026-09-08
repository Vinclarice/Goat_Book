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
