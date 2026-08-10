# TaskWorkspace redesign — closing the last Tailwind gap

Vince · brief · written August 10, 2026 · **not started, handoff for a new session**

## 1. Trigger and diagnosis

Vince shared a screenshot of an Area's task list (`/app/areas/:id`, the
"House hold" area) mid-review of the Projects redesign, asking to examine
it before deploying: "the tasks are simply a mess." The screenshot shows
due-date inputs, tag fields, and repeat selects rendering with no visible
border, background, or spacing — reading as a wall of running text rather
than a form.

**Root cause, confirmed by reading the code, not guessed:**
`TaskWorkspace.tsx` (rendered inside `AreaRoute.tsx`, below the
already-redesigned header) is one of the last two components — with
`AgendaWorkspace.tsx` — still styled through `src/static/site.css`'s
Bootstrap-era classes (`.form-control`, `.btn`, `.list-item`) rather than
the Tailwind utility classes `ProjectRoute`/`ProjectsIndexRoute`/`AreaRoute`
already use. `app_shell.html` says so directly in its own comment:

> Migrated components (AgendaWorkspace, TaskWorkspace) still use site.css's
> classes for now, so it has to load here too... Both drop once every
> component needing site.css has moved to Tailwind.

Tailwind's Preflight reset strips default browser chrome from every input,
select, and button so utility classes can restyle from scratch.
`site.css`'s Bootstrap-era rules don't fully win that fight once both
stylesheets load together (`app_shell.html` loads both), which is why
every form control in the screenshot renders with no visible boundary.
**This is the same Tailwind migration the Projects pages already got in
this session — not a fresh polish pass — just for the one screen that
carries the most fields per row.**

**Scope decision:** only `TaskWorkspace.tsx` is in scope. `AgendaWorkspace.tsx`
shares the same underlying problem but was not part of the brief and is
not touched by this plan.

## 2. Approved design

[`design/tasks-mockup.html`](tasks-mockup.html) — reviewed and approved by
Vince across several iterations. Open it for the actual visual reference;
this section is the written record of what it shows and why.

**Signature move:** the due-date pill and the recurrence pill each *are*
their real, functioning `<input type="date">` / `<select>`, restyled down
to pill size, rather than a separate read-only display plus a form control
duplicating the same information. Editing never looks different from
viewing.

### Approved scope, all of it

1. **Tailwind migration.** Rewrite `TaskWorkspace.tsx`'s markup from
   `site.css`/Bootstrap classes to Tailwind utility classes, matching
   `ProjectRoute`/`AreaRoute`'s own convention. Composer becomes one
   inline row (text input + due date + tags + repeat + Add, all compact);
   filters become pill buttons; task rows become bordered rows with pill
   metadata instead of stacked labeled form fields.
2. **Overdue rows get a red left-border accent** (`border-left`), not just
   a colored due-date pill — the same pattern `design/dashboard-mockup.html`
   already designed for this exact content type, reused rather than
   invented fresh.
3. **Due-date pill dedup.** Drop the separate "Overdue: Jul 31, 2026" /
   "Due Jul 31, 2026" text — the pill (the real date input, styled) already
   says it, in red when overdue.
4. **Recurrence pill dedup.** Drop the separate read-only "↻ Weekly" badge
   next to the repeat `<select>` — same reasoning, the select already shows
   its own state.
5. **Progressive disclosure for repeat and "+ tag".** Both go quiet
   (`opacity: 0`, revealed on row hover/focus — same mechanism the actions
   column already uses) since most tasks never repeat and already have
   whatever tags they're going to have. Due date and any *existing* tags
   stay visible always; only the two rarely-touched controls hide. An
   active (non-default) recurrence stays visible even without hovering.
6. **Tags become individually removable pills** (click ×) instead of one
   text field pre-filled with `"tag1, tag2"` that had to be text-edited to
   remove one. A small separate "+ tag" input adds one or more
   (comma-separated) without touching the existing set.
