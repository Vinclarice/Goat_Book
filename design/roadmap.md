# Clarice — Roadmap

Vince · living document · last resequenced July 31, 2026

## What this is

A living view of what ships next for Clarice and in what order, one level
above the implementation detail. `design/subtasks-plan.md` stays the source
of truth for *how* each feature gets built — the model shape, the
constraint edge cases, the settled decisions. This document says what's
next and why, and it's meant to get stale and get updated, not written once
and framed.

This revision incorporates an actionable resequencing worked out in a
follow-up analysis session the same day: two tracks running at once instead
of one linear list, and one new item — adversarial per-user isolation tests
— pulled forward from the public-readiness bar into the near-term work,
because it's cheap and it's the thing a portfolio reviewer actually pokes
at. Everything else below is carried over from the original draft unchanged.

A later review pass added a second new item, A5 (the database cluster's
open firewall), which A1's live run surfaced and originally left untracked;
tightened A2 and A3 against what the code actually looks like; and loosened
the gate on Track A/Next to A0 alone. Those changes are marked in place.

**A further follow-up session reviewed the shipped subtask and Capture MVP
code directly** — not waiting for a deploy or a checkpoint — and produced
three more specs, which went into `design/`:
`recurring-subtasks-addendum.md` (built since — see Track A/Next),
`capture-api-and-tokens-plan.md`, and
`capture-triage-and-polish-plan.md`. Details under Track A/Next and
Track B below. This document is now the single planning artifact for
Clarice — the parallel copy that lived in the planning conversation's own
document viewer has been retired in its favor.

## Where things stand

The last week closed out two overhauls at once. Clarice went from a single
Django app to an API-backed SPA: a Django Ninja `/api/v1/` skeleton and
OpenAPI-to-TS codegen, a React Router + TanStack Query shell, Tailwind v4
tokens with a shadcn component set, then the Agenda, Lists, Archive,
Preferences, and Task Detail routes migrated one at a time, a final cutover
that removed the dead legacy code, and a pass restyling the Django pages
that didn't move over so nothing still looks like Bootstrap. Separately,
production moved off a bind-mounted SQLite file onto a managed DigitalOcean
Postgres cluster.

Both were infrastructure and platform work — no user-facing task features
shipped in this stretch. `design/subtasks-plan.md`'s Step 2 (the Postgres
move) was the only item from that plan that was actually done; everything
else in it was still ahead. **That is no longer true — see below. The whole
of `subtasks-plan.md` has now shipped.**

