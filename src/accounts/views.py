from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render

from accounts.emails import notify_admins_of_pending_signup
from accounts.forms import AccountSettingsForm, LoginForm, SignUpForm


class LandingLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True


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
    form = AccountSettingsForm(
        request.POST or None,
        instance=request.user,
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Account settings updated.")
        return redirect("account_settings")

    return render(request, "accounts/settings.html", {"form": form})


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
