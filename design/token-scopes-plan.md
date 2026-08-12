# Personal access token scopes and expiry

Vince · brief · written August 10, 2026 · **all scope tiers, including
Agenda's and the Daily-edit slice's own, deployed and verified in
production, August 11, 2026 (see §6, §7, §8).**

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

## 6. Built, verified locally, deployed and verified in production

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

**Deployed and verified in production, August 11, 2026.** Verified with
markers the change actually added, not just a green playbook run:

- `GET /api/v1/day` answers 401 to no credentials and to a garbage bearer
  token on the live server (baseline sanity the deploy landed and the
  route is still guarded).
- The SM-S928U1's existing session was gone (never connected on this
  device before), so logging in fresh minted a token under the new
  Android default scopes automatically — no manual scope picking, per
  §3's design. Opening Today then rendered real production data: the
  actual date, a real overdue task ("Pay tmobile bill," correctly labelled
  "Added 13 days ago" / "11 days overdue"), its real area, and the correct
  empty states for Focus and Routines. That is the full chain — deploy,
  migration, `TokenAuth` scope check, and the Android client — working
  together against the live server, not a mock.
- The SM-F966U's pre-existing, grandfathered token still shows "Connected
  as Vrbeall01" in Settings after the deploy, confirming the migration's
  grandfathering preserved every already-connected phone's capture and
  identity access rather than silently narrowing it.

Every already-connected phone keeps working at its grandfathered scope
(`capture:write`, `identity:read`) until its owner reconnects; only a
fresh login picks up `day:read`. Both test phones now also have "Require
unlock to open" enabled.

## 7. Extending token auth to hand-rolled views (Agenda slice)

`android-full-client-plan.md`'s Agenda slice needs more than `/api/v1/agenda`
(a Ninja route, same shape as `/day` — add `TokenAuth(SCOPE_AGENDA_READ)`
and done). The Agenda page's own actions — complete a task, reschedule its
due date — call endpoints that were deliberately never moved onto the Ninja
router at all: `lists/api.py`'s docstring is explicit that item mutations
"stay on the hand-rolled `lists.api` endpoints... a route's migration PR
only moves what doesn't already have a JSON path." Those views use their
own `api_login_required`, a plain `request.user.is_authenticated` check
with no token concept whatsoever.

**Why this isn't just "add `TokenAuth` to another `auth=` list."** These
aren't Ninja operations, so there's no `auth=` list to extend. Worse, they
sit behind Django's *real* `CsrfViewMiddleware` — confirmed by
`lists/tests/test_api.py::test_rejects_missing_csrf_token`, which every
Ninja route is structurally immune to. Tracing why capture's own token path
already works clarified the actual mechanism, which turns out not to be
Ninja-specific magic:

1. Every Ninja view is marked Django-`csrf_exempt` at registration
   (`ninja/operation.py`), so `CsrfViewMiddleware` never touches any
   `/api/v1/...` request, token or session.
2. `SessionAuth` (which `SessionAuthIfLoggedIn` extends) re-implements the
   check itself, manually, only when *it* is evaluated —
   `ninja.security.apikey.APIKeyCookie._get_key()` calls
   `ninja.utils.check_csrf(request)`, which constructs a throwaway
   `CsrfViewMiddleware` and calls its real `process_request`/`process_view`
   directly. Same Django logic, just invoked by hand instead of by the
   middleware chain.
3. `TokenAuth` extends `HttpBearer`, a sibling class that never touches
   CSRF at all — there's nothing to skip, since a Bearer header isn't a
   cookie a cross-site request could ride on.
4. Because Ninja's `auth=[TokenAuth(...), SessionAuthIfLoggedIn()]` list
   stops at the first entry that resolves, a successful token auth means
   `SessionAuthIfLoggedIn` — and the CSRF check living inside it — never
   runs at all. That's the entire mechanism behind "a bearer request never
   reaches the cookie auth's CSRF check." Nothing about it is exclusive to
   Ninja.

