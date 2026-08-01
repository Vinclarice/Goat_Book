from axes.utils import reset as axes_reset
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.views import LoginView, PasswordResetConfirmView
from django.core.cache import cache
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.emails import notify_admins_of_pending_signup, send_support_message
from accounts.forms import ContactForm, LoginForm, SignUpForm, TokenForm
from accounts.models import PersonalAccessToken


CONTACT_WINDOW_SECONDS = 60 * 60


class LandingLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True


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


def signup(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    form = SignUpForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        notify_admins_of_pending_signup(user)
        return render(request, "accounts/signup_pending.html", {"user": user})

    return render(request, "accounts/signup.html", {"form": form})


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
@require_POST
def new_token(request):
    form = TokenForm(data=request.POST)
    if form.is_valid():
        _, raw = PersonalAccessToken.generate(
            request.user, label=form.cleaned_data["label"]
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
                send_support_message(
                    name=form.cleaned_data["name"],
                    email=form.cleaned_data["email"],
                    message=form.cleaned_data["message"],
                )
                _record_contact_send(ip)

            messages.success(
                request,
                "Thanks — your message is on its way. We'll reply to the "
                "address you gave us.",
            )
            return redirect("contact")

    return render(request, "accounts/contact.html", {"form": form})
