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
`recurring-subtasks-addendum.md`, `capture-api-and-tokens-plan.md`, and
`capture-triage-and-polish-plan.md` — all three built since. Details
under Track A/Next and
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
model from existing conviction rather than waiting on real usage. Both
became specs in `design/`; the subtask gap has since been built, the
triage model has not. See Track A/Next and Track B below.

### What is left, and it is not all code

- ~~**A5 — the database cluster firewall.**~~ Closed August 1, 2026: one
  droplet rule, verified from both sides. It was the only live production
  exposure recorded in this document, and it no longer is.
- ~~**A2 — the backup restore drill.**~~ Run and passed August 1, 2026;
  see `MIGRATION.md`. The Postgres move's central promise is now banked
  rather than assumed.
- ~~**A deploy.**~~ **Done — `albatross`, 2026-07-31 22:24 EDT.** Seven
  migrations (53 → 60), every new table and column in place, and not one
  row of existing data changed. `clarice_app` rotated in the same pass.
  The gap this bullet used to measure — a production database with no
  `capture_*` tables — is closed.
- **No specs left to build.** All four written in this stretch are done:
  `recurring-subtasks-addendum.md` (migration `0021`),
  `password-reset-plan.md` (A6, speced and shipped the same day after a
  real lockout-plus-forgotten-password incident),
  `capture-api-and-tokens-plan.md` (tokens plus `POST /api/v1/capture`),
  and `capture-triage-and-polish-plan.md` (migration `capture.0002` — the
  `Idea` domain and the four triage outcomes). All of it shipped live in
  `albatross`, 2026-07-31 22:24 EDT.
- **One known gap, small and unspeced.** A spawned recurring occurrence
  renders childless until the page is reloaded — the server creates the
  fresh subtask copies in the same transaction but doesn't serialize them.
  Surfaced by the orphaned-subtask fix and deliberately left there, since
  it wants a decision about the response shape rather than a patch. See
  Track A/Next.

A2, A5 and the deploy all need `doctl` or an Ansible run against the live
account, which is why they have outlasted everything that could be done
from an editor. The two remaining specs are ordinary coding work.

**The deploy has happened, and everything it gated is now live.** A4's
digest cron is installed and its first run was checked against real data
(it correctly found one task due today). The archive/restore fix is in
front of real data. **Track B's two-week usage checkpoint has been
dropped as a gate** — the triage model already shipped from direct
conviction rather than from that checkpoint, and there is no reason to
hold the next release back waiting on a calendar date. Real usage still
informs the design; it just does not block anything anymore. See Track B
below.

What the deploy itself taught, since both were invisible until a real run:

- **A playbook task that has never executed is not a working task.** A4's
  cron line was written weeks ago and looked fine; it set `user: root`
  with no `become`, so it would have failed on `crontab -u root` — and it
  sat immediately after the migration step, the worst place to stop.
  Fixed in `8ec93c8` before the successful run.
- **A hung SSH control socket looks exactly like a slow apt install.**
  Sixteen minutes of apparent progress on "Install docker" was a wedged
  multiplexed connection: no apt process on the server, no build locally,
  nothing happening at either end. `ControlMaster=no` plus
  `ServerAliveInterval` made the re-run proceed immediately, and the image
  then built in under ninety seconds. Worth reaching for that combination
  before believing a deploy is merely slow.

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
bar pulled into Track A/Now, and both are now built; everything else above
stays deferred.

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
  is now built too; A6 (password reset) came in and shipped the same day,
  so Now is back to A2 and A5, both ops rather than code.
- **Track B** — Capture MVP, built, waiting on a deploy to start its
  clock. Of the two specs queued behind it, the API/token foundation is
  built; the triage model is what's left.

**That "empty queue" state lasted about a day.** A direct review of the
shipped work found one real bug worth fixing and settled the triage
question the two-week checkpoint was meant to answer — ahead of schedule
and on purpose, not by accident. Three specs went into `design/`:
`recurring-subtasks-addendum.md`, `capture-api-and-tokens-plan.md`, and
`capture-triage-and-polish-plan.md`. **All three are now built.** None of
them competed for priority in an interesting way — the subtask fix was small and self-contained, the two Capture specs
were already sequenced against each other (tokens/API before Android,
triage before either), and all three were independent of Track A's
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

