# The web UI's second pass — what the application says

Vince · brief · written August 3, 2026

## 1. What this is, and what it replaces

`release-d-plan.md` §4 is a deliberate sketch. It was written before §2 and
§3 had migrations behind them, and it says so: "the full brief gets written
once §2 and §3 have shipped." They have — slices 1 to 8 are in production as
of `DEPLOYED-2026-08-03/0027`. This is that brief, and it supersedes §4.

The first pass (`ui_overhaul_plan.md`, Tailwind v4 and shadcn) replaced how
the application *looks*. C2's complaint, recorded in `roadmap.md`, is about
what it *says* and what it lets you confuse. That is still the subject here.

**Written from what the code does now, not from §4's predictions.** §4 made
four predictions about what would still need design once the model changed.
Checking each against the shipped interface found one already handled, one
partly handled and quietly still broken, and two untouched — plus a fifth
problem §4 could not have anticipated, because slice 8 introduced it. Method
was reading the current source rather than using the application; that is
weaker than C2's own evidence, which came from a real person failing a real
task three times, and §6 says what would strengthen it.

## 2. What the model change already dissolved

Recorded so this cycle does not re-plan solved problems, and because it is
the evidence for the roadmap's central thesis — that the interface was
confusing *because the model was undecided*.

- **The Repeat/Repeats collision is gone by construction.** A Checklist Step
  has no recurrence field, so no control on a step's row can be mistaken for
  a task's Repeat select. Nothing was redesigned to achieve this.
- **The promote affordance is settled.** A labelled `Promote` button per
  step, which is what §4 asked for and what `subtasks-plan.md` 6d's refusal
  of cross-level drag-and-drop implied.
- **`carries_forward` is correctly gated.** It renders only when the task
  actually repeats (`{repeats && …}` in `TaskDetailRoute.tsx`), so a step
  under a non-recurring task shows nothing about carrying forward.

## 3. Findings

### F1. The two-checkbox row survived the model change

**§4 predicted this would be mechanical and it did not happen.** It said "a
single, unambiguous checkbox per checklist step (mechanical, once `is_done`
is the only boolean on the row)." On a repeating task's step row there are
still two `<input type="checkbox">` elements side by side: `is_done`, then
`carries_forward`.

C2's original words were: "A subtask row carries two checkboxes with no
visual distinction: the leading one completes the task, a later one governs
recurrence." Two of those three clauses still describe the shipped row.

What genuinely improved: the second checkbox now has a visible text label
("Carries forward") and an `aria-label`, where the old one had neither, and
it disappears entirely when the task does not repeat. That is not nothing —
it is most of why the row is no longer actively misleading. But the shape C2
objected to is intact.

**`release-d-plan.md` §5 slice 3 overstated this**, and the overstatement is
worth naming because it is how a defect stays invisible: it reports "one
checkbox for done, and a separately labelled 'Carries forward' toggle." The
labelling claim is true. The word *toggle* is not — it is a checkbox, and it
was confirmed in a browser as one.

**The fix is already in the codebase.** `components/ui/switch.tsx` exists and
`PreferencesRoute` uses it. A switch reads as a persistent setting; a
checkbox reads as "tick this when it is done." Using different control types
for the two different questions is the visual distinction C2 asked for, and
it costs one component swap.

### F2. A project is invisible everywhere a task is actually worked

**The sharpest finding, and slice 8's own doing rather than an inherited
problem.** `project` appears in exactly three frontend files: the Area page,
`ProjectsPanel`, and the task detail page.

It does not appear on the Agenda, the Daily Page, the weekly review, or the
Archive. The Agenda already renders an area pill on every task row and has
the room for a second; it renders nothing. So a person can put a task into a
project and then never see that fact again anywhere they actually work —
assignment is effectively write-only.

This is worse than a missing feature. `principles.md` asks that automations
make their outcomes visible; the same standard should hold for a person's own
deliberate act. Grouping work and then being shown no grouping teaches that
the feature does nothing.

### F3. Projects are absent from navigation

§4 asked "where Area and Project appear in navigation and the sidebar, now
that they are two concepts instead of one," and slice 8 answered only half
of it. The side nav has three groups — Views, Areas, Account. A project is
reachable only by remembering which Area contains it and going there.

This is the part of C2 that has never been addressed. C2's original complaint
was "I can't tell where things are"; B0 rendered the navigation and the
roadmap judged the complaint might dissolve. It did, for Areas. Projects
reintroduce it.

### F4. Two near-identical add affordances on the Area page

"Add a project…" (`ProjectsPanel`) and "What is next?" (`TaskWorkspace`) are
both a single text input plus a button, stacked in the same column a screen
apart. Different meanings, near-identical shapes, adjacent — the same *class*
of defect as the Repeat/Repeats collision, at much lower severity because the
placeholders differ and neither silently hides the other.

