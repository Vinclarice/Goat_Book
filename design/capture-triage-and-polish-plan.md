# Capture triage: task, idea, reference, or discard

Replaces Capture MVP's single undifferentiated "Clear" with four real
outcomes, now that real usage (not a two-week experiment) has settled what
the shape needs to be: promote to a task, mark as an idea worth exploring,
file as a reference note you don't intend to act on but don't want to
lose, or discard it outright because it turned out to be nothing. That
third bucket is the actual "second brain" case this feature exists for;
the fourth exists because a capture box with zero friction will catch a
lot of things that don't turn out to matter, and that's expected, not a
failure of the capture itself.

Also gives `Idea` its own lifecycle rather than leaving it a write-only
bucket once triaged -- editable text and notes at any time, its own
promotion tracking when it becomes a task, and outright deletion when it
turns out not worth keeping -- and folds in the small, independent polish
items that don't touch the triage question at all and were always safe to
build regardless of what it turned out to look like. The one real gap
this pass does not close -- how an `exploring` idea ever gets looked at
again without you remembering to go check -- is deliberately deferred;
see **Future** below.

## Why one `Idea` model, not two

"An idea I want to explore further" and "a concept I don't want to explore
but don't want to forget" are the same shape of object — text, no due
date, no done/not-done state, nothing task-like about them. They differ
only in lifecycle stage, not in structure. Modeling them as two separate
tables would be splitting one domain in half for no structural reason;
modeling them as one `Idea` with a `status` field keeps the domain honest
without inventing complexity the data doesn't need. This is the same
reasoning that kept subtasks as one `Item` self-FK rather than a parallel
model.

## Settled decisions

| Question | Decision |
| --- | --- |
| Resolution outcomes | `task`, `idea` (with a status of `exploring` or `reference`), or `discarded`. Every resolved capture becomes one of these and the record says which. |
| Idea data model | One `Idea` model with `status`, not two models. |
| Idea due date / done state | None, ever. If it becomes actionable, it gets promoted to a task. |
| Capture discard: soft or hard | Soft. The `Capture` row stays, `resolution = discarded`, nothing created from it -- consistent with keeping a trace of what happened to every capture, and it's what makes discard undoable like the other outcomes. |
| Idea deletion | Hard, immediate, no soft-resolve trail. Different from Capture's discard on purpose: by the time something is a distinct Idea record you're actively managing it, not triaging a queue, so it doesn't need the same undo-able trail a fast-moving inbox does. |
| Idea promotion tracking | `Idea` gets its own `Status.PROMOTED` plus a `promoted_task` FK, mirroring how `Capture` already tracks what it became. A promoted idea's row survives (not deleted), so the Capture -> Idea -> Task lineage stays traceable end to end even though each link only tracks one hop forward. |
| Idea editing | Text and notes editable anytime while not yet promoted. Locked once promoted -- the task is the live record at that point, and further changes belong there. |
| Idea notes | Yes -- a plain-text `notes` field, same shape and rationale as `Item.notes` (no Markdown, same reasoning: a renderer and an XSS surface for little gain at this scale). |
| Ideas page search | Basic substring search ships in this pass, not deferred to Later. `reference` ideas are meant to sit for a long time and be found again -- a reference archive nobody can search fails at the one thing it exists for. |
| Traceability | `Capture` gets a `resolution` field plus two nullable FKs (`promoted_task`, `promoted_idea`) recording what was created from it -- null on both for a discard. `on_delete=SET_NULL` throughout, so deleting a downstream task or idea later doesn't silently erase what the history says happened. |
| Browsing ideas afterward | The Ideas page (below), filterable by status. Without it, "reference so I don't forget" isn't actually true. |
| Tags on ideas | Not yet. Same minimalism the original MVP shipped with. |
| Resurfacing `exploring` ideas / relating ideas to each other | Deliberately deferred -- see **Future** below. Both point at the same eventual work, so they're tracked together rather than as two separate loose ends. |

## Model

