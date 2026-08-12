# Android full client — from capture-only to a real mirror of the website

Vince · brief · written August 10, 2026 · **all three slices — Daily Page
read-only, its write extension, and Agenda — shipped, deployed and
verified live in production, August 11, 2026** — see `roadmap.md`'s own
account of this line of work

## 1. Trigger and diagnosis

Bittern's Android client was scoped deliberately narrow: "its only purpose is
getting a thought into the inbox quickly; triage remains in the web app"
(`roadmap.md`, Track F). `roadmap.md`'s own "Longer-term product direction"
section already named the reconsideration, dated August 10, 2026: *"Turn the
Android app into a fully functional client, not just capture... No trigger
has fired and nothing here is scheduled."*

The trigger is this conversation. Vince has put substantially more work into
the website since Bittern shipped — Daily Page, Agenda, Areas, Projects,
Review, Routines all now have real, Tailwind-redesigned surfaces — and wants
the phone to be able to do more than write into the Inbox and leave.

**What "mirror the website" actually requires — checked, and corrected once
by a real device.** `lists/api_v1.py`, `daily/api_v1.py`, `review/api_v1.py`,
and `routines/api_v1.py` are the same *routes* the SPA consumes — nav,
agenda, areas, projects, task detail, archive, the day, the week, routines.
What this section originally claimed, wrongly, is that they're the same
*auth* as `/api/v1/me`/`/api/v1/capture`. They are not: `clarice/api.py`
sets `NinjaAPI(auth=django_auth, ...)` as the default for every router, and
only `/me` and `/capture` explicitly opt into
`auth=[TokenAuth(), SessionAuthIfLoggedIn()]`. Every other router, daily
included, is session-cookie-only by deliberate design ("a day is written
from the browser", per that file's own comment) — a phone carries no
session, so a personal access token that authenticates `/me` perfectly is
simply refused by `/day`. This was invisible to every unit test, which mocks
the server response, and only surfaced installing slice 1 on a real device
— see §6. `capture.Idea` remains the other real gap: it has no Ninja API at
all (noted in `second-mind-discovery-plan.md` and `roadmap.md`'s own
direction note) — that stays out of scope until its own slice.

So this is mostly an Android build-out — a navigation shell plus a screen per
domain, wired to APIs that already exist — not a backend rebuild. It is still
large: comparable in total scope to the whole Tailwind redesign arc (Project
workspace, Task list, Agenda, Archive), each of which was its own
plan-build-verify cycle. This doc covers the first slice only; later slices
get their own section here rather than being guessed at now.

## 2. Decisions

Asked directly rather than guessed, since committing an architecture wrong
here would cost every later slice:

- **First surface: the Daily Page**, not Agenda. Vince's choice. It's the
  web's home/landing surface (`nav`'s `landing_surface` defaults new visits
  there), and it's the one page that already reads five different domains
  (day entry, focus, action items, routines, compass) through one endpoint —
  a good test of whether the Android data layer generalizes before committing
  to per-domain screens.
