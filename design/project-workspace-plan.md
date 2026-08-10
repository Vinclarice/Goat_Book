# Project becomes a workspace — the containment inversion

Vince · brief · written August 10, 2026

## 1. Purpose and scope

`Project` currently lives *inside* an `Area` (`List`): `Project.area` is a
required FK, and a task joins a project only if that project happens to
share the task's own area. This is why the side nav's "Projects" group,
added in `ui-second-pass-plan.md` F3, has never had anywhere to send a click
except back to the project's parent Area's page — Project has never had a
page of its own. Vince hit that gap directly, asking how to reach a project
from the nav and finding there wasn't a "there" there.

His stated direction: a Project should be a **dedicated workspace** — his
examples were "launching a business" and "progress on this website" — that
can hold one or more Areas underneath it, rather than the other way around.
A task keeps belonging to an Area exactly as it does today; it is the Area,
not the task, that optionally belongs to a Project now.

This is not a new idea arriving from nowhere. `release-d-plan.md` §3
originally specced `Project.area` as **nullable** — "a project can sit
inside an Area (List) or stand alone" — but it shipped **required** instead
on August 3, 2026, specifically because "required→nullable is a bare
`AlterField` [cheap to do later]; nullable→required [the other direction]
is expensive." That reasoning was explicit about which direction was being
kept cheap for later. This is later.

Scope: `src/lists/models.py`, `src/lists/services.py`,
`src/lists/projects.py`, `src/lists/api_v1.py`, `src/lists/api.py`,
`src/lists/serializers.py`, `src/daily/api_v1.py`, and the corresponding
frontend surfaces under `frontend/src/` (`SideNav.tsx`, `AreaRoute.tsx`,
`ProjectsPanel.tsx`, `TaskDetailRoute.tsx`, a new `ProjectRoute.tsx`).
Release-sized work — landed as its own tracked slice sequence over several
sessions, not one sitting, the same way Release D's original Project work
was.

**Not folded into Release F.** Release F is currently the second-mind
discovery pass (`second-mind-discovery-plan.md`) — unrelated domain, already
underway. This is separate work with its own trigger (a real navigation
dead-end Vince hit, not a discovery pass), so it gets its own line in
`roadmap.md` rather than being silently added to Release F's total.

## 2. Design cycle — inverting Project's containment

### Why

Three shape questions, resolved directly with Vince before this document was
written rather than guessed at:

1. **A Project can hold several Areas**, not just one — e.g. "Launch the
   business" containing separate Legal/Marketing/Product areas, or just one
   if that's all a given project needs. Modeled as a single nullable
   `project` FK on `List`, not a forced one-to-one; the schema doesn't force
   either usage pattern.
2. **No data-preservation migration.** There is not enough real Project
   data yet to justify reshaping it. Existing `Project.area`/`Item.project`
   links are retired outright — named explicitly below, per this project's
   practice of never silently discarding meaning, rather than reshaped.
