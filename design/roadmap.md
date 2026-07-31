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
move) is the only item from that plan that's actually done; everything else
in it is still ahead.

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
GTD-style someday/maybe item than a task. The current thinking is that this
argues for a genuinely separate Idea/Someday domain alongside Task, with an
explicit "promote to task" action for when one actually gets acted on,
rather than stretching Task to cover a shape it wasn't built for.
Deliberately not designed yet — see Capture MVP below for why.

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

Most of this stays a vision for now, not a milestone — except capture,
which is starting as a small side track (Track B below).

---

## Public-readiness bar

The actual goal for Clarice: a professional-grade, publicly-deployable
project that doubles as a personal productivity tool and as the premier
piece in a portfolio. "Public" splits into two bars worth keeping distinct,
since they carry very different amounts of work and only one of them is
currently in scope.

**The quality bar — public-ready, not necessarily commercial.**

- Self-service signup with email verification and self-service password
  recovery, replacing the current manual admin-approval flow.
- Per-user data isolation that's been adversarially tested (a real test
  suite that tries to read/edit/delete another user's data by id), not just
  assumed correct from ownership filters. **Pulled forward into Track A/Now
  as item A3 — see below.** Everything else on this list stays deferred.
- Rate limiting on signup and capture, not just login.
- A transactional email provider in place of personal Gmail SMTP.
- An account export/deletion flow.
- Basic error monitoring beyond `docker logs`.
- A privacy policy and terms of service.

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

Two tracks run at once from here:

- **Track A** — the main sequence: Now (infra hygiene, incl. A3) → Next
  (the feature plan).
- **Track B** — Capture MVP, parallel from day one, on its own clock.

They don't share code — Capture is an isolated model with no FK into
`List`/`Item` — so they don't block each other technically. They do share
the same developer, so Track B gets a fixed, small scope and an explicit
checkpoint below rather than open-ended parallel effort.

---

## Track A — Now: close the infrastructure gaps

The Postgres move solves the easy 80% of a few problems and leaves the rest
half-finished. Four items from the original plan, plus one pulled forward
from the public-readiness bar. All five are cheap now and get more annoying
to retrofit once schema work (Track A/Next) lands on top.

Order matters: CI goes first, so the DB-user restriction and the isolation
tests both land with automated coverage instead of a manual, one-time
check.

### A0. Stand up CI with a Postgres service container

There's no CI today (confirmed — no `.github/workflows`, no other CI config
anywhere in the repo) and the local suite still runs on SQLite while
production runs on Postgres — the exact combination the migration notes
call out as worse than either choice alone.

- GitHub Actions (or equivalent), one job: Postgres service container,
  `migrate`, run the full Django suite + `pnpm test`.
- This becomes the harness that A3 and everything in the Next queue verify
  against — do this before either.

### A1. Restrict the database user

The cluster is still using the default `doadmin` credential, which can read
and write every database on the cluster, not just Clarice's — confirmed in
`infra/provision-postgres.sh`. Harmless while Clarice is the only thing on
it; a five-minute fix now versus a real exposure the day a second project
shares the cluster.

