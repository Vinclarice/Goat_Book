# Superlists 2.0 — the day, the list and the log — focused spec

Vince · focused spec · written September 3, 2026 · **status is the strikes
below**

**What it is.** The task core rebuilt around one page: the list you chose for
today, a line under it, and the log of what actually happened, with every open
line you have in one pool beside it. Areas, priorities and manual ordering go.
An appointment gets its own record. The log is the task core's first intake
pipe into the knowledge core that carries content rather than only facts.

**Where it came from.** Vince, September 3, 2026: *"I want to redesign the
superlist core as I realize it's not really something I'm going to use."* The
shape that survived a morning of alternatives is the one he already ran on
paper — *"just had a list of things to do and crossed them out as I went, but
being paper it became tedious because it got spread out quickly."* Paper's
failure was spread, not the practice. This keeps the practice and fixes the
spread.

**What it replaces.** The Day page and the Agenda, both retired into one page;
Areas as a filing step; priority; the pipeline that made every arriving thought
a task-in-waiting. **What it keeps** is most of the schema, because the schema
had already half-moved — see *What is already there*.

**Reviewed the day it was written.** Vince brought eight edge-case points to it
on September 3, 2026, and all eight are folded in below rather than listed
apart: the name (*bounded*, not *closed*), what draws the line (D7, answered),
an existing pool line joining below it, empty and unlogged days, reopening
without erasure, fixed commitments against the chosen set, the composer's
default (D9), and the numbers describing rather than grading. Two of them
found something wrong rather than missing, and each says so where it lands.

**Not a module.** [`modules.md`](modules.md) governs surfaces that add a lens
over work they do not own. This is the task core's main surface, which owns its
work, so [`daily-operating-system-vision.md`](daily-operating-system-vision.md)
is the authority it answers to and `modules.md` is not. Its two rules — no
manual carry-forward, no duplicate task copies — are kept whole below.

## The design, as rules

Twelve rules. Each is stated once here and cited from the code rather than
restated.

**The word is *bounded*, not *closed*.** Forster's *closed list* means nothing
can be added, and this is not that: the morning's set is protected and the day
can still take things in below it. Calling it closed would have every reader
expect the wall the design deliberately does not build. *The bounded list*, or
just *the line*, from here on.

1. **One pool.** Every open line the owner has, in one list, with no Area. Two
   kinds of line: **floating**, which has no date and cannot be overdue because
   nothing was promised, and **fixed**, which has a due date. Age is shown as a
   fact — *added 40 days ago* — never as debt.
2. **The list is written *for* a day, never *on* it.** The morning's pick comes
   from the pool, or was made the evening before. It is finite because it was
   made before the day started.
3. **The first act of execution draws the line.** Ticking a chosen task, or a
   Did or Today line from the composer. A Note, a Pool capture, an appointment
   passing and every other derived event do not — otherwise capturing an early
   thought would finish the morning's planning by accident. Mechanical rather
   than a button, so it cannot be forgotten: the only way to avoid it is to
   execute nothing all day. Nothing more can join *above* it after that.
4. **The line is a boundary, not a wall.** What joins later — done on the spot,
   or added to do later today — sits *below* it, visibly, and is counted apart.
   Forster's strict closed list was tried in the mockup and rejected by Vince
   the same morning: *"one thing I will stray from is that I can add things to
   the list."* The finish rate divides by what was chosen; what joined later is
   the unplanned count, and a day with three chosen and four unplanned done is
   a good day this can say so about. **An existing pool line can join below
   the line too**: finding it at noon and choosing *Today* gives it a pin whose
   `selected_at` is after `list_closed_at`, which is all *below* means. The
   composer is not the only door.
5. **A tick is a log line with a time.** The list and the log are the same rows
   read from two ends. Nothing is copied — charter rule 5.
