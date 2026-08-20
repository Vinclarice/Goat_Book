"""A second factor: the machinery (increment 1) and enrolment (increment 2).

`design/admin-mfa-plan.md` §4 is the order, and the reason increment 1 is its
own deploy is that it must change nothing. What it adds is the ability to
*answer* whether a request has been verified -- `request.user.is_verified()`,
which `OTPMiddleware` attaches -- so that increment 4 has something to gate on.
Shipping the gate and the machinery together would mean deploying a lock and
finding out afterwards whether anybody was outside it.

So the second test below asserts the admin is still reachable on a password
alone. **That is a true statement about today and increment 4 inverts it**,
which is a contract change and belongs in that commit's story rather than being
quietly relaxed -- `principles.md`, "when a test fails, diagnose before editing
either side".
"""
from django.test import TestCase
from django.urls import reverse

from accounts.models import User


PASSWORD = "correct horse battery staple 47!"


class VerificationStateIsAvailableTest(TestCase):
    """`is_verified()` exists on every request, and is False for everyone."""

    def setUp(self):
        self.user = User.objects.create_user(
            "edith", "edith@example.com", PASSWORD, is_active=True
        )
        self.client.force_login(self.user)

    def test_an_authenticated_request_can_be_asked_whether_it_is_verified(self):
        # `tokens` rather than `account_settings`: the latter is a bare
        # redirect into the SPA, so it 302s whoever asks and would prove
        # nothing about the request that reached it.
        response = self.client.get(reverse("tokens"))

        self.assertEqual(response.status_code, 200)
        # Attached by OTPMiddleware. Without it this raises AttributeError,
        # which is the failure this test was written to produce first.
        self.assertFalse(response.wsgi_request.user.is_verified())

    def test_nobody_is_verified_yet_because_nobody_has_a_device(self):
        """The other half: `is_verified()` returning False has to mean "no
        confirmed device", not "the middleware defaulted to False for
        everybody". A device nobody can enrol yet would make the assertion
        above true for the wrong reason."""
        from django_otp.plugins.otp_totp.models import TOTPDevice

        self.assertEqual(TOTPDevice.objects.count(), 0)
        self.assertEqual(list(self.user.totpdevice_set.all()), [])


class NothingIsEnforcedYetTest(TestCase):
    """The deliberate no-op, asserted so that closing it is visible.

    Increment 4 turns this red, on purpose, and replaces it with its opposite.
    Until then it is what stops this increment from silently locking somebody
    out of production between deploys.
    """

    def setUp(self):
        self.admin = User.objects.create_superuser(
            "vince", "vince@example.com", PASSWORD
        )

    def test_a_superuser_still_reaches_the_admin_with_a_password_alone(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse("admin:index"))

        self.assertEqual(response.status_code, 200)


