# Agenda redesign — Tailwind, touch targets, unified filtering, search, staleness

Vince · brief · written August 10, 2026 · **shipped and deployed, August
10–11, 2026 — see §5**

## 1. Trigger and diagnosis

Vince asked for a mockup of improvements to the Agenda workspace
(`/app/agenda`, `AgendaWorkspace.tsx`) as a follow-on to the TaskWorkspace
redesign. A first visual pass covered Tailwind migration and touch targets;
asked directly what else was worth improving on a page that's "largely been
untouched since initial dev," a second pass added two functional gaps —
text search and a staleness signal — found by reading the actual code
rather than guessing. All four are now folded into one approved design.

**Root cause, confirmed by reading the code, not guessed:**
`AgendaWorkspace.tsx` is the *last* component still styled through
`site.css`'s Bootstrap-era classes now that `task-list-redesign-plan.md`
moved `TaskWorkspace.tsx` onto Tailwind — same diagnosis, same fix. It
carries more weight here than it did there: this is the page a signed-in
visit actually prefers to land on (`roadmap.md`, Crane), so it's the
highest-traffic screen still carrying the debt.

**Four problems, not one:**

1. **Bootstrap-era styling.** Same root cause as `TaskWorkspace.tsx` — see
   `task-list-redesign-plan.md` §1 for the mechanism (Tailwind's Preflight
   reset vs. `site.css`'s rules not fully winning the fight).
2. **Touch targets under the ~44px guideline**, measured directly against
   `site.css`: `.agenda-checkbox` is `1.2rem` (19.2px), `.tag-chip`/`.pill`
   padding produces roughly 24–28px, Bootstrap's own `.btn-sm` is ~28–31px.
   This is the same finding `roadmap.md`'s mobile-web-experience entry
   already recorded from Crane 1 slice 7: "the Agenda, which nothing in
   Crane touched, is worse at 19–31px" against the Daily Page's own 32px.
3. **Filtering split across three surfaces with two different shapes.**
   Scope (Overdue/Today/This week) lives in the header as boxed `.stat`
   cards; area lives as inline chips in the main column
   (`.agenda-list-chips`); tags live in a separate sidebar card. Three
   places, two visual vocabularies, for the same job — narrow what's
   showing.
4. **No text search, and no staleness signal.** There's no way to type and
   find one task — only category filters. And `age_in_days` lives on
   Daily's and the weekly review's own item types, not on the shared `Task`
   type this page's `items` are, so a task in "No due date" can sit for
   months with genuinely nothing on it: no due date, no age, no signal at
   all.

## 2. Approved design

[`design/agenda-mockup.html`](agenda-mockup.html) — built, iterated once
with Vince's own follow-up ("how could this page be improved"), and
approved across both passes. Open it for the actual visual reference; this
section is the written record of what it shows and why.

**Signature move:** the header's four scope counts (Overdue/Today/This
week/Open) go from boxy `.stat` cards to the same pill shape every other
filter/tag/due-date chip in the app already uses — not a new visual
language, just fixing the one place this screen wasn't speaking Clarice's
own idiom yet. The larger, generously-padded pill also solves most of the
touch-target problem for free.

### Approved scope, all of it

1. **Tailwind migration.** Rewrite `AgendaWorkspace.tsx`'s markup from
   `site.css`/Bootstrap classes to Tailwind utility classes, matching
   `TaskWorkspace`/`ProjectRoute`/`AreaRoute`'s own convention. Masthead
   (date + greeting) gets real typographic room as the page's one hero
   moment; scope counts become pills; composer becomes the same field-chip
   grammar `TaskWorkspace`'s own composer already shipped; task rows get a
   bordered-row-with-left-border-accent treatment matching
   `TaskWorkspace`'s overdue styling.
2. **Every interactive control gets a real ≥44px hit area** — checkbox,
   scope pills, area/tag chips, the search field, per-row Schedule/Edit
   buttons, sidebar disclosure summaries and links, the Archive link. Visual
   size of each stays what it is today (a bigger checkmark isn't the fix, a
   bigger tappable box around it is); only the hit area grows, mirroring
   `task-list-redesign-plan.md`'s own approach.
3. **Unified filter row.** Area chips and the tag cloud — split across the
   main column and a sidebar card today — collapse into one row directly
   under the composer, the same move `TaskWorkspace`'s toolbar already made.
   The sidebar's "Tags" card goes away entirely; its content moves up.
4. **Scope pills replace `.stat` cards** in the masthead, per the signature
   move above. Same click/toggle behavior, same counts, new shape.
5. **Search.** A chip-shaped text field beside the unified filter row,
   filtering by task text (case-insensitive substring), combined with
   whatever scope/area/tag filters are also active. Feeds the existing
   filter banner the same way the other three dimensions already do.
6. **Staleness signal.** A plain, borderless "Added N days ago" meta pill —
   no border/background, styled exactly like `tasks-mockup.html`'s
   `pill-created` — computed from each task's own `created_at` against
   `agenda.ts`'s existing `ageLabel`/`AGE_WORTH_MENTIONING` (7 days). Same
   wording Daily and the weekly review already use; not a new phrasing for
   the same fact.

