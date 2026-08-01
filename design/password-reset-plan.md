# Self-service password reset

Triggered by a real incident, not a planning pass: someone locked out of
their account by too many failed login attempts also couldn't remember
their password, and there was no way to reset it — no "forgot password"
link on the login page, and none on the admin login either.

## Why the admin login doesn't show one either

This isn't a missing template tweak — it's a missing URL. Django's admin
login page renders its "Forgot your password?" link with
`{% url 'admin_password_reset' as password_reset_url %}`: when a URL name
resolves to nothing, `as` swallows the `NoReverseMatch` silently and the
link just doesn't render, rather than the page erroring. Nothing in
`clarice/urls.py` currently registers that name, which is exactly why the
admin login page looks like it has no recovery option at all rather than a
broken one.

## Settled decisions

| Question | Decision |
| --- | --- |
| Recovery channel | Email only, via `User.email` (already unique and required — no new field needed). No security questions, no SMS. |
| Who can request one | Anyone can submit the request form. Django's built-in `PasswordResetView` never reveals whether an email is registered — same "don't leak existence" instinct already in `accounts.forms.LoginForm`. |
| Pending (unapproved) accounts | Get the same "check your email" response, but no email actually sends — `PasswordResetForm.get_users()` excludes `is_active=False` by default, which is already correct here: an unapproved account has nothing worth resetting into yet. |
| Interaction with axes lockout | A reset request/confirm isn't itself blocked by axes (it only wraps the login view) — but completing a reset should clear any existing lockout for that username, so someone isn't left with a new password and an hour still to wait. |
| Where the entry point lives | A "Forgot your password?" link on the login page and on the lockout page (the exact page someone in this situation lands on), plus registering the `admin_password_reset` URL name so the admin login page's own link starts showing up automatically. |
| Token lifetime | Django's default (`PASSWORD_RESET_TIMEOUT`, 3 days) — no reason to change it yet. |
| Email delivery | Reuses the existing `EMAIL_BACKEND` setup in `clarice/settings.py` (console in dev, Gmail SMTP in production) — the same channel `notify_admins_of_pending_signup` and `notify_admins_of_lockout` already use. Nothing new to configure. |

## Views

```python
# accounts/views.py
from django.contrib.auth import views as auth_views
from axes.utils import reset as axes_reset


class ClearLockoutPasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    """Same as Django's built-in confirm view, except completing a reset
    also clears any axes lockout on this username.

    Without this, someone who forgot their password *and* tripped the
    5-failed-attempt lockout (AXES_FAILURE_LIMIT in settings.py) -- a
    likely combination, since forgetting a password often means guessing
    at it first -- would set a new password and then still be told to
    wait out the hour-long cooloff. That defeats the point of giving them
    a way back in.
    """

    template_name = "accounts/password_reset_confirm.html"

    def form_valid(self, form):
        response = super().form_valid(form)
        axes_reset(username=self.user.username)
        return response
```

`self.user` is set by `PasswordResetConfirmView.dispatch()` before
`form_valid` runs, so it's available here without extra lookup work.

## URLs

```python
# accounts/urls.py
from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path("signup/", views.signup, name="signup"),
    path("login/", views.LandingLoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("settings/", views.account_settings, name="account_settings"),
    path("password/change/", views.change_password, name="change_password"),
    path(
        "password/reset/",
        auth_views.PasswordResetView.as_view(
            template_name="accounts/password_reset_form.html",
            email_template_name="accounts/password_reset_email.txt",
            subject_template_name="accounts/password_reset_subject.txt",
        ),
        name="password_reset",
    ),
    path(
        "password/reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="accounts/password_reset_done.html"
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
```

```python
# clarice/urls.py -- one addition, placed BEFORE path("admin/", admin.site.urls)
from django.views.generic import RedirectView

urlpatterns = [
    ...
    path("accounts/", include("accounts.urls")),
    path("capture/", include("capture.urls")),
    path(
        "admin/password_reset/",
        RedirectView.as_view(pattern_name="password_reset", permanent=False),
        name="admin_password_reset",
    ),
    path("admin/", admin.site.urls),
]
```

**Ordering matters here, not just style.** `admin.site.urls` is itself a
resolver mounted at `admin/` — if `path("admin/", admin.site.urls)` comes
first, Django tries to match `admin/password_reset/` *inside* the admin
app's own URLconf, which has no such pattern, and 404s before ever
reaching the redirect below it. The `admin_password_reset` path has to be
registered ahead of the `admin/` include for the name to resolve at all,
and for the admin login template's link to appear.

