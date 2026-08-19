# A second factor on the accounts that can read everything

Vince · plan · written August 19, 2026 · **not started**

## What this closes

[`security-and-resilience-plan.md`](security-and-resilience-plan.md) §1.5 owns
the argument and is not restated here. The short version it does not carry: the
work is shaped less by TOTP, which is a solved problem, than by **four
interactions in this codebase that a stock recipe gets wrong** — an API login
that is a password-only path to a 90-day token, an export that enumerates
models by app label, an erasure path that cannot use a plain cascade, and a
lockout mechanism that does not see the new failure mode at all.

Those are §2. They decide the design, so they come before it.

## The library, and what is refused

**`django-otp`**, plus `qrcode` for the enrolment image. It supplies models, a
middleware and a verification primitive, and leaves the views to the project.

**`django-two-factor-auth` is refused.** It is built on `django-otp` and adds
the part this project should not take: its own login views, its own URL
structure and its own templates. `ClariceLoginView` exists for a reason — the
axes interaction and the two-gate signup message — and the last release spent
itself giving all three surfaces one visual identity. Adopting a second login
flow with its own look would undo the thing that release was for.

**Rolling our own TOTP is refused.** Constant-time comparison, clock skew
tolerance, replay rejection and throttling are exactly the details that are
easy to get subtly wrong and impossible to notice when wrong.

**On `architecture-trajectory.md` §4.** These are a dependency's models adopted
wholesale rather than concepts designed here, so §4's charter is not really the
governing question. Worth noting that they would pass it anyway: a `TOTPDevice`
is enrolled once and lives as long as the account, and a `StaticToken` is a
consumable from a batch that is spent and regenerated. Different life cycles,
which is §4's actual test.

## 2. The four interactions that shape this

### 2.1 `/api/v1/login` is a password-only path to a 90-day token

`accounts/api_v1.py:44` trades a username and password for a
`PersonalAccessToken` carrying `ANDROID_DEFAULT_SCOPES` and a 90-day expiry. It
starts no session, so **every session-based gate misses it.** A second factor
on the web form and on `/admin/` while this endpoint stands is not a second
factor; it is a second factor on one of two doors.

The containment already built is real and worth stating precisely: those scopes
reach capture, the day, the agenda and routines. They do **not** reach
`/admin/`, so this is not a path to other people's data. It is a path to the
account holder's own tasks and journal for ninety days, on a password alone.

**The Android client cannot ship a new release.** `assembleRelease` produces
nothing usable until the keystore in
[`android-release-signing-plan.md`](android-release-signing-plan.md) exists,
and that is deliberately Vince's to generate by hand. So the obvious fix —
accept a `totp` field in the payload and add a third box to the Connect screen
— is not merely more work, it is **unavailable**, and would leave the bypass
open for as long as the keystore does not exist.

**So: refuse the endpoint for accounts with a confirmed device.** A specific
error telling the holder to create a token on the web, where the second factor
already stands. Small, complete, and reversible the day a signed release can
carry a TOTP field.

It costs exactly what the endpoint was built to buy — `android-login-plan.md`
added it so nobody would have to paste a token — and the population paying that
cost is the staff accounts of increment 1, which is one person who can paste.

### 2.2 The export would not leak the seed, but only by accident

`accounts/export.py` enumerates through `OWNED_APPS`, a tuple of six app
labels. `otp_totp` and `otp_static` are not among them, so `TOTPDevice.key` —
the shared secret — and the static recovery tokens would not be serialised into
a downloadable archive.

**That is the right outcome reached by the wrong mechanism.** Nothing states
the decision, nothing tests it, and it holds only as long as nobody adds the
new labels to `OWNED_APPS` while tidying. The export's own docstring records
what that costs: D12 was three owned models nobody noticed were missing, and
the lesson written down was that *the promise was not checkable, so it was not
true*.

Same lesson, opposite direction. The promise here is that a secret never leaves,
and it needs to be checkable in the same way.

### 2.3 Erasure works by cascade, and this must not change that

`purge_account` deletes `ActivityEvent` explicitly — it is append-only by
trigger and unreachable by cascade — and then calls `user.delete()` for
everything else. `django-otp`'s devices carry an ordinary `CASCADE` foreign key
to the user model, so they are removed by that call and reported in the
per-model counts it returns.

Nothing to build. It needs a test, because "the cascade covers it" is a claim
about a dependency's field definition, which is the kind of claim that is true
until a major version.

### 2.4 axes cannot see a wrong six-digit code

`django-axes` counts failures at `authenticate()`. Verifying a TOTP token is
not `authenticate()` — it is a second step against an already-authenticated
session. **So the five-attempt lockout does not apply to the second factor at
all**, and without something else in front of it a six-digit code is a
brute-force target with a bounded and small keyspace.

`django-otp`'s devices carry their own throttling, which backs off after
repeated failures. **Confirm it is active rather than assume it** — it is
version-dependent, it is the whole of the protection on this step, and a test
that a wrong code cannot be retried indefinitely is the only thing that turns
the assumption into evidence.

### 2.5 Two smaller ones