6. **The log is a read, not a table.** Written lines are `Node`s; derived lines
   are task completions, routine occurrences, bill payments, appointments that
   passed, and pins — every one of which already carries a timestamp. No new
   model holds the log. **Derived task lines are read from the life-event log,
   not from the task's current fields.** Unticking clears `completed_at`; the
   log must not lose the completion with it. `mind.EventType` already carries
   `TASK_COMPLETED` and `TASK_REOPENED` as separate append-only rows, so the
   log shows *done at 14:02, reopened at 14:05*, and what actually happened
   never changes retroactively. A read from `completed_at` would have been the
   bug, and the mockup had it.
7. **Leftovers get one decision each, never a move.** Tomorrow, back to the
   pool, or let go. The vision document's first rule, unchanged: *never
   automatically reschedule everything left incomplete.*
8. **The pool prunes itself.** A floating line unpicked for a stated number of
   days asks one question — *still want this?* — and *let go* archives the task
   and retires its facet while the node stays. Paper could not drop a task
   without losing the idea. This can.
9. **A fixed commitment is never invisible for not having been chosen.** A
   task due today, a bill due today and today's appointments appear in a
   *fixed today* strip above the list whether or not they were picked. Being
   picked is what puts a dated task in the chosen denominator; not being picked
   never hides it. `draft_day` already proposes dated work first, so the
   morning pick sees them before anything else.
10. **Choosing nothing is a valid day.** An empty bounded list is a fact about
    the morning, not a failure, and a list of zero has **no finish rate** —
    `None`, never `0%`, on the precedent of `typical_day_for` returning `None`
    below its evidence floor because *no evidence* and *nothing done* call for
    different responses.
11. **A past day is read-only, and the line not drawn stays not drawn.** No
    pin, tick or composer line can be added to a day before today. The freeze
    is derived from the date, not written: `list_closed_at` stays null for a
    day nothing executed on, because *the line was never drawn* is the fact
    S5 already insists on keeping — *a day nobody answered closes unclosed,
    which is itself a record*. Writing a midnight timestamp into it would be a
    row a read could have produced.
12. **The readback describes; it does not grade.** The finish rate, the
    below-the-line count and the leftovers explain the shape of a day. No
    streak, warning, badge or success colour derives from any of them — the
    S3 precedent, where a test asserts the scolding phrasing is *absent*. This
    is what keeps the page from becoming another source of task guilt, which is
    the failure that retired the paper list's successors.

## What is already there

Checked in the tree on September 3, 2026, before this was written. The
redesign is cheaper than it reads because four of its moves were made for other
reasons in August.

- **A task may already stand with no Area.** `Item.list` has been nullable since
  August 14, 2026 and `Item.owner` is direct, so the pool is a query over rows
  that exist — every active `Item` for the owner — with no migration.
- **Pinning to a date already exists.** `daily.services.pin_task(owner, day,
  task)` takes the day, and `DailyFocus` records `selected_at`, `released_at`,
  `task_text` snapshotted, and whether the pin came from a draft. Tomorrow's
  list is `pin_task` with tomorrow's date.
- **The task core already writes facts into memory.** Since `nightjar`, August
  22, `mind.EventType` carries `TASK_COMPLETED`, `TASK_REOPENED`,
  `TASK_ARCHIVED`, `COMMITMENT_CHANGED`, `COMMITMENT_ENDED`, `FOCUS_PINNED`,
  `FOCUS_RELEASED`, `WEEK_REVIEWED`, `INTENTION_SET` and `OUTCOME_CHOSEN`, and
  `clarice/recall.py` reads across both cores by time. Every tick and every
  pick already lands on memory's time axis. What does not flow is *content*,
  and that is what rule 6 adds.
- **A node, a facet and a task are already written in one transaction.**
  `mind.services.confirm_actionable` does it, keeps the node rather than
  consuming it, and takes an optional Area precisely so accepting a commitment
  asks no filing question. The composer below is this function with switches.
- **The calendar is a view over what exists**, shipped August 20 — tasks by due
  date, routines, bills, no model of its own. An appointment joins it as a
  fourth source.