**Bittern adds four more tracks, C through D through F, once `albatross`
was actually live and its scope got talked through.** Same discipline as
above: each one stays independently small rather than one open-ended
Bittern queue. See the `## Bittern` section below, after Track A/Next, for
what's in each.

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

**Status: Track A/Now is closed, all seven of it.** A0 through A6 are done
as of July 31, 2026 — A2 and A5, the two that needed `doctl` against the
live account and had outlasted everything doable from an editor, went in
one pass, and A4 came live with the `albatross` deploy that evening along
with the `clarice_app` rotation. Nothing in this track is waiting on
anything.

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

### A2. Prove the backups actually work — done

**Drill run August 1, 2026. It passed.** The whole cluster was restored
into a scratch clone from the 2026-07-31 06:56 UTC backup, and all 18
tables matched the live cluster exactly (`lists_item` 24, `lists_list` 17,
`accounts_user` 3, `django_migrations` 53, Postgres 18.4). Clone torn down
afterwards; the procedure and the result are written up in `MIGRATION.md`
under "Restore drill", because a restore that happened once and wasn't
recorded is indistinguishable from one that didn't.

All five sub-items below are closed:

- Backups confirmed on, cadence roughly daily (observed 07-29 22:59,
  07-30 10:59, 07-31 06:56 UTC), retention 7 days on this plan. That's the
  real answer to how far back a bad migration can be undone: a week.
- Restored the awkward, cluster-wide way, which is the only way there is.
- Verified by per-table row counts and `django_migrations` against live,
  not by "it connects".
- Staleness check added: `infra/check-backup-freshness.sh`, exit-code
  driven so cron can run it unattended. Verified on all three paths —
  fresh, stale, and no-such-cluster.
- Scratch cluster destroyed; `doctl databases list` shows only production.

Two things the drill taught that weren't in the plan:

- **A restore inherits the source's trusted sources.** The clone came up
  already carrying A5's droplet rule, so the firewall fix survives a
  recovery rather than needing to be redone during an incident. A cluster
  created from scratch still has none, which is the hole A5 existed to
  close.
- **The restored cluster's default database is `defaultdb`.** The URI
  `doctl databases connection` prints points there, not at `Clarice_todo`.
  Connect to the wrong one mid-incident and the restore looks empty.

The original specification follows.

### A2 (original). Prove the backups actually work

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

**The triage build honoured this too.** `capture-triage-and-polish-plan.md`
came with its own "Tests to add" section extending this discipline to
`Idea` and the Capture triage actions, and the coverage landed in the same
change rather than a follow-up — an intruder is refused on all nine new
id-addressable routes, including the two that take a list id in a POST
body rather than a path. Those tests live in `capture/tests/` rather than
here, since every route is capture-owned.

### A4. Wire up the digest email — done

**Live since the `albatross` deploy, 2026-07-31.** The cron is installed
and the first run was checked against real data rather than trusted
unattended, as this entry insisted: `send_due_digest --dry-run` in the
production container produced a correct digest for the real user, naming
one task genuinely due today. It fires at 07:00 daily.

The task itself needed a fix first — it wrote root's crontab without
`become`, so it had never been able to work. See the deploy notes under
"Where things stand".

The original entry follows.

### A4 (original). Wire up the digest email — written, not yet live

**Scheduled July 31, 2026** in `infra/deploy-playbook.yaml`, as an
`ansible.builtin.cron` task rather than a raw crontab line so the entry is
named and idempotent — redeploying updates it in place instead of
appending a duplicate copy every time.

`send_due_digest` had existed, worked, and been verified with `--dry-run`
for a while, but nothing invoked it, so the digest reached nobody.

**Still owed:** this takes effect on the next deploy and not before, and
the first live run wants checking against real data before it's trusted
unattended. Don't mark this closed until that's happened.