**Since this doc was written:** Track A/Now item A0 shipped — CI
(`.github/workflows/ci.yml`) now runs on every push and pull request,
with the Django suite running against a real Postgres service container
instead of SQLite. Merged via [PR #1](https://github.com/Vinclarice/Goat_Book/pull/1)
on July 31, 2026 (`f699b61`).

A1 is now fully done, script (PR #2) plus the actual production cutover,
also July 31, 2026 -- see the A1 entry below for what the live run
actually surfaced (two real bugs, both fixed same-day, and one exposure
left open that is now item A5).

**Then the feature work finally started.** In one pass on July 31, 2026,
five things landed together on `plan-implementation`: A3 (isolation
tests), A4 (the digest cron line), Next items 1 and 2 (the archive/restore
status fix and snooze presets), and the Track B Capture MVP.

**And then the rest of it, the same evening.** Notes, subtasks (backend
and UI), and the persistent side navigation, merged to `main` as `9c4a44d`
with CI green. **`design/subtasks-plan.md` is now fully built** — steps 1
through 7, with step 4 (the detail view) turning out to have been built by
the SPA cutover before this queue was even written. 272 Django tests and
108 frontend tests pass.

**And then, before any of it deployed:** a direct review of the shipped
code (not a scheduled checkpoint) found one real behavioral gap in the
subtask/recurrence interaction, and settled the shape of Capture's triage
model from existing conviction rather than waiting on real usage. Both are
now specs in `design/`, unbuilt. See Track A/Next and Track B below.

### What is left, and it is not all code

- **A5 — the database cluster firewall.** Zero rules, reachable from any
  IP, password-only. The only live production exposure recorded anywhere
  in this document.
- **A2 — the backup restore drill.** Still the unbanked reason the
  Postgres move happened at all.
- **A deploy.** None of the work above is running anywhere. Production is
  still serving the code as it stood before any of this.
- **Three specs to build.** `capture-api-and-tokens-plan.md` and
  `capture-triage-and-polish-plan.md` under Track B -- see below for what
  each contains -- plus `password-reset-plan.md` under Track A/Now (A6),
  triggered by a real lockout-plus-forgotten-password incident rather than
  either track's own planning. `recurring-subtasks-addendum.md` is the one
  of the original three that's now built (migration `0021`, July 31,
  2026) and, like everything else here, undeployed.

The first three need `doctl` or an Ansible run against the live account,
which is why they have outlasted everything that could be done from an
editor. The fourth is ordinary coding work that simply hadn't been scoped
yet when the rest of this document was last touched.

**The deploy is still the one that unblocks the most.** It activates A4's
digest cron, puts the archive/restore fix in front of real data, and —
the part with a date attached — starts Track B's two-week capture clock.
That clock has not started. The mid-to-late August checkpoint was written
assuming it had, so it now resolves later than planned, or on thinner
usage.

---

## Vision — capture, agenda, and review

Where this could head, beyond the plan below: Clarice today is a to-do app
with lists. The direction now under discussion reframes it around three
layers instead of one — a capture inbox, the daily agenda as the app's
centerpiece, and a review cadence sitting above both. None of this is
scheduled. It's recorded here so it survives past the conversation that
produced it, rather than getting reconstructed from scratch later.

**Capture.** The old Notion daily-entry template this reacts to had a
"Catch-All for Rapid Logging" section that lived outside the real lists, so
anything captured there had to be manually retyped elsewhere to become
actionable. The direction decided so far: capture holds anything — a task,
a stray idea, a fleeting thought worth writing down before it's gone — with
zero categorization forced at the moment of writing. Whether something
becomes a task, a note, or neither gets decided later, during triage, not
at capture. Frictionless capture only works if writing something down never
requires a decision first.

What a capture resolves into isn't uniform, either. "Schedule vet
appointment" wants a due date and a clear done/not-done state;
"maybe read a book on product design" wants neither — it's closer to a
GTD-style someday/maybe item than a task. **This is no longer an open
question** — `design/capture-triage-and-polish-plan.md` specs it: one
`Idea` domain with an `exploring`/`reference` status, its own notes and
editing, and an explicit "promote to task" action, decided from direct
usage conviction rather than the Track B checkpoint below. What that spec
itself still defers — how an `exploring` idea ever resurfaces, and how
ideas relate to each other — lives in that document's own **Future**
section (a mind-map-style view, possibly AI-assisted sorting).

**Daily agenda as centerpiece.** The agenda already solves the other half
of the old friction — an incomplete task keeps showing up under overdue or
no-due-date on its own, with nothing to manually carry forward. What's
under discussion is promoting the agenda from one page among several to the
app's home surface: the first thing you see, anchoring both fresh captures
and triage of whatever has piled up in the inbox since the last visit.

**Review cadence.** Whether weekly, monthly, and quarterly planning become
a wider-lens view of the same agenda data, or genuinely separate planning
sessions with their own prompts, is still open — deliberately undecided.
Worth designing once capture and the daily agenda are further along, not
before.

Most of this stays a vision for now, not a milestone — Capture itself has
moved further than the rest (see Track B below), but promoting the agenda
to the home surface and the review cadence remain undesigned.

---

## Public-readiness bar

The actual goal for Clarice: a professional-grade, publicly-deployable
project that doubles as a personal productivity tool and as the premier
piece in a portfolio. "Public" splits into two bars worth keeping distinct,
since they carry very different amounts of work and only one of them is
currently in scope.

**The quality bar — public-ready, not necessarily commercial.**

- Self-service signup with email verification, replacing the current
  manual admin-approval flow. Self-service password recovery used to be
  bundled into this bullet; it's been split out and pulled forward — see
  A6 below, `design/password-reset-plan.md`.
- Per-user data isolation that's been adversarially tested (a real test
  suite that tries to read/edit/delete another user's data by id), not just
  assumed correct from ownership filters. **Pulled forward into Track A/Now
  as item A3 — see below.**
- Rate limiting on signup and capture, not just login.
- A transactional email provider in place of personal Gmail SMTP.
- An account export/deletion flow.
- Basic error monitoring beyond `docker logs`.
- A privacy policy and terms of service.

Password recovery (A6) and isolation tests (A3) are the two pieces of this
bar pulled into Track A/Now; everything else above stays deferred.

This is the bar that matters for a portfolio-grade public deployment, and
it's mostly productization work layered on architecture that's already
sound.

**The business bar — only if this becomes a monetized product.**

- Billing and subscription lifecycle.
- Support operations at real volume.
- Deeper legal (data processing agreements, ToS enforcement).
- Horizontal scaling of the app tier.

Deliberately out of scope until the quality bar above is genuinely met — no
reason to design for a business model that doesn't exist yet.

Neither bar is scheduled work today, beyond A3. This section exists so
"eventually public" has a concrete definition to design toward when it's
time, instead of staying a vague aspiration.

---

## How the work is sequenced

Two tracks ran at once, and both had emptied of code — briefly:

- **Track A** — Now (infra hygiene, A0–A6) → Next (the feature plan).
  Next is closed, and its one follow-up (the recurring-subtasks addendum)
  is now built too; Now has A2, A5, and the new A6 (password reset) left —
  A2 and A5 are ops, A6 is code.
- **Track B** — Capture MVP, built, waiting on a deploy to start its
  clock, with two more specs now queued behind it (the API/token
  foundation, and the triage model).

**That "empty queue" state lasted about a day.** A direct review of the
shipped work found one real bug worth fixing and settled the triage
question the two-week checkpoint was meant to answer — ahead of schedule
and on purpose, not by accident. Three specs went into `design/`:
`recurring-subtasks-addendum.md`, `capture-api-and-tokens-plan.md`, and
`capture-triage-and-polish-plan.md`. **The first is now built**; the two
Capture specs are not. None of them competed for priority in an
interesting way — the subtask fix was small and self-contained, the two
Capture specs are already sequenced against each other (tokens/API before
Android, triage before either), and all three are independent of Track A's
remaining ops work (A2, A5).

The original caution here — don't fill Next with the largest idea from
**Later** just because the queue looks empty — still applies in spirit.
These three didn't come from that impulse; they came from a deliberate
review of what had just shipped. That distinction is the thing worth
preserving, not the empty-queue state itself, which no longer holds.

They don't share code — Capture is an isolated model with no FK into
`List`/`Item` — so they don't block each other technically. They do share
the same developer, so Track B still gets a fixed, small scope rather than
open-ended parallel effort.

---

## Track A — Now: close the infrastructure gaps

The Postgres move solves the easy 80% of a few problems and leaves the rest
half-finished. Four items from the original plan, two pulled forward from
the public-readiness bar (A3, A6), and one surfaced by A1's live run (A5).
All seven are cheap now and get more annoying to retrofit once schema work
(Track A/Next) lands on top.

Order matters at the front: CI goes first, so the DB-user restriction and
the isolation tests both land with automated coverage instead of a manual,
one-time check. After that the order is preference, not dependency — A2,
A4, A5, and A6 are independent of each other and of the feature plan.

**Status:** A0, A1 and A3 are done; A4 is written and waiting on a deploy.
**A2, A5, and A6 are what's left.** A2 and A5 need `doctl` against the
live account rather than code, which is why they've outlasted everything
that could be done from an editor. A6 is ordinary coding work — it just
wasn't scoped until a real lockout-plus-forgotten-password incident
surfaced it.

### A0. Stand up CI with a Postgres service container — done

Shipped July 31, 2026, [PR #1](https://github.com/Vinclarice/Goat_Book/pull/1)
(`f699b61`). There was no CI (confirmed — no `.github/workflows`, no other
CI config anywhere in the repo) and the local suite ran on SQLite while
production ran on Postgres — the exact combination the migration notes
call out as worse than either choice alone.

- `.github/workflows/ci.yml`, two jobs on every push/PR: `django` runs the
  suite against a real Postgres service container (`postgres:18` — see the
  skew note below); `frontend` runs `pnpm test` and `pnpm build`.
- `clarice/settings.py`'s `DEBUG` branch now honors `DJANGO_DATABASE_URL`
  when set, falling back to SQLite unchanged when it isn't — local dev is
  untouched, CI opts into Postgres.
- Verified both on a live Postgres container locally and on the real first
  GitHub Actions run (both jobs green) before merging.
- This is the harness A3 and everything in the Next queue now verify
  against.
- **Version skew found and fixed after the fact.** The workflow originally
  pinned `postgres:17`, carrying the same stale assumption the provisioning
  docs did until A1 found the real cluster running Postgres 18. Nothing
  depended on the difference (`nulls_distinct=False`, the one version-gated
  thing in the plan, needs only 15+), but A0's whole point was to stop
  testing against a database production doesn't run. `ci.yml` now pins
  `postgres:18`; the change is verified by the next CI run on push, not
  before it.

### A1. Restrict the database user — done

The cluster was using the default `doadmin` credential, which can read and
write every database on the cluster, not just Clarice's — confirmed in
`infra/provision-postgres.sh`. Script merged
[PR #2](https://github.com/Vinclarice/Goat_Book/pull/2) (`c6d1071`); the
live cutover ran the same day, `clarice_app` is now the app's production
credential.

- `infra/restrict-database-user.sh` creates a per-database DO user via
  `doctl`, temporarily whitelists the operator's IP on the cluster
  firewall to run SQL against it (removed again in a cleanup trap
  regardless of how the script exits), revokes `CONNECT` on every other
  database, grants schema privileges, and prints a `DJANGO_DATABASE_URL`.
- **The real cluster didn't match the docs**: named `db-pgsql-nyc1-16061`,
  not `clarice-db`; database `Clarice_todo` (mixed case), not `clarice`;
  running Postgres 18, not 17. Caught by a preflight `doctl` check before
  running anything mutating, rather than by a failed run.
- **First real bug found: `GRANT ALL PRIVILEGES` isn't ownership.**
  Existing tables were still owned by `doadmin` (whoever ran the original
  migrations), and Django's `ALTER TABLE` migrations require ownership,
  not just grants. The `accounts.0008_user_theme` migration failed
  mid-deploy with `InsufficientPrivilege: must be owner of table
  accounts_user` — caught cleanly (Django wraps each migration in its own
  transaction, so nothing was left half-applied) but the container was
  already live on the new credential at that point, so anything touching
  `User.theme` was briefly degraded. Fixed with `REASSIGN OWNED BY doadmin
  TO clarice_app`, now a permanent step in the script so a future run
  (e.g. a second project sharing the cluster) doesn't hit the same bug.
- **Second, unrelated bug found in the same incident**: after re-deploying,
  the site itself became unreachable (`connect ... timed out` on 443) —
  not caused by anything above. A DigitalOcean Cloud Firewall attached to
  the droplet, created that day from DO's general preset, allowed only
  port 22. Fixed by adding inbound rules for 80/443
  (`doctl compute firewall add-rules`); confirmed both from outside
  (`curl` returning 200 on `/` and `/admin/login/`, a correct 302 on
  `/dashboard/`) and via clean `docker logs clarice` on the server.
- **Still open, found but not fixed today**: the *database cluster's own*
  firewall (a separate DO resource from the droplet's Cloud Firewall
  above) currently has zero rules — reachable from any IP, password-only.
  Contradicts what `provision-postgres.sh` assumes. Out of scope for what
  A1 asked for — now tracked as **A5** below, rather than left as a note
  inside a finished item where it would quietly disappear.
- Cross-referenced from `infra/provision-postgres.sh`, `MIGRATION.md`, and
  `design/subtasks-plan.md`'s "One cluster, several projects" section.

### A2. Prove the backups actually work

Backups were the strongest reason to move to managed Postgres in the first
place — the plan was to solve them by procurement instead of a hand-rolled
cron job. That's only true if snapshots/PITR are confirmed on and a restore
has actually been tested once. Don't let "we moved to managed Postgres"
quietly stand in for "backups are handled."

- Confirm snapshots/PITR are actually enabled on the cluster, and record
  the retention window — "backups are on" without a retention number
  doesn't answer how far back a bad migration can be undone.
- **Restore the way you'd actually have to, not the convenient way.**
  `design/subtasks-plan.md`'s "One cluster, several projects" section notes
  backups are *cluster-wide*: recovering Clarice means restoring the entire
  cluster to a new one and extracting `Clarice_todo` from it. Test that
  path end to end. A single-database restore would pass while proving
  nothing about the procedure a real incident forces.
- Verify the restored data is intact — row counts per table against the
  live cluster, plus `showmigrations` matching, not just "it connects".
- Add a cheap staleness check: something that surfaces the last successful
  backup's timestamp, so a silently broken backup is detectable without
  running the whole drill again.
- Tear down the scratch cluster afterwards; it bills by the hour.

Done means all five, written down somewhere durable — a restore that
happened once and wasn't recorded is indistinguishable from one that
didn't.

### A3. Adversarial per-user data isolation tests — done

**Shipped July 31, 2026** — `lists/tests/test_isolation.py`, 15 tests, run
as their own named CI step. Isolation held: every one of the eight pairs
already returned 404 to an intruder, so this bought regression protection
rather than a bug fix, which is what the item predicted. Two things worth
recording from the build:

- **The named CI step runs *before* the general suite, not after.** Steps
  are sequential, so the obvious ordering would have meant an isolation
  regression fails the broad step and the named step never executes — the
  unmissable signal, never appearing. Position is the whole point.
- **Positive controls matter more than they look.** Six tests fire the
  identical request against the intruder's *own* object and assert it
  succeeds. Without them the module would stay green if a route were
  deleted, because a missing route 404s exactly like a blocked one.

The original specification follows, kept because the endpoint inventory is
still the checklist to extend when Step 6c lands.

Isolation rested entirely on ownership filters at the query layer
(`get_object_or_404(List, id=list_id, owner=request.user)` in
`lists/api_v1.py:147`, `list__owner=user` filters elsewhere) — never
adversarially tested end-to-end.

- New test module, e.g. `lists/tests/test_isolation.py`. Two authenticated
  users, `owner` (creates data) and `intruder` (tries to reach it).
- **The id-taking surface is eight method/path pairs, not eighteen** — an
  earlier draft of this item overcounted, and this is a checklist someone
  will tick off, so it's worth being exact. In `lists/api_v1.py`: GET,
  PATCH, DELETE `/lists/{list_id}` and GET `/tasks/{item_id}`. In
  `lists/api.py` (legacy): POST `create_item`, POST `reorder_items`, and
  PATCH and DELETE on `item_detail`. `accounts/api_v1.py` contributes
  none — preferences are a singleton resolved from `request.user`, with no
  id in the path. There is likewise no id-addressable tag endpoint; tags
  are set by name through the item PATCH, so "read another user's tag by
  id" isn't a reachable request to write a test for.
- For each: act as `intruder` against `owner`'s object, assert 404 (not
  403 — matches the codebase's existing pattern of not revealing
  existence), and assert nothing was mutated.
- **Cover id-bearing request bodies, not just path ids — that's where the
  next bug will be.** The path-id helpers are uniform and, as far as
  reading them goes, correct today: `_owned_list` filters `owner=`,
  `_owned_item` filters `list__owner=`, and `services.reorder_items`
  requires exact set equality between `ordered_ids` and the list's own
  items before touching anything. So A3's value here is regression
  protection, not discovery. The genuine hole is an id arriving in a
  payload rather than a URL, and Step 6c of `subtasks-plan.md` introduces
  exactly one: `create_item` accepting `parent`, and `item_detail` PATCH
  accepting `parent` for promote/demote. An `intruder` passing one of
  `owner`'s item ids as `parent` is the isolation bug this codebase does
  not have yet.
- **Therefore A3 expires when subtasks land.** Extending this module with
  the cross-user `parent` cases is part of Step 6, in the same PR — not a
  follow-up. Without that, the suite stays green while the newest
  attack surface goes untested, which is worse than not having it.
- Run as its own *step* in the existing `django` job — A0 has landed, so
  the harness is there (`python src/manage.py test
  lists.tests.test_isolation`) — not as its own job. A separate job means a second Postgres service container and a
  second full dependency install for ~20 tests, roughly doubling CI
  wall-clock; a named step that goes red is exactly as unmissable in the
  GitHub UI for none of that cost.
- Out of scope for this pass: self-service signup/password recovery, rate
  limiting, transactional email, export/deletion, monitoring. Real work,
  correctly deferred — isolation tests are the one item worth decoupling
  from the rest of the quality bar because they're cheap and high-signal on
  their own.

**Note for whoever builds `capture-triage-and-polish-plan.md`:** it comes
with its own "Tests to add" section extending this same isolation
discipline to `Idea` and the new Capture triage actions. Same expectation
as A3 set for subtasks — land the isolation coverage in the same change,
not a follow-up.

### A4. Wire up the digest email — written, not yet live

**Scheduled July 31, 2026** in `infra/deploy-playbook.yaml`, as an
`ansible.builtin.cron` task rather than a raw crontab line so the entry is
named and idempotent — redeploying updates it in place instead of
appending a duplicate copy every time.

`send_due_digest` had existed, worked, and been verified with `--dry-run`
for a while, but nothing invoked it, so the digest reached nobody.

**Still owed:** this takes effect on the next deploy and not before, and
the first live run wants checking against real data before it's trusted
unattended. Don't mark this closed until that's happened.

### A5. Close the database cluster's firewall

**New in the review pass — surfaced by A1's live run and originally left as
a note inside A1's own entry, which is where items go to be forgotten.**
The cluster's firewall (a DO resource distinct from the droplet's Cloud
Firewall that A1 also had to fix) currently has zero rules: the production
database accepts connections from any IP, defended by a password alone.
`infra/provision-postgres.sh` assumes otherwise.

This is the only live production exposure recorded anywhere in this
document, and the fix is roughly one `doctl` invocation, so it's tracked
here rather than deferred to the public-readiness bar.

- Restrict inbound access to the droplet (by droplet resource, not by IP —
  the droplet's address shouldn't become a second thing to keep in sync).
- Keep A1's pattern of temporarily whitelisting the operator's IP for
  manual SQL and removing it again, rather than leaving a standing rule.
- Re-check `provision-postgres.sh` so the script and reality agree
  afterwards — the docs-vs-reality drift A1 ran into is the same failure
  mode. Partly done already: its `ENGINE_VERSION` default was 17 against a
  cluster running 18, now corrected (and `MIGRATION.md` with it). What's
  left is the firewall claim — the script and `MIGRATION.md` both state the
  cluster is restricted to the droplet, which is exactly what this item
  exists to make true.
- Verify from outside: the app still connects, an unlisted host doesn't.

### A6. Self-service password reset

**New from a real incident, not a review pass** — someone locked out of
their account by too many failed attempts (see `AXES_FAILURE_LIMIT`
above) also couldn't remember their password, and there was no way to
reset it: no "forgot password" link on the login page, and none on the
admin login either, because the admin's own login template only shows
that link when the URL name `admin_password_reset` actually resolves, and
it didn't.

`design/password-reset-plan.md` specs the fix: Django's standard
email-based reset flow (the `User` model's email is already unique and
required, so no new field is needed), styled to match the existing
card-based login/lockout pages, wired into `accounts/urls.py`, with a
`ClearLockoutPasswordResetConfirmView` that also clears any axes lockout
for that username on successful completion — otherwise setting a new
password wouldn't actually get someone back in until the hour-long
cooloff expired. It reuses the SMTP/console email setup already in
`clarice/settings.py` for signup and lockout notifications; nothing new
to configure there.

- Register `admin_password_reset` as a URL name in `clarice/urls.py`,
  *before* the `admin/` include — Django's admin login template silently
  omits the "Forgot your password?" link if the name doesn't resolve, and
  the ordering matters because `admin.site.urls` would otherwise try (and
  fail) to match `password_reset/` itself first.
- Add a "Forgot your password?" link to
  `accounts/templates/accounts/login.html`.
- Add a reset link to `accounts/templates/accounts/lockout.html` too —
  that page is exactly where someone in this situation lands, and axes
  doesn't block the reset flow itself, only the login view.
- Not built yet.

---

## Track B — Capture MVP — built, clock starts on deploy

**Shipped July 31, 2026** as a Django-only `capture` app: model, entry
form, Inbox, and one resolve action, with an Inbox link in the nav. No
API and no SPA route — an explicit scope decision, since the point of
this pass is to generate usage evidence, not to be architecturally
consistent with the rest of the app.

Two departures from the sketch below, both deliberate:

- **The model carries an owner and a resolved timestamp**, not just text
  and a timestamp. Clarice has two users, so an owner is not optional, and
  "everything not yet resolved" needs something to test against.
- **There is exactly one triage affordance**, a resolve action that takes
  a capture out of the Inbox without recording what became of it. Anything
  richer would be inventing the triage model this checkpoint exists to
  inform. Promote-to-task, the Idea/Someday domain and agenda integration
  all stayed out.

Capture is unrated — the quality bar lists rate limiting on signup and
capture, and that's still deferred. Fine at two users; worth remembering
before this is ever public.

**Since then:** the persistent side nav (Next item 5) put Inbox in the
nav on every SPA page with its unresolved count, which removes the one
thing most likely to have made this checkpoint fail quietly — an inbox
reachable only by typing the URL collects no evidence.

The original scope sketch, for the record:

- A `Capture` model that's just text and a timestamp.
- One entry point built for speed rather than completeness — no list, no
  type, no required fields beyond the text itself.
- An Inbox view listing everything not yet resolved into anything else.

**Deliberately out of scope for now:** the Idea/Someday domain, agenda
integration, and any triage workflow. No upfront design pass was written
for those — the plan is to use plain capture for real, for a couple of
weeks, and let what actually gets typed into it settle whether the
task/idea/note split holds up, rather than designing that shape from
speculation.

**Checkpoint, not open-ended — and the clock has not started yet.** The
MVP is built but not deployed; the two weeks of real use begin when it's
live on the production droplet, not when it merged. Target stays
mid-to-late August 2026.

**What the checkpoint validates changed.** It was meant to be the source
of the triage design — use it for real, then design the task/idea/note
split from what actually got captured. Instead, the triage model got
decided directly (see below), from existing conviction about real usage
rather than waiting out the two weeks. That's a legitimate call to make,
but it means the checkpoint's job now is to confirm the decided model
holds up against real use, not to originate it. If two weeks of real
captures disagree with the task/idea/reference/discard split, that's
still a real signal worth revisiting — the checkpoint just isn't the only
source of truth for that shape anymore. This checkpoint is what stops
Track B from quietly becoming a second, open-ended feature queue running
alongside Track A.

### Two more specs queued behind this, one of them jumping the checkpoint on purpose

**`design/capture-api-and-tokens-plan.md`** lays the two prerequisites for
a phone-based capture client: a `PersonalAccessToken` model (hashed
storage, shown once, revoked by deletion) and a create-only
`POST /api/v1/capture` endpoint, using a Django Ninja `HttpBearer` auth
class that runs alongside the existing session auth rather than replacing
it. Explicitly sequenced *before* any Android code, with the zero-code
home-screen-shortcut experiment recommended first, to find out whether
that alone solves the actual friction before writing a single line of
Kotlin.

**`design/capture-triage-and-polish-plan.md`** is the bigger departure
from plan: it designs the triage model — promote to a task, mark an idea
`exploring` or `reference`, or discard outright — from direct usage
conviction rather than waiting out the checkpoint above. The spec adds a
lightweight `Idea` model (its own `notes`, anytime editing while not yet
promoted, and a `promoted_task` FK mirroring how `Capture` already tracks
what it became), makes idea deletion a hard, immediate, non-undoable
action distinct from Capture's soft discard, and moves basic substring
search on the Ideas page into this pass rather than deferring it, since a
`reference` archive nobody can search defeats its own purpose. What it
still doesn't solve — how an `exploring` idea ever resurfaces without you
remembering to check, and how ideas relate to each other — is named
explicitly in the spec's own **Future** section (a mind-map-style view,
possibly AI-assisted sorting) rather than guessed at now.

