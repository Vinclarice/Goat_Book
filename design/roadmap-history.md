# Clarice — Roadmap History

Vince · completed work and decision record · archived from `roadmap.md` on
August 1, 2026

## Why this file exists

This preserves the reasoning, deployment record, and lessons behind completed
work without making the active roadmap hard to scan. The active plan is
[`roadmap.md`](roadmap.md).

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

One deliberately unscoped consequence remains: a spawned recurring task does
not serialize its copied subtasks in the mutation response, so they appear
after refresh. This is retained in the active roadmap as a known gap.

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