**Deliberately out of scope, named so nobody adds it by accident:** bulk
actions and a manual sort/reorder control were both considered directly
(Vince asked "how could this page be improved," and both came up) and
deliberately not incorporated — the recommendation given and accepted was
that search and staleness serve Agenda's actual job (find and triage,
read-only), while bulk-edit and reordering are editing-shaped and already
live on the Area page (`TaskWorkspace`) that owns them. Revisit only if
that reasoning changes, not as a default follow-on.

**Deliberately unchanged:** the masthead's greeting and date wording — no
motivational copy, no streaks, nothing added to how the page talks. See the
mockup's own closing annotation for why: `agenda.ts`'s `ageLabel` doc
comment already commits to "reports a fact and draws no conclusion," and a
quieter header shouldn't start speaking in a different voice than the
labels sitting right underneath it.

## 3. Technical findings from investigation (read once, reuse — don't re-derive)

- **`AgendaFilters`/`NO_FILTERS`/`hasFilters`/`applyFilters` (`agenda.ts`)
  are used nowhere except `AgendaWorkspace.tsx` and `agenda.test.ts`** —
  confirmed by search. Adding a `query: string` field to the shared
  `AgendaFilters` interface, `NO_FILTERS`, `hasFilters` (check
  `filters.query.trim() !== ""` alongside the existing three), and
  `applyFilters` (case-insensitive substring match against `task.text`) is
  self-contained — no other consumer to keep in sync.
