# Clarice — Roadmap History

Vince · completed work and decision record · archived from `roadmap.md` on
August 1, 2026

## Why this file exists

This preserves the reasoning, deployment record, and lessons behind completed
work without making the active roadmap hard to scan. The active plan is
[`roadmap.md`](roadmap.md).

## Crane — shipped August 2, 2026

`crane` (`e0acf05`) was deployed at 20:05 EDT and marked by
`DEPLOYED-2026-08-02/2005`. Two deploys carried it: 17:54 EDT, which took
Crane 0a, 1 and 2 in one run of ten migrations, and the last one, which took
Crane 3's four. The tag went on after production was verified rather than
alongside the deploy, which is the correction Bittern's own record asks for.

The plan, the settled design decisions and the slice-by-slice acceptance
conditions are in [`crane-plan.md`](crane-plan.md), which is kept rather
than archived; the product direction behind it is in
[`daily-operating-system-vision.md`](daily-operating-system-vision.md).

It closed with work outstanding by decision rather than omission: the
remainder of Bittern's carried-in checklist, most of which this deploy
finally unblocked. That list stays in `crane-plan.md` §2 and in the active
roadmap until it is cleared.

### What shipped

- **Crane 0 and 0a — the repetition domain.** A design brief settling
  routines, targets and occurrences, plus the one half built immediately:
  `RecurringCommitment` and `Item.commitment`, so a recurring task's
  occurrences form a series rather than a chain of rows whose only
  connection was a matching text string. Its backfill linked both repeating
  tasks in production. The vocabulary half — moving `text` and `recurrence`
  onto a real template — went to release D with the parent–child redesign it
  depends on.
- **Crane 1 — the Daily Page**, in seven slices: a written day, the agenda
  embedded rather than copied, capture, a durable Daily Focus whose
  `released_at` distinguishes a decommitment from an unfinished commitment,
  the Personal Compass, the home surface with a preference to opt back out,
  and a phone-viewport pass over the assembled page.
- **Crane 2 — routines and task age**, in five slices: `Routine` and
  `RoutineOccurrence` with lazily created periods and snapshotted targets,
  correction and skip as distinct statements, routines on the day, pausing
  that keeps what already happened, and how long a task has been waiting
  said without reproach.
- **Crane 3 — the weekly review**, in ten slices: what a week finished, what
  it planned and what came of it, its own words and what is still waiting, a
  dated review record that stamps the figure it concluded from, one explicit
  decision at a time with no bulk reschedule anywhere on the surface, how
  habits performed over the periods a week actually asked of them, a paused
  week that says it was paused, a satisfied-but-partial close that is not a
  skip, four weeks of context, and a phone pass.

### What it taught

- **A slice list hides a missing surface unless you look for one.** It had
  happened twice — the Daily Page reachable only by typing its URL until
  slice 6, routine creation with no surface at all until Crane 2 slice 3 —
  so Crane 3's list was read back for that specific failure before any code
  was written. It found three: the navigation entry, the way to reach the
  week *before* this one, and a control for the new partial close. Reading
  the list for a known failure mode is cheaper than a slice discovering it.
- **A test can be wrong about the world rather than about the code.** Four
  times in this release: an assertion that the week of July 27 was not the
  current one, made on a Sunday inside it; a British date order asserted
  against a locale-following formatter; an unanchored `/all/` matching "Call
  the bank"; and a straight apostrophe asserted against the typographic one
  the application renders. Each looked like a defect for as long as it took
  to read it. `principles.md` already says to diagnose before editing either
  side; the corollary is that the test is a suspect too.
- **The schema could not answer a question the plan asked.** Slice 9 needed
  "before the account existed" and `accounts.User` carries no creation
  timestamp at all — no `date_joined`, no `created_at` — which a test found
  by asserting against one that was not there. Adding the field would have
  meant defaulting three real accounts to today and marking their whole
  history prehistoric, so the line was drawn at the owner's first trace
  instead: earliest day written, task made, routine kept, thought captured.
  The better question, arrived at by being unable to ask the worse one.
- **A rule emerged that no single slice set out to make.** Released pins,
  skipped periods and periods closed as enough all leave a denominator —
  three decisions taken a slice apart that turned out to be one: *a
  deliberate decision leaves the denominator; only what merely elapsed stays
  in it.* It is written that way in the code rather than as three
  subtractions, so the next decision-shaped outcome inherits it.
- **A guard that has never been seen red is a claim, not a check.** Three
  passed on their first run this release — that nothing in the review
  mutates a task, that the pause backfill seeds what it should, and that the
  page does not scroll sideways at 375px. Each was made to fail on purpose
  before being left alone.