3. **The task-level project override goes away.** Today a task can join a
   project independent of its own Area (`Item.project`, guarded by
   `set_task_project`'s cross-area check). That stops being possible — a
   task's project is derived purely from `task.list.project`. Vince's own
   framing: "the task will belong to an area, just that area lives within
   the project."

### The settled decision

```python
# lists/models.py

class List(models.Model):
    owner = models.ForeignKey(
        "accounts.User", related_name="lists", on_delete=models.CASCADE,
    )
    title = models.CharField(max_length=100, default="Untitled list")
    updated_at = models.DateTimeField(auto_now=True)
    # An Area optionally belongs to a Project -- the inverse of the old
    # Project.area. SET_NULL, not CASCADE: a Project groups Areas, it does
    # not own them, so deleting one says the grouping was wrong rather than
    # that the work is gone -- the same reasoning Item.project already
    # carried one level down.
    project = models.ForeignKey(
        "Project", related_name="areas", null=True, blank=True,
        on_delete=models.SET_NULL,
    )


class Project(models.Model):
    # `area` REMOVED. A Project is the top-level record now; it has nothing
    # above it to belong to, and owner is the only ownership path.
    owner = models.ForeignKey(
        "accounts.User", related_name="projects", on_delete=models.CASCADE,
    )
    title = models.CharField(max_length=100)
    due_date = models.DateField(blank=True, null=True)
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Unchanged. ordering, valid_project_completion, and
        # project_owner_state_idx were never about `area` -- they key on
        # is_completed/created_at/owner, none of which move.
        ordering = ("is_completed", "-created_at", "id")
        constraints = [...]  # valid_project_completion, unchanged
        indexes = [...]      # project_owner_state_idx, unchanged
```

`Item.project` is removed entirely. Every existing constraint/index on
`Item` (`unique_active_item`, `valid_item_status_timestamps`, all four
indexes) is already keyed on `list`/`status`/`due_date`/`commitment`, never
`project` — nothing there changes.

No new index is needed on `List.project`: Django's automatic FK index
already backs the one new query this field introduces
(`List.objects.filter(project=...)`), and there is no compound filter
anywhere in this brief that would justify a hand-written one.

### Migration — expand, migrate, contract

**Expand — `0032_list_project`.** `AddField(List, "project", null=True,
blank=True, on_delete=SET_NULL)`. Purely additive: `Project.area` and
`Item.project` stay untouched and every existing code path keeps working
unmodified while this is out alone. Its own commit, deployable standalone
ahead of the rest per `principles.md`'s "a migration that can be applied
ahead of the code using it earns its own commit."

**Migrate.** The service, API, and frontend layers move onto `List.project`
between the two migrations — not a migration itself, ordinary commits (§3).

**Contract — `0033_retire_project_area_and_item_project`,** once nothing
left reads either old field:

```python
def log_before_removal(apps, schema_editor):
    Project = apps.get_model("lists", "Project")
    Item = apps.get_model("lists", "Item")
    print(f"projects_with_area={Project.objects.exclude(area=None).count()}")
    print(f"items_with_project={Item.objects.exclude(project=None).count()}")

class Migration(migrations.Migration):
    dependencies = [("lists", "0032_list_project")]
    operations = [
        migrations.RunPython(log_before_removal, migrations.RunPython.noop),
        migrations.RemoveField(model_name="project", name="area"),
        migrations.RemoveField(model_name="item", name="project"),
    ]
```

Same practice `0028_delete_ownerless_lists` already used before its own
destructive step: the loss is counted and named, not silent.

**What is actually lost, stated plainly rather than discovered later:**
every existing `Project.area_id` link (a Project becomes areas-less until
someone manually assigns an Area to it); every existing `Item.project_id`
cherry-pick (a task manually placed in a project independent of its area
will, after the cutover, show whatever project its area happens to belong
to instead — possibly a different one, possibly none; there is no successor
field for this at all, because the whole point of the redesign is that
task-level assignment stops existing).

### Charter compliance (`architecture-trajectory.md` §4)

- **Rule 1, owned at birth.** Unaffected — both models already carry a
  direct, non-null `owner`. If anything, `Project.owner` is more clearly
  the only ownership path now that Project has no parent record left to
  borrow from at all.
- **Rule 5, reference never copy.** *Strengthened.* Dropping `Item.project`
  removes the one place a task's project was stored rather than derived —
  a task's project becomes two hops of pure computation
  (`item.list.project`), nothing left to keep in sync.
- **Rule 6, deletion.** Restated both directions. Deleting a **Project**:
  `List.project` is `SET_NULL` — its Areas survive, unparented, same
  hard-delete/no-tombstone answer as before. Deleting an **Area**: today
  this cascades to delete the Area's Projects (`Project.area` was
  `CASCADE`); once the FK direction inverts there is no FK left for that
  cascade to travel through, so deleting an Area has **zero effect on any
  Project** it belonged to. This falls out for free from the schema change,
  but earns its own explicit test rather than being assumed.
- **Rules 2, 3, 4, 7, 8** — unaffected; nothing about public identifiers,
  snapshots, the read/service split, indexing beyond the above, or
  repetition changes.

