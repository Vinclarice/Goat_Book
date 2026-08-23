from axes.utils import reset as axes_reset
import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, update_session_auth_hash
from django_otp import devices_for_user, login as otp_login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.http import HttpResponseRedirect
from django.contrib.auth.views import (
    LoginView,
    PasswordResetConfirmView,
    PasswordResetView,
)
from django.core.cache import cache
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.views.decorators.http import require_http_methods, require_POST

from accounts.emails import (
    notify_admins_of_pending_signup,
    send_activation_email,
    send_support_message,
)
from accounts.forms import ContactForm, LoginForm, SignUpForm, TokenForm
from accounts.services import redeem_invitation
from accounts.mfa import enrolment_qr, issue_recovery_codes
from django_otp.plugins.otp_totp.models import TOTPDevice
from accounts.models import Invitation, PersonalAccessToken, User
from accounts.tokens import activation_token


CONTACT_WINDOW_SECONDS = 60 * 60


def privacy(request):
    """Public, and reachable without an account on purpose.

    Somebody deciding whether to sign up needs to read this *before* there is
    an account to read it from, which is also why it is at the site root rather
    than under accounts/ -- the same reasoning the contact form carries.

    The support address comes from settings rather than being typed into the
    template, so there is one place it can be wrong.
    """
    return render(
        request, "accounts/privacy.html", {"support_email": settings.SUPPORT_EMAIL}
    )


def terms(request):
    """Public, for the reason given in privacy() above."""
    return render(
        request, "accounts/terms.html", {"support_email": settings.SUPPORT_EMAIL}
    )


def home(request):
    """The signed-out home page, which is no longer the login form.

    `product-stories.md` S1 scored the old arrangement impossible, and its
    requires line ended "a landing page that is not a login form": a stranger
    following a link got a username field under the words "Welcome back".

    Signed-in visitors never see it. That is not only tidiness -- it is the
    behaviour `redirect_authenticated_user` gave the view this replaces, and
    dropping it would put a marketing page in front of somebody who has
    already bought.

    Nothing about the throttling moved with the form. /accounts/login/ has
    carried its own nginx limit all along (`clarice_auth`, in the
    accounts/login|signup location), so taking POSTs off "/" opens no hole; the
    `location = /` rule is now inert rather than wrong, and says so.
    """
    if request.user.is_authenticated:
        return redirect("dashboard")
    return render(request, "accounts/landing.html")


class ClariceLoginView(LoginView):
    """The login form, at /accounts/login/ and nowhere else now.

    Was `LandingLoginView`, and served "/" as well -- which is what made the
    landing page a login form. The name went with the responsibility.
    """

    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True


class ResilientPasswordResetView(PasswordResetView):
    """Django's reset view, except a mail failure is not a 500.

    `form_valid` sends inside the request, so an unreachable relay was an
    unhandled exception on a **public** page, for the one person who by
    definition cannot log in and work around it. Live on this deployment until
    the transport moved: DigitalOcean drops outbound SMTP, so every reset for a
    real account 500d.

    **It cannot say what the contact form says, and that is the interesting
    part.** `password_reset_done.html` states the constraint in its own
    comment -- the page renders identically whether or not the address matched,
    so it cannot be used to discover which addresses are registered. A send is
    only *attempted* when an account matched, so an error page shown on failure
    would announce precisely what that comment protects. The contact form has
    no such problem: the visitor typed their own address and no account is
    implied by it.

    So the failure is swallowed *to the visitor* and reported to us. The done
    page carries a support address on every reset, not only the failed ones --
    a line appearing only on failure would be the same disclosure by another
    route.
    """

    def form_valid(self, form):
        try:
            return super().form_valid(form)
        except Exception:
            # The only place this failure is visible at all, since the page
            # deliberately cannot mention it. sentry-sdk's LoggingIntegration
            # turns an ERROR into an event.
            logger.exception("password reset email failed to send")
            # The same redirect the success path returns, so the two responses
            # are indistinguishable -- which is the property under test.
            return HttpResponseRedirect(self.get_success_url())