- **Running the tests does not migrate the development database.** The first
  browser check of the review record failed with `no such table` on a suite
  that had been green for an hour, because tests build their own database
  and `migrate` had never been run against the dev one. The page said
  "Couldn't reach Clarice" with a retry rather than rendering blank, which
  was B2.1's fix doing precisely what it was built for — an unplanned
  confirmation of an earlier release from a mistake in this one.

## Bittern — shipped August 2, 2026

`bittern` (`359a7e3`) was deployed at 00:35 EDT and marked by
`DEPLOYED-2026-08-02/0035`. Three deploys carried the release: 11:56 EDT on
August 1 (`fed210b`), 21:51 EDT that evening, and the last one, which was
the only one to carry B2.1 and B2.2 — their commits landed after the second
deploy, and an earlier claim that Bittern was already live rested on
`/contact/` returning 200, which proved B3 and nothing else.

It closed with work outstanding by decision rather than omission: five
after-deploy checks never run, three infrastructure confirmations owed, and
several Android gaps. All are carried into Crane and listed there. The
executable detail is in [`bittern-plan.md`](bittern-plan.md), which is kept
rather than archived.

### What shipped

- **A native Android capture client** (`android/`, M1–M5). Personal access
  token authentication, capture online or offline, a durable encrypted
  queue drained in the background, a share target, and idempotent writes
  that cannot duplicate a thought. 143 JVM tests and 16 instrumentation
  tests.
- **Per-user time zones.** Left the deferred list the day both halves of
  its trigger fired: a second active user in Indonesia, and a digest
  delivering at 03:00 Eastern.
- **Web session and state gaps closed** — B1's spawned recurring subtasks,
  B2's SPA logout, B2.1's failure states, B2.2's browser smoke coverage.
- **Branded email and a contact path** (B3), and **production error
  monitoring** (B4).
- **B0** — the missing side navigation, diagnosed and fixed; see its own
  section below.

### What it taught

- **A phone was the first thing to discover a production contract gap.**
  The Android client's first real connection failed because the bearer-auth
  `/api/v1/me` endpoint was still only on `main`. The token was always
  valid. Check the deployed OpenAPI schema before pointing a client at an
  endpoint, not after. B0.1 exists because of this.
- **Verification tooling can lie.** The script written to prove production's
  duplicate protection matched `"id":[0-9]*` against an API that renders
  `"id": 2`, extracted nothing from either response, compared the two
  nothings, and announced that production was broken — over evidence in its
  own output showing it working. Assert on values you have proven you can
  parse.
- **Rebuilding a state object silently drops fields.** Twice in one evening:
  a pending count left standing over an emptied queue, and a keyboard
  preference reverting on every capture. Neither would ever be reported as a
  bug; people would just quietly stop trusting the app.
- **Some defects only exist on hardware.** Background delivery worked on its
  first real attempt, and the count on screen did not update, because a
  screen cannot see a background drain. Every unit test asserting that count
  was correct.
- **A marker has to be something the change introduced.** Checking whether
  B2.1 was deployed, `Something went wrong.` was found in the served bundle
  and nearly taken as proof — it predates B2.1 by months. `RequestFailed`,
  which B2.1 actually added, was absent. The weaker check would have
  confirmed a deploy that never happened, and the same instinct produced a
  premature "Bittern is live" in these documents an hour earlier.
- **`state: latest` on an infrastructure package** means a routine deploy is
  willing to restart the thing running the application. The "Install docker"
  task looked hung on three separate deploys and was cancelled each time.
- **Isolating one half of a store's identity is isolating neither.** The
  instrumentation tests parameterised the Keystore alias but not the
  preference file, so running them deleted a live token off a real phone.

## Albatross — shipped July 31, 2026

`albatross` (`f5ddb85`) was deployed at 22:24 EDT and marked by
`DEPLOYED-2026-07-31/2224`. It carried seven migrations, taking the schema
from 53 to 60 without changing existing rows.

### Platform and production work

- Replaced the task UI with a React Router/TanStack Query SPA backed by a
  Django Ninja `/api/v1/` contract and generated TypeScript types.
- Moved production from bind-mounted SQLite to managed Postgres.
- Added GitHub Actions: Django tests run against Postgres and frontend tests
  and builds run on every push and pull request.
- Restricted the application to a dedicated Postgres database user, proved
  the backup/restore path, and restricted the database firewall to the
  application droplet.
- Added the daily-digest cron job, verified by dry run. Its first unattended
  cron fire is 07:00 on August 1, 2026; "runs as root from cron on a
  schedule" has a failure mode that "prints to stdout when I run it" does
  not, so this is not proven until that run is checked.
- Added self-service password reset and production-ready static asset
  handling through Docker, Gunicorn, WhiteNoise, nginx, and Ansible.

### Task and agenda work

- Added archive/restore state handling and snooze presets.
- Added notes as plain text on task detail.
- Added one-level subtasks with duplicate protection, ordering, ownership
  isolation, archive/restore, completion, recurrence, and undo behavior.