### A5. Close the database cluster's firewall — done

**Closed August 1, 2026.** The cluster had zero trusted-source rules,
confirmed by `doctl databases firewalls list` returning nothing but a
header. It now has exactly one, by droplet resource
(`--rule droplet:585969543`) rather than by IP, so the droplet's address
never becomes a second thing to keep in sync.

Verified both directions, because only one of them is reassuring on its
own:

- The app still reaches the database — `/` returns 200 repeatedly and
  `/dashboard/` still 302s for an anonymous visitor.
- An unlisted host cannot open the port at all: `Test-NetConnection` to
  25060 from the operator's machine reports `TcpTestSucceeded: False`,
  where minutes earlier it answered anyone on the internet.

No operator-IP rule was left behind. The A2 drill needed live row counts
and read them through the droplet over SSH instead of reopening the
cluster, which is strictly better than A1's temporary-whitelist pattern
and is what `MIGRATION.md`'s drill procedure now recommends.

`provision-postgres.sh` needed no correction: line 82 already appends
exactly this rule. The live cluster simply wasn't created by the script —
the same reason A1 found its name and database didn't match the docs — so
it never got one. Script and reality now agree.

**One thing this surfaced, since it's the kind of note that otherwise
disappears:** while gathering cluster metadata for A2, a `doctl ... --output
json` call printed the `doadmin` and `clarice_app` passwords into a session
transcript. `doadmin` was rotated immediately (nothing uses it since A1
moved the app to `clarice_app`, and the app was verified still serving 200s
afterwards). **`clarice_app` was rotated too, right after the `albatross`
deploy** — reset, new URL written to the droplet's `~/.db-connection-url`,
and the container recreated in place with its other eight environment
variables copied verbatim off the running one, so the outage was seconds
rather than the minutes a second playbook run would have cost. Verified by
connecting as `clarice_app` and reading 24 items back. The old URL backup
was shredded afterwards, since it held the very password being retired.

Both credentials are now clean. Throughout, the exposure was contained by
the firewall above — a fair illustration of why defence in depth is worth
the hour it took.

The original specification follows.

### A5 (original). Close the database cluster's firewall

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

### A6. Self-service password reset — done

**Shipped July 31, 2026**, the same day it was speced. All four reset
views, six templates, the `admin_password_reset` redirect, and both entry
points; 13 new tests. Two things worth recording:

- **A live smoke test found the one bug the tests couldn't.** Three
  multi-line `{# #}` template comments were rendering as visible page
  text — Django's `{# #}` is single-line only, and every assertion in the
  suite was checking for copy that was still there either way. Now guarded
  by a test asserting no page renders raw template syntax, which is the
  general form of the mistake rather than the specific one.
- **axes answers a lockout with 429, not 403** — worth knowing before
  writing anything that asserts on that response.

The original entry follows.

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

---

## Track B — Capture MVP — built and deployed, no checkpoint gate

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

**No longer a scheduled gate.** The MVP deployed with `albatross` on
July 31, 2026, and the triage model
(`design/capture-triage-and-polish-plan.md`) shipped the same day from
direct conviction rather than from waiting on usage data. The original
plan held further Capture work behind a two-week real-use checkpoint
(target: mid-to-late August); that gate is dropped, and Bittern is not
waiting on it. Real usage is still worth watching informally, and if it
disagrees with the shipped task/idea/reference/discard split, that is
still a real signal to revisit — it just does not have a calendar
deadline attached anymore.

**What the checkpoint validates changed.** It was meant to be the source
of the triage design — use it for real, then design the task/idea/note
split from what actually got captured. Instead, the triage model got
decided directly (see below), from existing conviction about real usage
rather than waiting out the two weeks. That's a legitimate call to make,
but it means the checkpoint's job now is to confirm the decided model
holds up against real use, not to originate it. If two weeks of real
captures disagree with the task/idea/reference/discard split, that's
still a real signal worth revisiting — it just is not gated behind a
calendar date anymore. What keeps Track B from becoming an open-ended
queue is no longer a fixed checkpoint but keeping each release's scope
explicit, the same discipline Track A already runs on.