```python
# capture/models.py
class Idea(models.Model):
    class Status(models.TextChoices):
        EXPLORING = "exploring", "Exploring"
        REFERENCE = "reference", "Reference"
        PROMOTED = "promoted", "Promoted"

    owner = models.ForeignKey(
        "accounts.User", related_name="ideas", on_delete=models.CASCADE
    )
    text = models.TextField()
    notes = models.TextField(blank=True, default="")
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.EXPLORING
    )
    created_at = models.DateTimeField(auto_now_add=True)
    promoted_task = models.ForeignKey(
        "lists.Item", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+",
    )

    class Meta:
        ordering = ("-created_at",)


class Capture(models.Model):
    ...  # existing fields unchanged
    class Resolution(models.TextChoices):
        TASK = "task", "Task"
        IDEA = "idea", "Idea"
        DISCARDED = "discarded", "Discarded"

    resolution = models.CharField(
        max_length=20, choices=Resolution.choices, blank=True
    )
    promoted_task = models.ForeignKey(
        "lists.Item", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+",
    )
    promoted_idea = models.ForeignKey(
        "Idea", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="+",
    )
```

The two `promoted_task` FKs (one on `Capture`, one on `Idea`) answer
different questions. Capture's says "did this raw thought become a task
directly." Idea's says "did this idea, once it existed as its own thing,
later become a task." A capture that went Capture -> Idea -> Task has both
set at their respective hop: `Capture.promoted_idea` points at the idea,
`Idea.promoted_task` points at the task, and `Capture.promoted_task` stays
null the whole time -- it never became a task directly.

Migrations: `capture.0002_idea` (model, including `notes` and
`promoted_task` from the start), `capture.0003_capture_resolution` (the
three new fields on `Capture`) -- all additive with defaults, no data
migration, same shape as `lists.0019_item_notes`.

## Triage actions

Three POST views replace the single `resolve_capture`, unchanged from the
previous revision:

- **`promote_to_task(capture_id, list_id)`** -- creates an `Item` via
  `lists.services.create_item` using the capture's text verbatim; due
  date/tags get set afterward through the normal task UI. Sets
  `capture.resolution = TASK`, `capture.promoted_task = <new item>`,
  `capture.resolved_at = now`.
- **`promote_to_idea(capture_id, status)`** -- creates an `Idea` with the
  given status. Sets `capture.resolution = IDEA`,
  `capture.promoted_idea = <new idea>`, `capture.resolved_at = now`.
- **`discard_capture(capture_id)`** -- sets `capture.resolution =
  DISCARDED`, `capture.resolved_at = now`, creates nothing.

Four buttons per capture row in the Inbox: Task / Explore / Keep for
reference / Discard.

Two more actions live on the Idea side, reachable from the Ideas page
rather than the Inbox:

- **`promote_idea_to_task(idea_id, list_id)`** -- creates an `Item` via
  the same `create_item` service, using the idea's text, and carries its
  `notes` across into the task's own `notes` field so thinking already
  recorded isn't lost. Sets `idea.status = PROMOTED`,
  `idea.promoted_task = <new item>`.
- **`delete_idea(idea_id)`** -- an immediate, hard delete. No soft-resolve
  step and no undo -- see **Undo** below for why that's a deliberate
  asymmetry with the Capture-side actions.

## Undo

Same shape as undo elsewhere in this app already -- the agenda's inline
undo, and the subtask cascade's `_cascaded` response field that undo reads
to know exactly what to reopen. Applies to the three Capture-side
outcomes: reversing means clearing `resolution`/`resolved_at` (and, for
task or idea, deleting the created row and clearing
`promoted_task`/`promoted_idea`), putting the capture back in the inbox
exactly as it was.

**Idea deletion does not get this treatment.** By the time something is a
standalone `Idea` you're actively managing it, not moving it through a
queue, and "not worth keeping" is meant to be final the way archiving a
task isn't. Worth revisiting if that turns out to feel too final in
practice, but it's a deliberate choice here, not an oversight.

## Ideas page

A view listing every `Idea` owned by the current user, defaulting to
`exploring` and `reference` -- a promoted idea drops out of the default
view once it's become a task (the task is the live record at that point),
though its row isn't deleted and stays reachable for history.

- Filterable by status (`exploring` / `reference`).
- Substring search over `text` and `notes` (`?q=`, `icontains`) --
  shipping now, not deferred; see the settled-decisions note on why
  `reference` needs this sooner than the Inbox did.