### What this cycle does not decide

Whether a Project needs its own recurrence — unchanged from
`release-d-plan.md`'s original open question, still nothing in Clarice's use
asks it. Whether an Area can move between Projects with history preserved
(today, reassigning just overwrites `List.project` — no record of a prior
project is kept, matching how the rest of this domain treats a live
grouping rather than a logged event). Whether a `/projects` index page ships
in this same slice or a follow-up — the nav's existing Projects group
already covers the common case (open projects); an index page's actual
job is showing *completed* ones, the same gap `/archive` fills for tasks,
and it can slip without blocking `ProjectRoute` itself.

### Acceptance examples

**A Project with two Areas.** "Launch the business" is created with no
Area. "Legal" and "Marketing" — two existing Areas — are each assigned to
it via `PATCH /areas/{id}/project`. Both now show "part of Launch the
business" on their own pages; the project's own page lists both, each with
its own open-task count; the nav's Projects group links straight to
`/projects/{id}`.

**Deleting a Project.** "Launch the business" is deleted. "Legal" and
"Marketing" still exist, still have all their tasks, and no longer show any
project — `List.project` was set to null on both, nothing about the Areas
or their tasks changed.

**Deleting an Area that belongs to a Project.** "Legal" is deleted. "Launch
the business" still exists, still shows "Marketing," and its own
`open_task_count` no longer includes anything from "Legal."

## 3. Proposed slice sequence

Ordered thinnest usable path first, per `principles.md`, expand before
contract within the migration boundary — see below for why that principle
stops mattering at the API/frontend boundary for this particular app.

1. **This document**, plus a pointer from `roadmap.md`. Its own commit,
   before any code changes.
2. **Expand migration** `0032_list_project` — own commit, full suite green,
   safe to deploy alone if desired.
3. **Service + read layer rewrite** (`lists/services.py`,
   `lists/projects.py`) — TDD, isolation test first for
   `add_area_to_project`. The full suite is *not* green at the end of this
   slice alone, since the API layer still calls the old signatures — a
   deliberate, contained red window that never reaches `main` on its own.
4. **API layer rewrite** (`lists/api_v1.py`, `lists/api.py`,
   `lists/serializers.py`) — full backend suite green again; the first
   point after step 2 where the backend is internally consistent by itself.
5. **Contract migration** `0033_retire_project_area_and_item_project` — own
   commit, safe now that step 4's green suite proves nothing reads either
   retired field.
6. **Regenerate the OpenAPI client** (`dump_openapi_schema` +
   `pnpm --dir frontend generate:api`) — own commit for review clarity, but
   must land in the *same deploy* as steps 4 and 7, never split across one,
   per `principles.md`'s build-ability rule ("a schema change and the
   client regenerated against it do not [get separate commits], because
   separating them produces a commit that cannot build").
7. **Frontend rewrite** — new `ProjectRoute.tsx` and `/projects/:projectId`
   route, `SideNav.tsx`'s project link retargeted, `AreaRoute.tsx` gains a
   "part of project X" indicator and assign/unassign control,
   `TaskDetailRoute.tsx` loses its per-task Project select in favor of a
   read-only indicator, `ProjectsPanel.tsx` deleted. Test-first per
   component.
8. **Browser smoke pass** — mandatory per `CLAUDE.md` (touches routing,
   navigation, the app shell). Rewrite the `functional_tests/` journey
   exercising the old task-level project select; manually verify create
   project → add area → area shows "part of project X" → nav link opens
   `/projects/:id` directly → delete project leaves the area intact.

**Two sequencing calls, stated plainly rather than left implicit:**

- **Expand-before-contract matters at the schema boundary only.** Step 2
  earns its own commit specifically because a migration is genuinely
  harder to roll back than a code deploy. Steps 3 and 4 are ordinary code
  changes with no equivalent asymmetry.
