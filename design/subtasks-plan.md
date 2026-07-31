# Subtasks, notes and snooze — plan of action

Working plan for the next round of features. Decisions already settled are
recorded as such; open questions are flagged inline.

**Status, July 31, 2026.** Step 2 is done — Clarice is on managed
DigitalOcean Postgres, and CI runs the Django suite against a real Postgres
service container. Three consequences for reading the rest of this
document:

- **Step 2a is dead.** It was the "if we stay on SQLite" branch. Kept below
  for the record, struck through in effect — do not implement it.
- **Step 6a has one answer, not two.** The two-partial-constraint SQLite
  workaround is no longer a live option; the `nulls_distinct=False` form is
  what gets built.
- **Migration numbers have shifted by one.** `0017` is now taken by
  `0017_remove_item_item_list_state_idx_and_more`, so steps 1, 5 and 6a
  become `0018`, `0019` and `0020`. Corrected in place below.

`design/roadmap.md` owns sequencing and what's next. This document stays
the source of truth for *how* each step gets built.

## Settled decisions

| Question | Decision |
| --- | --- |
| Subtask model | Self-FK on `Item`. Subtasks are full tasks — own due dates, own tags, own agenda rows. |
| Nesting depth | One level. A subtask cannot have subtasks. |
| Completing a parent with open subtasks | Cascade to the open children, with a single undo that restores exactly those. |
| All subtasks complete | Parent does **not** auto-complete. Show `5/5` and let the user tick it. |
| Recurrence on subtasks | Not allowed. Parents only. |
| Agenda layout | Flat and date-ordered. Subtasks appear as their own rows with a parent breadcrumb. The list page is the nested view. |

## Why there are prerequisite steps

Cascade archive and cascade restore are the heart of the subtask work, and
they sit on a foundation that is currently cracked: **archiving destroys the
pre-archive status**, so a cascade restore would mark active children as
completed (step 1). That is not caused by subtasks, but it becomes a
correctness bug because of them.

The second prerequisite was a decision rather than a fix: **if Postgres is
coming, it should come before the feature work, not after** (step 2). It
came; step 2 shipped ahead of all the feature work below, as intended.

---

## Step 1 — Preserve status across archive/restore

**Problem.** `services.archive_item` does:

```python
item.completed_at = item.completed_at or now
```

Archiving an *active* task fabricates a completion timestamp, so afterwards
there is no way to distinguish "was active when archived" from "was completed
when archived". That is why `restore_item` unconditionally returns tasks to
`COMPLETED`. Tolerable for one task; wrong for a cascade, where a parent with
3 active and 2 completed children would restore all 5 as done.

**Fix.** Stop fabricating. Let `completed_at IS NULL` mean "was active when
archived", and have `restore_item` read it.

- `lists/models.py` — relax the archived arm of `valid_item_status_timestamps`
  from `Q(status="archived", completed_at__isnull=False, archived_at__isnull=False)`
  to require only `archived_at`.
- `lists/services.py` — `archive_item` no longer sets `completed_at`;
  `restore_item` returns the task to `ACTIVE` when `completed_at` is null and
  `COMPLETED` otherwise.
- Migration `lists/0018_archived_status_timestamps` — constraint change only.
  Add a comment noting that existing archived rows all carry a
  `completed_at`, real or fabricated, and are indistinguishable; they keep
  restoring as completed. Only new archives get the correct behaviour.

**Tests.** `lists/tests/test_services.py` already asserts the current
behaviour around lines 30–160 and will need updating — those assertions are
the specification of the bug. Add: archive an active task then restore it,
expect `ACTIVE`; archive a completed task then restore it, expect `COMPLETED`.

**Risk.** Low, and self-contained. Worth doing and deploying on its own before
any subtask work starts.

---

## Step 2 — Move to managed Postgres — done