Neither spec is built yet.

---

## Track A — Next: closed, with one follow-up queued

**Everything in this queue has shipped**, all of it on July 31, 2026, and
the queue is kept here as a record rather than a plan. `main` is at
`9c4a44d` with CI green. What each item turned into:

| Step | Outcome |
| --- | --- |
| 1. Archive/restore status | Migration `0018`. Restore returns a task to whichever status it held before archiving — the prerequisite cascade restore needed. |
| 2. Postgres | Done earlier, and the reason step 6's constraint is expressible at all. |
| 3. Snooze presets | Tomorrow / This weekend / Next week / Clear, one menu replacing the Tomorrow-or-Schedule split. |
| 4. Task detail view | Already built by the SPA cutover; discovered when this queue reached it. |
| 5. Notes | Migration `0019`. Plain text, no Markdown, saved on blur. |
| 6. Subtasks | Migration `0020`. Self-FK, one level, `nulls_distinct=False`, three cascades, `archive_group`, and the nested UI. |
| 7. Side navigation | One nav across every SPA page; mocked first, in `design/side-nav-mockup.html`. |

Two things this queue taught that were not in the plan:

- **Step 4 had already been built**, by the cutover, before the queue was
  written. Nobody noticed until something went to implement it. Worth
  remembering that a plan written alongside fast-moving work can describe
  as pending something that already exists.
