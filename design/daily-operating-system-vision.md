# Daily operating system — product direction

## The premise

> Track the Past, Order the Present, Design the Future.

Clarice began as a Daily Entry template with action, intention, reflection,
gratitude and rapid logging in one place. It failed as a system because every
useful thing had to be moved by hand: a rapid capture into a task or reference,
an unfinished task into tomorrow, a recurring commitment back onto the next
day's page.

Clarice preserves the practice and removes the clerical work: capture what
arrives, order what matters now, retain what happened, and plan at wider time
horizons.

## Product thesis

**The Daily Page is a lens over durable records, not a new place to copy them.**

- A capture lands without requiring a decision about what it is.
- A task remains one task until it is completed, archived, or deliberately
  changed; it is not copied into tomorrow.
- A true recurring commitment produces its next occurrence automatically.
- Reflections belong to their date and stay findable as a record of the day.
- Wider reviews draw from actual history rather than asking the person to
  reconstruct it.

Two rules follow, and the code cites them by name:

1. **No manual carry-forward.** An incomplete task stays open and appears
   through date and age logic; its due date is not silently rewritten at
   midnight. One item, one decision — **never automatically reschedule
   everything left incomplete.**
2. **No duplicate task copies.** A Daily Entry may reference or display a task,
   but it does not own a checklist row that can drift from real status.

And two rules about honesty in the numbers, which is where a day page is most
tempted to lie:

- A finish rate is **completed planned commitments over planned commitments** —
  the pins that were still standing when the period ended. That denominator is
  recorded at the moment of choosing, because it **cannot be reconstructed
  after the fact from a mutable due date**.
- **Habit metrics must not infer the past from a task's current state.** A page
  for a past date shows what was written, which is a real record, and no live
  work at all.

## The daily loop

```text
Capture quickly -> Clarify when ready -> Work from today's page
       ^                                        |
       +-------- Review and reflect <-----------+
```

**Capture and clarify.** Any thought, errand, observation or possible
commitment can be written down immediately, and capture does not ask what it
is. What happens to it afterwards belongs to the knowledge core, designed in
Second Mind's own `docs/design-concept.md`. The direction that matters here is
that it is *not* a promotion path: the old pipeline ran `Capture -> Idea ->
Task`, and a pipeline whose terminus is a task makes everything inside it a
task-in-waiting. Heron deleted it.

**Order the present.** The Daily Page is the main working surface. It assembles
the day from the existing task system — open tasks relevant today, overdue work,
recurring occurrences — and lets the person add day-specific context:
intentions, gratitude, happenings, and a rapid-logging affordance that matters
most on mobile.

**Track the past and design the future.** A review is not another task list. It
is a guided view of completed work, unfinished work, stale material and dated
reflections, plus a small set of deliberate planning prompts.

## Routines are their own domain

"Pay rent every month" is a recurring task: one discrete commitment whose
completion creates the next. "Do five lessons today" is not five copied
calendar tasks and not five named subtasks — it is one commitment measured
toward a quantity over a period, which is a different life cycle.

`Routine` and `RoutineOccurrence` exist for exactly that and are deliberately
unreachable from `Item`: a routine never spawns a task, and completing a task
never creates an occurrence. Do not misuse task recurrence to fake a count it
was never built to hold.

## Design principles

- Reduce transfer work, not reflection.
- Keep the person in control of commitments and priorities.
- Prefer durable records over copied checklists.
- Let history be useful without making missed work feel like punishment.
- Build the manual workflow first; automate only where the pattern is stable.
- Treat privacy as part of usefulness, especially for capture and reflection.