- **No new date-math functions needed for staleness.** Unlike
  `TaskWorkspace.tsx` (which had no server `today` and had to read the
  browser clock itself), `AgendaWorkspaceData.today` already exists and is
  already destructured at the top of `AgendaWorkspace.tsx`. The staleness
  pill is exactly `ageLabel(daysBetween(task.created_at.slice(0, 10),
  today))`, reusing `agenda.ts`'s existing exports as-is — confirmed
  `created_at` is on the shared `Task` type; `age_in_days` is not, and stays
  that way (this computes the label client-side, the same trick
  `TaskWorkspace`'s own redesign used, rather than adding a backend field).
- **`AgendaWorkspace.tsx` imports no CSS module** — it uses bare global
  class strings (`"agenda-row"`, `"pill pill-list"`, etc.) straight from
  `site.css`, unlike `TaskWorkspace.tsx`'s prior use of
  `workspace.module.css`. The migration is a pure JSX/class rewrite; there
  is no CSS-module cleanup step (`task-list-redesign-plan.md`'s §5)
  equivalent here.
- **`AgendaWorkspace.test.tsx` anchors three assertions on
  `.closest(".agenda-row")`** (the `openSnoozeMenu` helper, and two direct
  uses in the project-pill test) — all three need to move to a stable
  semantic hook once `.agenda-row` stops existing. Follow
  `task-list-redesign-plan.md`'s own precedent: wrap each row in
  `<article>` and match on that, not on a Tailwind utility string.
- **The existing filter-click tests query by ARIA role and name, not by
  DOM location** (`getByRole("button", { name: "#errand" })`,
  `getByRole("button", { name: /Home/ })`) — moving the tag cloud out of
  the sidebar and into the unified filter row should not break any of
  them. Only the three `.agenda-row` selectors above need touching for
  reasons unrelated to the filter-row move itself.
- **`createTask` (`api.ts`) already accepts optional `tags`/`recurrence`
  parameters** — `TaskWorkspace`'s composer passes them, Agenda's
  deliberately doesn't (a minimal quick-add is the intended design, not a
  gap). Not in scope here; noted so nobody "completes" the parity by
  accident.
- **`app_shell.html`'s comment is already stale.** It reads "Migrated
  components (AgendaWorkspace, TaskWorkspace) still use `site.css`'s
  classes for now... Both drop once every component needing `site.css` has
  moved to Tailwind" — written before `TaskWorkspace`'s own migration
  shipped, and never updated. Fix the comment once Agenda migrates too, but
  **don't drop the `<link rel="stylesheet" href="site.css">` itself yet**:
  `ArchiveManager.tsx`'s `workspace.module.css` still references
  `var(--sl-accent)`, `var(--sl-muted)`, `var(--sl-border)`, and
  `var(--sl-bg)`, which are defined only in `site.css`'s `:root`. Dropping
  the stylesheet is gated on `ArchiveManager`'s own Tailwind migration too,
  which is not part of this brief — flagged so the natural-looking cleanup
  isn't attempted mid-slice and quietly breaks the Archive page.

## 4. Suggested implementation order (TDD per `principles.md`)

Read `frontend/src/AgendaWorkspace.test.tsx` and `frontend/src/agenda.test.ts`
first — every slice below should extend those files, not replace them.

1. **Search**, in `agenda.ts` first: add `query` to `AgendaFilters` and
   `NO_FILTERS`, extend `hasFilters` and `applyFilters`, with new cases in
   `agenda.test.ts` (currently 28 tests) covering a matching substring, a
   non-matching one, and case-insensitivity. Then wire a search field into
   `AgendaWorkspace.tsx` and add a component-level test that typing narrows
   the visible rows and updates the filter banner.
2. **Staleness label.** No new `agenda.ts` function — call
   `ageLabel(daysBetween(...))` directly in the row-rendering code. Test a
   task created 7+ days ago shows "Added N days ago" and one created more
   recently shows nothing, using the fixed `TODAY` fixture the test file
   already uses for date-sensitive assertions.
3. **Unified filter row.** Move the sidebar's tag-cloud rendering to sit
   beside the existing area chips in the main column; delete the sidebar
   "Tags" card. Re-run the existing filter-click tests unmodified first to
   confirm the role-based queries still pass (per the finding above), then
   add anything new only if a gap turns up.
4. **Tailwind visual/markup pass**, mostly markup over already-correct
   state/handlers: masthead + scope pills, composer field-chips, bordered
   rows with the overdue/today left-border accent, ≥44px targets
   throughout, sidebar cards Tailwind-ified. Wrap each row in `<article>`,
   replacing `.agenda-row`.
5. **Update the three `.agenda-row` selectors** in
   `AgendaWorkspace.test.tsx` to `.closest("article")` (see §3).
6. Full frontend suite, `tsc --noEmit`, `pnpm build`. No backend changes
   are expected anywhere in this brief — confirm rather than assume, same
   as `task-list-redesign-plan.md`'s own §4 step 6.
7. **Browser smoke pass** — warranted per `CLAUDE.md`: this is the app's
   actual landing surface, and the filter consolidation is a real
   information-architecture change, not just page content. Rebuild first
   (`pnpm --dir frontend build`) or the suite tests a stale bundle.
8. **Verify live** the same way `TaskWorkspace`'s own redesign was verified:
   `previewuser` login, driven at the DOM level (`get_page_text` /
   `javascript_tool`) per the `project_local_browser_verification` memory —
   search a real task by text, expand "No due date" and confirm an old task
   actually shows its age, and confirm the merged area/tag filter row
   narrows results the same way the old split surfaces did.
9. **Not required for this brief, worth a quick look afterward:** whether
   `app_shell.html`'s stale comment can finally be corrected, and whether
   anything else in that template assumed `AgendaWorkspace` would keep
   needing `site.css`. Do **not** attempt to drop the stylesheet itself —
   see §3's `ArchiveManager` dependency.

## 5. Status

**Shipped and deployed, August 10–11, 2026.** Committed as `0725516`
(plan/mockup) and `94a6c4f` (implementation), pushed to `main`, and
deployed to production — `LIVE` and `DEPLOYED-2026-08-10/2100` both tag
`94a6c4f`, moved only after Vince confirmed the redesign live on the real
Agenda page. The deploy itself hit a real WSL2 DNS-resolution failure in
the local Docker build step (`auth.docker.io` unreachable through the
`10.255.255.254` relay) — unrelated to this change, resolved with
`wsl --shutdown` to reset the network stack, and worth remembering if a
future deploy fails at the same "Build container image locally" step with
a similar `dial tcp: lookup ... i/o timeout` error. All nine steps landed
in order: search (`agenda.ts` + `AgendaWorkspace.tsx`),
the staleness label, the unified filter row, the full Tailwind pass,
updating the `.agenda-row` test selectors to `article`, full suites,
browser smoke, live verification, and the `app_shell.html` comment
correction. 263 frontend tests, 867 backend tests (confirmed unaffected,
not assumed), `tsc --noEmit` and `pnpm build` all green.
`manage.py test functional_tests` shows the same two pre-existing
`ProjectJourneyTest` failures already known unrelated to this work (carried
over from the TaskWorkspace redesign's own bisect) — nothing Agenda-touching
regressed, including the real smoke test that types a task, completes it,
and reopens it through the actual built bundle.

Live verification against `previewuser` caught one real bug the mocked
component tests couldn't: the search field's `w-full` collapsed to 30px
wide because it had no `flex-shrink:0` guard against the filter chips
sharing its row — fixed with `shrink-0`, confirmed 240px after rebuilding.
Verified live: search narrows results, the unified filter row shows area
and tag chips together, "No due date" tasks show real ages (7+ days on the
seeded data), and every interactive element measures a real ≥44px hit area
on the actual rendered page, not just in the mockup.

One correction beyond the brief's own scope, worth naming since it wasn't
anticipated: the original bucket-collapse implementation risk — conditionally
un-rendering a collapsed section's rows instead of just hiding them with
`display:none` — was caught by the existing test suite (`groups tasks from
every list by how soon they are due` and the `AgendaRoute` integration test
both failed) before it ever reached a browser. Fixed by keeping the rows in
the DOM and toggling a `hidden` class, matching the original CSS-only
behavior. Recorded here as a reminder that "conditionally render" and
"conditionally hide" are not interchangeable when a test — or a real
person — expects content to still be there once revealed.

`design/agenda-mockup.html` was the only artifact that existed before this
session — reviewed, iterated once to add search and staleness, and approved
both times. Committed as `0725516` (plan) and `94a6c4f` (implementation),
deployed and verified live August 10–11, 2026 — see `roadmap.md`'s own
account of this line of work.