- **A stacked branch merges its base with it.** Notes, subtasks and the
  side nav ended up in one merge because each branch was cut from the
  previous one rather than from `main`. The result is correct and the
  history is readable, but the individual pieces were never merged
  separately, so none of them was ever `main` on its own.

**One follow-up, now built.** A direct review of the shipped subtask work
found a real gap: a subtask completed *before* its recurring parent
silently never reappeared in the next occurrence, because `complete_item`
reused the same "still-active children" query both to decide what to
cascade-complete and what to clone forward into the next occurrence — two
different questions that had been sharing one answer.
`design/recurring-subtasks-addendum.md` speced the fix and it shipped
July 31, 2026: migration `0021_item_always_recurs`, a per-subtask
`always_recurs` boolean (default `true`), and a `_children_to_carry_forward`
query kept deliberately separate from `_lock_open_children`.

Three things worth recording from the build:

- **The bug was confirmed before it was fixed, not just reasoned about.**
  The new test was run against the old one-query behaviour first and
  failed exactly as predicted (the early-completed subtask missing from
  the spawned occurrence), so the suite is known to catch a regression
  rather than merely assumed to.
- **The carry-forward query only runs when the task actually recurs.**
  The spec put it unconditionally before the cascade; guarding it on
  `is_recurring` keeps the ordering the spec cared about while sparing
  every non-recurring completion an extra query.
