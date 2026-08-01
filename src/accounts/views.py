from axes.utils import reset as axes_reset
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.views import LoginView, PasswordResetConfirmView
from django.shortcuts import redirect, render

from accounts.emails import notify_admins_of_pending_signup
from accounts.forms import LoginForm, SignUpForm


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