Recorded rather than scheduled. It earns work if someone actually adds a
project meaning to add a task; it does not earn a redesign on the strength of
looking similar in source.

### F5. The Area page now carries three structural actions

Rename with "Save name", "Delete area", and per-project "Delete project" —
two destructive actions with different scopes on one screen, plus a rename
that looks like an edit field until you notice the button. Worth a look when
F2 and F3 are being designed, since they change this page anyway.

## 4. What this cycle will do

Ordered thinnest first, per `principles.md`.

1. **`carries_forward` becomes a `Switch` — done, August 3, 2026.** F1. Both
   controls, not one: the step row's *and* the add form's, because they ask
   the identical question and leaving one a checkbox would trade C2's defect
   for a smaller copy of it. Guarded by a test that counts controls by role —
   one `checkbox` and one `switch` per step row — which failed with "expected
   2 to have a length of 1" before the swap. Frontend green at 225, browser
   smoke at 25, `tsc --noEmit` and the build clean.

   Every existing behaviour test passed unchanged, including the
   `toBeChecked()` assertions, because jest-dom reads `role="switch"` with
   `aria-checked` the same way. That is the evidence the swap changed the
   control type and nothing else.

   **Not viewed in a browser**, and it did not need to be: `PreferencesRoute`
   already renders this same component in production, so whether a `Switch`
   is visible in this application is a settled question rather than an open
   one. The role-based test is the substantive claim.

   **A touch-target note, named rather than fixed** — the discipline §4 asked
   for and §5 repeats. At `size="sm"` the switch is 14×24px with an `after`
   inset extending the hit area to roughly 30×48px. Wider than the checkbox
   it replaced, still short of the ~44px height WCAG 2.5.8 asks for. It
   belongs to **Mobile web experience** with the rest of the measurements,
   not here.