7. **"Created Jul 29, 2026, 12:46 AM" becomes Agenda's own age language.**
   Reuse `agenda.ts`'s existing `ageLabel(days)` / `AGE_WORTH_MENTIONING`
   (currently 7) exactly as written — **do not re-derive this rule.**
   `ageLabel` returns `null` under 7 days, meaning a task under a week old
   shows **no age text at all**, not "Added today" (the mockup's
   placeholder text was written before cross-checking this — treat
   `ageLabel`'s actual behavior as authoritative, not the mockup's exact
   wording, and mention the discrepancy when reporting back).
8. **A completed task's line becomes "Completed <date>"** using its own
   `completed_at`, replacing the age line rather than appending "· Completed"
   to it — more relevant once a task is done. Not explicitly called out as
   its own numbered item when the mockup was reviewed; flag it as an
   addition made during implementation, the same way the Projects session
   flagged unplanned-but-clearly-in-scope choices.
9. **Sort control** (toolbar): "Manual order" (default — today's only
   behavior, unchanged) or "Due date". Switching to Due date reorders the
   *visible* list (ascending, no-due-date last — the same rule
   `bucketFor`'s own bucket ordering already implies: dated before
   "someday") and disables dragging while active — the same
   on/off precedent `canReorder` already sets when a filter, search, or
   tag filter is active. Confirmed directly against `models.py`:
   `Item.Meta.ordering = ("position", "id")` is the *only* order that has
   ever existed; there is no due-date/alphabetical/created sort in the API
   today, so this is purely a client-side sort over already-loaded
   `items`, no backend change.
10. **Select mode + bulk actions**, added after Vince asked for it directly
    mid-review (not in the original brief). A "Select" toggle reveals a
    checkbox per row (replacing the drag handle for that row) and a bulk
    action bar: "Mark complete" / "Archive" / "Clear", plus a count. Only
    those two actions bulk — they're already single, safe per-task calls;
    editing due date/tags/repeat stays per-task since "set every selected
    task's due date to the same day" isn't a real request anyone's made.

Any of items 3–8 can be left as their current behavior if reviewed again
and found not worth it — they were offered as "considered simplifications,"
not a single non-negotiable bundle — but Vince's own reply to the mockup
was "go ahead and implement everything," so build all of them unless a
fresh look during implementation turns up a reason not to.

## 3. Technical findings from investigation (read once, reuse — don't re-derive)

- **`workspace.module.css` is shared with `ArchiveManager.tsx`**, which
  uses `.archiveSearch`, `.feedback`, `.error`, `.empty`, `.dialogBackdrop`,
  `.dialog` — **keep those classes untouched**. Every other class in that
  file (`.addForm`, `.inputRow`, `.addExtras`, `.dueDateField`,
  `.dueDateInline`, `.tagFilters`, `.tagChip`, `.tagRow`, `.tagPill`,
  `.tagEdit`, `.recurrenceInline`, `.recurrenceBadge`, `.overdue`,
  `.itemLead`, `.dragHandle`, `.dragging`, `.toolbar`, `.filters`,
  `.filter`, `.filterActive`, `.search`, `.editForm`, `.inlineActions`) is
  `TaskWorkspace`-only and safe to delete once its Tailwind replacement
  lands. `AgendaWorkspace.tsx` does not import this module at all — it has
  its own separate (also-unmigrated) markup, out of scope here.
- **No bulk API endpoint exists** (`api.ts` has no `bulkUpdateTaskStatus`
  or similar) — bulk actions loop the existing single-task
  `updateTaskStatus(task, status)` per selected id via `Promise.all`,
  same as every other call in this file.
- **Completing vs. archiving a recurring task behave differently,
  confirmed in `services.py`:** `complete_item` auto-archives a recurring
  task and spawns its next occurrence (`item.status` comes back
  `"archived"` even though the caller asked for `"completed"` —
  `changeStatus` already branches on this). `archive_item` does **not**
  spawn anything, ever — a plain status flip. So bulk "Mark complete"
  needs the same archived/spawned branching `changeStatus` already has;
  bulk "Archive" does not.