- **An event already earns a model.** [`clarice-v3-plan.md`](clarice-v3-plan.md)
  argued it against §4 on August 20: *it happens at a time whether or not you
  act, and is never completed.* This plan builds it and calls it
  `Appointment`; the name is D1.
- **A bill is no longer an `Item`**, since September 1, so a bill due today is a
  fixed line drawn from `money`, not a pick. Only an `Item` can be picked.
- **The Day page already reads the day's writing for commitments** and proposes
  facets with cited spans. That producer is kept and pointed at reflection
  only — D5.

## The page

[`day-mockup.html`](day-mockup.html) is the page, and **this plan owns that
file**: its three moments — morning picking, midday with the line drawn, evening
leftovers — are the acceptance for increments 2, 3, 4 and 5 respectively. The
mockup was drawn before this plan and iterated twice on Vince's reading of it;
the below-the-line section and the whole-pool link are both his corrections.

Top to bottom: the appointments strip, with what is coming up; the chosen list;
the line, with the weekday's standing order under it; what joined below the
line; the log, newest at the bottom; one composer. Beside it, the head of the
pool — fixed lines in the next week, today's arrivals, the oldest floating
lines — linking to the whole pool as its own page.

**The pool is a panel *and* a page.** Vince: *"I like the panel but also I'd
perhaps like a second page with the entire list."* Both read the same query, so
neither is a copy of the other. On a phone the panel collapses to the link.

## The composer

One box. Two questions decide where a line goes — *is it done?* and *is it for
today?* — so there are four destinations and one existing service:

| Destination | `Node` | Facet and `Item` | Pin | Completed |
|---|---|---|---|---|
| **Note** | yes | no | no | — |
| **Did** | yes | yes | below the line | yes |
| **Today** | yes | yes | below the line | no |
| **Pool** | yes | yes | no | no |

Every line is a `Node` first, which is what makes the log an intake pipe: a
line is searchable, mentionable and proposable the moment it is written. The
morning pick is the same facet confirmed with a pin *above* the line — a pin
whose `selected_at` precedes `list_closed_at`. **Above or below is not a
field**; it is a comparison of two timestamps the tables already carry.

**Which destination the box defaults to is D9**, not a settled fact. The first
draft said Did. The objection is that Did creates a completed task for every
line, so the task history fills with things that were never commitments, and
**capacity reads it**: `typical_day_for` is computed from `DailyFocus`, so a
day of eight Did lines would raise what a *typical day* holds and quietly hide
over-commitment on the next draft. Two consequences, and the second is a rule
whatever D9 decides: **capacity and the finish rate count above-the-line pins
only.** Below-the-line pins are reported, never used as evidence of what a day
can hold.

The phone gets all of this through `/api/v1/capture`, which it already calls,
with the destination as one optional field defaulting to Note. Its offline
queue is untouched.

## Appointment

Vince, September 3: *"I think an appointment should have its own model. This
should include events such as me going to Dutch Wonderland this weekend."*
That example settles the shape — no time, two days, attended rather than
finished — so the record holds a **span with an optional time of day**, not an
instant.

```text
Appointment
  owner            non-null, direct                       rule 1
  public_id        uuid, client-suppliable                rule 2
  text
  starts_on        date, required
  ends_on          date, null means one day
  starts_at        time of day, null means all day
  ends_at          time of day, null
  location         text, blank
  notes            text, blank
  cancelled_at     null unless called off
  deleted_at       null unless removed                    rule 6
  created_at, updated_at
  index (owner, starts_on)                                rule 7
```

**Dates and a separate time, not an aware datetime.** The Day page is keyed on
the owner's local date decided at the request boundary; an all-day event stored
as midnight UTC lands on the wrong day away from Greenwich, and a weekend stored
as two instants is a pair of datetimes pretending to be two dates.

Against [`architecture-trajectory.md`](architecture-trajectory.md) §4, rule by
rule, so the charter is pointed at rather than paraphrased:

- **1, owned at birth** — direct, non-null, first migration.
- **2, public identifier** — included now, because the Android full-client
  direction is live in [`roadmap.md`](roadmap.md) and identity cannot be
  retrofitted.