- **The spec's last test is vacuous, and is kept anyway.** "The clone
  keeps its source's `always_recurs`" can only ever observe `True`,
  because the carry-forward query filters on exactly that field. It's
  retained as a guard for the day that filter widens, with a comment
  saying so rather than leaving it looking like it proves more than it does.

The UI landed narrower than "a checkbox at creation": both the creation
checkbox and the per-subtask toggle only appear once the parent actually
repeats, since on a task that doesn't, "comes back next time" has nothing
to mean. The flag still defaults to `true` underneath, so nothing is lost
by not showing it.

The original queue, for the record:

**Done and slid out of this queue, July 31, 2026:** the archive/restore
status fix (migration `0018`; restore now returns a task to whichever
status it held before archiving, which is what cascade restore needs) and
snooze presets (Tomorrow / This weekend / Next week / Clear, replacing the
single Tomorrow-or-Schedule button).

One loose end from the snooze work: `snooze_presets` in `lists/agenda.py`
has no server-side caller. The Django agenda redirects to the SPA after
the cutover, so the presets are computed client-side and the Python copy
is a reference implementation only its own tests exercise. Either serve
them from the agenda payload so there's one source of truth, or delete the
Python side — worth deciding when something next touches `agenda.py`,
not before.

**Also slid out: the task detail view (was item 3).** It already exists —
`frontend/src/app/routes/TaskDetailRoute.tsx` shows text, list, due date,
tags and recurrence, everything the step asked for except notes and
subtasks, which don't exist yet. It arrived during the SPA cutover, before
this queue was written, and nobody noticed it had pre-empted a planned
item. Its other half — "a full page for the no-JS path" — is not deferred
but **impossible**; see the no-JS note below.

