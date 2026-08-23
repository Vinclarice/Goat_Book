"""The admin asks for a second factor — **`admin-mfa-plan.md` increment 4**.

The plan's own ordering: *enrol before enforcing. This is the ordering that
matters most, and getting it backwards means deploying a lock and then
discovering you are outside it.* Increments 1 and 2 shipped — middleware,
devices, enrolment and recovery codes at `/accounts/security/`. **Increment 3 is
a person's step and is not done**, so this code exists and must not deploy until
it is.

**Two commits, one deploy.** §4: *between enforcing the admin and refusing
`/api/v1/login`, a password alone still mints a ninety-day token — a window that
exists only because the two halves were split.* So both halves are here.

**Enforcement is `has_permission()` and nothing else.** §3 chose a project-owned
`AdminSite` subclass over `OTPAdminSite`, because unfold overrides admin
templates and `OTPAdminSite`'s bundled login form would render into one that
does not know about it (§2.5). The whole control is one overridden method.

**The acceptance is written to refuse a test that would pass against no
implementation.** §4: *proved by a test that authenticates successfully and is
still turned away — **not** by a test that fails to authenticate.* Every admin
test below signs in first and asserts the session is real before asking what
`/admin/` does with it.
"""

from django.test import TestCase
from django.urls import reverse
from django_otp.oath import TOTP
from django_otp.plugins.otp_static.models import StaticDevice, StaticToken
from django_otp.plugins.otp_totp.models import TOTPDevice

from accounts.models import User


PASSWORD = "a rather secure password"


def a_confirmed_device(user):
    return TOTPDevice.objects.create(user=user, name="phone", confirmed=True)


def code_for(device):
    """A currently-valid code, computed the way the device will check it."""
    totp = TOTP(device.bin_key, device.step, device.t0, device.digits, device.drift)
    totp.time = __import__("time").time()
    return f"{totp.token():0{device.digits}d}"


class TheAdminAsksForASecondFactorTest(TestCase):
    def setUp(self):
        self.vince = User.objects.create_superuser(
            "vince-admin", "vince@example.com", PASSWORD
        )

    def sign_in(self):
        """A real session through the real form, and asserted.

        **`Client.login` will not do**, for two reasons that happen to point the
        same way. `AxesBackend` needs a request and raises without one — and the
        plan's acceptance asks for *a test that authenticates successfully and
        is still turned away*, which a helper that bypasses the form does not
        demonstrate. Posting the form is both the thing that works and the thing
        being claimed.
        """
        self.client.post(
            reverse("login"), {"username": "vince-admin", "password": PASSWORD}
        )
        self.assertIn(
            "_auth_user_id",
            self.client.session,
            "the password itself must be accepted, or the test below proves nothing",
        )

    def test_an_unverified_admin_is_sent_to_verify_rather_than_back_to_login(self):
        """**The loop this was shipped with, found in a production log.**

        Django's `AdminSite.login` redirects to the index only when
        `has_permission()` — which is exactly what is false here. So an
        authenticated staff account with no verified device went `/admin/` →
        `/admin/login/` → log in → `/admin/` → `/admin/login/`, and the log
        shows five successful logins in a row. It reads as *my password is not
        working*; it was the second factor with nothing pointing at it.

        **`/accounts/verify/` existed and nothing routed to it** — the
        un-switched-on seam this project keeps shipping, committed by the change
        that was meant to close one.
        """
        self.sign_in()

        response = self.client.get("/admin/", follow=True)

        # Two hops -- `/admin/` -> `/admin/login/` -> `/accounts/verify/` --
        # because the first is Django's own `admin_view` plumbing and reusing it
        # is better than reimplementing it. What matters is where somebody ends
        # up, so the chain is followed rather than its first step asserted.
        self.assertEqual(response.redirect_chain[-1][0].split("?")[0],
                         reverse("verify"))

    def test_it_comes_back_to_where_it_was_going(self):
        """A verify page that dumped you on the index would lose the page you
        asked for, which is the thing `next` exists for.

        Encoded, because a changelist with filters carries a query of its own
        and an unencoded `next` truncates at its first `&`."""
        self.sign_in()

        response = self.client.get("/admin/accounts/user/", follow=True)

        self.assertIn("next=%2Fadmin%2Faccounts%2Fuser%2F",
                      response.redirect_chain[-1][0])

    def test_verifying_returns_you_to_the_page_you_asked_for(self):
        device = a_confirmed_device(self.vince)
        self.sign_in()

        response = self.client.post(
            reverse("verify") + "?next=/admin/accounts/user/",
            {"code": code_for(device)},
        )

        self.assertEqual(response["Location"], "/admin/accounts/user/")

    def test_somebody_not_signed_in_at_all_still_gets_the_login_form(self):
        """Only an *authenticated* staff account is redirected. A stranger has
        no business being told a second factor exists."""
        response = self.client.get("/admin/", follow=True)

        self.assertEqual(response.redirect_chain[-1][0].split("?")[0],
                         "/admin/login/")

    def test_a_superuser_with_the_right_password_is_still_turned_away(self):
        """**The whole control.** Correct password, real session, no verified
        device — and `/admin/` does not open."""
        self.sign_in()

        response = self.client.get("/admin/", follow=False)

        self.assertNotEqual(response.status_code, 200)

    def test_an_unconfirmed_device_is_not_a_second_factor(self):
        """A QR scanned into an app that never synced. `is_verified()` ignores
        an unconfirmed device, and so must this."""
        TOTPDevice.objects.create(user=self.vince, name="phone", confirmed=False)
        self.sign_in()

        self.assertNotEqual(self.client.get("/admin/").status_code, 200)

    def test_verifying_opens_it(self):
        device = a_confirmed_device(self.vince)
        self.sign_in()

        self.client.post(reverse("verify"), {"code": code_for(device)})

        self.assertEqual(self.client.get("/admin/").status_code, 200)

    def test_a_recovery_code_opens_it_too(self):
        """The route that exists for a lost phone. Without it the only way back
        is `docker exec` on the droplet — see §5, which is exactly the bound on
        what this control is worth."""
        a_confirmed_device(self.vince)
        recovery = StaticDevice.objects.create(
            user=self.vince, name="recovery codes", confirmed=True
        )
        StaticToken.objects.create(device=recovery, token="abcd1234")
        self.sign_in()

        self.client.post(reverse("verify"), {"code": "abcd1234"})

        self.assertEqual(self.client.get("/admin/").status_code, 200)

    def test_a_recovery_code_is_spent_by_using_it(self):
        a_confirmed_device(self.vince)
        recovery = StaticDevice.objects.create(
            user=self.vince, name="recovery codes", confirmed=True
        )
        StaticToken.objects.create(device=recovery, token="abcd1234")
        self.sign_in()

        self.client.post(reverse("verify"), {"code": "abcd1234"})

        self.assertFalse(recovery.token_set.filter(token="abcd1234").exists())

    def test_a_wrong_code_does_not_open_it(self):
        a_confirmed_device(self.vince)
        self.sign_in()

        self.client.post(reverse("verify"), {"code": "000000"})

        self.assertNotEqual(self.client.get("/admin/").status_code, 200)

    def test_a_wrong_code_cannot_be_retried_indefinitely(self):
        """**§2.4.** `django-axes` counts failures at `authenticate()`, and
        verifying a token is not that — so the five-attempt lockout does not
        cover the second factor at all. `django-otp`'s own `ThrottlingMixin`
        does, backing off 1, 2, 4, 8 seconds. Asserted rather than assumed,
        because a six-digit code with no throttle is a small keyspace."""
        device = a_confirmed_device(self.vince)
        self.sign_in()

        for _ in range(4):
            self.client.post(reverse("verify"), {"code": "000000"})

        device.refresh_from_db()
        allowed, _ = device.verify_is_allowed()
        self.assertFalse(allowed, "the device should be refusing attempts by now")

    def test_somebody_who_is_not_staff_is_turned_away_as_before(self):
        """The existing check is kept rather than replaced: verification is
        *alongside* staff, not instead of it."""
        priya = User.objects.create_user("priya", "priya@example.com", PASSWORD)
        a_confirmed_device(priya)
        self.client.post(
            reverse("login"), {"username": "priya", "password": PASSWORD}
        )
        self.assertIn("_auth_user_id", self.client.session)

        self.assertNotEqual(self.client.get("/admin/").status_code, 200)

    def test_the_verify_page_is_this_application_s_own(self):
        """§3 chose a project-owned view over `OTPAdminSite` because unfold
        overrides admin templates and the bundled form would render into one
        that does not know about it."""
        a_confirmed_device(self.vince)
        self.sign_in()

        body = self.client.get(reverse("verify")).content.decode()

        self.assertIn("Clarice", body)

    def test_somebody_with_no_device_is_told_where_to_get_one(self):
        """Deploying enforcement before enrolling is the ordering mistake the
        plan warns about, and this is what makes it recoverable rather than a
        lockout: enrolment lives at `/accounts/security/`, outside the admin."""
        self.sign_in()

        body = self.client.get(reverse("verify")).content.decode()

        self.assertIn(reverse("security"), body)


