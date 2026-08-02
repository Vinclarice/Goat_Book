# Daily operating system — product direction

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
Capture quickly → Clarify when ready → Work from today's page
       ↑                                      │
       └────────── Review and reflect ←───────┘
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
| “Pay rent every month” | Recurring task; completion creates the next occurrence | Already supported. |
| “Follow this checklist each weekday” | Recurring parent with reusable subtasks | Largely supported; Bittern B1 fixes immediate rendering. |
| “Do five lessons today” | Daily target/routine with progress toward a count | Not yet modeled; needs a focused design. |

Five lesson sessions are neither five copied calendar tasks nor necessarily five named subtasks. **Routines and habits are their own domain**, not a variant
of `Item` recurrence. A future Routine model needs an explicit cadence, target
quantity/unit, daily occurrence/progress record, and a definition of success,
partial completion, skipped days, and historical edits. It also needs a
per-user time-zone decision before day boundaries and streaks can be trusted.
Do not misuse task recurrence to fake this before those rules are designed.

## Crane 0 — Routine and target domain design

Do this design work immediately after Bittern, before Crane implementation,
even though routine implementation follows the Daily Page foundation. The
“five daily lessons” case is a central reason Clarice exists and must not stay
as a placeholder while adjacent surfaces ship.

**Wider scope proposed and settled, August 2, 2026.** The brief below is the
routine half and stands unchanged. The proposal was that it sit inside a wider
one covering repetition generally, because recurring tasks are missing the same
template-and-occurrence shape this section designs for routines:
`_spawn_next_occurrence` writes no link back to the item that spawned it, so a
recurring commitment has no identity across its occurrences beyond a matching
text string. Nothing below is violated by that — the rules here already say not
to fake a routine with task recurrence. The point is the mirror image: the
routine half will be able to answer “how has this gone over eight weeks” and
recurring commitments will not, for the same question, unless the same shape is
designed for them at the same time. It was accepted in narrowed form: the
missing occurrence link is built before Crane 1, and the fuller template that
would move text and cadence off the task waits for release D. Both halves, and
the reasoning for splitting them, are in [`crane-plan.md`](crane-plan.md) §3.

Settle, in a focused design brief:

- A `Routine` template's owner, title, active/paused state, cadence, target
  quantity, and human unit such as “lessons” or “sessions.”
- A dated `RoutineOccurrence` record with target, actual progress, and an
  explicit completed/skipped/open outcome; history must not be recalculated
  from a routine's current settings.
- The minimum initial cadence, how a person logs one unit of progress, how
  they correct it, and what a deliberate skip means.
- The per-user time-zone model required for day boundaries, streaks, and
  weekly habit metrics.
- The boundary with tasks: a routine measures repeated practice; a recurring
  task represents one discrete commitment that creates its next occurrence.

The deliverable is a spec and acceptance examples, not a migration. Use the
lesson target, a daily exercise target, and a weekly practice target as cases.

## Crane — Daily Page foundation

Crane follows Bittern. It is deliberately sequenced after production stabilization and Android capture so the daily surface can rely on a dependable task and capture loop.

### Crane 1 — ship a small Daily Entry

- Add an owner-scoped, date-unique Daily Entry record.
- Start with plain-text or simple structured fields for intentions, gratitude, and happenings; do not build a rich block editor.
- Add a user-level **Personal Compass**: a rarely edited purpose statement and
  guiding question, such as “What is the most I can do?” Display it on the
  Daily Page, but keep it separate from that day's Intentions and do not copy
  it into every Daily Entry.
- Add a date-scoped **Daily Focus** join between a Daily Entry and an existing
  task. “Pin this to today” creates a focus record; it does not alter the
  task's due date, status, or ownership. Show the deliberate focus list above
  the broader embedded Agenda output so the Daily Page is visibly a planning
  surface on its first day.
- Give focus records an order and selection timestamp. If a person removes a
  focus, retain enough history to distinguish an intentional decommitment from
  an unfinished planned commitment in a later review.