- **3, snapshot** — nothing external to snapshot; text, span and location are
  the record's own meaning. If `location` later references a place concept,
  the name is copied at that point.
- **4, reads and services from the first slice** — its own Django app, on the
  `routines` precedent, and **added to the CI app list and `CLAUDE.md`'s test
  line in the same commit**, or the guards catch it.
- **5, reference never copy** — the day reads appointments for its date live;
  nothing is written onto `DailyEntry`.
- **6, deletion** — two states with two meanings. *Cancelled* is a fact about a
  life and stays visible on its day, struck. *Deleted* is a typo, soft, and is
  the tombstone rule 2 requires. No hard delete outside `purge_account`.
- **7, index the query** — owner and start date serves the day, the week ahead
  and the pool's fixed lines.
- **8, template and occurrences** — **deliberately not in the first cut.** A
  weekly standup wants a series template; the nullable foreign key it needs is
  added when one exists, and nothing above changes to allow it.

Where it appears: the pool's fixed lines, not pickable and not completable; the
day's strip, on every day of its span; the calendar, as a fourth source; the
log, as a derived line when its start passes — **whether you went is a line you
write, not something inferred**, and a cancelled one produces no log line.

## What stays, what goes

| Today | Under this plan |
|---|---|
| `Item` | Stays, as the line. Loses `list` as a filing step, `priority`, `position`. |
| `List` (Area) | Retired from the interface — D3 decides the table. |
| `Project` | Leaves the day and the pool; its Decide-loop stories are *works* and untouched — D3. |
| `DailyFocus` | Stays and becomes the centre. |
| `DailyEntry` | Stays, plus one `list_closed_at`. Its three prose fields are D5. |
| `Routine` | Stays; it is where rules go rather than the list. |
| `ChecklistStep` | Stays, for procedures later. |
| `RecurringCommitment` | Narrows to acts that need a line on a date. Bills already left. |
| `Tag` | D4. |
| Day route, Agenda route | Retired into the new page, with redirects. |
| Archive route | Stays — *let go* lands there. |
| Calendar route | Stays, gains appointments. |

## Second Mind

Two pipes, one in each direction, and the finding that shaped both is in
[`product-stories.md`](product-stories.md) *The three loops*: memory's intake
was capture and the journal, and the task core, which records most of what
happens, was not one. `nightjar` answered the *facts* half. This answers the
*content* half by rule 6, and gets the rest of the knowledge core's machinery
without further work:

- **Mentions.** *Neighbour asked about the fence* links a person and a place.
  Over a month the log becomes the graph's main source of people, places and
  activities.
- **Proposals.** A Note that reads like a commitment gets an actionable facet
  proposed with its cited span, by the capture producer that already exists.
  Accepting it is the Pool destination after the fact.
- **Letting go keeps the thought** — rule 8. The someday pile becomes nodes
  whose commitment was released, not a third list.
- **Attendance.** `recall.attendance_between` counts days the log holds
  anything for. A day you logged is a day you were present, whether or not the
  list finished.
- **Appointments** emit their own life events and mention their place and
  people — the first task-core record to link into the graph, which is D6 and
  its own increment.

Coming back: a pool line shows the note it came from through the facet's
backlink and what came of it since through `recall.since`; the morning pick is
retrieval in *planning* mode, which `mind/retrieval.py` already distinguishes;
the awareness half of the daily brief gains log lines as evidence; the weekly
review reads the week's log as prose beside its numbers.

## Increments

Vertical slices, in order. Each is struck here with its date in the commit that
ships it. **Nothing is deleted until increment 8, and nothing in 1–7 depends on
a deletion.** The manual week is numbered 0 because it costs no code and is the
cheapest evidence there is, not because it gates 1 and 2.

0. **The manual week.** Vince's, not code. Pin once in the morning and never
   again above the line; log through the day with the existing capture box;
   work from the flat open list rather than Areas. At the end of the week, the
   question is which of the page's sections got used, and that is the order
   for 3–7. [`daily-operating-system-vision.md`](daily-operating-system-vision.md):
   *build the manual workflow first.*