- **`TaskWorkspaceData` has no server-supplied "today"** (unlike
  `AgendaWorkspaceData.today`). `TaskWorkspace.tsx` already has its own
  local `todayIsoDate()` reading the browser clock directly — pre-existing
  code, not something this plan introduces. Reuse it for the age
  calculation feeding `ageLabel`; do not add a new client-clock read
  pattern, and don't attempt to fix this pre-existing gap as part of this
  slice (would need a backend field, out of scope, not asked for).
- **Tag color hashing (`tagColor`) is unrelated to the `--list-color-*` /
  area-color system** — a separate deterministic hash over the 8-color
  `TAG_COLORS` array already in the file. Not a bug, not in scope to
  unify; noted so nobody "fixes" it by accident.

## 4. Suggested implementation order (TDD per `principles.md`)

Read `frontend/src/TaskWorkspace.test.tsx` and `frontend/src/test/fixtures.ts`
(the `task()` builder) first — every slice below should extend that file,
not replace it.

1. Sort control (client-side only, easiest to isolate and test: given
   items with mixed due dates, "Due date" sort produces the expected
   order with no-due-date last; switching back to "Manual order" restores
   original order; `canReorder`/drag handle disabled while sorted).
2. Select mode + bulk actions (state, checkboxes, bulk bar; test bulk
   complete against both a plain task and a recurring one — the
   archived/spawned branch — and bulk archive).
3. Tag pills: split the single comma-text field into read-only removable
   pills + a small add-input. Test remove-one-tag and add-one-tag
   independently.
4. Visual/markup pass: composer → one row; filters/search → pills;
   due-date and recurrence dedup; overdue left-border; progressive
   disclosure; age-label swap; completed-date line. Mostly markup +
   Tailwind classes over already-correct state/handlers — lower test
   surface, but re-run the full suite since text assertions
   (`screen.findByText("Created ...")` etc.) will need updating same as
   `ProjectRoute.test.tsx` did during the Projects redesign.
5. Delete the now-unused classes from `workspace.module.css` (see §3 —
   leave `ArchiveManager`'s classes alone), confirm `ArchiveManager.test.tsx`
   still passes untouched.
6. Full backend suite (no backend changes expected, but confirm), full
   frontend suite, `pnpm --dir frontend build`.
7. Browser smoke pass **is** warranted here per `CLAUDE.md` — this touches
   drag-and-drop interaction and a real information-architecture change
   (sort), not just page content. Rebuild first (`pnpm --dir frontend build`)
   or the suite tests a stale bundle.
8. Verify live the same way the Projects redesign was verified this
   session: `previewuser` login, driven at the DOM level (`get_page_text` /
   `javascript_tool`) since the Browser pane doesn't composite frames
   here — see the `project_local_browser_verification` memory for the
   exact recipe (login, `manage.py migrate` if the local `db.sqlite3` has
   drifted again, `HTMLInputElement.prototype.value` setter + dispatched
   `input` event to drive React-controlled inputs from JS).

## 5. Status

**Shipped, August 10, 2026 (uncommitted — awaiting Vince's review before
committing).** All ten approved-scope items landed in the suggested order:
sort control, select mode + bulk actions, removable tag pills, the full
Tailwind/markup pass (composer, filter pills, overdue left-border, pill
dedup, progressive disclosure, age-label swap, completed-date line), and
the `workspace.module.css` cleanup (only `ArchiveManager`'s six classes
remain). 254 frontend tests, 867 backend tests, `tsc --noEmit` and
`pnpm build` all green. `manage.py test functional_tests` shows the same
two pre-existing `ProjectJourneyTest` failures confirmed present on `main`
before this work started (a `git stash` bisect) — nothing in this change
caused or fixed them, and no `TaskWorkspace`/`AreaRoute` journey regressed.

Verified live against the real backend (`previewuser`, DOM-level driving
per the local-browser-verification memory): due-date sort, select mode +
bulk complete (confirmed the archived/spawned branch actually fires for a
recurring task, not just in the mocked test), and adding/removing tag
pills all round-tripped through the real API.

One deviation from the brief worth naming: the per-row archive button's
label changed from "Move to archive" to "Archive" to match the mockup and
the bulk bar's own wording — no test had locked in the old string, and the
functional-test suite doesn't reference it either.