**Shipped July 2026.** Production runs on a managed DigitalOcean Postgres
cluster; `design/roadmap.md`'s A0 added CI against a Postgres service
container and A1 replaced the default `doadmin` credential with a
per-database `clarice_app` user. Two things the live run corrected in what
follows: the cluster runs **Postgres 18**, not the 17 assumed here (CI was
pinned to 17 on the same assumption and has since been corrected to match),
and backups being handled by procurement is a claim that stays unverified
until roadmap item A2 does a real restore.

The reasoning below is kept as the record of why the move happened before
the feature work, not as a pending decision.

**Do this before the feature work, not after.** Five reasons, strongest first.

1. **It deletes the SQLite tuning work entirely.** WAL, `IMMEDIATE`,
   `busy_timeout` are all SQLite-only. Doing them and then migrating is
   throwaway effort.
2. **`nulls_distinct=False` collapses the messiest part of step 6.** The
   two-partial-constraint workaround below exists only because SQLite can't
   express it. On Postgres 15+ it becomes one constraint:
   ```python
   UniqueConstraint(
       fields=("list", "parent", "text"),
       condition=~Q(status="archived"),
       nulls_distinct=False,
       name="unique_active_item",
   )
   ```
3. **`select_for_update()` stops being a no-op.** All 11 calls become real row
   locks. That is a behaviour change, and it is far better to make it against
   today's simple, well-tested code than at the same moment as introducing
   multi-row cascades. Once locks are real, **cascade lock ordering becomes a
   genuine deadlock risk** — a cascade locking parent-then-children can
   deadlock against a transaction locking child-then-parent. Worth designing
   for from the start rather than retrofitting.
4. **It solves the outstanding backup problem by procurement.** Managed
   snapshots and PITR instead of hand-rolled cron.
5. **It is cheapest now.** Fewer constraints, less data, and the current 182
   passing tests are the verification harness. Migrate afterwards and you're
   validating against subtask tests that have never run anywhere.

### The migration is clean — verified

The chain contains only `RunPython` data migrations. No `RunSQL`, no PRAGMAs,
no SQLite-specific DDL, including in the tricky
`0004_numeric_user_primary_key` / `0010` / `0011` primary-key rebuilds. It
will replay on an empty Postgres.

### Work involved

- `psycopg[binary]` in `requirements.txt`; `DATABASES` read from env.
- Provision the instance, TLS required, `CONN_MAX_AGE` set — connection reuse
  matters much more with a network round trip than with a local file.
- `migrate` on the empty database, then
  `dumpdata --natural-foreign --natural-primary`, excluding `contenttypes` and
  `auth.permission`, then `loaddata`. Seconds, at this data size.
- `Dockerfile` — the build stage runs `collectstatic` with
  `DJANGO_DB_PATH=/tmp/build.sqlite3`; that needs a placeholder connection
  string instead. `collectstatic` never connects, but settings must import.
- `infra/deploy-playbook.yaml` — swap `DJANGO_DB_PATH` for the DB env vars.
- `functional_tests/reset_test_database` flushes the database. The existing
  `ALLOW_DATABASE_FLUSH` guard matters a great deal more when the target is a
  managed instance rather than a throwaway file.

### The real cost

Not the migration — the development environment. Once step 6 depends on
`nulls_distinct=False`, **the test suite has to run on Postgres**, because
that behaviour cannot be reproduced on SQLite. That means Docker Postgres
locally and in CI. Testing on SQLite while deploying on Postgres would be
worse than either option alone.

*Settled:* A0 did this — `DJANGO_DATABASE_URL` opts the suite into Postgres
and CI supplies a service container, with local dev still defaulting to
SQLite when the variable is unset.

### Honest counter-argument — resolved

At two users, SQLite is genuinely fine. The strongest single reason to move is
backups, and that is achievable far more cheaply with `VACUUM INTO` on a cron
and an offsite copy. Against that: a monthly bill, a heavier dev setup, a
network dependency, and the loss of "the whole database is one file". If
backups are the actual motivation, solve backups. If the motivation is wanting
Postgres in the project, that is a fine reason too — but worth naming.

