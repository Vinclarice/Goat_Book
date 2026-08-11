# Personal access token scopes and expiry

Vince · brief · written August 10, 2026 · **built and tested locally August
11, 2026, not yet deployed** — see §6.

## 1. Trigger and diagnosis

`android-full-client-plan.md` §6: installing slice 1 on a real phone found
that `/api/v1/day` refuses the same Bearer token `/api/v1/me` accepts
cleanly, because only `capture` and `me` were ever opted into `TokenAuth` —
everything else is session-only by design. Asked what the right fix is
before touching any more endpoints' auth, Vince's answer was to design for
more than today's actual threat model: *"a secure option, just in case this
ever goes beyond just simply being my own personal to-do app."*

**What "secure enough for more than one trusted user" actually requires,
checked against the real model rather than assumed:**
`accounts.models.PersonalAccessToken` today is `owner`, `label`,
`token_hash`, `created_at`, `last_used_at` — nothing else. `TokenAuth`
(`accounts/auth.py`) resolves a valid hash to its owner and stops; there is
no concept of what a token is *for*, and no token has ever expired. Two
separate gaps, both real:

- **No scope.** A token minted to let a phone write captures already
  authenticates `/api/v1/me` too, because `TokenAuth` doesn't distinguish —
  it's identity, not capability. Opting `/api/v1/day` into the same
  all-or-nothing check (the quick fix considered and rejected in
  `android-full-client-plan.md` §6) would mean every existing capture token
  can now also read the Compass and journal text, silently, the moment that
  router's auth list changes.
- **No expiry.** A token is valid from creation until somebody remembers to
  delete it. Scoping bounds *what* a stolen token reaches; nothing today
  bounds *how long*.

## 2. What this deliberately isn't

Not an OAuth2 authorization-code flow, third-party client registration, or
short-lived-access-token-plus-refresh-token machinery. Those solve a
different problem — an app that isn't this one, or a user who isn't the
account holder, obtaining delegated access — and this product has neither
today: every client is either the browser (session auth, already correct)
or a device the account owner personally set up with their own username and
password. Building that machinery now would be exactly the "design for
hypothetical future requirements" `principles.md` warns against. What's
real and worth fixing now is narrower: least-privilege scope, and a bounded
lifetime. Both are additive to the existing token model, not a replacement
for it — a reversible step that leaves the door open to something heavier
later if an actual third-party-client requirement ever shows up, rather
than building for one that hasn't.

## 3. Design

### Schema

Two additive fields on `PersonalAccessToken`, both nullable so the migration
touches no existing row's meaning:

- `scopes` — **not** `django.contrib.postgres.fields.ArrayField`. Production
  runs Postgres but local dev and CI default to SQLite
  (`clarice/settings.py`, `DJANGO_DATABASE_URL` unset), and `ArrayField` has
  no SQLite backend at all — it would break `manage.py test` for anyone who
  hasn't exported that variable, which today's `CLAUDE.md` test command
  doesn't. A `TextField` storing a sorted, comma-separated set of scope
  strings, validated against a Python-level enum
  (`SCOPE_CAPTURE_WRITE = "capture:write"`, etc.) at the one place tokens
  are minted, is portable across both and exactly as queryable as this
  model needs — nothing here does a scope-based database query, only an
  in-process membership check after a token already resolved.
- `expires_at` — nullable `DateTimeField`. Null keeps meaning "never
  expires" for every token that already exists at migration time; making it
  non-null would be reinterpreting rows nobody re-consented to. New tokens
  get a real value going forward (§5).

### Enforcement

`TokenAuth` becomes parameterized by the scope an operation needs:

```python
class TokenAuth(HttpBearer):
    def __init__(self, scope):
        self.scope = scope

    def authenticate(self, request, token):
        pat = ...  # unchanged lookup
        if pat.expires_at and pat.expires_at < timezone.now():
            return None
        if self.scope not in pat.scopes:
            return None
        ...
```

Every operation that accepts a token names what it needs explicitly —
`auth=[TokenAuth("day:read"), SessionAuthIfLoggedIn()]` — the same shape
`capture/api_v1.py` already uses, just no longer scope-blind.
`identity:read` stops being implicitly free: `/api/v1/me` requires it like
everything else, kept uniform rather than special-cased, with the Android
client's own default scope set (below) always including it so nothing
observable breaks.

**Scopes named now, growing one at a time as each slice needs them —**
matching `android-full-client-plan.md`'s own per-domain, per-slice
approach, not pre-declared for surfaces that don't exist yet:

- `capture:write` — what every existing Android token already does.
- `identity:read` — `/api/v1/me`, needed by Connect and Settings.
- `day:read` — this slice's actual blocker.

