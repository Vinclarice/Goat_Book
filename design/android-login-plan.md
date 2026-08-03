# Logging in from the app, instead of pasting a token

Vince · brief · written August 3, 2026

## 1. Trigger

Stated directly: connecting the Android app currently means leaving it,
logging into the website, navigating to Settings → Access tokens, creating
one, copying it, and pasting it back into the app. "Very tedious" — and the
reason it exists at all is that the app has never had a way to authenticate
someone directly. That's the actual gap this closes.

## 2. What this reuses, and why

Everything about *how a token is stored and used* is already built and
stays exactly as it is: `KeystoreTokenStore`, the `Authorization: Bearer`
header, revocation-by-deletion. This slice only changes how the *first*
token gets onto the device.

**`django.contrib.auth.authenticate()`, not a hand-rolled password check.**
`axes.backends.AxesBackend` is registered in `AUTHENTICATION_BACKENDS`
globally, so calling `authenticate()` from anywhere — a view, an API
endpoint — gets the same five-attempts-then-an-hour lockout the web login
already enforces, keyed on username, and the same admin notification
(`axes.signals.user_locked_out`, wired once in `accounts/apps.py`). Writing
a separate check for this endpoint would mean a second place that rule
could drift from the first.

**`PersonalAccessToken.generate()`, the same call `accounts.views.new_token`
already makes.** A token minted by logging in in the app and one created by
hand on the web Settings page are the same kind of row, revocable the same
way, visible in the same list.

## 3. What this does not do, and why

**The paste-a-token flow is not removed.** Login becomes the *primary*
path on Connect, not the *only* one. Someone who would rather not type
their account password into this specific screen, or who wants a token
scoped/labelled a particular way, keeps the option that already works. This
is `principles.md`'s "prefer reversible, evolutionary decisions" applied
plainly: adding a path costs nothing the removing one would.

**The app still never stores a password.** It exists in memory for the one
request that exchanges it for a token, the same way it always has on the
web login form — Django's session middleware doesn't persist it either.
What Keystore holds is unchanged: one revocable token, nothing else.

**No "remember these credentials" or biometric re-auth.** Out of scope —
the app already keeps the token indefinitely until Disconnect, so there is
no recurring login to smooth over. If that changes, it's a different
trigger.

## 4. The slice

1. **`POST /api/v1/login`**, unauthenticated, in `accounts/api_v1.py`:
   `LoginIn { username: str, password: str, label: str = "Android" }` →
   `LoginOut { token: str, username: str, email: str }` on success. Calls
   `authenticate(request, username=..., password=...)`; `None` (bad
   credentials, inactive account, or an axes lockout — indistinguishable on
   purpose, the same as the web form) is a generic `401`. Success mints a
   token via `PersonalAccessToken.generate(user, label=label)` and returns
   the raw value, the only time it's ever available.
2. **Android — `ClariceApi.login()`**: a new method alongside `identify`
   and `capture`, POSTs credentials, parses `{token, username, email}` on
   200 into an `Identified`-shaped result the existing Connect flow already
   knows how to handle, `Unauthorised` on 401, `Unreachable` on anything
   else — the same three-outcome shape `identify` already uses, for the
   same reason: a wrong password and a dead network need different words.
3. **Connect screen**: username and password fields above the existing
   token field, with a clear division — "Log in" as the primary action,
   "…or paste a token" underneath for the existing path. Submitting login
   calls `ClariceApi.login()`, stores the returned token exactly where a
   pasted one would go, and clears the password field from state
   immediately regardless of outcome.

## 5. Verification

Django: a valid-credentials test asserting exactly one new token exists and
the response carries it; a wrong-password test asserting `401` and that no
token was created; a sixth attempt after five wrong ones asserting the
account is locked out via axes and a genuine correct password is *also*
rejected while locked; an inactive-account test; a test that the error body
is the same shape whether the username doesn't exist or the password is
wrong (no enumeration).

Android: `ClariceApi` tests against a real HTTP server (MockWebServer,
matching `ClariceApiTest`'s own pattern) for the request shape and all
three outcomes; a view-model test that a successful login stores the token
via the same `TokenStore` the paste path uses. Verified for real by logging
into the actual phone against the built app and confirming a working
session — no shortcut for that step exists in this project's practice.
