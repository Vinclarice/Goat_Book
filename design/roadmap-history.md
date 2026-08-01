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
- Added persistent SPA navigation in source. Its absence in production is
  now Bittern B0.
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

### Engineering lessons

- A deployment task is not proven until it has run against production.
- Test against the same database family and relevant version as production.
- Database grants are not ownership; Django migrations require ownership of
  existing tables.
- A clean hard refresh does not prove the deployed frontend image contains
  current source. Inspect the served bundle when UI source and production
  disagree.
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