### Two more specs queued behind this — one built, one still to go

**`design/capture-api-and-tokens-plan.md` — built July 31, 2026.** The two
prerequisites for a phone-based capture client: a `PersonalAccessToken`
model (migration `accounts.0009` — hashed storage, shown once, revoked by
deletion), a create-only `POST /api/v1/capture`, and the self-service
token page at `/accounts/tokens/`, linked from Preferences. Verified end
to end with curl: a token created in the browser posts a capture with no
cookie anywhere, and stops working the moment it's revoked.

Two things worth recording:

- **A real bug that only curl could see.** Ninja's `SessionAuth` runs its
  CSRF check inside `_get_key`, *before* looking for a cookie — so a
  client whose token was revoked or mistyped fell through to session auth
  and got `403 CSRF check Failed` instead of `401`. That is exactly the
  "silent fallback to session auth" the spec said not to have, and the
  Django test suite could not see it, because the test client disables
  CSRF enforcement by default. `accounts.auth.SessionAuthIfLoggedIn`
  declines when there's no authenticated session rather than raising CSRF
  at someone who never had one; the API tests now run with
  `enforce_csrf_checks=True` in both directions. Second time in two
  features that a live run found what a green suite didn't.
- **`TokenAuth` went in `accounts/`, not `capture/`** as the spec
  sketched. It resolves a token to its owner and knows nothing about
  captures; capture is just the first endpoint to want one.

**Still ahead, and the actual next step:** the zero-code home-screen
shortcut experiment the spec sequences before any Android code. The point
of it is to find out whether a shortcut alone solves the friction — which
would make the case for a native app weaker, not stronger. Worth knowing
before writing any Kotlin.

**`design/capture-triage-and-polish-plan.md` — built July 31, 2026.**
Migration `capture.0002`: the `Idea` model, `Capture.resolution` and the
two lineage FKs, the four triage outcomes with undo, the Ideas page
(filter, search over text and notes, inline editing, promote, hard
delete), and the polish items — capture editing, inbox search, and an
oldest-waiting signal. Ideas went into both navs, because the Capture MVP
already taught that a page reachable only by URL collects nothing.

Two things worth recording:

- **The multi-line `{# #}` bug came back**, on the Ideas page. The guard
  written when A6 hit it swept the pages that had already broken, not the
  ones nobody had written yet — so it was silent, and a live page caught
  it again. Replaced with a static sweep of every template file in the
  project (`lists/tests/test_base_template.py`), verified by planting an
  offender and watching it fail. A scoped guard against a general mistake
  is barely a guard.
- **Undo is safe precisely because it's brief.** It deletes whatever the
  resolution created, which is only sound while nothing else can have
  referenced the new row — so the offer lives for exactly one page load,
  popped from the session, rather than sitting on a resolved capture
  indefinitely.

The spec's own design, for the record: it designs the triage model — promote to a task, mark an idea
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

Both are now built. What neither solves — how an `exploring` idea
resurfaces on its own, and how ideas relate to each other — stays in the
triage spec's **Future** section, undesigned on purpose.

---

## Track A — Next: closed, with two follow-ups built

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

**A second follow-up, also built: the orphaned subtask.** The same query
that hid the carry-forward bug hid a second one on the way out. A subtask
completed before its recurring parent was left at `completed` under a
parent that had just archived itself, because `complete_item`'s cascade
asked for children that were still *active*. `/api/v1/lists/{id}` drops
archived items from the payload, so the parent vanished and
`TaskWorkspace`'s `rows()` — which promotes a child whose parent isn't on
screen to the top level rather than losing it — drew the leftover subtask
as a root task. Confirmed live on July 31, 2026 before it was fixed.

The rule that settles it was already written down, just not applied here:
`archive_item` has always taken *every* non-archived child with it, on the
grounds that an archived parent must not leave live children behind. A
recurring completion archives a parent too, so it now obeys the same rule
through the same query (`_lock_live_children`, shared by both).

What made this more than a filter change is that one query was answering
two questions again, exactly as before:

