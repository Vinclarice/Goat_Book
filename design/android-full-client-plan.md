# Android full client — from capture-only to a real mirror of the website

Vince · brief · written August 10, 2026 · **slice 1 shipped and verified
in production August 11, 2026**

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