*Outcome:* the move happened anyway, and the counter-argument's sharpest
point still stands unanswered — "if backups are the actual motivation,
solve backups" is precisely what roadmap item A2 exists to close, and until
that restore has actually been performed, this section is still correct
that the strongest reason for the move has not been banked.

### Why not MySQL or MongoDB

**MySQL is disqualified by the schema we already have.** Verified against the
installed Django:

```
supports_partial_indexes                 MySQL=False
supports_deferrable_unique_constraints   MySQL=False
```

`unique_active_list_item` is a *partial* unique constraint
(`condition=~Q(status="archived")`). On MySQL, Django raises check `models.W036`
— "does not support unique constraints with conditions" — with the hint
"A constraint won't be created." It warns and carries on. The rule that
currently stops duplicate active tasks would silently stop existing, enforced
only by the application-level guard in `services._duplicate_exists`. The same
flag also rules out the deferrable-constraint idea for `position`.

**MongoDB is the wrong shape.** The data model is thoroughly relational —
`List → Item → parent Item`, an M2M to `Tag`, FKs to `User`, a check
constraint tying status to its timestamps, partial unique constraints. Those
constraints are doing real correctness work. A document store means giving
them up and reimplementing them in Python.

### One cluster, several projects

A managed cluster hosts many databases, and DigitalOcean explicitly
recommends sharing one cluster across applications rather than paying per
cluster. A DO "Project" is an organisational label for billing, not an
isolation boundary — it has no bearing on how many of our apps can use the
cluster.

Two things to get right:

- **Create a restricted user per database.** By default every user has full
  rights to every database in the cluster, so Clarice's credentials could read
  another project's data. Per-database users via SQL, not the default --
  `infra/restrict-database-user.sh` does this.
- **Connection budget.** Clusters allow 25 connections per GiB of RAM with 3
  reserved, so the $15/mo 1 GiB plan gives 22. Our `Dockerfile` runs gunicorn
  with its default single worker, so Clarice needs 1–2. Ample for several
  small projects. PgBouncer is built in if it ever gets tight — but note that
  transaction-mode pooling requires `DISABLE_SERVER_SIDE_CURSORS = True` in
  Django settings.

Backups are cluster-wide, so restoring one project's database means restoring
the whole cluster elsewhere and extracting. Acceptable, but worth knowing
before it's needed.

### What Postgres would unlock later

Only counting things that genuinely need it or are materially better on it.

| Feature | Why Postgres | Verdict |
| --- | --- | --- |
| **Ranked full-text search** | `SearchVector`/`SearchRank` + GIN index, native in `django.contrib.postgres.search`. `pg_trgm` adds typo tolerance; `SearchHeadline` highlights matches. SQLite's FTS5 works but is a separate virtual table you sync yourself, unranked and unstemmed by default. | Biggest single win |
| **Real-time sync for shared lists** | `LISTEN`/`NOTIFY` is a push channel with no Redis and no extra service — pair it with SSE. On SQLite this means polling or new infrastructure. | Enables sharing properly |
| **Conflict handling on shared lists** | `select_for_update()` becomes real, plus `skip_locked`, `nowait` and `of=`. None exist on SQLite. | Prerequisite for sharing |
| **Position integrity on reorder** | `DEFERRABLE INITIALLY DEFERRED` allows a real `UNIQUE (parent, position)` constraint that survives a mid-transaction shuffle. Today we simply don't constrain `position`, so nothing stops duplicates. | Directly improves step 6 |
| **Per-user timezones** | `timezone.localdate()` currently uses the server timezone, so "due today" is one global answer. `AT TIME ZONE` makes per-user date bucketing a clean query; SQLite emulates it with registered Python functions. | Real gap, real fix |
| **Audit log / general undo** | `JSONB` with GIN indexing for change payloads. SQLite's JSON1 has no comparable index. | Enables the undo-everywhere idea |
| **Time blocking** | `tstzrange` + `ExclusionConstraint` prevents overlapping blocks *in the database*. Not expressible in SQLite at all. | Only if we ever want it |
| **Completion stats / streaks** | `generate_series` fills empty days trivially; SQLite needs a recursive CTE. | Marginal |