- **Slice 1 is read-only.** View real data end-to-end — auth, network,
  parsing, rendering — before adding the write paths (pin/unpin, routine
  logging, the day's own text form). A vertical slice that ends at "I can see
  it" is smaller, faster to verify without a device, and doesn't half-build a
  write path with no test coverage on the JVM (Keystore-backed pieces aside,
  everything else here is instrumentation-free).
- **Navigation: no NavHost, no icon library.** `MainActivity.kt` currently
  has no navigation graph "on purpose... adding one now would be scaffolding
  for screens the plan says not to build" — that sentence stops being true
  today, but a full Jetpack Navigation Compose graph is still more than two
  destinations justify. A hand-rolled tab switcher (a `Row` of two
  `TextButton`s, styled by `ClariceTheme`'s own accent) matches the app's
  existing idiom — no `Scaffold`, no `TopAppBar`, no Material icons
  dependency anywhere else in this codebase — and is trivially replaceable
  with a real `NavigationBar` once there are enough tabs to need one.
  Settings stays reachable the way it already is on Capture: a `TextButton`
  in each tab's own header row, not a third tab.
- **API layer: one file per domain, not one growing `ClariceApi`.**
  `ClariceApi.kt` owns identify/login/capture; a new `DailyApi.kt` owns
  `GET /api/v1/day`, following the exact same shape (sealed result type,
  `OkHttpClariceApi`-style implementation, `Authorization: Bearer` header,
  parsed with `org.json`, tested against a real `MockWebServerRule`). Later
  domains (Agenda, Areas, Projects) get their own API files the same way
  rather than one file accreting every endpoint the app ever calls.
- **Display wording ported by hand, not shared.** `dueLabel`, `ageLabel`
  (`frontend/src/agenda.ts`) and `standingLabel` (`DayRoute.tsx`) are pure
  display functions with no server authority — same category as
  `frontend/src/agenda.ts`'s own comment about `SCOPES`: "client-only... If
  the server ever [owns this], the definition moves there." There's no
  shared build step between a Gradle project and a Vite one, so these are
  ported by hand into Kotlin with the same wording and their own tests,
  documented as a manual-sync point the way `ui/theme/Color.kt` already
  documents itself against `tailwind.css`.

## 3. Slice 1 scope

**In:**

- `GET /api/v1/day` via a new `DailyApi`, authenticated with the stored
  token, returning a sealed result (loaded / unauthorised / unreachable —
  same three-way split `ClariceApi.identify` already uses, for the same
  reason: a revoked token and a flaky network need different words).
- A `DailyScreen` showing, in the same order as `DayRoute.tsx`: the date
  header (Today vs. a past day's own date), the Personal Compass if either
  field is set, Focus (read-only rows), Action Items (read-only rows with
  area/project chips and due/age labels, or the "only today shows action
  items" sentence on a non-today day — not reachable yet since there's no
  date picker, but the field exists in the response and the render logic
  should be honest about it), Routines (read-only progress line per
  standing), Paused routines, and the day's own written Intentions /
  Grateful for / Happenings as plain read-only text rather than editable
  fields.
- A `Today` tab beside the existing `Capture` tab, both reachable from the
  moment someone is connected; Settings unchanged.
- Failure and empty states matching `principles.md`'s "failure is
  recoverable and visible": a plain-language message plus a retry action on
  network failure, not a blank screen.

**Out, deliberately, named so nobody adds it by accident:**

- Pinning/unpinning a task to Focus, logging/skipping/pausing a routine,
  editing the day's own text, and the day's own quick-capture box (Capture
  is one tab away already — duplicating it here is the near-identical-control
  mistake C2 already spent a release fixing on the web).
- A date picker / past-day browsing (`GET /api/v1/day/{day}`). The schema
  and the non-today render branch are handled honestly, but there's no
  control to reach a past day yet.
- Any other domain — Agenda, Areas, Projects, Archive, Review, Ideas. Each
  earns its own slice and, if its shape turns out to need one, its own
  decisions section here.

## 4. Acceptance

Read-only parity with what `DayOut` actually returns, verified by:

- Unit tests for `dueLabel`/`ageLabel`/`standingLabel` (wording) and
  `DailyApi` (auth header, the three result outcomes, malformed-body
  handling) — written first, per `principles.md`.
- `:app:compileDebugKotlin` and the full `:app:testDebugUnitTest` suite
  green.
- Device pass, August 10, 2026: installed and launched clean on both the
  SM-S928U1 and the SM-F966U, no crashes, theme and tab switching correct.
  **Today itself did not load** — see §6 for the finding and
  `token-scopes-plan.md` for the fix.
- **Device pass, August 11, 2026, after `token-scopes-plan.md` deployed:**
  a fresh login on the SM-S928U1 minted a token under the new scopes with
  no manual step, and Today rendered real production data end to end — the
  actual date, a real overdue task with correct age/due labels and area,
  and the correct empty states for Focus and Routines. "Works end to end
  on a phone" is now true, against the live server, not a mock. The
  SM-F966U's pre-existing token also kept working (Settings still showed
  "Connected as Vrbeall01"), confirming the fix didn't strand an
  already-connected phone.

## 5. What this doesn't decide yet

Slice ordering after this one, whether write paths land as their own slices
per surface or bundled once the read side of everything exists, and whether
`capture.Idea` gets a Ninja API before or after the rest of the read-only
surfaces are mirrored. Recorded here as open rather than answered by
momentum.

## 6. Blocked: session-only auth, found by the device pass

`GET /api/v1/day` answers 401 to the same Bearer token that authenticates
`/api/v1/me` cleanly (confirmed on-device: Settings shows "Connected as
Vrbeall01" while Today shows "Reconnect in Settings to see today.," same
stored token, same request). Root cause is §1's correction above — `daily`
is session-only by design, not a bug in `DailyApi.kt`.

**Not a quick patch.** Copying `capture/api_v1.py`'s
`auth=[TokenAuth(), SessionAuthIfLoggedIn()]` onto `daily` (and later
`lists`/`routines`/`review`) would work, but it silently widens what a
personal access token can do. Today a token can write a capture and read a
username/email — a narrow, deliberately-scoped surface
(`bittern-plan.md`'s M1). Opting a router into `TokenAuth` as-is would let
that same token read the whole Daily Page, including the Compass and
journal text, with no way to grant read access without also trusting the
token for account identity. Vince's call, asked directly rather than
patched around: **design a scoped/read-only token tier before widening any
more endpoints**, rather than opting each one into today's all-or-nothing
`TokenAuth`. That design is its own piece of work, not sized or started
here — this section exists so slice 1's real status (compiles, tests green,
does not load real data on a phone) isn't lost between sessions, and so the
next session doesn't re-diagnose what this one already found.

## 7. Slice 2: Agenda, read + complete/reschedule

**Trigger:** Vince's own choice of next surface, August 11, 2026 — "let's
move on to the agenda." Asked whether this slice should stay read-only
like slice 1 or include completing a task, Vince chose the fuller,
harder version: *"let's make it fully functional which I realize will
require more work."* Named here so the scope decision reads as chosen,
not defaulted into.

**What "fully functional" means for this slice, checked against the real
page rather than assumed:** the web `AgendaWorkspace.tsx` does five things
— quick-add, complete/reopen, snooze/reschedule, area+tag filtering, and
search — plus links out to a task's own edit page for anything else
(retagging, renaming, notes). This slice mirrors exactly that boundary:
what the Agenda page itself does becomes what Android can do; everything
that page hands off to a task's own detail screen stays out of scope here
too, same as it does on the web.

**In:**

- `GET /api/v1/agenda` (`agenda:read`) — buckets, items, `completed_today`,
  areas, projects, same `TaskOut`/`AgendaAreaSummaryOut` shapes the SPA
  already reads.
- Complete / reopen a task — `PATCH {task.url}` with `{"status": ...}`
  (`agenda:write`, restricted to this field — see
  `token-scopes-plan.md` §7).
- Reschedule / snooze a task's due date — `PATCH {task.url}` with
  `{"due_date": ...}` (`agenda:write`, same restriction).
- Quick-add a task — `POST {area.create_item_url}` (`agenda:write`).
- Area and tag filter chips, text search, and the scope counts
  (overdue/today/week/open) — all client-side derivation over the already-
  fetched payload, the same way the web page computes them; `bucketFor`
  and a substring search filter get ported to Kotlin alongside the
  already-ported `dueLabel`/`ageLabel`, same manual-sync convention.

**Out, deliberately:**

- Editing text, tags, recurrence, or notes; deleting a task; reordering.
  None of these are things the Agenda page itself does — they live on
  `TaskDetailRoute`, which is its own future slice if it ever gets one.
- Creating a new area or project (Agenda's sidebar forms) — sidebar
  chrome, not the task-triage loop this slice is actually about.
- The Archive link and the daily-digest status line — informational
  chrome from the same reasoning.

**Auth mechanism:** see `token-scopes-plan.md` §7 for the full design —
`GET /api/v1/agenda` gets the same `TokenAuth(scope)` treatment `/day`
already has; `create_item` and `item_detail` (both in the *hand-rolled*
`lists/api.py`, never on the Ninja router) get a new
`token_or_session_required(scope)` decorator that ports Ninja's own
token-skips-CSRF / session-still-checks-CSRF mechanism to a plain Django
view, plus a field-level guard inside `item_detail` so `agenda:write`
can't reach the five capabilities named "out" above through the same
endpoint.

**Built and locally verified, August 11, 2026.** Backend: 918 backend
tests green (up from 899), `makemigrations --check` clean, new coverage
for every refusal case (wrong scope, expired, DELETE, and each of
text/tags/notes/recurrence via a token) alongside the success paths.
Android: `AgendaFormatting.kt` (`bucketFor`, `matchesQuery`, `filterTasks`,
`tomorrow`, `nextMonday`) TDD'd first; `AgendaApi`/`AgendaModels` against a
real `MockWebServer`; `AgendaViewModel` covering load, all three writes,
filter toggling, and the "a failed write must never blank an
already-visible list" rule. 260 Android tests green (up from 212),
`:app:compileDebugKotlin` clean. `AgendaScreen` added as a third tab
beside Capture/Today.

**Device pass, same day, SM-S928U1:** installed clean, no crash (checked
logcat directly, not inferred). The Agenda tab correctly shows "Reconnect
in Settings to see your agenda" — expected and correct, since
`agenda:read`/`agenda:write` exist only in this session's local database,
not yet deployed. Today and Capture re-checked on the same build for a
regression from the third-tab change: neither regressed:
Today still rendered real production data (the same overdue task,
correctly labelled, from the prior slice's own device pass).

**Not yet true, same gap slice 1 had:** nothing here has reached
production. Deploying is Vince's own step; once it lands, the real
end-to-end check is completing or rescheduling an actual task from the
phone and confirming it on the web.

## 8. Slice 1, extended: Daily Page becomes writable

**Trigger:** Vince's own choice, same day as slice 2 — "before we do
[Agenda], can we so the same process to the Today? Make the app able to
edits?" — asked and built before Agenda's own device pass, so this section
is numbered after §7 but was built and verified alongside it.

**What "writable" means for this slice, checked against `DayRoute.tsx`
rather than assumed:** the web Daily Page does four things beyond
displaying the day — pin/unpin a task to Focus, act on a routine
(log/skip/pause/resume/call-it-enough), keep a new routine, and save the
day's own Intentions/Grateful for/Happenings text. This slice mirrors
exactly that set. The quick-capture box stays off this screen, unchanged
from slice 1's own reasoning — Capture is one tab away already.

**In:**

- Pin/unpin a task to Focus — `POST`/`DELETE /api/v1/day/{day}/focus[/{id}]`
  (`day:write`).
- Save the day's own text — `PATCH /api/v1/day/{day}` with all three
  fields together, matching the web's own "Save the day" button rather than
  exposing the server's per-field-optional contract (`day:write`).
- Every routine action `DayRoute.tsx` itself offers — log an amount
  (`+1`/`-1`, a negative amount correcting a mis-tap rather than being its
  own endpoint), skip, call-it-enough, pause, resume, and keep a new
  routine (`routines:write`).

**Out, deliberately:** everything named out of slice 1 that this doesn't
touch — a date picker / past-day editing, and any other domain. Editing a
routine's own title/cadence/target once kept, or deleting one, since
`DayRoute.tsx` doesn't offer those either.

**Auth mechanism:** both new endpoints groups are Ninja operations
(`daily/api_v1.py`, `routines/api_v1.py`), so unlike Agenda's write half
this needed no CSRF-porting — the same `TokenAuth(scope)` +
`SessionAuthIfLoggedIn()` pair slice 1's `day:read` already uses, just two
new scopes: `day:write` (`pin_to_day`, `unpin_from_day`, `write_day`) and
`routines:write` (all six routine actions). See
`token-scopes-plan.md` for the scope constants; no new CSRF mechanism to
document since none was needed.

**Built and locally verified, August 11, 2026.** Backend: 933 tests green
(up from 918), covering every write's success path, wrong-scope refusal,
expired-token refusal, and session-still-works alongside the token path.
Android: `DailyApi` extended with `pinFocus`/`unpinFocus`/`writeDayText`
and the six routine actions against a real `MockWebServer`;
`DailyViewModel` gained draft text state (seeded once per calendar date,
not once per load, so a background reload after a routine action can't
stomp on in-progress typing — the same `seededFor` idea `DayRoute.tsx`
itself uses) and a shared `write()` helper that reloads the day on success
and leaves it untouched on failure, matching `AgendaViewModel`'s own rule.
`DailyScreen` rebuilt: pinned/unpinned rows with an explicit indicator,
multi-line routine cards with the exact button visibility `DayRoute.tsx`
itself uses, a collapsed-by-default "keep a routine" form, and the three
text sections turned into editable fields with their own "Save the day"
button. 285 Android tests green (up from 260), `:app:compileDebugKotlin`
clean.

**Device pass, August 11, 2026, SM-S928U1:** installed clean, no crash
(checked logcat directly). The Today tab renders the full new UI —
pin/unpin link on each action item, the routine section's empty state and
"Keep a routine" form, and editable Intentions/Grateful for/Happenings
fields all render correctly. Tapping "Pin to today" correctly shows
"Reconnect in Settings to change today" without disturbing the
already-displayed day — expected and correct, the same "exists only
locally, not yet deployed" state §7's Agenda device pass hit, not a bug:
`day:write`/`routines:write` aren't on production yet, so a write is
refused exactly the way `DayWriteUnauthorised` is supposed to be handled.

**Not yet true, same gap as slice 2:** nothing here has reached
production. Deploying is Vince's own step; once it lands, the real
end-to-end check is pinning a task or logging a routine from the phone and
confirming it on the web.
