# Release D — the commitment vocabulary

Vince · plan for the next release · drafted August 2, 2026

## 1. Purpose and scope

Release D is the first release Crane does not touch. `roadmap.md` names two
design cycles — the parent–child domain redesign and the web UI overhaul's
second pass — and `architecture-trajectory.md` §5 argues they should be
*designed* separately but **ship together**, because C2's own evidence was
one person needing three attempts to set up one recurring parent with three
children, caused by two independent defects: a model that never decided what
a subtask is, and an interface built on top of that undecided model. This
document is the brief for both, plus a third question `architecture-trajectory.md`
§5 raised and left open — what `List` is — which is decided here because it
touches the same container vocabulary the other two cycles are already
rewriting.

It does not restate `principles.md`'s delivery practices or
`architecture-trajectory.md`'s charter — both are read alongside this. Model
decided first, per `roadmap.md`'s own instruction; the UI cycle in §4 is
therefore a sketch of what the model changes make possible, not a finished
brief, and gets filled in once §2 and §3 have shipped and there is a
redesigned model to build an interface for.

**Two decisions this document answers that no prior document did**, both
raised as open in `architecture-trajectory.md` §8 and settled by Vince on
August 2, 2026 while this brief was being drafted:

- **What a subtask is: a Checklist Step**, a new model with its own life
  cycle, separated from Task — with the ability to promote one into a full
  task. Not "keep subtasks as full tasks" and not a dependent-task
  relationship; §2 is the brief for the model this implies.
- **What `List` is: an Area**, a bucket that never completes, with `Project`
  joining it as a genuinely new model for work that does. §3 is the brief for
  that.

## 2. Design cycle 1 — the parent–child domain redesign

### Why

Restated only as far as it bears on the model, since `roadmap.md` and
`architecture-trajectory.md` §5 already argue this at length. A task's
**Repeat** select sits directly above a subtask's **Repeats** checkbox —
near-identical words, opposite meanings — because recurrence had to be bolted
onto parents only and `always_recurs` onto children only, with the relation
between them left implicit. And a subtask row carries two visually identical
checkboxes, one completing the task and one governing recurrence, because
*completion* and *recurrence* were never separated as concepts on a subtask.
**The interface is confusing because the model is undecided**, and
relabelling over an undecided model moves the confusion rather than removing
it.

### The settled decision

A subtask is a **Checklist Step**: no due date, no tags, cannot recur, dies
with its parent. `Item` (Task) keeps everything it has today for root tasks.
This clears the charter's "does this earn a model" test in
`architecture-trajectory.md` §4 directly — a Checklist Step has a different
life cycle from a Task, not just a different name.

**With one addition Vince asked for explicitly: promotion.** A Checklist Step
can become a real Task. Someone starts "call the vet" as a step under "Get
the dog ready for the trip" and later realizes it needs its own due date and
should stand on its own — promotion is how that happens without deleting and
retyping it.

### The model

```python
# lists/models.py

class ChecklistStep(models.Model):
    # Charter rule 1: a direct, non-null owner rather than reaching one
    # through `task` alone. architecture-trajectory.md §4 named this exact
    # gap against the Routine/RoutineOccurrence sketch -- a two-hop owner
    # makes every isolation test a two-hop assertion, and it's cheap to get
    # right at the first migration and expensive to retrofit.
    owner = models.ForeignKey(
        "accounts.User", related_name="checklist_steps", on_delete=models.CASCADE,
    )
    # CASCADE: a Checklist Step has no existence apart from its task. This is
    # the "dies with its parent" half of the decision -- there is no
    # independent archive/restore cycle for a step the way there is for a
    # subtask today.
    task = models.ForeignKey(
        Item, related_name="checklist_steps", on_delete=models.CASCADE,
    )
    text = models.TextField(default="")
    position = models.PositiveIntegerField(default=0)
    is_done = models.BooleanField(default=False)
    completed_at = models.DateTimeField(blank=True, null=True)
    # Same question always_recurs answers today, carried over under a name
    # that doesn't collide with a task's own Repeat control -- see §4.
    # Meaningful only when `task` recurs; a step under a non-recurring task
    # simply never reads this field.
    carries_forward = models.BooleanField(default=True)

    class Meta:
        ordering = ("position", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("task", "text"),
                condition=Q(is_done=False),
                nulls_distinct=False,
                name="unique_open_checklist_step_text",
            ),
        ]
        indexes = [
            models.Index(fields=("task", "is_done"), name="step_task_done_idx"),
        ]
```