1. ~~**The pool, as a read and a page.** `lists/agenda.py`, the task core's
   query module, gains the flat open list: fixed lines by date with bills and appointments interleaved, floating
   lines oldest first, age as a label, search. A route at its own address. No
   write path yet; nothing retired.~~ **Shipped September 3, 2026.**
   `agenda.pool_for`, `GET /api/v1/pool` and `/app/pool`, in the Views nav
   beside the Agenda. Appointments are the one thing named here that is not in
   it, because increment 7 is what builds the record; the fixed row is tagged
   with its `kind` so a third variant joins without either existing one
   changing. Two decisions the plan left open and the code had to close: a
   bill sorts *before* a task on a shared date, stated in `POOL_ROW_KINDS`
   rather than left to whichever query was concatenated first; and the search
   is a substring that keeps the pool's order rather than `lists.search`,
   which ranks and would rearrange the list you were pointing at as you typed.
   Age says *added today* on every floating line, where the Day page's
   `AGE_WORTH_MENTIONING` threshold would say nothing — one phrasing,
   `ageSentence`, with `ageLabel` now calling it.
2. ~~**Pick to a date, and the line.** `DailyEntry.list_closed_at`, set by the
   first act of execution — rule 3, D7 answered. The day's read splits pins by
   `selected_at` against it; `typical_day_for` and the finish rate read
   above-the-line pins only; a zero-pin day yields `None`. `pin_task` to
   tomorrow from the pool page, and `pin_task` to today after the line from an
   existing pool line, which lands below it. `pin_task` and the composer refuse
   a past day. The *fixed today* strip, rule 9.~~ **Shipped September 3, 2026**,
   with three things different from the text above and one deliberately left.

   **The refusal is at the endpoint, not in `pin_task`.** Written there first,
   it made the service unable to write history — which is what sixty tests
   across `daily`, `review`, `lists` and `clarice` use it for, because *on
   August 3rd I pinned this* is a fixture rather than a defect. Rule 11 is
   about what a person may add to a day they are looking at, and
   `daily.api_v1`'s two pinning endpoints are the only door to that; both
   already hold the request's own `today` in the owner's zone, which the
   service would have had to read from the clock. `pin_task`'s docstring
   carries the reasoning and `test_the_line.py` holds both doors.

   **Ticking a task nobody chose leaves the list open.** Rule 3 enumerates —
   *a tick on a chosen task, or a Did or Today line* — and an unchosen tick is
   on neither list. Narrow on purpose, and the first thing to revisit if the
   line turns out to be drawn too rarely; the site says so.

   **A zero-pin day needed no new code.** `typical_day_for` already skips a day
   whose `planned.total` is zero rather than averaging in a nought, and a day
   whose whole list joined below the line now has a total of zero — so rule 10
   arrives as a consequence of the denominator rather than as a nullable field.
   A `joined_in_week` was written and then removed: the week grain has no use
   for it until the closing ritual, and this repository fails a build for a
   read nothing calls.

   **What is left of the morning moment.** The line, the two sides, the pick
   from the pool for today or tomorrow, and capacity measured against the
   chosen count alone. The appointments strip is increment 7, the log is 3 and
   the composer is 4, so the mockup's morning cannot be met whole here; the
   *fixed today* strip needed no server work, because `action_items` and
   `bills` have always shown every dated claim on the day whether or not it was
   picked — which is rule 9 already true. The pool's rows gained `picked_for`,
   without which a Pick button is one that appears to do nothing.
