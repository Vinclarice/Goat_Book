# Archive redesign — the last Tailwind migration

Vince · brief · written August 11, 2026 · **not started, handoff for a new session**

## 1. Trigger and diagnosis

Direct follow-on to `task-list-redesign-plan.md` and `agenda-redesign-plan.md`.
With `TaskWorkspace.tsx` and `AgendaWorkspace.tsx` both migrated,
`ArchiveManager.tsx` is now the *only* component left on `site.css`'s
Bootstrap-era classes, and — unlike those two — it has no Tailwind-migrated
wrapper above it either: `ArchiveRoute.tsx` renders it directly, so today
it's the one screen in the whole app with zero Tailwind on it. Asked for a
mockup of improvements as the natural next step, confirmed against the code
rather than assumed.

**Root cause, confirmed by reading the code:** same mechanism as the other
two — `ArchiveManager.tsx` uses `site.css`'s Bootstrap-era classes
(`list-panel`, `archived-task-row`, `btn btn-outline-light`,
`btn-outline-danger`) rather than Tailwind utilities, and Tailwind's
Preflight reset strips default browser chrome from every input/button that
those rules don't fully restyle back.

**Two problems, not one:**

1. **Bootstrap-era styling**, as above.
2. **Touch targets under the ~44px guideline**, measured directly against
   `site.css`: Bootstrap's own `.btn-sm` (Restore, Delete) is ~28–31px, the
   delete-confirmation dialog's plain `.btn` (Keep task, Delete
   permanently) ~32–34px. Same category of finding as the other two
   redesigns.

This is a smaller page than the other two — no bulk actions, no filtering
beyond the search it already has, no sort. The scope here is narrower on
purpose: close the migration, fix touch targets, and decide one small
wording question the mockup surfaced. Nothing else was found worth adding.

## 2. Approved design

[`design/archive-mockup.html`](archive-mockup.html) — built, reviewed, and
approved. Open it for the actual visual reference; this section is the
written record of what it shows and why.

### Approved scope

1. **Tailwind migration.** Rewrite `ArchiveManager.tsx`'s markup from
   `site.css`/Bootstrap classes to Tailwind utility classes, matching the
   heading scale `AreaRoute`/`ProjectRoute` already use (`text-3xl
   font-bold`, not the old dashboard-era `clamp(1.8rem, 4vw, 2.6rem)` this
   page alone still had). Rows become bordered cards with a gap between
   them — the same language `TaskWorkspace`'s and `AgendaWorkspace`'s own
   redesigns already settled on — replacing the single `list-panel` with
   internal row dividers.
2. **Every interactive control gets a real ≥44px hit area** — Restore,
   Delete, the search field, and the delete dialog's Keep/Delete permanently
   buttons. Visual size stays what it is today; only the hit area grows,
   same approach as the other two.
3. **The delete-confirmation dialog is restyled** to match the visual
   language of the `AlertDialog` component `AreaRoute`/`ProjectRoute`
   already use for the exact same "delete this permanently" moment. See §3
   for whether to also adopt the actual component, which is an
   implementation decision this brief flags but does not make.
4. **Row dates switch from `created_at` to `archived_at`**, worded
   "Archived `<date>`" instead of "Created `<date>`", dropped to a
   medium date-only format (matching `task-list-redesign-plan.md` item 8's
   own `formatCompletedDate` precedent) rather than the current full
   timestamp. See §3 for why `archived_at` is the correct field, not a
   style preference.

Everything else about the page — search behavior, the empty state's
copy, the restore/delete flow itself — stays exactly as it is today.

## 3. Technical findings from investigation (read once, reuse — don't re-derive)