class ClearLockoutPasswordResetConfirmView(PasswordResetConfirmView):
    """Django's confirm view, except finishing a reset also clears any axes
    lockout on the username.

    Without this, someone who forgot their password *and* tripped the
    five-attempt lockout -- a likely pair, since forgetting a password
    usually means guessing at it first -- would set a new one and still be
    told to wait out the hour. That defeats the point of offering a way
    back in.
    """

    template_name = "accounts/password_reset_confirm.html"

    def form_valid(self, form):
        response = super().form_valid(form)
        # dispatch() resolves self.user from the uidb64 before this runs, so
        # there's nothing to look up again here.
        axes_reset(username=self.user.username)
        return response


def _send_activation(request, user):
    """Mail the link, and never let a failed send become the person's problem.

    The account exists by the time this runs, so an unguarded raise leaves a
    real one behind an error page: they never learn whether it worked, and a
    second attempt fails on a duplicate username. That is the shape of the
    August 18 contact-form outage, and the answer is the same one — the page
    that follows names the resend path, so a failed send is a detour rather
    than a dead end.

    Deliberately *not* rolled back, unlike `services.request_deletion` where
    the email **is** the protection. Signing up is this person's own action and
    it succeeded; deleting the account because the mail bounced would destroy
    the thing the mail was about.
    """
    try:
        send_activation_email(
            user,
            activation_url=request.build_absolute_uri(
                reverse(
                    "activate",
                    kwargs={
                        "uidb64": urlsafe_base64_encode(force_bytes(user.pk)),
                        "token": activation_token.make_token(user),
                    },
                )
            ),
        )
        return True
    except Exception:
        # An event, not a log line: somebody is sitting in front of a page
        # telling them to check an inbox that will stay empty.
        logger.exception("activation email failed for %s", user.pk)
        return False