3. ~~**The log, as a read.** The day's timeline: nodes captured that day, task
   events **from the life-event log** — completed and reopened as separate
   lines, rule 6 — routine occurrences, bill payments, pins, in one order by
   time, each saying which it is. **Acceptance: the mockup's midday moment**,
   minus the composer.~~ **Shipped September 3, 2026.** `clarice/day_log.py`,
   beside `life_log.py` and `recall.py` because a read crossing both cores
   belongs to neither — this one reaches into `mind`, `lists`, `daily`,
   `routines` and `money` at once. Seven kinds, four sources, merged by time
   and no new table.

   **Two of the five sources are not in the log at all**, which is why this is
   a module rather than a call to `recall.around`: a bill's `paid_at` and an
   occurrence's `decided_at` are columns on records that were never events.
   Ticks, unticks and picks come from `ActivityEvent`; notes come from
   `live_nodes`, so there is one node-visibility rule and a note somebody
   deleted is not a line of their day.

   **Rule 6's correction is proved rather than asserted.** Reopening a task
   clears `completed_at`, and the log still reads *done at 01:49, reopened at
   02:16* — verified in a browser, not only in a test.

   **The log shows on a past day**, where `action_items` and `bills` cannot.
   Those are live task state and a task holds no record of what it looked like
   on the 30th; every source here is a dated record of something that happened.
   That is the split `routines` already makes on the same page.

   Two wordings moved to the domains that own them —
   `routines.reads.progress_detail` and `money.reads.paid_detail` — so the log
   never says a tally or a figure in a way its own module would not, and
   `clocks.day_bounds` now owns a day's two edges, with `recall._start_of`
   delegating to it rather than keeping a second copy.
4. ~~**The composer.** Four destinations over `confirm_actionable`, with Did
   creating the task completed. One optional field on `/api/v1/capture`, the
   contract regenerated. The phone sends Note by default and needs no change.~~
   **Shipped September 3, 2026.** `clarice/composer.py`, and the Day page's
   capture box grown a question rather than a second box beside it — *one
   composer* is what the page says, and two input fields would be the two
   pipelines this redesign is undoing.

   **The line is drawn before the pin, not after**, and that is the one thing
   the table above could not have told you. A Did or Today line is an act of
   execution, so it closes the morning's list — and then joins *below* what it
   just closed. Drawing afterwards would stamp `list_closed_at` later than the
   pin's `selected_at` and put the line that ended the morning inside it. The
   ordinary tick has the opposite shape for the same rule, because there the
   pin was made hours earlier.

   **`mind.services.attach_commitment` is the other door to
   `confirm_actionable`**, and it does not go round `propose_facet`'s refusal of
   an explicit actionable facet: what that guard enforces is that nothing
   becomes a task except through `confirm_actionable`, which this calls. The
   facet is `explicit` with a blank `producer`, so the commitment producers'
   attribution stays about producers.

   **A bearer token may send any of the four, and that is a widening**, stated
   at the field rather than discovered: `capture:write` could previously only
   write a node. Allowed because the plan asks for one endpoint rather than
   two, because every one of those acts is the owner's own and undoable on the
   day page, and because refusing would mean dropping a queued capture.

   **The box defaults to Note and ~~D9 stays open~~** — see D9 below, which
   now carries what shipped and what would answer it.
5. ~~**The evening.** The closing ritual that already exists gains the three
   moves on each unfinished pin, above or below the line: tomorrow, pool, let
   go. **Acceptance: the mockup's evening moment.** Never a date move.~~
   **Shipped September 3, 2026.** `clarice/leftovers.py` holds the three, the
   closing block offers them one row at a time, and the readback gained the
   below-the-line pair — *you finished 0 of 1, and 1 you set aside. 1 of 1
   below the line.*

   **None of the three rewrites today, and that is the whole of *never a
   move*.** Each decides what happens next. *Tomorrow* pins to tomorrow and
   leaves today's pin standing as unfinished, because you chose it, did not do
   it, and are choosing it again — releasing it would make a finish rate nobody
   can fail. *Pool* and *let go* release the pin, which lands in `set_aside`,
   reported beside the denominator rather than inside it.

   **The Day page's own row-level *Tomorrow* was moving a due date**, and
   stopped. Rule 7 is *never a move* and this increment says *never a date
   move* in as many words; leaving both would have had one word doing two
   opposite things a few inches apart. A due date is a promise to somebody, and
   choosing to work on something tomorrow is not the same act as re-promising
   it. Found by writing this increment, not by looking for it.

   **`joined_in_week` came back**, with the caller it was removed for lacking
   at increment 3 — the closing ritual needs below-the-line pins bucketed the
   same way, so *one of two below the line* is the same kind of statement as
   *three of four chosen*.

   *Let go* is `let_go`, shared with increment 6's stale prompt: it archives the
   task, retires every live actionable facet on it, and leaves the node. Retired
   rather than dismissed — `dismiss_facet` means *this was never a commitment*
   and is the one correction the parser will ever get, and spending it on a
   commitment that was real and is now over would teach it the wrong thing.