A plain `RedirectView` to the existing `password_reset` flow, rather than
a second `PasswordResetView` instance, so there's exactly one reset flow
with one set of templates — the admin login page just gets an extra door
into it.

## Templates

All five match the existing card-based Tailwind layout already used by
`login.html`, `lockout.html`, and `change_password.html`.

`accounts/templates/accounts/password_reset_form.html`:

```html
{% extends "base.html" %}
{% load frontend_tags %}

{% block title %}Reset your password · Clarice{% endblock %}

{% block content %}
  <section class="mx-auto max-w-md py-8">
    <div class="rounded-xl border border-border bg-card p-6 sm:p-8 space-y-6">
      <div class="space-y-1">
        <p class="text-xs font-bold uppercase tracking-wide text-accent">Account recovery</p>
        <h1 class="text-2xl font-bold">Reset your password</h1>
        <p class="text-sm text-muted-foreground">
          Enter the email on your account and we'll send you a link to set
          a new password.
        </p>
      </div>

      <form method="post" class="space-y-4">
        {% csrf_token %}
        {% for field in form %}
          <div class="space-y-1">
            <label for="{{ field.id_for_label }}" class="text-sm font-bold">{{ field.label }}</label>
            {{ field|add_class:"w-full rounded-lg border border-border bg-input px-3 py-1.5" }}
            {% for error in field.errors %}
              <div class="text-sm text-destructive">{{ error }}</div>
            {% endfor %}
          </div>
        {% endfor %}
        <button
          class="w-full h-10 rounded-lg bg-primary text-primary-foreground hover:bg-primary/80 font-bold text-sm transition-colors"
          type="submit"
        >
          Send reset link
        </button>
      </form>

      <p class="text-sm text-muted-foreground">
        <a class="text-accent hover:underline" href="{% url 'login' %}">Back to login</a>
      </p>
    </div>
  </section>
{% endblock %}
```

`accounts/templates/accounts/password_reset_done.html`:

```html
{% extends "base.html" %}

{% block title %}Check your email · Clarice{% endblock %}

{% block content %}
  <section class="mx-auto max-w-md py-8">
    <div class="rounded-xl border border-border bg-card p-6 sm:p-8 space-y-6">
      <div class="space-y-1">
        <p class="text-xs font-bold uppercase tracking-wide text-accent">Account recovery</p>
        <h1 class="text-2xl font-bold">Check your email</h1>
        <p class="text-sm text-muted-foreground">
          If that address matches an account, we've sent a link to reset
          your password. It expires in a few days.
        </p>
      </div>

      <p class="text-sm text-muted-foreground">
        <a class="text-accent hover:underline" href="{% url 'login' %}">Back to login</a>
      </p>
    </div>
  </section>
{% endblock %}
```

`accounts/templates/accounts/password_reset_confirm.html` (Django's
context supplies `validlink`, true only for an unused, unexpired token):

```html
{% extends "base.html" %}
{% load frontend_tags %}

{% block title %}Set a new password · Clarice{% endblock %}

{% block content %}
  <section class="mx-auto max-w-md py-8">
    <div class="rounded-xl border border-border bg-card p-6 sm:p-8 space-y-6">
      {% if validlink %}
        <div class="space-y-1">
          <p class="text-xs font-bold uppercase tracking-wide text-accent">Account recovery</p>
          <h1 class="text-2xl font-bold">Set a new password</h1>
        </div>

        <form method="post" class="space-y-4">
          {% csrf_token %}
          {% for field in form %}
            <div class="space-y-1">
              <label for="{{ field.id_for_label }}" class="text-sm font-bold">{{ field.label }}</label>
              {{ field|add_class:"w-full rounded-lg border border-border bg-input px-3 py-1.5" }}
              {% if field.help_text %}
                <div class="text-xs text-muted-foreground">{{ field.help_text|safe }}</div>
              {% endif %}
              {% for error in field.errors %}
                <div class="text-sm text-destructive">{{ error }}</div>
              {% endfor %}
            </div>
          {% endfor %}
          <button
            class="w-full h-10 rounded-lg bg-primary text-primary-foreground hover:bg-primary/80 font-bold text-sm transition-colors"
            type="submit"
          >
            Set new password
          </button>
        </form>
      {% else %}
        <div class="space-y-1">
          <p class="text-xs font-bold uppercase tracking-wide text-accent">Account recovery</p>
          <h1 class="text-2xl font-bold">This link no longer works</h1>
          <p class="text-sm text-muted-foreground">
            Reset links expire after a few days, or this one has already
            been used. Request a new one below.
          </p>
        </div>
        <p class="text-sm">
          <a class="text-accent hover:underline" href="{% url 'password_reset' %}">Request a new link</a>
        </p>
      {% endif %}
    </div>
  </section>
{% endblock %}
```