**`django-unfold` overrides admin templates; `admin.site` is stock.** So
`OTPAdminSite`'s replacement login form would render into a template that does
not know about it. Avoided entirely by the design below, which verifies on a
project-owned view rather than inside the admin's login.

**The enrolment QR must be a `data:` URI.** `img-src 'self' data:` already
permits it, so this needs no CSP change — which matters because
`security-and-resilience-plan.md` §1.2 wants that policy promoted to enforcing,
and a new control that forced the policy open would be a poor trade.

## 3. The design

**Verification is a project-owned view, and the admin only asks a question.**

- `django_otp.middleware.OTPMiddleware` sits after `AuthenticationMiddleware`,
  giving `request.user.is_verified()`.
- An `AdminSite` subclass overrides `has_permission()` to require
  `is_verified()` alongside the existing staff check. That is the entire
  enforcement, and it is small enough to read in one sitting.
- `/accounts/verify/` collects the code, in this application's own templates
  and palette, and redirects back. Enrolment lives beside it at
  `/accounts/security/`.

The alternative — `OTPAdminSite` with its bundled form — is fewer lines and
buys a template collision with unfold plus a login screen that looks like
neither core. Not worth it for the lines saved.

## 4. The increments

**Enrol before enforcing. This is the ordering that matters most**, and getting
it backwards means deploying a lock and then discovering you are outside it.

| # | Increment | Ships with |
|---|---|---|
| 1 | Apps, migrations, middleware. **No enforcement.** | its own deploy |
| 2 | Enrolment and recovery codes at `/accounts/security/` | 1, or just after |
| 3 | **Vince enrols in production** | nothing — it is a person's step |
| 4 | Enforcement, **and** closing 2.1 together | one deploy, after 3 |

**4 is one deploy and not two.** Between enforcing the admin and refusing
`/api/v1/login`, a password alone still mints a ninety-day token — a window
that exists only because the two halves were split, which is
`principles.md`'s *slice the work, split the commits* applied the right way
round: two commits, one deploy.

### Acceptance, per increment

1. `is_verified()` is present on the request and false for everyone; every
   existing test still passes. This increment changes no behaviour, which is
   the point of it having its own deploy.
2. A device can be enrolled, a wrong code is refused, **a wrong code cannot be
   retried indefinitely** (2.4), and a batch of recovery codes is generated
   once and shown once. Plus the two regression tests the interactions demand:
   an export archive contains neither the device key nor any static token
   (2.2), and `purge_account` removes the devices and says so (2.3).
3. Not a code change. Recorded when done, with the recovery codes stored
   somewhere that is not the laptop holding the password.
4. A superuser with a correct password and no verified device is refused by
   `/admin/`, proved by a test that authenticates successfully and is still
   turned away — **not** by a test that fails to authenticate, which would pass
   against no implementation at all. And `POST /api/v1/login` for an account
   with a confirmed device returns its specific refusal rather than a token.

## 5. Break-glass, and what it implies

A lost phone and lost recovery codes leave one route: `docker exec clarice
./manage.py` on the droplet, deleting the device row.

**That is worth stating rather than leaving implicit, because it is also a
bound on what this control is worth.** Shell access to the droplet is
equivalent to bypassing the second factor. It does not make MFA pointless — it
moves the bar from *knows a password* to *has shell on the host*, which is an
enormous move — but it does mean the answer to
`security-and-resilience-plan.md` D5, what stands in front of port 22, is part
of this control's strength rather than a separate topic.

Write the break-glass procedure down **before** increment 4 ships, not after.
The moment it is needed is the worst moment to work it out.

## 6. What this plan refuses

- **Forcing a second factor on ordinary accounts.** Increment 1's scope is
  staff, who are the accounts with reach beyond their own data. Ordinary
  accounts get it as an option when there are enough users for it to matter,
  and that needs a recovery path designed for people who are not Vince.
- **SMS as a factor.** SIM-swap is a real and cheap attack, and it would need a
  new outbound provider on a host that cannot even reach SMTP.
- **Email as a factor.** The mailbox is a password-reset target, so it is
  substantially the same factor wearing a hat.
- **A remember-this-device cookie**, at this scale. It is a second credential
  with its own lifetime and its own theft story, to save one person a code.

## 7. Open decisions

1. **M1. Does `/api/v1/login` refuse, or grow a `totp` field?** §2.1 recommends
   refusing, largely because the keystore blocks the alternative. If the
   keystore is generated first, that ordering is worth revisiting — but not by
   leaving the bypass open in the meantime.
2. **M2. Where do the recovery codes live?** A password manager is the obvious
   answer and makes the manager a single point of failure for both factors.
   Printed and physical is the honest alternative. This is the decision most
   likely to be skipped and most likely to matter.

## Relationship to other documents

- The argument for doing this at all, and its rank: `security-and-resilience-plan.md` §1.5.
- Why the Android client cannot ship: `android-release-signing-plan.md`.
- Why `/api/v1/login` exists: `android-login-plan.md`.
- The charter for new models: `architecture-trajectory.md` §4, addressed above.
- Delivery standards, including the failing-test-first rule increment 4's
  acceptance depends on: `principles.md`.