**The no-JS path is gone, and three steps below still assume it.** Every
task-facing Django view is now a redirect into the SPA — `dashboard`,
`archive`, `view_list` and `edit_item` all bounce to `/app/...`, leaving
`new_list` (a POST handler) as the only real rendering view in
`lists/views.py`. That was a deliberate consequence of the cutover, but
the feature plan predates it and still designs around a fallback surface
that isn't there. `design/subtasks-plan.md` steps 5, 6d and 7 have been
corrected. Worth stating plainly here too, since "works without JS" was a
real principle for this project and is now simply not one — for lists and
tasks, at least. The Capture MVP is server-rendered, so Django templates
aren't dead, they just aren't the task UI any more.

3. ~~**Notes.**~~ Shipped. A plain-text field on the detail view —
   deliberately not Markdown, which would add a renderer and an XSS surface
   for little gain at two users. It needed one thing the plan didn't
   mention: the field had to reach `serialize_item` and the v1 schema,
   because a Django template would have read the model directly but the SPA
   can only show what it can fetch.
4. ~~**Subtasks.**~~ Shipped. The large one. A self-referencing FK on `Item`, one level
   of nesting only, cascading complete/archive/restore with proper undo,
   sibling-scoped duplicate and position logic, API changes to
   `create_item`, `item_detail`, and `reorder_items`, and UI work across the
   list page, agenda, and detail view. `design/subtasks-plan.md` §6 has the
   full shape, including the Postgres-specific constraint that's now
   available since Step 2 is done and A0's CI runs against Postgres. Ships
   with the cross-user `parent` cases added to A3's isolation module — see
   A3 for why that belongs in this PR and not a follow-up.