### Web: minting a token

`accounts/views.py`'s `TokenForm` gains a multi-select for scopes (nothing
checked by default — an explicit, least-privilege choice, not a
pre-selected "read everything") and an expiry choice (a short list — 90
days, 1 year, no expiry — rather than a free-text date, so "no expiry" is a
decision someone visibly makes rather than the silent default it is today).
`PersonalAccessToken.generate` takes both.

### Android: minting a token

The in-app login (`ConnectViewModel.logIn` → `POST /api/v1/login`) is a
different path from the web's manual picker — nobody using the app should
have to understand scopes to log in, the same reasoning that keeps Capture
itself down to a text field and a button. `/api/v1/login` mints a token
with a fixed, versioned default scope set for "the Android client" —
`capture:write`, `identity:read`, `day:read`, extended in the same commit
that adds each new slice's own scope — and a sensible expiry (matching the
web's own default, not "no expiry": a lost phone should not be a
standing, unbounded risk). A manually pasted token (Connect's "paste a
token instead" path) carries whatever scopes its owner picked on the web
when they made it, which may legitimately be narrower.

### Grandfathering

Every `PersonalAccessToken` row that exists when this ships has `scopes`
unset. Rather than reinterpret that as "no scopes" (which would silently
break every currently-connected phone's capture flow) or "every scope"
(which reintroduces the exact problem this fixes), the migration sets
existing rows to exactly what they can do today —
`{capture:write, identity:read}` — the same additive-migration shape
`principles.md` asks for: nobody's phone stops working, and nobody's token
silently gains `day:read` it was never granted. Anyone who wants slice 1
working reconnects (logs in again from the app), which mints a fresh token
under the new default set — the same action `android-full-client-plan.md`
§6 already expects a token holder to take.

## 4. Acceptance

- A token scoped to `{capture:write}` alone gets 403 (not 401 — the token
  is valid, the request just isn't allowed) from `/api/v1/day`.
- A token past its `expires_at` is refused the same way a revoked one is
  today, and the failure message a client shows doesn't need to
  distinguish expired from revoked from wrong-scope — "reconnect" is the
  correct instruction for all three, the same message Android's
  `DayUnauthorised` already shows.
- Existing tokens keep working for capture and identity, unchanged, after
  the migration runs — verified by a test that creates a token before the
  scope column exists (or asserts the migration's default directly) and
  confirms it still authenticates `/api/v1/capture` and `/api/v1/me`.
- `manage.py test` passes with no `DJANGO_DATABASE_URL` set, proving the
  scope field doesn't secretly require Postgres.

## 5. What this doesn't decide yet

Whether `day:read` is the only new scope this ships with or whether it's
worth adding the next slice's scope (whatever Agenda needs) in the same
migration to avoid a second one immediately after. Rate limiting per-token,
audit logging of scope usage, and anything resembling delegated
third-party access stay explicitly out of scope per §2 unless a real
client that isn't Vince's own shows up to justify them.

## 6. Built, verified locally, not deployed

Implemented in full August 11, 2026: `PersonalAccessToken.scopes`/
`expires_at` (migration `0013`, grandfathering existing rows to
`capture:write,identity:read`), `TokenAuth` now takes a required scope and
checks expiry, `/api/v1/me` requires `identity:read`, `/api/v1/capture`
requires `capture:write`, `/api/v1/day` and `/api/v1/day/{day}` now accept
`day:read` alongside session auth (§1's actual blocker), `/api/v1/login`
mints Android tokens with `ANDROID_DEFAULT_SCOPES` and a 90-day expiry, and
the web's token-creation form gained a required scope picker (nothing
pre-checked) and an expiry choice (90 days / 1 year / never, defaulting to
90). Every existing test that minted a token for a successful call was
updated to grant the scope its endpoint now requires — a genuine contract
change, not a relaxed assertion — plus new tests for each refusal case
(wrong scope, expired, no scope at all). Full backend suite: 899 tests,
0 failures. `makemigrations --check` clean.

**Not yet true:** this only exists on the local dev database. Production
still runs pre-scope `TokenAuth()`, so `/api/v1/day` is still session-only
there and Android's Today tab is still blocked exactly as
`android-full-client-plan.md` §6 found it. Deploying is Vince's own step
(`CLAUDE.md`'s "Deploying" section) — this migration is additive and safe
to run ahead of the code that depends on it, same as any other migration
this project ships separately from its feature. After deploying, every
already-connected phone's existing token keeps working at its grandfathered
scope; only a fresh login (reconnect) picks up `day:read`.