Explicitly **not** reasons to move: tags (already normalised — `ArrayField`
would be a downgrade), performance at this scale, subtasks themselves, the
recurrence logic, or the digest. Those are identical on either database.

## Step 2a — SQLite tuning — dead, do not implement

**Superseded by step 2 shipping.** This was the branch for staying on
SQLite; production is on Postgres and CI tests against it. None of what
follows applies any more — `journal_mode`, `synchronous`, `busy_timeout`
and `transaction_mode` are SQLite-only knobs, and the `select_for_update()`
note at the end has been overtaken by events: those locks are real now, and
the deadlock risk it warns about is live, which is why step 6b's cascade
ordering matters. Kept only so the reasoning isn't rediscovered from
scratch if SQLite ever comes up again.

`DATABASES` currently has no `OPTIONS` at all (`clarice/settings.py:195`).
Measured defaults on the current setup:

| Pragma | Current | Meaning |
| --- | --- | --- |
| `journal_mode` | `delete` | Rollback journal: a writer blocks all readers |
| `synchronous` | `2` (FULL) | Safest, slowest fsync behaviour |
| `busy_timeout` | `5000` | 5s, from Python's `sqlite3` default |
| `foreign_keys` | `1` | Already on — Django enables it itself |
| transaction mode | `DEFERRED` | Lock acquired mid-transaction, not at `BEGIN` |

```python
"OPTIONS": {
    "timeout": 20,
    "transaction_mode": "IMMEDIATE",   # Django 5.1+; we're on 5.2
    "init_command": (
        "PRAGMA journal_mode=WAL;"
        "PRAGMA synchronous=NORMAL;"
    ),
},
```

- **`transaction_mode: "IMMEDIATE"` is the one that matters.** Every service
  function is `@transaction.atomic` and does
  `select_for_update().get(...)` then `.save()` — a read followed by a write.
  Under the default `DEFERRED` mode, `BEGIN` takes no lock, the read takes a
  shared lock, and the write then tries to upgrade it. If any other connection
  wrote in between, that upgrade cannot succeed, so SQLite returns
  `SQLITE_BUSY` **immediately** — the busy timeout does not apply, because
  waiting would deadlock both sides. Django surfaces it as
  `OperationalError: database is locked`. `IMMEDIATE` takes the write lock at
  `BEGIN` instead, so contending writers queue and wait rather than failing.
- WAL lets readers proceed during a write, rather than blocking them.
- `synchronous=NORMAL` is the usual pairing with WAL: safe against process
  crashes, with a small window for losing the most recent transactions on
  power loss.
- `foreign_keys` needs no pragma — Django already sets it per connection.
  Verified, not assumed.

**Also worth a code comment, not a change:** the 11 `select_for_update()`
calls in `services.py` are no-ops. SQLite reports
`connection.features.has_select_for_update is False`, so Django silently
omits the clause — verified, no exception raised. The code is still correct,
because SQLite serialises writers at the transaction level, but it is correct
for a different reason than it appears. If this ever moves to PostgreSQL those
locks become real and could deadlock. One comment above the first use.

**Knock-on:** WAL means the database is three files. Any backup must use
`.backup` or `VACUUM INTO`, never a file copy. This is now a hard blocker on
the still-outstanding backup work.

---

## Step 3 — Snooze presets

Independent of everything else; small; ships on its own.

- `lists/agenda.py` — a `snooze_presets(today)` returning Tomorrow, This
  weekend (next Saturday), Next week (next Monday), plus Clear.
- `frontend/src/agenda.ts` — mirror it, same as the bucketing rules already
  are.
- Replace the single Tomorrow/Schedule button with one menu, which also
  removes the current awkward split where dated tasks show "Tomorrow" and
  undated ones show "Schedule".
- `set_item_due_date` already accepts an arbitrary date and needs no change.

---

## Step 4 — Task detail view

Prerequisite for both notes and subtasks: a row cannot hold either, and
`edit_item.html` is currently a bare text form.