- Edit `text` and `notes` inline, any time, while not yet promoted.
- Promote to a task (a list picker, same shape as the Capture-side
  promotion).
- Delete outright -- immediate, not undoable.

## Also incorporating now -- independent of triage, safe regardless of how it landed

- **Edit a capture while unresolved.** A form + view with the same guard
  shape as `edit_item`'s `InvalidTaskTransition` -- here, raise once
  `resolved_at` is set. Fixes the "typo, can't touch it" gap. (Idea
  editing has its own, less restrictive rule -- see Ideas page above --
  since an idea has no resolved state to guard against, only a promoted
  one.)
- **A staleness signal on the Inbox.** Oldest unresolved capture's age
  (or just the count the nav badge already computes), surfaced on the
  page itself.
- **Substring search on the Inbox.** `?q=`, `text__icontains` -- cheap
  now; full ranked Postgres full-text search stays a `Later` item until
  there's enough volume that ranking, not just filtering, starts to
  matter.

## Non-goals for this pass

- No agenda integration for ideas -- still a Vision-layer item, still
  undesigned.
- No automatic resurfacing of `exploring` ideas, and no idea-to-idea
  relationships or linking -- see **Future** below.
- No tags on ideas.
- No API/Android surface for triage or idea management.
  `design/capture-api-and-tokens-plan.md` only covers *writing* a capture
  from an external client; triaging one and managing ideas both stay
  browser-only, same reasoning as the original MVP scope.
- No retention/cleanup policy for discarded captures. Revisit only if the
  table's size ever actually becomes a problem worth solving.

## Future -- resurfacing and relating ideas

Two open threads that turn out to be the same underlying problem: how
does an `exploring` idea ever get looked at again without you remembering
to go check, and how do ideas relate to each other once there are enough
of them that two entries are obviously connected but nothing in the
system knows that.

The instinct so far points toward something more visual than a filtered
list -- a mind-map-style view of ideas and how they relate, possibly with
AI-assisted sorting or clustering doing some of the connecting work
rather than requiring manual tagging or linking. Both directions are
genuinely further out and deliberately not designed here: they need their
own design pass once there's enough real idea volume to know what
"relates to" should even mean in this data -- the same reason Capture MVP
itself waited on real usage before this triage model got designed around
real captures instead of a guess.

In the meantime, the substring search on the Ideas page above is at least
a way to deliberately go looking, even without anything automatic doing
the resurfacing for you.

## Tests to add

- Ownership isolation for `Idea`, matching A3's pattern for Task/List: an
  intruder can't read, edit, delete, or promote another user's idea by
  id.
- Ownership isolation for the two new Capture actions
  (`promote_to_task`/`promote_to_idea`) and `discard_capture`, extending
  the existing isolation suite the same way subtasks extended it for
  `parent`.
- `promote_to_task` creates an `Item` owned correctly, in the specified
  list, and sets `capture.resolution`/`promoted_task` correctly.
- `promote_to_idea` creates an `Idea` with the given status and sets
  `capture.resolution`/`promoted_idea` correctly.
- `discard_capture` sets `resolution = discarded` and creates nothing.
- Each triage action rejects (or safely no-ops on) a second attempt
  against an already-resolved capture.
- Undo correctly reverses each of the three creating/discarding outcomes:
  deletes the created row where one exists, clears
  `resolution`/`resolved_at`/`promoted_task`/`promoted_idea`, and the
  capture reappears in the inbox unchanged.
- Idea `text`/`notes` are editable while `exploring`/`reference`, rejected
  once `promoted`.
- `promote_idea_to_task` creates an `Item` carrying the idea's text and
  notes, and sets `idea.status = PROMOTED`, `idea.promoted_task`
  correctly.
- Deleting an `Idea` that a `Capture` had promoted into
  (`Capture.promoted_idea`) leaves the capture's own `resolution`
  untouched and its `promoted_idea` FK null (`SET_NULL` doing its job) --
  the capture's history still says "became an idea" even after that idea
  is gone.
- Ideas-page search is scoped to the current user only -- a substring
  match doesn't surface another user's ideas.