class EnrolmentTest(TestCase):
    """Increment 2: a person can turn a second factor on, and prove it works
    before it is trusted.

    **Confirmation is the whole point of the flow.** A device is created
    unconfirmed and stays that way until a code generated from it comes back
    correct, so somebody who scans a QR into an app that then fails to sync --
    or who never scans it at all -- has not silently armed a lock they cannot
    open. `TOTPDevice.confirmed` is the flag, and `is_verified()` ignores
    unconfirmed devices.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            "edith", "edith@example.com", PASSWORD, is_active=True
        )
        self.client.force_login(self.user)

    def device(self):
        from django_otp.plugins.otp_totp.models import TOTPDevice

        return TOTPDevice.objects.get(user=self.user)

    def valid_code(self, device=None):
        """A code the device itself would accept, at this instant."""
        from django_otp.oath import TOTP

        device = device or self.device()
        totp = TOTP(device.bin_key, device.step, device.t0, device.digits)
        return totp.token()

    def test_visiting_the_page_offers_a_device_to_scan(self):
        response = self.client.get(reverse("security"))

        self.assertEqual(response.status_code, 200)
        # The QR travels as a data: URI because the policy in
        # clarice/middleware.py allows `img-src 'self' data:` and nothing
        # else -- a generated file served from a URL would need a new rule.
        self.assertContains(response, "data:image/svg+xml;base64,")

    def test_the_device_starts_unconfirmed(self):
        self.client.get(reverse("security"))

        self.assertFalse(self.device().confirmed)

    def test_a_correct_code_confirms_the_device(self):
        self.client.get(reverse("security"))

        self.client.post(reverse("security"), data={"token": self.valid_code()})

        self.assertTrue(self.device().confirmed)

    def test_a_wrong_code_does_not_confirm_the_device(self):
        self.client.get(reverse("security"))

        self.client.post(reverse("security"), data={"token": "000000"})

        self.assertFalse(self.device().confirmed)

    def test_a_wrong_code_cannot_be_retried_without_limit(self):
        """The plan's §2.4: axes counts failures at authenticate(), and this is
        not authenticate() -- so the five-attempt lockout does not reach the
        second factor at all and the device's own throttling is the whole of
        the protection. Asserted here rather than trusted to a dependency's
        default, because that default is the only thing standing in front of a
        six-digit keyspace.

        This asserted a rising failure count first, and that was wrong about
        the domain rather than about the code: the count reached 1 and stopped.
        After the first failure the backoff is already running, so the attempts
        behind it are refused by `verify_is_allowed` *before* any verification
        happens and never reach the increment. Punishing an attempt that was
        never checked would be the odd behaviour; this is the right one.

        So the property worth asserting is not how high a counter climbs. It is
        that a **correct** code is refused while the backoff runs, which is what
        makes guessing cost wall-clock time rather than requests.
        """
        self.client.get(reverse("security"))
        device = self.device()

        self.client.post(reverse("security"), data={"token": "000000"})

        self.assertEqual(self.device().throttling_failure_count, 1)
        self.client.post(reverse("security"), data={"token": self.valid_code(device)})
        self.assertFalse(self.device().confirmed)

    def test_confirming_hands_over_recovery_codes(self):
        self.client.get(reverse("security"))

        response = self.client.post(
            reverse("security"), data={"token": self.valid_code()}, follow=True
        )

        from django_otp.plugins.otp_static.models import StaticToken

        codes = StaticToken.objects.filter(device__user=self.user)
        self.assertGreaterEqual(codes.count(), 8)
        for code in codes:
            self.assertContains(response, code.token)

    def test_recovery_codes_are_shown_once_and_not_again(self):
        """Same discipline as the raw access token: they ride in the session
        through one redirect and are popped, so a refresh does not re-display a
        credential the person was told to write down."""
        self.client.get(reverse("security"))
        first = self.client.post(
            reverse("security"), data={"token": self.valid_code()}, follow=True
        )
        a_code = first.context["recovery_codes"][0]

        again = self.client.get(reverse("security"))

        self.assertNotContains(again, a_code)

    def test_one_person_cannot_see_another_persons_device(self):
        other = User.objects.create_user(
            "sam", "sam@example.com", PASSWORD, is_active=True
        )
        self.client.get(reverse("security"))
        mine = self.device()

        self.client.force_login(other)
        self.client.get(reverse("security"))

        from django_otp.plugins.otp_totp.models import TOTPDevice

        self.assertEqual(TOTPDevice.objects.filter(user=other).count(), 1)
        self.assertNotEqual(TOTPDevice.objects.get(user=other).pk, mine.pk)


class TheSecretNeverLeavesTest(TestCase):
    """`accounts/export.py` walks whole apps, and the OTP apps are deliberately
    outside `OWNED_APPS` (see settings.py). That is the right outcome reached
    by app naming, so it is held here instead: the export's own docstring
    records D12, where a promise that was not checkable turned out not to be
    true."""

    def setUp(self):
        self.user = User.objects.create_user(
            "edith", "edith@example.com", PASSWORD, is_active=True
        )
        self.client.force_login(self.user)
        self.client.get(reverse("security"))

    def test_an_export_carries_neither_the_shared_secret_nor_a_recovery_code(self):
        from django.utils import timezone

        from accounts.export import build_archive
        from django_otp.plugins.otp_static.models import StaticDevice, StaticToken
        from django_otp.plugins.otp_totp.models import TOTPDevice

        device = TOTPDevice.objects.get(user=self.user)
        static = StaticDevice.objects.create(user=self.user, name="recovery")
        token = StaticToken.objects.create(device=static, token="abcd1234")

        archive = build_archive(self.user, now=timezone.now())

        self.assertNotIn(device.key.encode(), archive)
        self.assertNotIn(token.token.encode(), archive)


class ErasureTakesTheDevicesTest(TestCase):
    """The plan's §2.3: nothing to build, because django-otp's FK to the user
    is an ordinary CASCADE and `purge_account` calls `user.delete()`. A test
    anyway, since "the cascade covers it" is a claim about a dependency's field
    definition, which is true until a major version says otherwise."""

    def test_purging_an_account_removes_its_devices_and_says_so(self):
        from django.utils import timezone

        from accounts.services import purge_account
        from django_otp.plugins.otp_static.models import StaticDevice
        from django_otp.plugins.otp_totp.models import TOTPDevice

        user = User.objects.create_user(
            "edith", "edith@example.com", PASSWORD, is_active=True
        )
        TOTPDevice.objects.create(user=user, name="phone", confirmed=True)
        StaticDevice.objects.create(user=user, name="recovery")

        removed = purge_account(user, now=timezone.now())

        self.assertEqual(TOTPDevice.objects.count(), 0)
        self.assertEqual(StaticDevice.objects.count(), 0)
        self.assertIn("otp_totp.TOTPDevice", removed)