- **This is the last piece of two separate cleanup arcs at once.**
  `workspace.module.css` (`.archiveSearch`, `.feedback`, `.error`, `.empty`,
  `.dialogBackdrop`, `.dialog`) is imported nowhere except
  `ArchiveManager.tsx` — confirmed by search. Once this migrates, **delete
  that file entirely.** And `site.css` itself is loaded by exactly one
  template, `app_shell.html` — confirmed by search across
  `src/lists/templates/` and `src/accounts/templates/`. Once
  `ArchiveManager.tsx` stops needing it, **the `<link
  rel="stylesheet" href="{% static 'site.css' %}">` in `app_shell.html` can
  finally come out**, along with the `body#app-body` background/text
  override style block that exists solely to out-rank `site.css`'s own
  plain `body` rule (see that template's own comment, corrected in
  `agenda-redesign-plan.md`'s own implementation). This is the deploy that
  actually retires `site.css` from the running app, not just from one more
  component.
- **`archived_at` is the right field, confirmed against the model, not
  assumed.** `Item`'s `CheckConstraint` groups guarantee `archived_at` is
  non-null for every row with `status="archived"` — exactly the rows this
  page ever shows — while `completed_at` is only guaranteed non-null for
  `status="completed"`. A task archived directly (never completed first)
  has `completed_at = None`. So `archived_at` needs no null-fallback here;
  `completed_at` would. Every `ArchiveManager.test.tsx` fixture already sets
  `archived_at` explicitly, confirming this reading of the constraint.
- **Rows already use `<article>`** (`ArchiveManager.test.tsx` already does
  `screen.getByText(...).closest("article")`), unlike `TaskWorkspace`'s and
  `AgendaWorkspace`'s own redesigns, which each had to introduce that
  element and update their test files to match. Nothing to change here —
  keep the `<article>` wrapper as-is and the existing row-scoped test
  queries keep working unmodified.
- **The search input is already `type="search"`** (`getByRole("searchbox")`
  already used in the test file) and already matches both task text and
  area title. No behavior change, Tailwind classes only.
- **On adopting the real `AlertDialog` component instead of the hand-rolled
  dialog** (§2 item 3's open question): `AreaRoute.tsx`'s own "Delete this
  area?" flow is the reference (`@/components/ui/alert-dialog`,
  `AlertDialog`/`AlertDialogTrigger`/`AlertDialogContent`/
  `AlertDialogAction`/`AlertDialogCancel`). Adopting it here would let
  `ArchiveManager.tsx` delete its entire hand-rolled accessibility layer —
  the `useEffect` Escape-key listener, `workspaceRef`/`deleteTriggerRef`
  focus-management, `closeDeleteDialog` — roughly 20 lines, all superseded
  by Radix's own focus trap and Escape handling. **The real risk, not yet
  verified either way:** Radix's `AlertDialogAction` closes the dialog
  immediately on click by default, while the current flow keeps it open
  showing "Deleting…" until the DELETE request resolves, and only then
  closes it (and only on success — a failed delete leaves the dialog open
  with an error). Confirm whether `AlertDialogAction`'s `onClick` can
  `event.preventDefault()` to keep the dialog open through an async action
  before committing to the swap; if it can't cleanly, restyle only (§2 item
  3) and leave the hand-rolled logic in place rather than changing
  behavior no one asked to change.
- **No backend changes anywhere in this brief.** Confirm rather than
  assume, same as the other two.

## 4. Suggested implementation order (TDD per `principles.md`)

Read `frontend/src/ArchiveManager.test.tsx` first — every slice below
should extend it, not replace it.

1. **Date field and wording**, first because it's the one behavior change:
   swap `created_at` → `archived_at`, "Created" → "Archived", full
   timestamp → medium date-only (mirror `formatCompletedDate` from
   `TaskWorkspace.tsx`, or extract it somewhere shared if a third place
   ends up wanting the exact same formatter — judgment call at
   implementation time, not decided here). Add a test asserting the new
   wording and field; update `getByText`/snapshot-style assertions that
   depended on the old "Created" text if any exist.
2. **Tailwind visual/markup pass** — mostly markup over already-correct
   state/handlers: heading scale, card-style rows, hover-reveal actions
   matching `TaskWorkspace`/`AgendaWorkspace`'s own convention, ≥44px
   targets throughout, dialog restyle (component swap only if §3's Radix
   question resolves cleanly — otherwise restyle in place). Re-run the
   full test file; `<article>` and `searchbox` role queries should need no
   changes per §3.