- **What the cascade must sweep** is now "every child not already
  archived", because the orphan is what that prevents.
- **What an undo reopens** stays "the children that were active", because
  reopening a child finished before its parent would silently un-complete
  work nobody undid. That set is still what `_cascaded` carries on the
  completing path.

The two only diverge when the parent archives, and on that path undo is
`restore_item`, which reads each child's own `completed_at` to decide
where it goes back to rather than reopening the set wholesale — the
pattern migration `0018` established. So the early-completed child keeps
its real completion time through the archive instead of being stamped
with the parent's, which is the whole reason restore can tell the two
kinds of child apart afterwards.

The client had to change too, or the fix was invisible in the session that
triggered it: the server had been returning `cascaded` since the subtask
work and nothing consumed it, so a completed parent's children sat in
local state at their old status until a reload. Both workspaces now fold
it in. That also fixed a quieter version of the same staleness on the
agenda, where a cascaded child stayed in the open list.

**Known gap, deliberately not fixed here:** the spawned next occurrence
comes back without the fresh copies of its subtasks, which the server
creates in the same transaction but doesn't serialize. So a recurring
parent with subtasks shows up childless until the page is reloaded. It's
a missing-children bug rather than the orphan one, wants its own decision
about the response shape, and is noted at the call site in
`TaskWorkspace.changeStatus`.

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

## Bittern — scoping the next release

**Not started. Scoping only, as of August 1, 2026.** Everything below is
new work identified after `albatross` shipped, split into four tracks the
same way Track A and Track B ran side by side — each one independently
small, so Bittern doesn't become the open-ended queue the empty-queue
caution above kept warning against. List sharing (real-time sync,
conflict handling) is explicitly held off for now; see `Later` below.

### Track C — Navigation & UI

**C0. The persistent side nav isn't rendering in production, and a hard
refresh didn't fix it.** `frontend/src/app/main.tsx` correctly wraps
`/agenda` (and every other SPA route) in `AppLayout`, which renders
`SideNav` — Inbox, Ideas, Archive, Lists, Preferences, and Settings are
all there in the source on `main`. A live screenshot taken after the
`albatross` deploy shows none of it, and a real hard refresh (not just a
stale tab) didn't surface it either, which rules out ordinary browser
caching. The likely cause is the production image itself: the Docker
frontend build stage (`pnpm build`) may not have actually re-run with the
current source, or a build-cache layer reused an older `frontend/`
checkout. This needs droplet access to diagnose properly — confirm what
JS bundle the container is actually serving, force a clean rebuild
(`docker build --no-cache`), and verify by checking that the served
bundle includes the Inbox/Ideas links — before anything else in this
track is worth touching. Until it's fixed, Ideas and Inbox are still
reachable directly at `/capture/ideas/` and `/capture/`, which are plain
Django pages independent of the broken bundle.

**C1. No logout anywhere in the SPA.** Confirmed by reading
`SideNav.tsx` and `PreferencesRoute.tsx` — neither has one. The only
working logout is a POST form in `base.html`, the legacy Django template
the SPA cutover left behind. Small, concrete, and worth fixing regardless
of how C0 resolves.

**C2. An information-architecture pass, once C0 is confirmed fixed.**
The complaint that prompted this track — "I can't tell where things are"
— needs to be re-evaluated against a nav that's actually rendering before
scoping a real redesign. Concrete friction points once that's true (not
guessed at now) are what this item should be built from.

### Track D — Postgres-unlocked features

Four of the six ideas in the old `Later` table, each independently
shippable. List-sharing-only items (real-time sync, conflict handling)
are cut, since list sharing itself is on hold.

- **Ranked full-text search.** `SearchVector`/`SearchRank` + a GIN index,
  `pg_trgm` for typo tolerance. Prioritize the Ideas/`reference` page
  first, not the Inbox — `capture-triage-and-polish-plan.md` already
  notes basic substring search matters more there, since a `reference`
  archive nobody can find again defeats its own purpose, and the Inbox is
  meant to be worked down quickly rather than searched.