`accounts/templates/accounts/password_reset_complete.html`:

```html
{% extends "base.html" %}

{% block title %}Password updated · Clarice{% endblock %}

{% block content %}
  <section class="mx-auto max-w-md py-8">
    <div class="rounded-xl border border-border bg-card p-6 sm:p-8 space-y-6">
      <div class="space-y-1">
        <p class="text-xs font-bold uppercase tracking-wide text-accent">Account recovery</p>
        <h1 class="text-2xl font-bold">Password updated</h1>
        <p class="text-sm text-muted-foreground">
          Your password has been changed. If you were previously locked
          out after too many failed attempts, that's cleared too — log in
          below with your new password.
        </p>
      </div>

      <p class="text-sm">
        <a class="text-accent hover:underline" href="{% url 'login' %}">Log in</a>
      </p>
    </div>
  </section>
{% endblock %}
```

`accounts/templates/accounts/password_reset_email.txt`:

```
{% autoescape off %}
Hi {{ user.username }},

Someone (hopefully you) asked to reset the password on your Clarice
account.

Set a new password here:
{{ protocol }}://{{ domain }}{% url 'password_reset_confirm' uidb64=uid token=token %}

If you didn't request this, you can ignore this email — your password
won't change unless you click the link above and set a new one.

-- Clarice
{% endautoescape %}
```

`accounts/templates/accounts/password_reset_subject.txt` (must stay one
line — Django strips newlines from the rendered subject):

```
Reset your Clarice password
```

## Login and lockout page changes

`accounts/templates/accounts/login.html` — add a link near the password
field:

```html
<div class="flex justify-end">
  <a class="text-sm text-accent hover:underline" href="{% url 'password_reset' %}">Forgot your password?</a>
</div>
```

`accounts/templates/accounts/lockout.html` — add a second link. This is
the page that matters most: someone here has already failed 5 times, so
"forgot password" is a likely reason, and finishing a reset is what
actually gets them back in before the cooloff expires:

```html
<p class="text-sm text-muted-foreground">
  Don't remember your password either?
  <a class="text-accent hover:underline" href="{% url 'password_reset' %}">Reset it</a> —
  finishing a reset clears the lockout immediately, so you won't need to
  wait out the hour.
</p>
```

## Sequencing

1. `ClearLockoutPasswordResetConfirmView` in `accounts/views.py`, the four
   new paths in `accounts/urls.py`.
2. The five new templates plus the email/subject templates.
3. The `admin_password_reset` redirect in `clarice/urls.py`, registered
   before the `admin/` include.
4. The two link additions (`login.html`, `lockout.html`).
5. Manual smoke test end to end using the console email backend in dev —
   the reset link prints straight to the `runserver` console, no real
   inbox needed to verify the flow.

## Tests to add

- Requesting a reset for a real, active user's email sends exactly one
  email and renders the "done" page.
- Requesting a reset for an email that doesn't exist, or belongs to a
  pending (`is_active=False`) account, also renders the "done" page and
  sends zero emails — matches the existing don't-reveal-existence pattern
  in `LoginForm`.
- A valid reset link renders the set-new-password form (`validlink` is
  `True`); submitting it lets you log in with the new password, and the
  old one stops working.
- An invalid, expired, or already-used token renders the "this link no
  longer works" branch (`validlink` is `False`) and does not allow setting
  a password.
- A user who is currently axes-locked-out can still load and submit both
  the reset-request and reset-confirm views — axes only guards the login
  view itself.
- Completing a reset for a locked-out user clears the lockout: logging in
  with the new password immediately succeeds instead of hitting the
  lockout template.
- `reverse("admin_password_reset")` resolves, and the rendered admin login
  page contains the "Forgot your password?" link — this is the test that
  actually covers the `clarice/urls.py` ordering requirement above, since
  a regression there would silently drop the link rather than error.

## Non-goals

- No email verification on signup — a separate, still-deferred item on the
  public-readiness bar.
- No rate limiting specifically on the reset-request view. Same call
  already made for the rest of the quality bar; axes doesn't cover this
  view since it only wraps login. Revisit before anything public.
- No change to axes configuration itself (`AXES_FAILURE_LIMIT`,
  `AXES_COOLOFF_TIME`) — this only adds a place where an existing lockout
  gets cleared early, not a change to when one starts.
- No security questions or SMS-based recovery — email only, matching how
  `notify_admins_of_pending_signup` and `notify_admins_of_lockout` already
  reach a person.