- Added `always_recurs` to decide which subtasks return with a recurring
  parent, plus the follow-up fix that prevents completed children from being
  orphaned when their recurring parent archives.
- Added persistent SPA navigation in source. Its absence in production was
  Bittern B0, diagnosed and patched on August 1, 2026 — see below. The
  deployed bundle was never the problem.
- Added direct Inbox and Ideas links to the Agenda workspace as a fallback
  entry point. They mitigate a missing side nav only once the current frontend
  bundle is deployed; they do not replace B0's production-bundle diagnosis.

### Capture and account work

- Added Capture: a zero-friction, owner-scoped inbox for untriaged thoughts.
- Added Capture triage into a task, an Idea, or a discarded record; added
  undo for that brief transition period.
- Added Ideas with exploring/reference states, notes, edit/delete, and
  promotion to a task.
- Added personal access tokens and `POST /api/v1/capture` for non-browser
  capture clients.
- Added account themes, daily-digest preferences, and password reset.

## Completed tracks

### Track A — infrastructure and public-readiness foundations

All A0–A6 work is complete:

| Item | Result |
| --- | --- |
| A0 | CI with a Postgres 18 service container, Django tests, frontend tests, and build verification. |
| A1 | Dedicated production database user, including ownership correction required for Django migrations. |
| A2 | Restore drill passed against a cloned managed database. |
| A3 | Adversarial per-user isolation suite, including id-based task/list and subtask cases. |
| A4 | Daily digest cron installed; first unattended run still to be checked. |
| A5 | Database firewall closed to the production droplet. |
| A6 | Self-service password reset, including live validation of lockout behavior. |

### Track B — Capture MVP

Capture shipped as a Django app before being expanded with token-authenticated
API capture, then its triage and Idea model. The two-week usage checkpoint was
dropped as a release gate: the triage model had enough direct product
conviction to ship. Real usage should still inform future scope.

### Track A Next — task model improvements

The original queue — archive/restore correction, snooze presets, task detail,
notes, subtasks, and persistent navigation — is complete. The recurring
subtask follow-up is also complete.

The one deliberately unscoped consequence — a spawned recurring task not
serializing its copied subtasks, so they appeared only after a refresh — was
closed as Bittern B1 on August 1, 2026.

## Bittern B0 — the missing side navigation, diagnosed August 1, 2026

### The artifact was never the problem

B0 existed to decide between two causes: a stale or mispackaged frontend
bundle, or a current bundle failing at runtime. Read-only evidence gathered
against the running albatross deployment, before any redeploy:

| Check | Result |
| --- | --- |
| Deployed asset | `frontend/app-shell.b94af7d63d1b.js`, 179,011 bytes |
| `Last-Modified` | 2026-08-01 02:23:16 GMT — the `DEPLOYED-2026-07-31/2224` deploy |
| Deployed `staticfiles.json` | Maps `frontend/app-shell.js` to that hash, so it is what `app_shell.html` referenced |
| Navigation strings in the served JS | Agenda, Inbox, Ideas, Archive, Preferences all present |
| `Log out` in the served JS | Absent, correctly — B2 was unbuilt, corroborating the artifact as albatross |
| Served `app.css` | Byte-identical to a local build, including the shell grid and the 760px rule |
| `AppLayout`/`SideNav`/`sidenav.module.css` at `f5ddb85` vs `main` | Unchanged |

The bundle was current and correct. The stale-artifact branch was closed on
evidence rather than assumption.

### The cause

`AppLayout` wrapped `SideNav` in a `<details>` that nothing ever opened,
while `sidenav.module.css` hid its `<summary>` unconditionally. Above the
breakpoint the nav was therefore sealed inside a closed disclosure with no
handle to open it — the source comment asserted "above it the nav is always
open," but no code implemented that.

A closed `<details>` has its contents skipped, so the element collapsed to
zero height. Measured on the live page:

```text
detailsBox: 210x0     <- the empty gutter the user could see
navBox:     210x306   <- a skipped subtree keeps its geometry
shellCols:  210px 1814px
```

Firefox does not paint skipped content, so the column was simply empty.
Chromium 148 still paints it, which is why the same page looked correct in
Edge and on a Chromium phone, and why the defect shipped.

### Why no test caught it

`SideNav.test.tsx` renders the component directly, never inside the
`<details>`, and jsdom has no paint model in any case. The condition is
invisible to unit tests by construction. `AppLayout.test.tsx` now asserts
the invariant that was violated — above the breakpoint the disclosure is
open, and stays open across navigation — but proving what a person actually
sees needs B2.2's browser-level coverage.

### The fix

The layout now holds the disclosure open above the breakpoint via
`matchMedia`, rather than depending on how an engine treats a closed one,
and only closes on navigation when narrow. Verified by measurement: with
the patch applied the disclosure's own box goes from `210x0` to `210x145`,
matching its content, so no engine has anything left to disagree about.