class TheOtherDoorTest(TestCase):
    """**§2.1**, and the reason increment 4 is one deploy rather than two.

    `/api/v1/login` trades a password for a `PersonalAccessToken` carrying
    ninety days and the Android scopes. **It starts no session, so every
    session-based gate misses it** — a second factor on the admin while this
    stands is a second factor on one of two doors.

    **Refused rather than extended**, because the Android client cannot ship a
    release: `assembleRelease` produces nothing usable until the keystore
    exists, and that is deliberately Vince's to generate. So accepting a `totp`
    field would leave the bypass open for as long as the keystore does not.
    """

    def setUp(self):
        self.vince = User.objects.create_superuser(
            "vince-admin", "vince@example.com", PASSWORD
        )

    def log_in(self, username="vince-admin"):
        return self.client.post(
            "/api/v1/login",
            {"username": username, "password": PASSWORD, "label": "phone"},
            content_type="application/json",
        )

    def test_an_account_with_a_second_factor_cannot_trade_a_password_for_a_token(self):
        a_confirmed_device(self.vince)

        response = self.log_in()

        self.assertNotEqual(response.status_code, 200)
        self.assertNotIn("token", response.json())

    def test_the_refusal_says_what_to_do_instead(self):
        """*A specific error telling the holder to create a token on the web,
        where the second factor already stands.* A generic 401 here would be
        indistinguishable from a wrong password and would send somebody to
        reset a password that was correct."""
        a_confirmed_device(self.vince)

        body = str(self.log_in().json())

        self.assertIn("token", body.lower())
        self.assertIn("web", body.lower())

    def test_an_unconfirmed_device_does_not_close_the_door(self):
        """Somebody halfway through enrolling has not armed anything, and
        locking them out of the phone would be a lock they did not set."""
        TOTPDevice.objects.create(user=self.vince, name="phone", confirmed=False)

        self.assertEqual(self.log_in().status_code, 200)

    def test_an_account_without_one_is_unaffected(self):
        """The population paying this cost is the staff accounts of increment
        1, which is one person who can paste a token. Everybody else keeps the
        endpoint the Android app was built around."""
        priya = User.objects.create_user("priya", "priya@example.com", PASSWORD)

        response = self.log_in(username=priya.username)

        self.assertEqual(response.status_code, 200)
        self.assertIn("token", response.json())
