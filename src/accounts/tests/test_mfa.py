"""A second factor, increment 1: the machinery, and deliberately no enforcement.

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