6. **The stale prompt.** A floating line unpicked past the threshold (D8) asks
   once. *Let go* archives the task and retires the facet; *keep* resets the
   clock. The weekly review reports lines let go, which is a better number than
   lines open.
7. **Appointment.** The app, the model above, its reads and services, the day
   strip, the pool's fixed lines, the calendar source, the two life events.
   Companions and place as text — mentions are D6.
8. **Retire.** The Day and Agenda routes redirect to the new page. Areas leave
   the navigation and the composer. Priority and manual ordering leave the
   interface. The tables stay until D3 is answered.
9. **Second Mind.** Whether log lines run the proposal detectors at capture
   (D2); the journal producer scoped to reflection (D5); appointment mentions
   (D6).

## Decisions

Open until struck. A header may state a decision and never a tally, so this
section is the status of what is undecided and nothing above summarises it.

- **D1. The name.** `Appointment` is Vince's word and reads oddly on a theme
  park; `Engagement` is the English word for any fixed claim on time; `Event`
  is taken twice in the knowledge core (`ActivityEvent`, `EventType`). The
  field list is the same under all three.
- **D2. Whether log lines feed the concept machinery on capture.** Forty nodes
  a day will drown concept proposal and hypothesis detection if each is treated
  as a considered note. **The attention tier is not the lever**: `attention_tier`
  is computed at read time and already places any node with no confirmed
  actionable facet in *quiet knowledge*, so a Note is quiet by definition and a
  Did, Today or Pool line is a commitment by definition. What is open is
  whether a node whose source is the day's composer runs the proposal
  detectors at capture, or only once a mention or a confirmation has lifted
  it. Proposal: the latter, so the log is searchable and mentionable from the
  first line and proposes nothing until something links it.
- **D3. The fate of `List` and `Project`.** Retired from the day and the pool
  under increment 8, tables kept. Deleting them is a separate decision with its
  own plan: S10–S12 are *works* on `Project`, and a project's *why* has a home
  in the knowledge core's project concept that nothing has yet wired.
- **D4. Whether `Tag` survives** as the only grouping, or goes with Areas.
  Undecided, and nothing in 1–7 touches it.
- **D5. `DailyEntry`'s three prose fields.** With the log carrying what
  happened line by line, `happenings` is either retired or kept as end-of-day
  reflection. Proposal: kept, and the journal producer reads it alone, so the
  two commitment producers keep two signals as `Facet.producer`'s own comment
  intends.
- **D6. Appointment companions and place as mentions.** The first task-core
  record to link into `mind.Mention`. After increment 7, as its own increment,
  because it crosses the seam `confirm_actionable` names as one-directional.
- ~~**D7. What draws the line.** Rule 3 says the first log line. Whether a Note
  counts, or only a Did, Today or Pool, is a one-line decision in increment 2
  and should be made by using increment 2's manual equivalent in week 0.~~
  **Answered September 3, 2026, the day it was asked: the first act of
  execution** — a tick on a chosen task, or a Did or Today line. A Note, a Pool
  capture, an appointment passing and every derived event leave the list open.
  The reason is the early-thought case: writing down something overheard at
  breakfast is not the start of the day's work, and a rule that said it was
  would end morning planning by accident. Rule 3 carries the answer.