def signup(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    form = SignUpForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        return render(
            request,
            "accounts/signup_pending.html",
            # `applicant`, never `user`: that name is the context processor's,
            # and shadowing it renders the signed-in app bar -- username and a
            # Log out button -- for somebody who has no session at all.
            # `AbstractBaseUser.is_authenticated` is True on any real instance,
            # so the bar cannot tell the difference.
            {"applicant": user, "sent": _send_activation(request, user)},
        )

    return render(request, "accounts/signup.html", {"form": form})


def join(request, public_id):
    """Signing up through an invitation — **S1's last require, closed**.

    S1's done-means asks for *a usable workspace without waiting for a human*,
    and until now `is_active` was approval and approval was a person. The
    approval still is a person: it happens when Vince mints the link. **What is
    gone is the person in the loop**, which is the clause the story actually
    makes.

    **The account is active immediately, and the confirmation mail still
    goes.** `is_active` and `email_confirmed_at` were separated a week ago for
    exactly this — S1's own entry called it *"what makes closing this later a
    change of policy rather than of design."* Vince vouched for the person,
    which is what activation records; nobody has yet proved the address receives
    mail, which is what confirmation records, and the digest and password reset
    both need it. Four minutes does not include a round trip to an inbox.

    **Signed in on success**, unlike `activate`. There it would have been a way
    past approval; here the invitation *is* the approval, so the alternative is
    a working account behind a login form the person has no reason to expect.

    **Every dead invitation renders the same page** — expired, redeemed, revoked
    and never-existed are four things to us and one thing to whoever is holding
    the link: *ask for another*. Same choice `activate` makes, and here it also
    avoids telling the holder of a forwarded copy whether somebody else got
    there first.
    """
    if request.user.is_authenticated:
        return redirect("dashboard")

    invitation = Invitation.objects.filter(public_id=public_id).first()
    if invitation is None or not invitation.is_usable:
        return render(request, "accounts/invitation_spent.html")

    form = SignUpForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = redeem_invitation(invitation, form)
        # Before the mail: a failing SMTP server must not cost somebody the
        # session their invitation just bought them. `_send_activation` already
        # swallows and logs, and the same reasoning applies one step earlier.
        #
        # **The backend is named**, because `login` can only infer one from a
        # user that came back from `authenticate` and this one came from a
        # form. `AxesBackend` is first in the list and is the wrong answer here:
        # it exists to count failed *credential* attempts, and there were no
        # credentials to check -- the invitation was the credential.
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        _send_activation(request, user)
        return redirect("dashboard")

    return render(
        request, "accounts/join.html", {"form": form, "invitation": invitation}
    )


def activate(request, uidb64, token):
    """Confirming the address — the first of two gates, not the last.

    **It does not sign anybody in, and it does not set `is_active`.** Approval
    is still a person's decision, so what this earns is a place in the queue
    rather than a session. Signing them in here would be a way past approval
    entirely; `ModelBackend` would refuse the inactive account anyway, so the
    only thing a login attempt could produce is a confusing failure.

    **Admins hear about it here rather than at signup**, which is the better
    moment on both counts: a confirmed address means the review is of a person
    who read their mail rather than of whatever a form-filler typed, and it
    keeps the noise of unconfirmed signups out of the inbox entirely.

    **Every failure renders the same page.** A bad token, an expired one, a
    used one and an id that matches no account are four different things to us
    and must be one thing to a stranger, or the response answers "is there an
    account at this id" for anybody who walks the range.
    """
    try:
        user = User.objects.get(pk=urlsafe_base64_decode(uidb64).decode())
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is None or not activation_token.check_token(user, token):
        return render(request, "accounts/activation_failed.html")

    if user.email_confirmed_at is None:
        user.email_confirmed_at = timezone.now()
        user.save(update_fields=["email_confirmed_at"])
        try:
            notify_admins_of_pending_signup(user)
        except Exception:
            # Not the applicant's problem and not worth failing their
            # confirmation over -- the account is confirmed either way and the
            # admin can see it in /admin/. Reported because an admin who never
            # hears leaves somebody waiting on a queue nobody is reading.
            logger.exception("pending-signup notification failed for %s", user.pk)

    # `applicant` rather than `user`, for the reason given in signup().
    return render(request, "accounts/activation_confirmed.html", {"applicant": user})


@require_http_methods(["GET", "POST"])
def resend_activation(request):
    """A second copy of the link, because one lost email is otherwise the end.

    Without this the failure is unrecoverable in a way few are: the username is
    taken, the account cannot log in, and the address is spoken for — so the
    person can neither get in nor start again.

    **The response never varies.** Sent, not sent because no such address, and
    not sent because that address is already confirmed all render the same page,
    for the reason `password_reset_done.html` states about its own: a page that
    differs tells a stranger which addresses hold accounts.

    Keyed on `email_confirmed_at` rather than `is_active`: an account that is
    confirmed and waiting for approval has nothing to re-send, and a second
    link would only invite somebody to click a thing that changes nothing.
    """
    if request.method == "POST":
        email = (request.POST.get("email") or "").strip().lower()
        user = User.objects.filter(
            email=email, email_confirmed_at__isnull=True
        ).first()
        if user is not None:
            _send_activation(request, user)
        return render(request, "accounts/activation_sent.html")

    return render(request, "accounts/resend_activation.html")


@login_required
def account_settings(request):
    return redirect("/app/preferences")


@login_required
def tokens(request):
    """Manage the tokens a non-browser client authenticates with.

    Self-service rather than admin-only: it's the same instinct as the
    password reset above, and a token you can't rotate yourself is one
    you won't rotate.
    """
    return render(
        request,
        "accounts/tokens.html",
        {
            "form": TokenForm(),
            "tokens": request.user.tokens.all(),
            # Popped, not read: the raw value is shown on exactly the one
            # page load that follows creating it, and is unrecoverable
            # after that. It rides in the session because the create view
            # redirects (so a refresh can't mint a second token), and a
            # redirect has nowhere else to carry it.
            "raw_token": request.session.pop("raw_token", None),
        },
    )


@login_required
def verify(request):
    """Prove it is you, on a page this application owns — increment 4.

    **Not the admin's login form.** §2.5: unfold overrides admin templates, so
    `OTPAdminSite`'s bundled form would render into one that does not know about
    it. This costs a view and buys a screen that looks like the rest.

    **One box for both kinds of code.** A TOTP code and a recovery code are the
    same act — *prove it is you* — and asking which kind somebody is holding is
    a question they should not have to answer while locked out. Every confirmed
    device is offered the string in turn.

    **Throttling is the device's own**, and that is §2.4's finding rather than
    an omission here: `django-axes` counts failures at `authenticate()` and this
    is not that, so the five-attempt lockout does not cover the second factor at
    all. `ThrottlingMixin` does, backing off 1, 2, 4, 8 seconds, and it is on by
    default. `verify_token` consults it, so calling that is the whole
    protection.

    **Somebody with no device is sent to enrol rather than told no.** Enrolment
    lives outside the admin at `/accounts/security/`, which is what keeps
    deploying enforcement before enrolling a five-minute inconvenience instead
    of a lockout.
    """
    devices = list(devices_for_user(request.user, confirmed=True))
    error = ""

    if request.method == "POST":
        code = request.POST.get("code", "").strip()
        for device in devices:
            if device.verify_token(code):
                otp_login(request, device)
                # `next` off the query string on the POST too: the form posts
                # back to the same URL, so it survives -- and without honouring
                # it, verifying would drop somebody on the admin index having
                # asked for a particular page.
                return redirect(request.GET.get("next") or "/admin/")
        # One message for a wrong code, an expired one and a spent recovery
        # code. They are three things to us and one thing to somebody holding a
        # phone, and naming which would say whether the string was ever valid.
        error = "That code didn't work. Try the next one your app shows."

    return render(
        request,
        "accounts/verify.html",
        {"error": error, "has_a_device": bool(devices)},
    )


@login_required
def security(request):
    """Turn a second factor on, and prove it works before trusting it.

    **The device is created unconfirmed and stays that way until a code from it
    comes back correct.** Somebody who scans the QR into an app that never
    syncs, or who closes the page halfway, has not armed a lock they cannot
    open -- `is_verified()` ignores an unconfirmed device, so nothing changes
    for them until the round trip succeeds. That is what makes increment 4's
    enforcement safe to deploy.

    `verify_token` carries the throttling itself: it refuses while the backoff
    from earlier failures is still running, and resets the counter on success.
    That matters more here than it looks, because `django-axes` counts failures
    at `authenticate()` and this is not `authenticate()` -- the five-attempt
    lockout does not reach a six-digit code at all, so the device's own backoff
    is the entire protection on this step. See design/admin-mfa-plan.md §2.4.

    Recovery codes ride through the redirect in the session and are popped by
    the GET that follows, exactly as `new_token` does with a raw token: they
    are shown on one page load and are unrecoverable afterwards.
    """
    confirmed = TOTPDevice.objects.filter(user=request.user, confirmed=True).first()

    if request.method == "POST" and not confirmed:
        # Owner-scoped in the lookup, not checked afterwards -- there is no
        # code path here that loads somebody else's device in the first place.
        pending = TOTPDevice.objects.filter(
            user=request.user, confirmed=False
        ).first()
        if pending is not None and pending.verify_token(request.POST.get("token", "")):
            pending.confirmed = True
            pending.save(update_fields=["confirmed"])
            request.session["recovery_codes"] = issue_recovery_codes(request.user)
            return redirect("security")
        messages.error(
            request, "That code was not accepted. Check the clock on your phone."
        )
        return redirect("security")

    pending = None
    if confirmed is None:
        # get_or_create rather than create: a refresh must not strand the
        # previous secret, or the QR on screen stops matching the row that
        # will be asked to verify it.
        pending, _ = TOTPDevice.objects.get_or_create(
            user=request.user, confirmed=False, defaults={"name": "authenticator"}
        )

    return render(
        request,
        "accounts/security.html",
        {
            "confirmed_device": confirmed,
            "pending_device": pending,
            "qr": enrolment_qr(pending) if pending is not None else None,
            "recovery_codes": request.session.pop("recovery_codes", None),
        },
    )


@login_required
@require_POST
def new_token(request):
    form = TokenForm(data=request.POST)
    if not form.is_valid():
        # Re-rendered rather than redirected: scopes is required now
        # (token-scopes-plan.md), and a redirect to `tokens`'s own always-
        # fresh TokenForm() would silently drop every validation error,
        # which used to be harmless when the only field was an optional
        # label and stops being harmless the moment a required one exists.
        return render(
            request,
            "accounts/tokens.html",
            {
                "form": form,
                "tokens": request.user.tokens.all(),
                "raw_token": None,
            },
        )
    _, raw = PersonalAccessToken.generate(
        request.user,
        label=form.cleaned_data["label"],
        scopes=form.cleaned_data["scopes"],
        expires_at=form.expires_at(),
    )
    request.session["raw_token"] = raw
    return redirect("tokens")


@login_required
@require_POST
def delete_token(request, token_id):
    # Owner-scoped in the lookup rather than checked afterwards, same as
    # capture.views._render_inbox and lists.api_v1._owned_list: there is no
    # code path that loads someone else's token in the first place.
    token = get_object_or_404(PersonalAccessToken, id=token_id, owner=request.user)
    token.delete()
    messages.success(request, "Token revoked.")
    return redirect("tokens")


@login_required
def change_password(request):
    form = PasswordChangeForm(
        user=request.user,
        data=request.POST or None,
    )
    if request.method == "POST" and form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)
        messages.success(request, "Password updated.")
        return redirect("account_settings")

    return render(request, "accounts/change_password.html", {"form": form})


