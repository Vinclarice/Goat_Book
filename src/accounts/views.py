from axes.utils import reset as axes_reset
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.views import LoginView, PasswordResetConfirmView
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.emails import notify_admins_of_pending_signup
from accounts.forms import LoginForm, SignUpForm, TokenForm
from accounts.models import PersonalAccessToken


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