- **No compatibility window is worth building between the API rewrite and
  the frontend rewrite.** This app has a single-container, atomically
  recreated production deploy with no staging environment (`CLAUDE.md`'s
  deploy notes: the container is recreated as one unit before nginx/certbot
  run). There is no real window in which "backend redesigned, frontend
  still old" is ever live in production — that state only exists on a
  branch. Building compatibility scaffolding for a multi-version window
  that can't occur would be manufacturing insurance nobody can cash in, the
  same call already made and recorded for the Area vocabulary rename ("No
  compatibility window on the API, deliberately... there is none to
  strand"). Steps 3 through 7 land together in one deploy; step 2 is the
  only piece safe to ship alone ahead of the rest.

## 4. What this does not touch

Routines, Ideas, Capture, the Daily Page, and review — none of them
reference `Project` or `Item.project` today, and this redesign does not
give them a reason to start. The Android app's capture-only API is
unaffected; this is entirely a web/API surface change on an
already-web/API-only model (Project's own charter-compliance note: "No
client creates a Project offline").

## 5. Shipped — August 10, 2026

All eight slices landed, each its own commit, in order: the design doc
(this file), the expand migration, the service and read layer, the API
layer, the contract migration, the regenerated OpenAPI client, the
frontend rewrite, and the browser smoke pass. Full backend suite green
throughout except a deliberate, contained red window inside the service-
layer slice that never reached `main` alone (§3's own sequencing note,
confirmed exactly as planned). Final state: 858 backend tests, 231
frontend tests, 28 browser journeys, all green.

**One gap found only by writing the browser journey, not by the plan
itself: nothing created a *new* Project anywhere in the redesigned UI.**
`ProjectsPanel.tsx`'s deletion took its create form with it, and the
replacement (`ProjectRoute.tsx`) only ever manages a project that already
exists — this plan never named where creation would live once it left the
Area page. Fixed with a "New project" card in the Agenda sidebar, sibling
to "New area," driven by a mutation and the SPA router rather than a
plain form POST (a Project is API-only, unlike an Area, which has a
Django view to post to). Recorded here rather than left implicit, because
it's exactly the kind of gap this project's practice asks to be named
instead of quietly patched.

**One refinement against §"API layer" above, found by tracing actual call
sites rather than assumed from the brief:** `TaskOut.project_id` was not
dropped. It survives, now derived via `item.list.project_id` instead of
stored on the task — every caller already `select_related("list")`, so
this cost nothing — and it meant the Agenda/Area/Archive "project pill" on
every task row needed zero frontend changes. Only the *editable* per-task
override actually went away, which is what §"the settled decision" and
Vince's own answer to the task-project question actually asked for; the
plan's original "TaskOut loses project_id" line said more than the design
decision required.

The plan's other calls held exactly as written: `List.project` nullable
and multi-area-capable, no data-preservation migration, the task-level
override fully retired, `AreaDetailOut.projects` → `.project` (singular),
`project_ref_for`'s hand-built `/app/projects/{id}` URL, and the
service-layer owner guard modeled on `capture.services.link_ideas`.

## 6. Two follow-ups, same day, from Vince using the shipped feature

Both raised directly after the redeploy, both real gaps rather than
polish — recorded here rather than folded silently into §5 above, since
they arrived after this plan was first called done.

**A `/projects` index page.** §"What this cycle does not decide" flagged
this as deferrable; Vince asked for it directly ("a central project
landing page... click projects from the sidebar and it takes me there"),
so it shipped: `ProjectsIndexRoute.tsx` at `/projects`, listing every
project open and completed, and the sidebar's "Projects" heading links to
it. `GET /api/v1/projects` already returned everything unfiltered — no
backend change needed.

**A Project can create a new Area, not just reassign one.** The shipped
`ProjectRoute.tsx` only ever let you add an *existing* Area to a project —
Vince named the gap directly: "the predominant use case" is areas that
don't exist yet ("Legal", "Marketing" inside "Launch the business"), not
reassigning ones that do. Mid-conversation he also changed a standing
rule: an Area no longer needs a first task to exist. New
`services.create_area(owner, title, project=None)`, additive alongside
`create_list_with_item` rather than replacing it — the Agenda sidebar's
own "+ New area" form is unchanged and still asks for a first task. New
`POST /api/v1/projects/{id}/areas`.

**A real bug found only by writing the second follow-up's browser
journey, not by either plan:** `ProjectRoute.tsx`'s complete/reopen and
delete mutations, and `AreaRoute.tsx`'s project-assignment mutation, only
ever invalidated their own page's query, never `["nav"]`. The sidebar's
Projects group — filtered to open projects only — kept showing a
completed or deleted project, or a stale open-task count, until something
unrelated happened to invalidate nav. First surfaced as a Playwright
strict-mode violation (two "Website Relaunch" elements, one the stale
sidebar link) — exactly the class of defect `CLAUDE.md` names the browser
smoke suite for, and a second confirmation that shipping ahead of a
written-out plan for a small, clearly-scoped follow-up is fine as long as
the same verification discipline still runs.

Full backend suite green (865 tests), frontend green (239 tests), all 30
browser journeys green.

## 7. Visual redesign and two more editable fields, August 10, 2026

A separate, same-day request: "examine the Projects screen" per
`frontend-design`'s process (brainstorm, mockup, critique, then build) —
`design/projects-mockup.html` is that mockup, reviewed and approved before
any real component changed. Signature element: a **composition bar**, a
thin strip under a project's title segmented by its own areas' existing
`color_key`s, segment width following each area's `open_count` share. It
makes the containment inversion §2 shipped actually visible instead of a
bare "N areas" count — the same color identity every area dot already
carries, no new palette. Empty (no areas yet) renders as a dashed track.
`ProjectComposition.tsx`, shared by `ProjectsIndexRoute` (card grid,
replacing the old flat list) and `ProjectRoute` (under its own header).

Reviewing the mockup surfaced a real, code-verified gap of its own, not
speculation: creating a project only ever lived in the Agenda sidebar
(§5's own fix), a step removed from the page actually about projects.
`ProjectsIndexRoute` now has its own inline create form (title + optional
due date).

Asked directly afterward, "what am I missing" turned up two more, both
confirmed against the actual code before promising them: **a project's
title and due date were both already writable via `ProjectUpdateIn`, but
nothing in the UI ever offered to write them** — the create form hardcoded
`due_date: null` and `ProjectRoute` only ever exposed complete/reopen/
delete. Both are now editable inline on `ProjectRoute` (disabled-until-
changed Save buttons, `AreaRoute`'s own rename pattern extended to a
second field). Backend already supported both; no API change needed.

The third ask, an overdue indicator, did need one: `ProjectOut` gained
`is_overdue` (`lists/api_v1.py`, computed server-side from
`timezone.localdate()`), rather than the client inventing its own idea of
"today" — the exact thing `principles.md`'s "the server owns business
meaning" exists to prevent, and Agenda's own `today`-from-server precedent
this file's earlier sections never had to touch. A completed project is
never overdue regardless of `due_date`, mirrored in both the field's own
definition and its test. Additive: schema regenerated
(`dump_openapi_schema` + `generate:api`), one field added to
`ProjectOut`, no migration.

Verified live against a real local session (`previewuser`, driven at the
DOM level the same way `ui-second-pass-plan.md`'s own sitting was, since
the Browser pane would not composite frames here either): create with a
due date, rename, set a due date and watch the overdue flag and card-grid
warning both appear, add an area and watch the composition bar pick up
its color, sidebar staying in sync throughout. Caught one thing belonging
to neither this slice nor the last: the local dev `db.sqlite3` had never
had §3's own migrations applied, 500ing every list-touching endpoint until
`manage.py migrate` caught it up — unrelated to this change, fixed in
passing rather than left blocking verification.

867 backend tests (2 new: `is_overdue` true only for an open, past-due
project), 244 frontend tests (5 new: create-from-index, rename, due-date
edit, overdue flag on both surfaces), full suite green, build and
`tsc --noEmit` clean.