No `status` enum, no `archived_at`, no `archive_group`. A step has exactly
two states — done or not — because it never appears on the agenda in its own
right and never needs the active/completed/archived cycle a Task's own
history requires. That is what makes the two checkboxes on today's subtask
row stop being identical: a step's row has exactly one boolean to tick, and
`carries_forward` becomes a separate, differently-styled control that only
renders at all when its task recurs — never a second checkbox that looks
like the first.

**No `recurrence` field, on purpose — this is what dissolves the C2
collision rather than relabelling it.** A Checklist Step cannot recur, full
stop, so there is no control on a step's row that could ever sit next to a
task's Repeat select and be mistaken for it. The redesign doesn't need to
solve "how do we make these two controls look more different" because one of
them no longer exists.

### Promotion

```python
# lists/services.py

def promote_checklist_step(step):
    """Turn a Checklist Step into its own Task, in the same list as its
    former parent, at the end of the list's ordering. The step ceases to
    exist -- this is a state transition, not a copy, so there is exactly one
    live record of the work either way.
    """
```

- Creates an `Item` with `text=step.text`, `list=step.task.list`,
  `parent=None`, no due date, no tags, no recurrence — a plain new task,
  positioned last. The owner does whatever they were going to do with a new
  task next: add a due date, tag it, set it recurring.
- Deletes the `ChecklistStep` row. **Not soft-deleted, and no
  `promoted_from` pointer kept.** `principles.md`'s durable-history rule
  protects records of what *happened* — a completed task, a routine
  occurrence, a review's stamped counts. Promotion isn't a historical event
  in that sense; it's a correction to what something *is*, the same way
  renaming a task isn't logged. If real use says otherwise once this ships,
  adding a pointer later is additive and costs nothing today.
- `is_done` does not carry over as `Item.status`. A promoted step always
  becomes an active task — promoting something already checked off isn't a
  real scenario worth designing for, and if it comes up in practice, an
  explicit "un-tick, then promote" is one extra click rather than a second
  code path.

**Demotion is explicitly out of scope for this cycle.** Turning an existing
Task into a Checklist Step under another task would mean deciding what
happens to a due date, tags, and recurrence a step can't hold — a lossy
operation nobody asked for. New Checklist Steps are created directly under a
task ("add a step"); nothing here converts a standing task into one. If
demotion turns out to be wanted, it earns its own small brief once there's a
real case rather than a symmetric API added on the strength of promotion
alone.

### Migration — expand, migrate, contract

Per `principles.md`'s evolutionary-decisions and additive-migration rules.

**Expand.** Add the `ChecklistStep` table. `Item.parent`,
`Item.always_recurs`, and the subtask-scoped service functions
(`_duplicate_exists`, `_next_position`, the cascade logic in `complete_item`
/ `archive_item` / `restore_item`) are untouched in this step — both the old
self-FK subtask and the new model exist at once, and nothing reads the new
table yet.

**Migrate.** A data migration walks every existing `Item` with `parent_id`
set and converts it — **but not uniformly**, because `subtasks-plan.md`
settled subtasks as full tasks with their own due dates and tags, and some
existing rows may actually be using that. Checking local data found zero
subtasks carrying a due date, a tag, or a non-`NONE` recurrence — but that's
a two-user SQLite dev database, not the production evidence
`principles.md`'s "production truth beats local confidence" asks for, so the
migration has to handle the general case rather than assume the local one:

- A child with no due date, no tags, no notes, and `recurrence=NONE` becomes
  a `ChecklistStep`: `text`, `position`, `is_done` derived from
  `status=COMPLETED`, `completed_at`, and `carries_forward` from
  `always_recurs` carry straight across. The original `Item` row is deleted
  once copied — a step and a subtask are not two representations of one
  fact, and leaving both would be the two-sources-of-truth drift
  `principles.md` forbids. Every other Item FK that can point at a task —
  `DailyFocus.task`, `Idea.promoted_task`, `Capture.promoted_task` — is
  already `SET_NULL`, the same protection `delete_archived_item` relies on,
  so deleting a converted child is schema-safe even if it was ever pinned.
- A child carrying a due date, a tag, notes, or a recurrence value doesn't
  fit the new model and is **auto-promoted**: cleared to `parent=None` and
  repositioned after its list's existing root tasks, keeping the field the
  Checklist Step couldn't hold. **Notes only surfaced as a fourth trigger
  while writing the migration** — the original brief named due date, tags,
  and recurrence, and missed that `Item.notes` exists on every row including
  children; a child carrying notes would have silently lost them converting
  into a model with no notes field. This is the same shape of catch Crane 0a
  made for the parent's own notes on spawn, just found earlier this time.
  This means the migration cannot silently drop data — anything that doesn't
  fit becomes visible as its own task instead of disappearing.
- The migration prints (or logs) a count of each outcome, so running it
  against production is itself the evidence for how many of each case
  actually existed — the number this section can't state yet.