### Verified in production, August 1, 2026

Deployed at 11:56 EDT. The served bundle rotated from
`app-shell.b94af7d63d1b.js` to `app-shell.98590f71d7af.js`, byte-identical
to a local build of the same source, and contains the fix's own
`min-width: 761px` breakpoint. An authenticated visit confirmed what the
measurements predicted: the nav panel appears down the left above the
cutoff, and collapses into the ☰ menu below it. B0 is closed.

### A false trail worth keeping

The first reproduction reported the nav as "visible" in every browser,
which discarded the correct hypothesis for most of the investigation. The
instrument was wrong: it tested `getBoundingClientRect().width > 0 &&
height > 0`. **A layout box is not paint.** Content skipped by a closed
disclosure keeps its geometry, so the probe answered "visible" for
something invisible on screen, and the user's own report was trusted less
than a faulty measurement. The signal that finally settled it was a
container measuring `210x0` while its child measured `210x306` — a
contradiction that can only mean skipped content.

## Decisions and lessons retained from the work

### Product decisions

- Capture never forces categorization at entry time; triage decides whether a
  thought becomes a task, an Idea, or nothing worth keeping.
- An Idea is not a task without a due date. It has a distinct lifecycle and
  can later promote into a task, carrying its notes with it.
- The task UI is now SPA-only. Capture and account surfaces can remain
  Django-rendered where that is the better fit.
- The agenda is a date-based cross-list view; lists are navigation targets,
  not agenda filters in the persistent navigation.

### Deploy: the "Install docker" task that looked hung

Seen on at least two deploys before August 1, 2026, and again that day:
the playbook appears to stall on **Install docker** for minutes, long
enough that the natural response is to cancel the run — which is what
happened each time, leaving the deploy unfinished.

It was never hung. Read-only inspection of the droplet during the stall
showed the work genuinely in progress and nothing blocking it:

```text
142818   03:08  AnsiballZ_apt.py      <- the apt task, 3 minutes in
143131   02:03  apt-check --human-readable
load average: 2.49
```

The dpkg and apt lock files were unheld. The `unattended-upgrades` process
that normally deserves suspicion was only the `--wait-for-signal` shutdown
daemon, idle for twelve days, and that day's real unattended run had
finished cleanly hours earlier. The cause was the task's own configuration:
`state: latest` plus an unconditional `update_cache` made apt refresh every
index and resolve upgrade candidates for `docker.io` on a small busy
droplet, every single deploy.

Worse than slow, it was unsafe. `state: latest` meant an ordinary Clarice
deploy was willing to upgrade the Docker daemon, and upgrading Docker
restarts it — killing the running container partway through the deploy that
asked for it, at the one moment nobody would look for that as the cause.

Fixed in `fed210b` by using `state: present` with `cache_valid_time: 3600`,
so Docker is installed once and upgrading it becomes a deliberate act rather
than a side effect of shipping a Django change. The task now completes in
about twenty seconds.

If a deploy ever appears to stall on an apt task again, check before
cancelling: `ps -eo pid,etime,cmd | grep AnsiballZ`, the lock files under
`/var/lib/dpkg` and `/var/lib/apt/lists`, and `dpkg --audit`. Cancelling
mid-apt happened to leave the droplet consistent each time here — verified
by `dpkg --audit` and a check for half-configured packages before the rerun
— but that is luck rather than a property to rely on.

### Engineering lessons

- A deployment task is not proven until it has run against production.
- Test against the same database family and relevant version as production.
- Database grants are not ownership; Django migrations require ownership of
  existing tables.
- A clean hard refresh does not prove the deployed frontend image contains
  current source. Inspect the served bundle when UI source and production
  disagree.
- A layout box is not paint. `getBoundingClientRect` returns real geometry
  for content a browser has skipped rendering, so "has a box" is not
  evidence that anyone can see it. When a probe and a person disagree about
  what is on screen, suspect the probe.
- Markup must not depend on how an engine renders a closed `<details>`.
  Engines differ and are still converging; a layout that only works in the
  browser it was built in will look correct to whoever built it.
- Token and session authentication need deliberately different CSRF behavior.
- Every id-taking surface requires direct per-user isolation tests, not just
  trust in a general ownership convention.

## Release conventions

Releases use alphabetic bird names. A release receives three tags after it is
verified in production:

| Tag | Purpose |
| --- | --- |
| `LIVE` | Moving pointer to the exact code currently running. |
| `DEPLOYED-<date>/<HHMM>` | Permanent record of the deployment event. |
| Bird codename | Permanent annotated record of scope and verification. |

Do not reuse a letter: a follow-up production release receives the next bird
name, even if it immediately corrects the last one.