5. ~~**Persistent side navigation.**~~ Shipped, mocked first as the plan
   asked (`design/side-nav-mockup.html`). The mock forced a decision the
   plan never addressed: the agenda's sidebar was doing two jobs, since
   clicking a list there *filtered* rather than navigated, and "filter the
   agenda" means nothing on the archive page. So the nav navigates only,
   and list filtering moved to chips in the agenda header. The right rail
   is what yields at medium width, not the nav — and because the nav takes
   210px, it now stacks at 1180px rather than 900px, which is exactly the
   three-column crowding this step predicted.

---

## Later — on the radar, not scheduled

Nothing here is planned yet. Kept visible so none of it gets re-litigated
from scratch when it does become relevant.

### What the Postgres move specifically unlocked

| Idea | Why it needs Postgres |
| --- | --- |
| Ranked full-text search | Native `SearchVector`/`SearchRank` + GIN index; `pg_trgm` for typo tolerance. The single biggest win on this list. |
| Real-time sync for shared lists | `LISTEN`/`NOTIFY` as a push channel, no Redis needed — pairs with SSE. |
| Conflict handling on shared lists | `select_for_update()` becomes real, plus `skip_locked`/`nowait` — a prerequisite for sharing at all. |
| Per-user timezones | `AT TIME ZONE` makes "due today" a per-user answer instead of one global one. |
| Audit log / general undo | `JSONB` with GIN indexing for change payloads. |
| Time blocking | `tstzrange` + `ExclusionConstraint` to stop overlapping blocks at the database level. |