- **Per-user timezones.** `AT TIME ZONE` makes "due today" a per-user
  answer instead of one global one.
- **Audit log / general undo.** `JSONB` with GIN indexing for change
  payloads.
- **Time blocking.** `tstzrange` + an `ExclusionConstraint` to stop
  overlapping blocks at the database level.

### Track E — Public-readiness residuals

Two of the remaining quality-bar items, examined and ready to scope;
transactional email stays parked in `Later` for now.

- **Account export/deletion.** Export is a view that serializes
  everything a user owns (Lists, Items, Captures, Ideas, token metadata
  minus secrets) to a downloadable JSON, the same mechanism `dumpdata`
  already uses for the whole database, just scoped to one owner.
  Deletion should cascade cleanly, since every model already FKs to
  `User` with `CASCADE`. Open decision, and it echoes the Idea-vs-Capture
  deletion split already made in this app: does account deletion happen
  immediately on confirmation, or soft-delete with a grace period before
  a real purge?
- **Error monitoring.** Sentry (`sentry-sdk` + the Django integration) —
  a few lines in `settings.py`, one new prod env var for the DSN, same
  pattern as the existing email credentials. Catches unhandled exceptions
  automatically with no per-view changes. Free tier comfortably covers a
  2-3 user app; probably the cheapest item in this whole document.

### Track F — Android capture MVP

A basic native Kotlin app whose only job is capturing input against
`POST /api/v1/capture` (`design/capture-api-and-tokens-plan.md`) using a
personal access token. The spec's own sequencing suggested trying the
zero-code home-screen-shortcut experiment first, to see whether a
shortcut alone solves the friction before writing any Kotlin — deliberate
call made to skip that and go straight to a basic Kotlin app instead.

---

## Later — on the radar, not scheduled

Nothing here is planned yet. Kept visible so none of it gets re-litigated
from scratch when it does become relevant.

### What the Postgres move specifically unlocked

Four of the six ideas originally here (ranked full-text search, per-user
timezones, audit log/undo, time blocking) moved into Bittern's Track D.
What's left is sharing-only, and held with list sharing itself:

| Idea | Why it needs Postgres |
| --- | --- |
| Real-time sync for shared lists | `LISTEN`/`NOTIFY` as a push channel, no Redis needed — pairs with SSE. |
| Conflict handling on shared lists | `select_for_update()` becomes real, plus `skip_locked`/`nowait` — a prerequisite for sharing at all. |

### Rest of the public-readiness quality bar

Account export/deletion and error monitoring moved into Bittern's Track
E. Still here, deliberately not yet scoped: self-service signup/email
verification, rate limiting on signup and capture, a transactional email
provider (held off for now), and privacy policy/ToS. Isolation tests (A3)
and password recovery (A6) are the two pieces of this bar already pulled
into Track A/Now; the rest waits for a deliberate decision to pursue
public deployment.

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
resurfaces, how ideas relate to each other, and an append-only
comment/log on an idea rather than its single `notes` field — is tracked
in that document's own **Future** section (a mind-map-style view,
possibly AI-assisted sorting), all deliberately bundled together as the
same underlying problem rather than picked off piecemeal. The native
Android capture app is no longer here either — it's Bittern's Track F.

---

## Explicitly not planned

Decisions already made, kept here so they don't get re-opened by accident:

- Markdown rendering in notes — plain text only.
- Subtasks nested more than one level deep.
- Auto-completing a parent task when every subtask under it is done — it
  shows the count and waits for an explicit tick.
- Recurrence on subtasks — recurrence stays a parent-task-only feature.

---

## Releases

**Named after birds, alphabetically** — each release takes the next
letter, the way storms are named. `albatross`, then something with a B,
then a C. The scheme carries its own ordering, which is the point: a bare
`curlew` still tells you it came after `bittern`, so the tags sort
themselves and no version prefix is needed to make them readable.

Tagged on the commit that actually reached production, not the one that
merged — in this project those have already differed by hours more than
once.

**Three tags per deploy, each answering a different question**, and they
predate the bird scheme rather than being replaced by it:

