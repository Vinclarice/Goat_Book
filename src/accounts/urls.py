from django.contrib.auth import views as auth_views
from django.conf import settings
from django.urls import path

from . import views

urlpatterns = [
    path("signup/", views.signup, name="signup"),
    path("login/", views.LandingLoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("settings/", views.account_settings, name="account_settings"),
    path("password/change/", views.change_password, name="change_password"),
    path("tokens/", views.tokens, name="tokens"),
    path("tokens/new/", views.new_token, name="new_token"),
    path("tokens/<int:token_id>/delete/", views.delete_token, name="delete_token"),
    # Django's four-step reset flow, wired to Clarice's own templates. Only
    # the confirm step needs a subclass (it clears the axes lockout too);
    # the rest are the built-ins with a template name.
    path(
        "password/reset/",
        # Not auth_views.PasswordResetView: a mail failure here used to be a
        # 500 on a public page. See the subclass for why it cannot show an
        # error the way the contact form does.
        views.ResilientPasswordResetView.as_view(
            template_name="accounts/password_reset_form.html",
            email_template_name="accounts/password_reset_email.txt",
            subject_template_name="accounts/password_reset_subject.txt",
        ),
        name="password_reset",
    ),
    path(
        "password/reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="accounts/password_reset_done.html",
            # The page offers a human on every reset, so it needs the address
            # whether or not anything went wrong -- see the template's comment.
            extra_context={"support_email": settings.SUPPORT_EMAIL},
        ),
        name="password_reset_done",
    ),
    path(
        "password/reset/confirm/<uidb64>/<token>/",
        views.ClearLockoutPasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path(
        "password/reset/complete/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="accounts/password_reset_complete.html"
        ),
        name="password_reset_complete",
    ),
]