- Full page at `/lists/items/<id>/` for the no-JS path, reusing and replacing
  the existing edit view.
- Slide-over panel in the React island.
- Shows text, list, due date, tags, recurrence, notes, subtasks.

---

## Step 5 — Notes

Deliberately before subtasks: small, and it proves out the detail view.

- `Item.notes = TextField(blank=True)`, migration `0019_item_notes`.
- Plain text rendered with `linebreaksbr`. Not Markdown — it pulls in a
  renderer and an XSS surface for little gain at two users.
- A quiet marker on the agenda row when non-empty; editing happens in the
  detail view.
- Not indexed for search yet; that belongs with the FTS5 project.

---

## Step 6 — Subtasks

### 6a. Model

```python
parent = models.ForeignKey(
    "self", null=True, blank=True,
    on_delete=models.CASCADE, related_name="subtasks",
)
```

**The unique constraint is the sharp edge. Step 2 settled which shape it
takes:** one constraint with `nulls_distinct=False`, replacing
`unique_active_list_item`.

```python
UniqueConstraint(
    fields=("list", "parent", "text"),
    condition=~Q(status="archived"),
    nulls_distinct=False,
    name="unique_active_item",
)
```

Available on Postgres 15+; production and CI both run 18, so it is safe on
both. The reason it's needed at all: SQL normally treats NULLs as
distinct, so extending the existing constraint to `(list, parent, text)`
without `nulls_distinct=False` looks right and is wrong — with
`parent IS NULL` on every existing row, it would stop preventing duplicate
top-level tasks entirely.

*Historical, no longer applicable:* on SQLite this needed two partial
constraints instead — `unique_active_root_item` on `(list, text)` where
`~archived AND parent IS NULL`, and `unique_active_subtask` on
`(parent, text)` where `~archived AND parent IS NOT NULL`. Collapsing that
pair into the single constraint above was reason #2 for moving to Postgres
in the first place.

Migration `0020_item_parent` adds the FK, swaps the constraint, and adds an
index on `(parent, status)`. No data migration — every existing row gets
`parent = NULL`.

**Test the constraint directly, not through the service layer.**
`services._duplicate_exists` short-circuits before the database is reached in
most paths, so a service-level test would still pass against a broken
constraint.

### 6b. Services

Sibling-scoping — every one of these is currently list-scoped and must become
`(list, parent)`-scoped:

- `_duplicate_exists` (`services.py:35`), called from `create_item:82`,
  `edit_item:108`, `restore_item:250`
- `_next_position` (`services.py:54`)
- `forms.py:66` (`ExistingListItemForm`), `forms.py:110` (`QuickAddForm`),
  `forms.py:146` (`TaskTextForm`) each duplicate the check inline

Behaviour changes:

- `complete_item` cascades to open children **and returns which ones it
  completed.** This is the undo wrinkle: the server cannot reconstruct that
  set afterwards, because some children were already done before the parent
  was ticked. The API response carries the cascaded ids and undo reopens
  exactly those. The no-JS path has no undo, so the flash message must say
  what happened — *"Completed 'Plan Japan trip' and its 3 open subtasks."*
- `archive_item` cascades down. An archived parent cannot have live children.
- `restore_item` restores children sharing the parent's `archived_at`, each
  to its own prior status (which step 1 made possible). Same-instant
  `archived_at` is the grouping key; it works because the cascade happens in
  one transaction, but it is a timestamp doing a job an explicit marker
  should. **Open question: accept this, or add an `archive_group` uuid?**
- `_spawn_next_occurrence` clones children, resets them to active, and shifts
  their due dates by the same delta as the parent's. Undated children stay
  undated.
- `create_item` and `set_recurrence` reject recurrence when `parent` is set,
  and reject a parent that itself has a parent.
- `reorder_items` takes a parent scope and validates the id set against that
  sibling group only.

### 6c. API

- `create_item` accepts `parent`.
- `item_detail` PATCH accepts `parent` for promote/demote — fits the existing
  "exactly one of these fields per request" rule at `api.py`.