**The fix ports that exact mechanism, not a hand-rolled approximation of
it.** `accounts.auth.token_or_session_required(scope)` — a decorator for
plain Django views, sitting beside `TokenAuth`:

- A `Bearer` header present → resolve it exactly like `TokenAuth`
  (hash lookup, `is_active`, `is_expired()`, `has_scope(scope)`); on
  success, set `request.user` and `request.token_authenticated = True`,
  no CSRF check (same reasoning as `HttpBearer` — nothing to skip because
  nothing rides a cookie). On a *present but invalid* header, refuse
  outright rather than falling through — a failed token must not be told
  its problem is a missing cookie, same ordering rule `TokenAuth`'s own
  docstring already states.
- No `Bearer` header → the view is marked `csrf_exempt` at the Django
  level (mirroring step 1 above, otherwise a session request would 404⁠-
  proof itself against a check that used to run automatically), so the
  session path calls `ninja.utils.check_csrf(request)` itself — reusing
  Ninja's own primitive rather than re-deriving CSRF-checking logic by
  hand, a place mistakes are expensive — then falls back to
  `request.user.is_authenticated`. Byte-for-byte the same protection the
  browser path had before this decorator existed.

**A real scope-creep risk, found by reading `item_detail` rather than
assumed away.** It is one view handling `PATCH` (six different possible
field changes: `text`/`status`/`due_date`/`tags`/`recurrence`/`notes`,
exactly one per request) and `DELETE`, behind one auth check. A naive
`agenda:write` wrapping the whole view would let a token that can complete
a task *also* delete it, rename it, or rewrite its notes — none of which
Android's Agenda slice sends or needs. The guard belongs inside
`item_detail`, where the field-level knowledge already lives, not in the
generic decorator: once `changed_fields` is known, a token-authenticated
request (`request.token_authenticated`) is refused with 403 unless
`changed_fields ⊆ {"status", "due_date"}`, and `DELETE` is refused outright
for a token regardless of scope. Session requests are completely
unaffected — every existing capability stays reachable from the browser
exactly as it is today.

**New scopes**, following the existing `capture:write` split of narrow
verbs over one surface: `agenda:read` (`GET /api/v1/agenda`) and
`agenda:write` (`create_item`, and `item_detail`'s `status`/`due_date`
fields only, per the guard above) — not added to `ANDROID_DEFAULT_SCOPES`
until the Android client actually calls them, same discipline `day:read`
followed.

## 8. Two more write scopes for the Daily-edit slice

`android-full-client-plan.md` §8: the Daily Page's own write actions —
focus pin/unpin, the day's own text, and every routine action. Unlike
Agenda's write half (§7), every one of these endpoints already lives on
the Ninja router (`daily/api_v1.py`, `routines/api_v1.py`), so this needed
no CSRF-porting and no `token_or_session_required` — just the same
`TokenAuth(scope)` + `SessionAuthIfLoggedIn()` pair `day:read` already
uses, applied to two new scopes:

- `day:write` — `pin_to_day`, `unpin_from_day`, `write_day`
  (`daily/api_v1.py`). No field-level guard needed the way `agenda:write`
  needed one: `write_day` already only accepts
  `intentions`/`gratitude`/`happenings`, nothing more sensitive lives
  behind it.
- `routines:write` — `new_routine`, `log_routine`, `call_it_enough`,
  `pause`, `resume`, `skip_routine` (`routines/api_v1.py`), covering all
  six actions `DayRoute.tsx` itself offers, one scope rather than one per
  verb — none of these six needs to be grantable independently of the
  others.

Both scopes built and locally verified August 11, 2026 as part of
`android-full-client-plan.md` §8's own numbers (933 backend tests), and
already added to `ANDROID_DEFAULT_SCOPES` alongside `agenda:read`/
`agenda:write` — same discipline as `day:read`, added the moment the
Android client actually calls them, not before. Not yet deployed at all,
same gap §7's `agenda:read`/`agenda:write` has.