- Make the Daily Page the authenticated home surface while preserving direct access to Agenda, Inbox, Ideas, lists, and archive.
- Design its layout for a phone from the first day rather than adapting a
  desktop layout afterwards. The existing surfaces are desktop-first with two
  lone breakpoints, so Crane is the first chance to build the home surface
  mobile-aware instead of retrofitting it. See the roadmap's mobile web
  experience entry for why the layout work waits for this rather than
  preceding it.
- Embed existing agenda output as Action Items rather than duplicating task state.
- Add a direct capture action to the page.

**Success:** opening Clarice each morning gives a useful working page without
rebuilding a template or transferring yesterday's unfinished work — and makes
the person’s chosen commitments visibly different from the rest of the agenda.

### Crane 2 — refine daily planning

- Show task age and overdue context so carry-forward is visible, not silently punitive.
- Implement routine/target behavior only after Crane 0's design has settled
  its occurrence and progress model.

### Crane 3 — weekly review and trends

Weekly review is the first planning feature after the Daily Page. Start with
one guided weekly view, not weekly/monthly/quarterly at once. It should gather:

- completed work and recurring commitments from the preceding week;
- chosen daily-focus tasks that remain incomplete, with age and due context;
- unresolved captures and recently added Ideas;
- daily intentions, reflections, gratitude, and happenings; and
- a short planning area for the coming week.

The review should show what was actually done, what was deliberately planned
but remained incomplete, and how habits performed. It should also retain a
dated review record and any explicit task changes — never automatically
reschedule everything left incomplete.

#### Metrics need trustworthy denominators

“60% finish rate” must mean *completed planned commitments ÷ planned
commitments*, not “completed tasks ÷ every task in the backlog.” The Daily Page
therefore needs a durable record of deliberately chosen focus tasks before it
can report that metric over a week. Completed work can be derived from task
completion timestamps; the planned denominator cannot be reconstructed after
the fact from a mutable due date.

Routine metrics similarly need per-day occurrence/progress records. A weekly
language-learning result should say, for example, “4 of 5 planned lesson
targets met,” and later support trend views over several weeks. It must not
infer a habit from a recurring task's current state after history has changed.

Monthly and quarterly planning can reuse the same review model at wider
windows only after weekly use proves helpful.

## Second brain direction

Capture → Idea/Reference is the beginning of the second brain, not a side
feature. Its domain logic needs its own discovery pass before more features
ship: define the boundary between an idea, reference, project, task, and
routine; decide whether links and sources are plain text or structured data;
and establish what a relationship between two ideas actually means.

Before a visual map or AI-assisted grouping, ship a cheap, human-controlled
interim step: shared topic tags on Ideas and/or a manually selected “related
idea” link. Render those connections as ordinary chips or links, not a graph.
They let real use answer whether “relates to” means a shared topic, a source,
a follow-on, or something else — and create the relationship data a later map
would need.

Only after that examine richer retrieval and resurfacing: make old references
easy to find, let exploring ideas reappear at useful moments without anxiety,
and later consider a visual relationship view or an append-only idea log. The
system needs real information volume before it guesses what deserves
resurfacing or asks AI to make those connections.

## AI comes after the practice, as assistance

AI should not be the foundation. It first needs trustworthy daily records, clear task state, and real review behavior. When introduced, it should:

- Summarize evidence already in Clarice rather than inventing a narrative.
- Suggest priorities, routines, and review prompts rather than silently changing tasks, dates, or plans.
- Show the records and time range behind each suggestion.
- Require explicit confirmation for every mutation.
- Be opt-in, with clear control over what personal data is sent to a model.

Useful first experiments are a weekly-review summary, a stale-idea resurfacing prompt, and a proposed plan for the coming week. Autonomous scheduling, opaque scoring, and automatic task editing are non-goals until the person trusts the underlying system.

## Design principles

- Reduce transfer work, not reflection.
- Keep the person in control of commitments and priorities.
- Prefer durable records over copied checklists.
- Let history be useful without making missed work feel like punishment.
- Build the manual workflow first; automate only where the pattern is stable.
- Treat privacy as part of usefulness, especially for capture and reflection.