2. **A task shows its project wherever it shows its area.** F2. The Agenda's
   task row first, since it already has the pill pattern and the payload
   already carries `project_id`. Needs the project's title, which means the
   agenda payload grows a `projects` array beside its `areas` one — the same
   join `area_id` already relies on.

   **The Agenda half done, August 6, 2026.** `AgendaOut.projects` carries
   each of the caller's projects with an `id`, `title` and `url` — the url is
   the project's *area's*, since a project still has no page of its own
   (F3's absence, not fixed here). `AgendaWorkspace` joins it the same way it
   already joins `area_id` against `areas`, and renders a `pill-project` next
   to the area pill when a task carries one. Guarded by a test on each side:
   `test_carries_the_caller_s_projects_so_a_task_row_can_show_its_own` for the
   payload (and that it's owner-scoped, the same isolation shape every
   agenda field gets), and an `AgendaWorkspace` test asserting the pill
   renders with the right link on a task that has a project and not on one
   that doesn't. Frontend green at 226, browser smoke at 28, `tsc --noEmit`
   and the build clean, plus the Django suite at 829.

   **Viewed in the running app**, not just asserted in a test: logged into
   the same dev instance the §6 sitting used, against the same "Kitchen
   remodel" project and its tasks left over from that sitting. The Agenda's
   "Pick tile" row now shows both pills, "Preview List" and "Kitchen
   remodel", the second linking to `/areas/30/`.

   **What this does not yet touch**, named rather than silently deferred:
   the Daily Page and Archive rows F2's sitting also found silent (§8), and
   the Area page's own F2a — a project heading with no visual tie to the
   task rows under it. Each is the same join repeated on a different
   component, not a new design question, but repeating it here would make
   this entry the whole rest of step 2 rather than its first slice.
3. **Projects in the navigation.** F3, and the one that needs real design
   rather than transcription. At minimum the side nav gains projects; whether
   they nest under their Area, sit in their own group, or appear only when
   open is exactly the information-architecture question C2 raised and
   nothing has yet answered. **This should not be started by guessing** — see
   §6.
4. **The Area page's action density.** F5, once 3 has decided what that page
   is for.

## 5. What this cycle will not do

- **Touch targets.** Crane 1 slice 7 measured 32px buttons, a 20px "Edit your
  compass" link, and 19–31px on the Agenda, against the ~44px both platform
  guidelines and WCAG 2.5.8 ask for. The height lives on the shared `Button`,
  so fixing it restyles every page. That belongs to **Mobile web experience**
  in `roadmap.md`, which holds the measurements. Named here rather than
  quietly fixed, exactly as §4 required.
- **The two disagreeing breakpoints**, 760px for the side nav and 768px for
  the workspace input row. Same owner, same reason.
- **Renaming anything at the model layer.** `architecture-trajectory.md` §7's
  refusal stands; slice 5 did the vocabulary work at the boundary and there is
  nothing left owing.

## 6. The honest weakness in this brief, and how to fix it cheaply

C2 earns its authority from a real failure: one person needed three attempts
to set up one recurring parent with three children, and the interface caused
each failure. This document's findings come from reading source. F1 is solid
either way — two checkboxes in a row is a fact about the DOM. F2 and F3 are
inferences about confusion, not observations of it.

**What would settle them costs one sitting.** Release D's own features are
now in production and unused: there are zero projects on the live database,
and six Checklist Steps that a migration created rather than a person. Set up
one real project with three real tasks, from a phone, and write down every
place the answer was not where it was looked for. That is the same evidence
C2 has, it takes minutes, and it would either confirm F2 and F3 or replace
them with something better.

Until then, **step 1 was safe to build and steps 2 to 4 are not.** Step 1
fixed a defect with a DOM-level fact behind it, and has shipped. The rest
redesign navigation on the strength of a hunch, which is precisely what
`roadmap.md` tells this cycle not to do — they stay blocked on the sitting
described above.

## 7. Does this ship inside Release D?

**Recommended: no, and Release D closes at slice 8.**

Release D's stated purpose is the commitment vocabulary — what a subtask is,
what a List is, and the Project model that follows. All of it is built,
deployed and verified. Step 1 above is a small honest finish to that work and
could reasonably land as slice 9. Steps 2 to 4 are a different subject: they
are about navigation and information architecture, they are blocked on
evidence nobody has gathered yet, and holding the release open for them turns
a finished release into an indefinite one.

The alternative — declaring Release D done at slice 8, tagging it, and letting
this document become Release E's opening brief once §6's sitting has happened
— keeps the release honest about what it delivered and keeps this cycle
honest about what it still does not know.

**This is Vince's call, not the plan's.** Both options are recorded here so
whichever is chosen was chosen rather than defaulted into.

Release D shipped as Dunlin, at slice 8, on August 3, 2026 — see
`roadmap.md`. This document is Release E's opening brief, as the alternative
above anticipated.

## 8. The sitting, done — August 3, 2026

§6 asked for one thing before steps 2 to 4 could start: set up one real
project with real tasks and write down every place the answer was not where
it was looked for. That sitting happened, and F2 and F3 are now observations
rather than inferences.

**Method, stated plainly because it is not what §6 pictured.** §6 asked for a
phone. What ran instead was a local dev instance (fresh migrations, an
isolated `db.sqlite3`, the built bundle, `previewuser`) driven through a
browser held at 375×812 — the same viewport Crane 1 slice 7 and Crane 3 slice
10 used, but this session's Browser pane would not composite frames, so taps
were not literal taps. Each interaction was driven at the DOM level —
filling the real controlled inputs and dispatching the real change events
those controls listen for, then reading back the rendered page — rather than
clicking through pixel coordinates. That is sufficient for what F2 and F3 ask
— which page renders which content — and it is not evidence about tap
ergonomics or touch-target size; **Mobile web experience**'s existing
measurements are untouched by this sitting and stay exactly what they were.

**What was built**, through the real UI and nothing else: a project named
"Kitchen remodel" added to the Preview List area, three tasks created
through the ordinary "What is next?" form (Pick tile, Order cabinets,
Schedule electrician), and each joined to the project the only way the
interface offers — its own detail page's Project select, one at a time.

**F2, confirmed on every surface it named.** With "Kitchen remodel" carrying
three open tasks:

- **Agenda** — both due-date sections render each task with its area pill
  ("Preview List") and nothing else. Assigning a project produced no visible
  change here at all.
- **Daily Page** — Pick tile, given today's due date so it would appear in
  Action items, rendered with *less* context than the Agenda: no area pill
  either, only "Today" and "Pin to today".
- **Archive** — Order cabinets, moved to archive, reads "From Preview List ·
  Created …". Same omission.

**F2a, a sharper version F2 did not name.** Even the Area page itself, the
one screen that shows the project section at all, does not connect the two
halves of its own layout: "Kitchen remodel — 3 open" sits directly above the
Tasks list, and the three rows belonging to it are visually identical to the
two that do not. Knowing a task's project requires opening that task's
detail page — the same page required to set it. The project is not merely
invisible elsewhere; it is barely visible on the one page that has it.

**F3, confirmed.** The side nav has three groups — Views, Areas, Account —
across every route visited. "Kitchen remodel" is reachable from exactly one
place: the Preview List area page. There is no project heading, no listing,
no indication from anywhere else in the application that it exists.

**What this settles.** Steps 2 to 4 in §4 were blocked on F2 and F3 being
observations rather than a reading of source. They now are. The navigation
design question §6 said should not be started by guessing still has not been
answered — this sitting supplies the evidence the guess would have lacked,
not the answer itself.