3. **Delete `workspace.module.css`** and drop its import from
   `ArchiveManager.tsx`.
4. **Remove `site.css` from `app_shell.html`**, and the `body#app-body`
   override style block that exists only to out-rank it — confirm the
   theme-driven background/text still wins without it (`token_styles`
   should now be the only source once `site.css` is gone). This is the one
   step in this brief that touches something other components could
   theoretically still depend on; double-check nothing else references a
   `site.css`-only class or `--sl-*` custom property before removing the
   link, even though §3's search found nothing.
5. Full frontend suite, `tsc --noEmit`, `pnpm build`. No backend changes
   expected — confirm, don't assume.
6. **Browser smoke pass** — warranted: step 4 changes what loads on every
   authenticated page, not just the Archive route, so this is exactly the
   kind of static-asset change `CLAUDE.md` calls out for the smoke suite.
   Rebuild first or the suite tests a stale bundle.
7. **Verify live**, same recipe as the other two: `previewuser` login,
   DOM-level driving (`get_page_text`/`javascript_tool`) — restore a task,
   delete one through the confirmation dialog, search by area name, and
   confirm every touch target actually measures ≥44px on the real rendered
   page, not just in the mockup.

## 5. Status

**Shipped, August 11, 2026 (uncommitted — awaiting Vince's review).** All
seven steps landed in order. `archived_at` replaced `created_at` as
planned; the formatter turned out to be wanted in exactly the third place
§4 step 1 flagged as the trigger for extracting it, so `formatShortDate`
now lives in `format.ts` and `TaskWorkspace.tsx`'s own "Completed `<date>`"
line was updated to import it too rather than keep a second copy. The
`AlertDialog` question resolved to **restyle only** — the async
close-on-click risk named in §3 was never verified safe, so the hand-rolled
dialog logic stays. `workspace.module.css` is deleted; `site.css` itself
is removed from `app_shell.html` (and the source file deleted from
`src/lists/static/`) — confirmed by search first that nothing else
referenced its classes or `--sl-*` custom properties. A genuine regression
test (`test_loads_site_css_so_reused_components_stay_styled`) asserted
`site.css`'s presence for exactly the reason it's now gone; updated rather
than deleted, flipped to assert its absence so a future reused component
can't quietly bring the dependency back. 264 frontend tests, 867 backend
tests, `tsc --noEmit`, `pnpm build`, and browser smoke all green — same two
pre-existing `ProjectJourneyTest` failures as the other two redesigns,
confirmed unrelated to this change specifically (not re-bisected, since
that's already established).

**A real, cross-component bug caught only by live verification, not by
any test:** the delete dialog's "Keep task"/"Delete permanently" buttons
measured 32px despite the ≥44px claim — `Button`'s own size variants top
out at `h-9` (36px); none reach 44px, and no component test measures
rendered layout, so this passed every automated check while being visibly
wrong. Worse: checking `TaskWorkspace.tsx` and `AgendaWorkspace.tsx` for
the same pattern found **the exact same gap in both already-deployed
redesigns** — every `<Button size="sm">` composer/dialog button in all
three components (TaskWorkspace's "Add item"/"Save"/"Cancel",
`AgendaWorkspace`'s "Add"/"Create area"/"Create project") was actually
28-36px, not the ~44px each brief claimed and each live-verification pass
reported as confirmed. Fixed in all three with an explicit `className="h-11"`
override (`Button`'s variants never reach 44px on their own); re-verified
live on the real running server, all now measure a real 44px. Full
accounting of which buttons were affected and why the earlier
verifications missed it (measured checkboxes, chips, and search fields,
never the shadcn `Button` component itself) is in
`project_archive_redesign` memory.

`design/archive-mockup.html` was the only artifact that existed before
this session — reviewed and approved. Changes are uncommitted, sitting in
the working tree for Vince's review.