| Tag | Kind | Answers |
| --- | --- | --- |
| `LIVE` | moving, lightweight | What is running right now? Force-moved on every deploy. It sat 80 commits stale between July 24 and August 1, which is what a moving tag does when nobody moves it. |
| `DEPLOYED-<date>/<HHMM>` | permanent, lightweight | When did each deploy happen? Local time, matching the existing markers. This is the deploy *event*. |
| bird name | permanent, annotated | What went out, and why it mattered? The release, in language a person uses. The annotation carries the contents and the verification. |

| Release | Commit | Contents |
| --- | --- | --- |
| `albatross` | `f5ddb85`, deployed 2026-07-31 22:24 EDT (`DEPLOYED-2026-07-31/2224`) | The first release carrying the whole feature set: subtasks with `always_recurs` and the orphan fix behind it, notes, the side nav, self-service password reset, personal access tokens with `POST /api/v1/capture`, and Capture triage with the `Idea` domain. Seven migrations, 53 → 60, no existing row changed. Also the first deployed against a database firewalled to the droplet (A5) with a restore path actually proven (A2). |

Two rules that keep the scheme honest:

- **Tag after the deploy is verified, never before.** A tag pointing at
  code that didn't survive first contact with production is worse than no
  tag, because it looks authoritative. Twice in one day here, a bug showed
  up only on a live server or only under `curl`.
- **A letter is spent once.** If `bittern` ships broken and `bunting`
  follows an hour later, that's two releases and two letters, not a
  retagged one. The sequence is a history of what actually went out.

## Keeping this current

This is now the single planning document for Clarice — the parallel copy
that lived in the planning conversation's own document viewer has been
retired in its favor, so there's exactly one place this history lives.

Update "Where things stand" after each Now item ships, and slide finished
Next items out as they land. The Track B checkpoint is no longer tied to a
fixed date — watch real Capture usage on an ongoing basis, and if it
disagrees with the shipped triage design, record that as a scope change
when it actually happens rather than waiting on a calendar entry. When
something from Later gets a real reason to happen, it graduates into Next
with its own one-liner — that's the whole maintenance loop.

**`design/` was empty of unbuilt specs at the `albatross` deploy** — the
subtask addendum, the password-reset plan, the capture API/tokens plan and
the triage plan were all done and all shipped. A2 and A5 are done too. So
the deploy-era questions this section used to ask are answered, and Bittern
is genuinely new scope, not a Later item promoted out of momentum: see
`## Bittern — scoping the next release` above, Tracks C through F. The
spec's own suggestion to try a zero-code home-screen shortcut before
writing any Kotlin was deliberately not taken -- Track F goes straight to
a basic native app instead.

The original caution still applies in spirit: don't let Bittern grow past
its four scoped tracks just because the queue looks open again. Each new
addition earns its own track or its own item inside one, the same
discipline Track A and Track B already ran on.

### Deploy naming: bird codenames

Starting now, every production deploy gets a bird name alongside its
mechanical tag, assigned alphabetically (A, B, C, ...) so a release is
easy to talk about without memorizing a date or a SHA.

**This deploy — the SPA + Postgres cutover currently live in
production, the one the stale `LIVE`/`DEPLOYED-*` tags never caught up
to — is codenamed Albatross.** (Long-haul migration, in both senses of
the word.) Whatever ships next is Bittern, then Crane, and so on.

Keep the existing `DEPLOYED-<date>/<time>` tag format for exact,
sortable traceability — don't replace it, just make it an *annotated*
tag whose message carries the codename:

```
git tag -a DEPLOYED-<date>/<time> -m "Codename: Albatross -- SPA migration + Postgres cutover"
git push origin DEPLOYED-<date>/<time>
```

`LIVE` keeps floating to whatever's actually running, same as before:

```
git tag -f LIVE <commit>
git push -f origin LIVE
```

Since nothing tagged `LIVE` since July 24 has matched what's actually
running for a while now, moving it to the real current commit is also
the retroactive fix for that gap, not just going-forward hygiene.