### Rest of the public-readiness quality bar

Self-service signup/email verification, rate limiting on signup and
capture, a transactional email provider, account export/deletion, error
monitoring beyond `docker logs`, privacy policy and ToS. Isolation tests
(A3) and password recovery (A6) are the two pieces of this bar pulled into
Track A/Now; the rest waits for a deliberate decision to pursue public
deployment.

### Business bar

Billing/subscription lifecycle, support operations at volume, deeper legal
(DPAs, ToS enforcement), horizontal scaling. Out of scope until the quality
bar above is genuinely met.

### Vision layer beyond Capture MVP

Promoting the agenda to the app's home surface, and the review cadence
(weekly/monthly/quarterly) — both still undesigned. The Idea domain itself
(exploring/reference, with its own promote-to-task action) is no longer on
this list: it's speced in `design/capture-triage-and-polish-plan.md`,
decided from direct usage conviction rather than waiting on the Track B
checkpoint. What that spec itself defers — how an exploring idea ever
resurfaces, and how ideas relate to each other — is tracked in that
document's own **Future** section (a mind-map-style view, possibly
AI-assisted sorting).

---

## Explicitly not planned

Decisions already made, kept here so they don't get re-opened by accident:

- Markdown rendering in notes — plain text only.
- Subtasks nested more than one level deep.
- Auto-completing a parent task when every subtask under it is done — it
  shows the count and waits for an explicit tick.
- Recurrence on subtasks — recurrence stays a parent-task-only feature.

---

## Keeping this current

This is now the single planning document for Clarice — the parallel copy
that lived in the planning conversation's own document viewer has been
retired in its favor, so there's exactly one place this history lives.

Update "Where things stand" after each Now item ships, and slide finished
Next items out as they land. When the Track B checkpoint resolves
(mid/late August 2026, once deployed), replace its entry above with either
a confirmation that the shipped triage design holds up, or a scope change
if real usage disagrees with it — don't leave it silently open-ended. When
something from Later gets a real reason to happen, it graduates into Next
with its own one-liner — that's the whole maintenance loop.

**The three specs still queued in `design/` — the capture/token plan, the
triage plan, and the password-reset plan — are the next coding tasks**
(the subtask addendum, the fourth of the original set, is built), not a
reason to pick something new from Later or the public-readiness bar. Once
those land, the first three questions are: has it been deployed; did A2
and A5 get done; and does the shipped triage model actually hold up
against real use, now that it's been decided ahead of the original
checkpoint. Only after those does it make sense to graduate anything from
Later. The caution underneath the old "empty queue" framing still applies
in spirit — don't reach for the largest remaining idea out of momentum —
it's just that the queue isn't empty right now.
