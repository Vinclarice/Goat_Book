# Daily operating system â€” product direction

## The premise

> Track the Past, Order the Present, Design the Future.

Clarice began as a Daily Entry template with action, intention, reflection, gratitude, and rapid logging in one place. It failed as a system because every useful thing had to be moved by hand: a rapid capture into a task or reference, an unfinished task into tomorrow, and a recurring commitment back onto the next day's page.

Clarice should preserve the practice and remove the clerical work. It is evolving from a task app into a private daily operating system: capture what arrives, order what matters now, retain what happened, and plan at wider time horizons.

## Product thesis

**The Daily Page is a lens over durable records, not a new place to copy them.**

- A capture lands in the Inbox without requiring a decision.
- A task remains one task until it is completed, archived, or deliberately changed; it is not copied into tomorrow.
- A true recurring commitment produces its next occurrence automatically.
- Reflections belong to their date and stay findable as a record of the day.
- Wider reviews draw from actual history rather than asking the person to reconstruct it.

The Daily Page will be the shared center of the website and, later, the mobile
experience. Bittern's Android app deliberately begins with capture alone: it
solves the highest-friction moment without prematurely duplicating the web
workflow. Its share target then makes text and links from other Android apps
available as editable capture drafts.

## The daily loop

```text
Capture quickly â†’ Clarify when ready â†’ Work from today's page
       â†‘                                      â”‚
       â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ Review and reflect â†â”€â”€â”€â”€â”€â”€â”€â”˜
```

### Capture and clarify

Any thought, errand, observation, idea, or possible commitment can be written down immediately. Capture does not ask what it is. Inbox triage later makes it a task when it needs action, an Idea/Reference when it is worth retaining, or a discarded capture when it was useful only to get out of the head.

### Order the present

The Daily Page is the main working surface. It assembles the day from the existing task system and lets the person add day-specific context:

- **Action items:** open tasks relevant today, including overdue work and recurring occurrences.
- **Intentions:** a small set of outcomes or ways of showing up; not always tasks.
- **Grateful for:** short reflective entries.
- **Happenings:** what actually occurred, useful later during reviews.
- **Rapid logging:** a direct capture affordance, especially important on mobile.

### Track the past and design the future

A review is not another task list. It is a guided view of completed work, unfinished work, stale captures, ideas, and dated reflections, plus a small set of deliberate planning prompts.

## Records and sources of truth

| Need | Durable record | What the Daily Page does |
| --- | --- | --- |
| Something actionable | `Item` task | Shows it when relevant; completion changes the task itself. |
| Something to remember or explore | Capture, then `Idea` | Offers capture and triage; never makes a fake task to hold a thought. |
| What mattered or happened today | Future dated Daily Entry | Stores the day's intention/reflection and chosen focus tasks in place. |
| Why this work matters | Future user-level Personal Compass | Displays a rarely edited purpose and guiding question without copying them into each day. |
| A repeating commitment | Recurring task today; future Routine where needed | Produces the next occurrence or shows today's target. |
| A wider planning decision | Future Review Entry | Summarizes evidence and records the resulting decision. |

1. **No manual carry-forward.** An incomplete task remains open and appears through date and age logic. Its due date is not silently rewritten at midnight.
2. **No duplicate task copies.** A Daily Entry may reference or display a task, but it does not own a checklist row that can drift from real status.

## Recurrence, routines, and targets

| User intention | Appropriate shape | Current position |
| --- | --- | --- |
| â€œPay rent every monthâ€ | Recurring task; completion creates the next occurrence | Already supported. |
| â€œFollow this checklist each weekdayâ€ | Recurring parent with reusable subtasks | Largely supported; Bittern B1 fixes immediate rendering. |
| â€œDo five lessons todayâ€ | Daily target/routine with progress toward a count | Not yet modeled; needs a focused design. |

Five lesson sessions are neither five copied calendar tasks nor necessarily five named subtasks. **Routines and habits are their own domain**, not a variant
of `Item` recurrence. A future Routine model needs an explicit cadence, target
quantity/unit, daily occurrence/progress record, and a definition of success,
partial completion, skipped days, and historical edits. It also needs a
per-user time-zone decision before day boundaries and streaks can be trusted.
Do not misuse task recurrence to fake this before those rules are designed.

## What used to be here

**Two kinds of section came out on August 16, 2026, and both had the same
problem in different clothes.**

**The Crane slice plans** â€” Crane 0's routine and target design, and Crane 1, 2
and 3's Daily Page sequence â€” described work that shipped on August 2. A shipped
plan embedded inside a standing authority is the drift engine in the one place a
file-level rule cannot reach it: nobody deletes a *section*. What they built and
what it taught is in [`roadmap-history.md`](roadmap-history.md) under *Crane*.

**The second-brain and AI-assistance sections** were superseded on August 13 and
then overtaken entirely by the merger. The knowledge core is `src/mind/` in this
repository now; its design authority is Second Mind's own
`docs/design-concept.md`. The one correction those sections had already reached
is worth keeping in a sentence: *the defect was never that Clarice lacked places
to put non-actionable material* â€” `Capture` and `Idea` existed and worked. The
defect was that the central pipeline ran `Capture â†’ Idea â†’ Task`, a promotion
path whose terminus is a task, and everything inside it inherited that direction.
Heron deleted that pipeline.

What remains below is what this document is actually the authority for: the
premise, the thesis, the daily loop, the records, and the design principles.

## Design principles

- Reduce transfer work, not reflection.
- Keep the person in control of commitments and priorities.
- Prefer durable records over copied checklists.
- Let history be useful without making missed work feel like punishment.
- Build the manual workflow first; automate only where the pattern is stable.
- Treat privacy as part of usefulness, especially for capture and reflection.