- Create a restricted user per database via SQL (see "One cluster, several
  projects" in `design/subtasks-plan.md`), not the default admin credential.
- Update `~/.db-connection-url` on the droplet and re-verify a deploy.

### A2. Prove the backups actually work

Backups were the strongest reason to move to managed Postgres in the first
place — the plan was to solve them by procurement instead of a hand-rolled
cron job. That's only true if snapshots/PITR are confirmed on and a restore
has actually been tested once. Don't let "we moved to managed Postgres"
quietly stand in for "backups are handled."

- Confirm snapshots/PITR are actually enabled on the cluster.
- Do one real test restore (to a scratch cluster or database) and verify
  the data is intact.

### A3. Adversarial per-user data isolation tests

**New in this pass — not in the original July 31 draft's Now list; pulled
forward from the public-readiness bar because it's cheap and it's the
single item on that whole bar most likely to get poked at by a portfolio
reviewer.** Isolation today rests entirely on ownership filters at the
query layer (`get_object_or_404(List, id=list_id, owner=request.user)` in
`lists/api_v1.py:147`, `list__owner=user` filters elsewhere) — never
adversarially tested end-to-end.

- New test module, e.g. `lists/tests/test_isolation.py`. Two authenticated
  users, `owner` (creates data) and `intruder` (tries to reach it).
- Cover every id-taking endpoint across the three routers
  (`lists/api_v1.py`, `lists/api.py` legacy, `accounts/api_v1.py` — 18
  endpoints total as of this writing): GET/PATCH/DELETE a list, item, tag,
  or preference belonging to `owner`, authenticated as `intruder`. Assert
  404 (not 403 — matches the codebase's existing pattern of not revealing
  existence), and assert nothing was mutated.
- Run as its own CI job once A0 lands, not folded into the general suite,
  so a regression here is unmissable in CI output rather than buried in a
  broader pass/fail.
- Out of scope for this pass: self-service signup/password recovery, rate
  limiting, transactional email, export/deletion, monitoring. Real work,
  correctly deferred — isolation tests are the one item worth decoupling
  from the rest of the quality bar because they're cheap and high-signal on
  their own.

### A4. Wire up the digest email

`send_due_digest` exists, works, and has been verified with `--dry-run` —
but nothing calls it. It needs one cron line to actually reach anyone.

- One line in `infra/deploy-playbook.yaml`:
  `0 7 * * * docker exec clarice python manage.py send_due_digest`
  (already documented in the command's own docstring).
- Verify once against production data before trusting it unattended.

---

## Track B — Capture MVP (parallel, starts now)

Started deliberately small, running alongside Track A rather than pausing
it — the two tracks don't block each other technically, but Track B gets a
fixed scope and a fixed checkpoint precisely because attention is the
shared, scarcer resource.

**Scope for this pass:**

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

**Checkpoint, not open-ended:** once the MVP is live, use it for real for
~2 weeks (target: mid-to-late August 2026) before writing any triage
design. At that checkpoint, either the task/idea/note split holds up and
gets a real design pass (`subtasks-plan.md`-style), or it doesn't and the
model changes before more is built on it. This checkpoint is what stops
Track B from quietly becoming a second, open-ended feature queue running
alongside Track A.

---

## Track A — Next: resume the feature plan

Once Track A/Now (A0–A4) is closed, pick `design/subtasks-plan.md` back up
in the order it already lays out. It re-sequences below only to give each
step a one-line "why," not to change the order. Step 2 (Postgres) is
skipped — it's done.

1. **Fix status handling across archive and restore.** Archiving currently
   fabricates a completion timestamp on active tasks, so there's no way to
   tell afterward whether a restored task was active or done. Small,
   self-contained, and a hard prerequisite for cascade restore once
   subtasks exist — ship and verify it alone before anything else touches
   archive/restore.
2. **Snooze presets.** Independent of everything else. Replaces the single
   Tomorrow/Schedule button with Tomorrow, This weekend, Next week, and
   Clear — removes an existing rough edge and ships fast.
3. **Task detail view.** A full page for the no-JS path and a slide-over
   panel in the React app, showing text, list, due date, tags, recurrence,
   notes, and subtasks. Nothing to show in notes or subtasks yet, but
   nowhere for either to live until this exists.
4. **Notes.** A plain-text field on the detail view — deliberately not
   Markdown, which would add a renderer and an XSS surface for little gain
   at two users. Small, and it proves the detail view actually works before
   subtasks lands on top of it.
5. **Subtasks.** The large one. A self-referencing FK on `Item`, one level
   of nesting only, cascading complete/archive/restore with proper undo,
   sibling-scoped duplicate and position logic, API changes to
   `create_item`, `item_detail`, and `reorder_items`, and UI work across the
   list page, agenda, and detail view. `design/subtasks-plan.md` §6 has the
   full shape, including the Postgres-specific constraint that's now
   available since Step 2 is done and A0's CI runs against Postgres.
6. **Persistent side navigation.** Left nav for lists, archive, and
   settings across all three main pages — today it only exists on the
   agenda, so navigation disappears the moment you drill into a list. Last,
   because it touches nearly every template and is easier to get right once
   the detail view's layout is settled. Mock it before building.

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

Self-service signup/email verification/password recovery, rate limiting on
signup and capture, a transactional email provider, account export/
deletion, error monitoring beyond `docker logs`, privacy policy and ToS.
Isolation tests (A3) are the one piece of this bar pulled into Track A/Now;
the rest waits for a deliberate decision to pursue public deployment.

### Business bar

Billing/subscription lifecycle, support operations at volume, deeper legal
(DPAs, ToS enforcement), horizontal scaling. Out of scope until the quality
bar above is genuinely met.

### Vision layer beyond Capture MVP

Promoting the agenda to the app's home surface, the Idea/Someday domain
with its "promote to task" action, and the review cadence (weekly/monthly/
quarterly). Deliberately undesigned until the Track B checkpoint gives real
usage to design from.

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

Update "Where things stand" after each Now item ships, and slide finished
Next items out as they land. When the Track B checkpoint resolves
(mid/late August 2026), replace its entry above with either a real design
pass or a scope change — don't leave it silently open-ended. When something
from Later gets a real reason to happen, it graduates into Next with its
own one-liner — that's the whole maintenance loop.