def visitor_ip(request):
    """The visitor's address, not the proxy's.

    Django sits behind nginx, which connects from localhost -- so
    REMOTE_ADDR is the same value for every visitor on earth and anything
    keyed on it is one shared bucket, not a per-visitor limit. nginx sets
    X-Real-IP to the real peer and *overwrites* whatever the client sent,
    and gunicorn only listens on 127.0.0.1, so nginx is the only way in and
    the header cannot be forged. Off-proxy -- dev, tests -- there is no
    header and REMOTE_ADDR is already the real peer.
    """
    return request.headers.get("X-Real-IP") or request.META.get("REMOTE_ADDR", "")


logger = logging.getLogger(__name__)

def _contact_sends_key(ip):
    return f"contact-form-sends:{ip}"


def _record_contact_send(ip):
    key = _contact_sends_key(ip)
    # add() only writes when the key is absent, so the hour is measured
    # from the first send. cache.set() here instead would let a steady
    # drip keep pushing the expiry out and never reset the count.
    cache.add(key, 0, CONTACT_WINDOW_SECONDS)
    try:
        cache.incr(key)
    except ValueError:
        # Expired in the gap between add() and incr(). Start a fresh window
        # rather than lose the count entirely.
        cache.set(key, 1, CONTACT_WINDOW_SECONDS)


