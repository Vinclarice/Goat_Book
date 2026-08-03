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

1. **`carries_forward` becomes a `Switch`.** F1. One component swap in
   `TaskDetailRoute.tsx`, its existing tests updated for the control type.
   Closes the last clause of C2's original evidence that is still true.
2. **A task shows its project wherever it shows its area.** F2. The Agenda's
   task row first, since it already has the pill pattern and the payload
   already carries `project_id`. Needs the project's title, which means the
   agenda payload grows a `projects` array beside its `areas` one — the same
   join `area_id` already relies on.
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

Until then, **step 1 is safe to build and steps 2 to 4 are not.** Step 1 fixes
a defect with a DOM-level fact behind it. The rest redesign navigation on the
strength of a hunch, which is precisely what `roadmap.md` tells this cycle not
to do.

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