- **`parent` is the first id this API accepts in a request body rather than
  a path, and it must be ownership-checked like one.** Every existing
  ownership check keys off the URL — `_owned_list` filters `owner=`,
  `_owned_item` filters `list__owner=` — so a `parent` resolved with a bare
  `Item.objects.get(pk=...)` would let one user graft a subtask onto
  another user's task. Resolve it through the same owner-scoped helper, and
  return 404 rather than 403, matching the rest of the API. Roadmap item A3
  covers the existing surface; the cross-user `parent` cases are added to
  that module as part of this step, not afterwards.
- `reorder_items` gains a parent scope. **This breaks the existing signature**
  and with it `lists/tests/test_api.py`, `lists/tests/test_services.py` and
  `frontend/src/TaskWorkspace.test.tsx`. Expected, not incidental.
- Complete response gains a `cascaded` list.
- `serialize_item` gains `parent` (id + text) and subtask counts.

### 6d. UI

- **List page** — nested rendering, expand/collapse, add-subtask on a row.
  Dragging reorders within a sibling group only; changing a parent is an
  explicit promote/demote action. Drag-and-drop across nesting levels is not
  worth attempting.
- **Agenda** — flat rows with a `Plan Japan trip ›` breadcrumb beside the list
  pill; parent rows also show `2/5`.
- **Detail view** — where subtasks are actually managed.
- **Fallback** — nested `<ul>`, a per-row add form, plain links.

Two consequences to accept: `summary_counts` and the sidebar list counts will
count parents and children alike, so a task with 5 subtasks reads as 6 open;
and a parent and its child can land in different sections of the same page.

---

## Step 7 — Side panel

Last, because it touches every template and benefits from knowing what the
detail view looks like.

Fixes a real inconsistency: the agenda has a sidebar, the list page and
archive have none, so list navigation disappears the moment you drill in. A
persistent left nav (lists, archive, settings) across all three pages.

Two constraints: left nav + agenda + the current right sidebar is three
columns, too many below ~1400px, so filters move into the agenda header as
chips. And a mobile drawer normally means JavaScript, which cuts against the
no-JS principle — a `<details>` disclosure, or falling back to the existing
top nav on narrow screens, avoids that.

Mock it before building.

---

## Order and rationale

1. **Archive/restore status fix** — small, database-agnostic, blocks cascade
   restore. Deploy and verify on its own.
2. **Postgres migration** — done. Pure infrastructure, zero feature work
   attached. Isolating it is the point: don't couple a database move to a
   schema change. It landed on its own, which is what made A1's two
   production bugs cheap to diagnose.
3. **Snooze presets** — small, independent, immediately useful
4. **Detail view** — prerequisite for 5 and 6
5. **Notes** — small, proves out the detail view
6. **Subtasks** — the large one
7. **Side panel** — touches everything, wants the detail view settled first

The governing principle: each of steps 1 and 2 is risky in a different way,
so neither should be carrying passengers. Land them separately, verify
separately.

## Still outstanding from earlier

- **Backups — still open, and now the last unbanked reason for step 2.**
  The move to managed Postgres was supposed to resolve this by procurement,
  but "managed" is not the same as "verified": snapshots and PITR have not
  been confirmed on and no restore has been tested. Roadmap item A2 owns
  this. The SQLite caveat (WAL ruling out file-copy backups) is moot.
- **`send_due_digest` is never run.** The command exists; nothing invokes it.
  Needs a cron entry in `infra/deploy-playbook.yaml`. Roadmap item A4.
- **~~No CI.~~ Done.** `.github/workflows/ci.yml` runs the Django suite
  against a Postgres service container plus a frontend job, on every push
  and PR (roadmap A0). This was the right call for exactly the reason
  stated: steps 1 and 6 both rewrite existing test expectations, and they
  now do it with a net underneath.
- **Database cluster firewall is open** — found during A1's production
  cutover, tracked as roadmap item A5. Not a feature-plan concern, noted
  here only because `provision-postgres.sh` assumes the opposite.