- **D8. The stale threshold.** Three weeks in the mockup, chosen for the
  picture. If it reaches a second language it belongs in
  `lists/tests/test_mirrored_business_rules.py`'s table beside
  `AGE_WORTH_MENTIONING`, which that test reads in TypeScript and Kotlin; the
  number itself does not live in this file.
- **D9. The composer's default.** Note, Did, or remember the last choice. The
  argument against Did is in *The composer*: it manufactures completed tasks
  and, without the above-the-line rule stated there, it would have fed
  capacity. The argument for it is that the log-first habit is the whole
  premise. **This is a week-0 question**, to be answered by which destination
  the manual week reached for, not by preference.
  **Shipped as Note on September 3, 2026, and still open.** Note is the
  reversible choice: a wrong default there costs a second click, and a wrong
  default on Did fills the task history with completed things that were never
  commitments. What has changed is that the question is now answerable by
  ordinary use rather than by a manual week — the box exists, so which
  destination gets reached for is a fact the log will hold. Changing it is one
  line in `DayRoute.tsx`'s `Composer`.

## What this refuses

- **Automatic carry-forward**, in any form, including *tomorrow* applied to a
  set. One item, one decision.
- **A walled closed list.** Below the line exists so that the boundary can be
  kept honestly rather than broken quietly.
- **Priorities.** The morning pick is the priority.
- **Areas as a filing step.** A line that needs a *why* mentions a project the
  way the knowledge core mentions a person.
- **A `tomorrow:` prefix.** It was in the first mockup and is unnecessary once
  arrivals go to the pool and tomorrow's pick finds them there.
- **A recurrence that manufactures list entries for a rule.** *Friday afternoon
  is admin* is a standing order shown on Fridays; *five lessons a day* is a
  `Routine`. Neither is a task, and `RecurringCommitment` narrows to acts that
  genuinely need a line on a date.
- **Inferring attendance.** An appointment that passed is a derived log line;
  whether you went is yours to write.
- **A log table.** Rule 6. Nothing may write a row a read could have produced,
  which is `nightjar`'s own rule for the substrate.
- **Grading.** Rule 12. No streak, no warning, no success colour and no badge
  derives from the finish rate or from anything else the readback shows. The
  numbers describe the shape of a day and stop there.
- **A midnight row.** Rule 11. A day the line was never drawn on keeps
  `list_closed_at` null; the freeze on a past day is derived from the date.

## Acceptance

**Scored by using it, not by looking at it** — [`module-score.md`](module-score.md)
learned that on Money and it applies here with more force, because the whole
premise is that the current task core is competent and unused.

- **The page is used on ordinary days for two weeks** after increment 5, with
  the log holding lines on most of them. `recall.attendance_between` is the
  measurement and it already exists.
- **S3 and S5 stay *works*.** Both moved to *works* on August 20 on `DailyFocus`
  and the closing ritual, and both are kept whole here: the finish rate keeps
  its frozen denominator, the closing ritual keeps its three moves.
- **S1 improves or the plan has failed its own premise.** A stranger's first
  four minutes should be a pool and a pick, with no Area to name. If it is not
  simpler for Sam it is not simpler.
- **The corpus grows from the log.** After increment 4 and D2, the count of
  nodes captured per week from the Day page should exceed the count from
  deliberate capture. If it does not, rule 6 was wrong about where content
  comes from, and that is worth knowing.

## Where the facts live

| Fact | Owner |
|---|---|
| Whether this is active | [`roadmap.md`](roadmap.md) |
| The rules a day page must not break | [`daily-operating-system-vision.md`](daily-operating-system-vision.md) |
| Whether `Appointment` earns a model | [`clarice-v3-plan.md`](clarice-v3-plan.md), *New models* — argued there August 20 as `Event` |
| The charter its fields answer to | [`architecture-trajectory.md`](architecture-trajectory.md) §4 |
| What the page looks like | [`day-mockup.html`](day-mockup.html), owned here |
| Which increments have shipped | The strikes above, and nothing else |
| What shipped, when, how verified | [`roadmap-history.md`](roadmap-history.md), when it closes |