**Contract.** Once the frontend is reading and writing `ChecklistStep`
end to end (§4's UI work), remove `Item.parent`, `Item.always_recurs`, and
every subtask-shaped branch in `services.py`, `api.py`, and their tests in a
later migration. Not in the same commit as the expand step — a schema change
and the contract that retires the old path earn separate commits per
`principles.md`, and the contract step should only land once nothing reads
the old column, the same discipline Crane 0a used for `Item.commitment`.

### Charter compliance

- **Rule 1 (owned at birth).** Direct `owner` FK on `ChecklistStep`, not
  reached through `task` alone.
- **Rule 2 (public identifier for offline creation).** Not needed — no
  client creates a Checklist Step offline; this is a web/API-only surface,
  same reasoning as `RecurringCommitment`.
- **Rule 3 (snapshot what a record's meaning depends on).** Doesn't apply in
  the way it does to an occurrence — a step isn't a record of what happened
  during a period, it's a live checklist item. Nothing to snapshot.
- **Rule 4 (read and service modules from the first slice).** Checklist
  Step reads (rendering a task's steps) belong in `lists/agenda.py` or a
  sibling read function; mutations (`add_step`, `promote_checklist_step`,
  toggling `is_done`) belong in `services.py` alongside the Task functions
  they interact with — no separate app, the same way subtasks never got one,
  because a step has no life outside its task.
- **Rule 6 (state the deletion decision).** Hard delete via `CASCADE` when
  the task is deleted, stated in the model comment above. No tombstone: same
  reasoning as rule 2 — nothing offline to strand.
- **Rule 7 (index the actual query).** `(task, is_done)`, backing "this
  task's open steps," the only query this model runs.
- **Rule 8 (repeating things carry a template and occurrences).** Doesn't
  apply — a Checklist Step doesn't recur on its own; `carries_forward` is a
  flag read by the *task's* recurrence machinery, not a repetition of its
  own.

### Acceptance examples

**Setting up the C2 scenario again.** A task "Get the dog ready for the
trip" is set to repeat weekly, with three checklist steps: "Refill
medication," "Book the kennel," "Wash the travel crate." Setting the task's
Repeat to weekly changes nothing about any step's row — there is no control
on a step that could be confused with it, because a step has no recurrence
control at all. Ticking "Refill medication" done changes only that step;
nothing nearby governs whether it reappears next week, because that's a
separate, clearly-labelled toggle rather than a second checkbox in the same
row.

**Promotion.** "Book the kennel" turns out to need its own due date and a
`Travel` tag. Promoting it removes it from the checklist and creates "Book
the kennel" as its own task in the same list, active, no due date yet — the
owner then sets the due date and tag exactly as they would for any other new
task. The original task's other two steps are untouched.

**Migration, run against a database with a due-dated subtask.** A subtask
"Renew passport" carries `due_date=2026-09-01` under a non-recurring parent.
Running the data migration promotes it to a root task with that due date
intact, rather than silently dropping the date to fit the new model — the
migration's own count reports one promotion, zero silent losses.

## 3. Design cycle 2 — what `List` is

### The settled decision

`List` becomes **Area** in vocabulary: a bucket that never completes, exactly
what it already is today — owner, title, nothing else. This needs no schema
change, only the vocabulary migration `architecture-trajectory.md` §7 already
prescribes for exactly this situation: rename at the API and UI boundary,
never the Django model or app, the same call already made for `Item` →
"task". Renaming the `List` model or the `lists` app for a purely cosmetic
reason is refused for the same reason `architecture-trajectory.md` §7
refuses it for `Item` — migration churn, no behaviour change.

**`Project` joins it as a genuinely new model**, because a project completing
is a different life cycle from an area that never does — the charter test in
`architecture-trajectory.md` §4 is exactly this example, named there before
this document existed.

```python
# lists/models.py

class Project(models.Model):
    owner = models.ForeignKey(
        "accounts.User", related_name="projects", on_delete=models.CASCADE,
    )
    # Optional: a project can sit inside an Area (List) or stand alone. See
    # the reasoning below for why this is additive rather than replacing
    # Item.list.
    area = models.ForeignKey(
        "List", related_name="projects", null=True, blank=True,
        on_delete=models.SET_NULL,
    )
    title = models.CharField(max_length=100)
    due_date = models.DateField(blank=True, null=True)
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

**How a Task joins a Project — the one real open question this cycle
raises, and the recommendation below is additive on purpose.** The
straightforward-looking option is to let `Item.list` point at either an Area
or a Project. That's refused here: it would touch the FK every uniqueness
constraint and every agenda query already keys off, on a table that also has
a parent–child redesign landing in the same release. Recommended instead:
add `Item.project`, nullable, alongside the existing `Item.list`, which stays
mandatory exactly as it is today.

```python
project = models.ForeignKey(
    "Project", related_name="tasks", null=True, blank=True,
    on_delete=models.SET_NULL,
)
```

A task keeps belonging to an Area the way it always has, and can *additionally*
belong to a Project. Nothing about `unique_active_item`, the agenda's
per-list queries, or any existing test changes. If a Project turns out to
need tasks that live outside any Area, that's a `list` nullability question
for a later release, not this one — `principles.md`'s reversible-decisions
practice is exactly the argument for taking the additive shape now rather
than the more sweeping one.

### What this cycle does not decide

Whether `Item.list` (Area) itself becomes optional once `Item.project`
exists. Whether a Project needs its own recurrence (a recurring project is a
different question from a recurring task, and nothing in Clarice's use so
far has asked it). `List.owner`'s nullability was the third item here and is
no longer open — it got the separate slice this paragraph asked for rather
than being folded into the Project migration, and shipped as slice 6.

### Acceptance examples

**Area, unchanged behaviour.** Every existing List continues to behave
exactly as before — the migration touches no rows, because Area is a
vocabulary change with no schema behind it. A user renames nothing and
notices nothing except new words in the interface once §4 ships.

**A Project.** "Website Relaunch" is created as a Project inside the "Work"
Area, with a due date of September 30. Three existing tasks in "Work" are
assigned to it via `Item.project`; they keep appearing in "Work"'s task list
exactly as before, and now also carry a Project label. Marking the Project
complete does not touch any of its tasks' own status — same "reference,
never copy" rule the Daily Focus join already follows.

## 4. Design cycle 3 — the web UI overhaul, second pass

**Deliberately a sketch, not a brief, per `roadmap.md`'s "model decided
first."** The full brief gets written once §2 and §3 have a real migration
behind them, the same way Crane 2's UI decisions waited for Crane 0's model.
What's fixed here is scope and what changes by construction versus what
still needs designing.

**Dissolved by the model change, not redesigned:** the Repeat/Repeats label
collision. A Checklist Step has no recurrence control, so there is nothing
left that could sit next to a task's Repeat select and read as the same
word. This is the strongest evidence the roadmap's own thesis was right —
"the interface is confusing because the model is undecided" predicts that
fixing the model removes a defect the interface never had to be redesigned
to fix.

**Still needs real design work, once §2 ships:**

- A single, unambiguous checkbox per checklist step (mechanical, once
  `is_done` is the only boolean on the row).
- A clearly separate `carries_forward` control, visible only when the task
  actually recurs, styled so it reads as "does this repeat with the task"
  rather than a second completion checkbox.
- The promote action's affordance — a menu item, not a drag gesture, given
  `subtasks-plan.md` 6d already ruled out cross-level drag-and-drop as not
  worth attempting.
- Where Area and Project appear in navigation and the sidebar, now that they
  are two concepts instead of one.

**Explicitly not this cycle's job**, per `roadmap.md`'s own boundary:
reconciling the two disagreeing mobile breakpoints and the touch-target
measurements from Crane 1 slice 7 belong to the separate Mobile web
experience item, with its own trigger. This cycle may incidentally touch
components the mobile item also cares about (the shared `Button` component,
checklist rows) — if so, name it for that item rather than quietly fixing it
here, the same discipline Crane's own plan asked of itself.

## 5. Proposed slice sequence

Ordered thinnest usable path first, per `principles.md`, and following the
expand/migrate/contract split within §2 so no single commit both changes a
schema and removes the path it's replacing.

1. **Expand — the Checklist Step table — done.** `lists.ChecklistStep` and
   migration `0025_checklist_step`, covered by `ChecklistStepModelTest`
   (default state, owner and task relations, cascade delete with its task,
   position ordering, and the `(task, text)` uniqueness constraint while
   open). Nothing reads or writes it outside tests yet — no service, no API,
   no UI, and `Item.parent`-based subtasks are completely untouched. Full
   suite green (753 tests) after landing it.
2. **Migrate — convert existing subtasks — done.** Migration
   `0026_convert_subtasks_to_checklist_steps`, covered by
   `ChecklistStepBackfillTest`'s nine cases: a plain subtask converts and its
   `Item` row is deleted; a completed one converts as done; a due-dated,
   tagged, recurring, or noted subtask is promoted instead, keeping the
   field a step can't hold; several promotions in one list don't collide on
   position; an ownerless list's subtasks are left untouched; a root task is
   never touched. Driven through the real `MigrationExecutor`, same as
   `test_commitment_backfill.py`. **Not the same as "the old subtask UI
   keeps working until slice 4," which is what this section originally
   said** — reasoning it through while writing the migration made clear that
   claim didn't hold: leaving both an `Item.parent` row and a `ChecklistStep`
   copy alive at once would be duplicated data representing one fact, so a
   converted or promoted child's old row is gone the moment this migration
   runs. The old subtask UI has nothing left to show between this slice and
   slice 3 shipping — an acceptable gap once, given how little production
   data this touches, but not a promise repeat this pattern with. Full
   required suite green (762 tests) after landing it. **Not yet run against
   production** — that's a deploy decision, not a local one.
3. **Checklist steps end to end — done.** Services
   (`add_checklist_step`, `set_checklist_step_done`,
   `set_checklist_step_carries_forward`, `edit_checklist_step_text`,
   `delete_checklist_step`, `reorder_checklist_steps`,
   `promote_checklist_step`), the hand-rolled JSON API
   (`/api/tasks/{id}/checklist-steps/`, `/api/checklist-steps/{id}/`,
   `/api/checklist-steps/{id}/promote/`, and reorder), the `/api/v1/tasks/{id}`
   read contract, and the Task Detail page's UI. 42 new Django tests (26
   service, 16 API) plus 6 rewritten frontend tests; full required suite
   green at 804, frontend suite green at 224, `tsc --noEmit` and the build
   both clean. Verified in a real browser against a seeded task: add, toggle
   done, and promote all round-tripped correctly, and the promoted task
   appeared on the list page as a plain root task.

   `_spawn_next_occurrence` now clones every `carries_forward` step onto a
   recurring task's next occurrence, fresh and unchecked — the checklist
   equivalent of the old `always_recurs` carry-forward, without which a
   recurring task's checklist would have quietly vanished every cycle.

   **Confirmed in the browser, not just asserted in a test:** the Repeat/
   Repeats collision is gone by construction. A task with `Repeat: Weekly`
   and a checklist step underneath shows nothing on the step's row that
   could be mistaken for a recurrence control — one checkbox for done, and a
   separately labelled "Carries forward" toggle that only appears when the
   task actually repeats.

   **Two scope decisions made while building this, neither written into the
   original brief:**

   - **Detail-page UI only, not the list page's nested rendering.**
     `TaskWorkspace.tsx` (the list page) turned out to have its *own* subtask
     UI — nested rendering, an inline add-subtask form, drag-and-drop scoped
     by parent — which subtasks-plan.md 6d had always specified alongside
     the detail view and this document's original slice 3 didn't
     distinguish. Building a second full checklist-step surface there was
     out of proportion to this slice. Instead: the list page's "Add subtask"
     form is removed outright (it would otherwise keep creating the old
     self-FK shape from a screen the checklist UI never touches, reopening
     exactly the split-brain the redesign exists to close), while the
     now-inert nested-rendering and `subtask_counts` display code is left in
     place — harmless, since nothing populates it going forward, and
     slated for removal in slice 4's contract along with everything else
     `Item.parent`-shaped. Checklist management stays where
     subtasks-plan.md always said it primarily lived: the detail view.
   - **No drag-reorder UI for checklist steps.** The service and API
     (`reorder_checklist_steps`) exist and are tested; nothing in the
     detail-page UI calls them yet, because the old subtask UI never had
     drag-reorder in the detail view either — only the list page did, which
     scope decision above defers. Revisit alongside a future list-page
     checklist surface, not before.
4. **Contract — retire `Item.parent`-based subtasks — done.** Migration
   `0027_retire_subtask_fields` drops `Item.parent`, `Item.always_recurs`,
   and `Item.archive_group` (the third was vestigial the moment children
   were gone: it existed only to group a cascade archive for restore, and
   there is no cascade left to group). Every service function, API field,
   and serializer that existed only for subtasks is gone rather than left
   dead: `set_parent`, `set_always_recurs`, `_reject_invalid_parent`,
   `_lock_live_children`, `_children_to_carry_forward`,
   `annotate_subtask_counts`, `TaskParentOut`, `SubtaskCountsOut`, the
   `cascaded`/`spawned_subtasks` response fields, and the parent-scoping on
   `_duplicate_exists`/`_next_position`/`reorder_items`. `complete_item`,
   `archive_item`, and `restore_item` lost their entire cascade branch in
   the same pass — nothing left to cascade to.

   **Wider than the plan said.** The original brief scoped this to
   `lists`. In fact `daily` and `review` each carried their own hand-rolled
   `parent` breadcrumb in their own task-shaped API schemas (`FocusOut`,
   `PlannedTaskOut`, `CompletedTaskOut`) rather than reusing
   `lists.serializers.serialize_item` — a real instance of the "one
   authoritative definition" drift `principles.md` warns about, discovered
   only by grepping for every caller rather than trusting the plan's scope
   line. All three needed the same field removed independently. On the
   frontend, `TaskWorkspace.tsx` (the list page) turned out to carry an
   entire second nested-rendering implementation — parent/child grouping,
   drag-and-drop scoped by sibling group, collapse/expand, a promote button
   — that slice 3's brief didn't know existed because it only read the
   detail page. It's now a flat list, matching what the backend actually
   returns.

   **A finding that fell out of simplifying the constraint, not something
   this slice set out to do.** Dropping `parent` left `unique_active_item`
   with only `(list, text)`, neither field nullable, which means
   `nulls_distinct=False` — needed only because a nullable `parent` was in
   the fields tuple — was doing nothing. Same reasoning applied to
   `ChecklistStep`'s constraint, which never needed the flag in the first
   place; it was copied from `Item`'s without checking. Removing it from
   both lets SQLite create the constraints it was silently skipping. **The
   local suite went from 7 skipped tests to 0 in this change** — closing
   part of the gap `architecture-trajectory.md` §6 tracked as a reason to
   move local development onto Postgres; see that document's update.

   Two whole test files deleted outright (`test_subtasks.py`,
   `test_spawned_subtasks.py`) rather than left half-alive, plus the
   `ParentPayloadIsolationTest` class and the subtask section of
   `test_api.py` — all tested behavior that no longer exists. Full backend
   suite green at 721 (down from 804 as retired tests left, not from
   anything failing); frontend suite green at 207; `tsc --noEmit` and the
   build both clean. Verified live in a browser against the same seeded
   task from slice 3: list page renders flat with no console errors,
   agenda and review pages unaffected, and a full add-step →
   complete-recurring-task round trip still correctly carried the step
   onto the new occurrence, confirmed from the raw API response rather
   than just the UI.
5. **Area vocabulary — done.** API and UI, no migration, and independently
   deployable as the brief said. `lists/tests/test_area_vocabulary.py` is the
   durable guard: six cases asserting that the agenda, nav, archive and task
   payloads say `areas`/`area_id`/`area`, that `/api/v1/areas/{id}` reads,
   renames and deletes, and that the old spelling is gone. Full required
   suite green at 728, frontend at 208, the 23-test browser smoke suite green
   against a fresh build, `tsc --noEmit` and the build both clean.

   **The boundary rule this slice actually used**, since "API and UI text"
   turned out to under-describe it. Everything a person reads says Area:
   visible copy, `aria-label`s, JSON field and schema names, and URL paths
   (`/api/v1/areas/{id}`, `/api/areas/{id}/items/`, `/app/areas/{id}`,
   `/areas/new`). Everything only Python or the ORM reads keeps its old
   spelling: the `List` model, the `lists` app, Django URL *names*, locals
   like `our_list`, `agenda.list_summaries`, the `--list-color-*` CSS tokens,
   and the `name="list"` field a capture form posts to its own Django view.
   That last one is the edge case worth stating — a form field is not a
   client contract, it is the same code on both ends, so it is a kwarg rather
   than a boundary.

   **Three scope decisions made while building it:**

   - **URL paths changed, which the brief did not say.** A nav reading
     "Areas" and linking to `/app/lists/3` is the half-rename this release
     exists to remove, and the `Item` → "task" precedent renamed paths too.
     Because that breaks a saved URL, both old spellings redirect rather than
     404: `/lists/<id>/` at the Django layer and `/app/lists/:id` in the
     route table, each with its own test confirmed to fail without the
     redirect.
   - **No compatibility window on the API, deliberately.** `principles.md`
     prefers staged, compatible API changes, but that rule exists to avoid
     stranding a client and there is none to strand — the SPA ships in the
     same Django deploy, and the Android client only ever calls the capture
     API. Dual-serving both spellings would preserve the drift. The reasoning
     is recorded in the test that asserts the old route is gone.
   - **`Item.notes`-style near-miss: the model default stays.**
     `List.title` defaults to `"Untitled list"`, which reads like user-facing
     text. It is not reachable — `create_list_with_item` always supplies a
     title, falling back to the first task's text — so changing it would have
     bought a state-only `AlterField` migration for a string nobody can see,
     and cost this slice its "no migration" property.

   `daily` and `review` both needed the same field renamed independently,
   for the reason slice 4 recorded: `review.api_v1` hand-rolls its own
   task-shaped schema rather than reusing `lists.serializers.serialize_item`.
   `daily` does reuse it, and picked the rename up for free — the difference
   between the two is the argument for the shared serializer.
6. **`List.owner` non-null — done.** The small outstanding infra item from
   `architecture-trajectory.md` §6, taken now because Area is meant to be
   "owned at birth" and this release is already in the model. Two migrations:
   `0028_delete_ownerless_lists` removes the anonymous-era rows and prints
   `areas=` / `tasks=` counts, `0029_list_owner_required` makes the column
   required. Covered by `OwnerlessListRemovalTest`'s three cases — an
   ownerless area and its tasks go, an owned one is untouched, and a real
   user's Idea survives losing the task it pointed at — driven through the
   real `MigrationExecutor`, plus a model test asserting the database now
   rejects an ownerless area. Full required suite green at 731 (728 + 4 new,
   − 1 retired), frontend at 208 and the browser smoke suite at 23, neither
   of which had anything to change: `owner` was never in the API contract, so
   `openapi.json` did not move.

   **`0029` is hand-written**, not generated. `makemigrations` insists on a
   one-off default for any nullable-to-required change because it cannot know
   whether NULL rows exist; `0028` has already deleted every one, so a default
   would stand in for a case that can no longer happen.

   **Removal, not backfill.** §6 offered both. An ownerless List is
   unreachable — every read is owner-scoped — so nothing a user can see is
   destroyed, and `0023` and `0026` had each already paid for the exception
   with a skip-clause. The one way the deletion is visible to somebody who
   still exists is an Idea that pointed at a promoted task inside an orphan:
   the FK is `SET_NULL`, so the Idea survives and reads "Became a task, since
   deleted." That case has its own test rather than a note.

   **The cost landed in the tests, not the code.** One production call site
   creates a List and it always passed an owner, so `services.py` needed no
   change; sixteen tests were creating ownerless areas incidentally and now
   share a class-level owner. `test_list_owner_is_optional` was deleted rather
   than adjusted — it asserted precisely the contract this slice reverses,
   and its replacement asserts the opposite at the database.
7. **Project — model and API.** The schema in §3, with `Item.project` as an
   additive nullable field.
8. **Project — UI.** Creating, completing, and assigning tasks to a
   Project.
9. **The UI overhaul's remaining brief.** Written once 1–8 are in, per §4.

## 6. What this release does not touch

Sharing, row-level security, the audit log, time blocking, Reference/Idea
search, and rich authored content all stay where `architecture-trajectory.md`
§5 puts them — releases E and F. Mobile web's browser-wide pass keeps its own
trigger, per §4 above. Nothing here changes `RecurringCommitment` or the
routine/occurrence domain Crane 0 and Crane 2 already settled — a Checklist
Step's `carries_forward` reads the same "does this task recur" question
those already answer, and doesn't touch how the commitment or the routine
tables work.

## 7. Open questions for Vince

- **Does the recurring-commitment vocabulary half join this release?**
  `crane-plan.md` §3 deferred moving `text`, `list`, `cadence`, tags and
  notes off each occurrence and onto `RecurringCommitment` itself, because it
  needed an answer to what a subtask is first. That answer now exists —
  Checklist Step — so the collision that deferred it is gone, but this plan
  hasn't given it a slice. It's a real, separate chunk of work — a
  commitment template has to decide what it holds for a task whose children
  are now a different model entirely — and belongs either at the end of §5's
  sequence or as its own follow-up brief once §2 has actually shipped and
  there's a rebuilt subtask model to design the template against.
- ~~**Should `List.owner` becoming non-null (slice 6) ship inside this
  release, or land as its own small infra change ahead of it?**~~ **Answered
  by doing it, August 2, 2026: inside the release, as slice 6.** It cost one
  model line, two migrations and a class-level owner in sixteen tests, which
  is small enough that splitting it out would have bought a separate deploy
  for nothing. Vince made the one decision the plan could not: ownerless rows
  are **deleted** rather than backfilled onto an account.
- **Does a Project ever need to exist without an Area?** §3 leaves `Project.area`
  nullable, which already permits this — flagging only because if the answer
  is "no, every project belongs to an area," the field should be required
  instead, and that's cheaper to decide now than after the migration ships.