def contact(request):
    """Public support contact. Deliberately not a ticketing system: it has
    no model and keeps no record, so the message only exists in the support
    inbox it was sent to.

    Rate limiting counts *sends*, not requests. Someone mistyping their
    address four times has not used up their allowance; a script posting
    valid messages has.
    """
    form = ContactForm()

    if request.method == "POST":
        ip = visitor_ip(request)
        if cache.get(_contact_sends_key(ip), 0) >= settings.CONTACT_MAX_PER_HOUR:
            return render(
                request,
                "accounts/contact.html",
                {"form": form, "rate_limited": True},
                status=429,
            )

        form = ContactForm(request.POST)
        if form.is_valid():
            # A caught bot gets the same page a person gets. Saying "you
            # tripped the honeypot" only tells whoever wrote it which field
            # to leave alone next time.
            if not form.looks_automated:
                try:
                    send_support_message(
                        name=form.cleaned_data["name"],
                        email=form.cleaned_data["email"],
                        message=form.cleaned_data["message"],
                    )
                except Exception:
                    # There is no model behind this page -- see the docstring,
                    # and it is a deliberate choice -- so a failed send means
                    # the message exists nowhere. Unguarded, the visitor got a
                    # 500 and their text went with it, which happened in
                    # production on 2026-08-18 when the relay stopped
                    # answering. A stranger with a question is the person least
                    # able to recover from that.
                    #
                    # Logged rather than only caught: sentry-sdk's
                    # LoggingIntegration turns this into an event, and without
                    # it catching the exception would take away the only reason
                    # anybody knew.
                    #
                    # 503 rather than 200, matching the 429 above: the page
                    # rendered fine and the thing behind it did not, and this
                    # is the one status that says so.
                    logger.exception("contact form send failed")
                    return render(
                        request,
                        "accounts/contact.html",
                        {
                            "form": form,
                            "send_failed": True,
                            "support_email": settings.SUPPORT_EMAIL,
                        },
                        status=503,
                    )
                _record_contact_send(ip)

            messages.success(
                request,
                "Thanks — your message is on its way. We'll reply to the "
                "address you gave us.",
            )
            return redirect("contact")

    return render(request, "accounts/contact.html", {"form": form})
