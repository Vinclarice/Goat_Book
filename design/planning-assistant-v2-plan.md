# Planning assistant v2 — the forward half of the weekly ritual

Vince · plan · written August 19, 2026 · **not started**

## What this is

V1 finds loose ends. **V2 decides what to do about them**, as a short guided
session that ends with a confirmed plan. The narrative of what v1 was, its four
decisions and what it taught are in [`roadmap-history.md`](roadmap-history.md);
the plan is a stub.

The target is five to ten minutes and perhaps five questions — each one a
question whose answer *changes the plan*. Not *"how can I help you plan your
week?"*, which asks the person to supply what the system already knows.

**The measure of success is decisions removed, not material produced.** A
session that generates more to read has failed even if every sentence is true.

## Read this part before the design

Three constraints govern this work. The first two are the obvious ones and the
third is the one that shapes the whole build.

### D1's trigger cannot fire yet

D1 deferred generated prose on August 18 **with two firing conditions rather
than a someday**, and neither can fire today:

1. **The extractive label degenerates** — a section whose connection has no
   mediating concept and no distinguishing terms, checkable in code because the
   extractive labeller returns nothing to show.
2. **A named miss** — after **at least eight weekly summaries**, one specific
   week where the citations were all present and it still was not possible to
   tell what had happened. Recorded as that week, not as an impression.

Increment 5 shipped the first extractive summary on August 19. **Eight weeks of
evidence do not exist and cannot be hurried.** D1 also settled the order if it
is ever reopened: **the brief explanation is the defensible first site and the
weekly summary is not carried along with it** — the summary hands a model
*everything written that week*, recurs, and fits the carve-out worst.

### The interactive-path rule, which is not this tree's to amend

`design-concept.md`'s ML policy is not only *"no generation yet"*. It is **"no
LLM in the real-time/interactive path"**, and that sentence names planning
explicitly. Core principle 8 says it from the other side: anything a person
interacts with in real time is *"fast, local, and testable with plain
input/output fixtures"*.

**This is a different decision from D1 and it belongs to Second Mind's `docs/`.**
[`principles.md`](principles.md) §Scope is explicit that this tree does not get
to weaken it. The carve-out's own reasoning shows where the line falls: a
user-initiated one-off *"is closer to an export than to a keystroke."* **One
button press is an export. Six exchanges in five minutes is a path.**

**This plan does not need the rule bent**, because the session below is a script
over state rather than a model in a loop. Every question it asks is *selected*,
not composed.

### The corpus is thin, and that is the real risk

The last recorded count is **41 nodes, 19 of them visible to the detectors**
([`product-stories.md`](product-stories.md) S16). A planning session arriving
confident on a corpus that thin is this design's characteristic failure, and it
is worth naming before the features rather than after.

**Everything in this product that works is the same instinct**: `DailyFocus`
snapshots the denominator at the moment of choosing; `typical_week_for`
(`review/reads.py:739`) returns `None` below two planned weeks because *"no
evidence yet"* and *"you have room"* call for opposite responses; `accept_rate`
(`mind/instrumentation.py:79`) returns `None` rather than zero because zero
would read as *"wrong every time"* when it means *"no data"*.

**So the whole session inherits that discipline: below the floor, say nothing.**
An empty section is honest; a confident section built on three data points is
not, and it is the one failure that would make the ritual unwelcome after two
weeks.

**A refusal recorded so it is not re-proposed: `semantic_echo` stays dark.** It
is built, tested and measured, and it is unavailable in production because
`sentence-transformers` is not in the image and `embed_nodes` is not called —
D4, deliberately. Its own firing condition is *a corpus large enough for the
detector to have something to say*, which is the same evidence this section says
does not exist. **Switching it on for v2 would be reopening D4 against its own
trigger**, and nothing in this plan needs it.

## Where this lives: the review, not a new surface

**V2 is the forward half of a ritual that already exists.** The review page
already carries loose ends (`review/reads.py:588`), upcoming constraints
(`review/reads.py:661`) and a draft of next week (`review/reads.py:776`).

Three reasons, and the third settles it:

- **The moment is already right.** Increment 6's own reasoning: *"somebody
  reviewing a week is already looking backwards and is the one moment they are
  placed to look forwards — `design-concept.md`'s ritual rather than a second
  thing to remember."*
- **Kestrel declined a second review surface** in as many words, and nothing has
  changed that would reopen it.
- **Silence may only be interpreted in one place.** `design-concept.md` is
  pointed that the chosen ritual is *the only place the system is allowed to
  interpret silence*, which is why `first_surfaced_at` is stamped there. Two
  rituals means two interpretations of not-answering, and the review window
  machinery would have to pick one.

A separate *"Plan the week"* entry point may still exist as a **route into the
same ritual** — what it must not be is a second surface with its own reads, its
own windows and its own idea of what silence means.

**The argument has a hole in it, and D6 is where it gets decided.** There are
already **two** review surfaces: `/mind/review/` carries connection proposals
and unresolved questions with their resolve and dismiss actions, and `/app/review`
carries the weekly review, the loose ends and the draft. Either the
one-place rule is already broken, or the two are legitimately one ritual per
core — and v2 is the thing that forces an answer, because **its inputs are split
across both**: blockers come from the knowledge core, tasks and dates from the
task core.

## What actually needs generation, and what does not

**"Prose" means composed sentences; "extractive" means facts, counts, dates and
cited spans arranged by rules.**

| Element | Needs prose? | Why |
|---|---|---|
| Check-in, capacity, constraints | **No** | Confirming what the system believes |
| *"Is this project still active?"* | **No** | No confirmed activity in N weeks |
| *"You deferred this three times"* | **No** | A count of moves |
| *"Which outcome matters more?"* | **No** | An ordering the person supplies |
| *"If Friday disappears, what survives?"* | **No** | Re-run the draft with a constraint |
| Review last week — **narrative** | **Yes** | D1's worst-fitting site |
| Review last week — what changed, cited | **No** | Shipped: `loose_ends` |
| Planning blockers | **No** | `unresolved_questions` (`mind/queries.py:484`) plus a project link |
| Outcomes and *"why this week"* | **No** | A deadline, a count of confirmed tasks, recent activity |
| The draft and its evidence column | **No** | Shipped: `draft_week` |
| Stress-testing | **No** | Overload is `typical_week_for`; orphan work is a set difference |
| Project briefing — **facts** | **No** | Shipped: `brief_for` (`lists/projects.py:86`) |
| Project briefing — **articulation** | **Yes** | D1's *defensible first site* |
| Ranking that quietens over time | **No** | `accept_rate`, gated on a sample |

**Two rows say yes and twelve say no.** Both yeses are the sites D1 already
sorted, and each gets a named, empty slot rather than a workaround — so
reopening D1 is a fill-in rather than a redesign.

**One row reads generative and is not.** A briefing's *"possible next move"*
derived from dates — *"this question is older than that deadline"* — is a rule.
But core principle 6 binds it either way: **the system may only assert what a
reader could verify from the cited passages alone, descriptive and never
explanatory.** A next move drawn from a date is fine; one explaining why the
person keeps avoiding it is the failure that rule exists to prevent.

## The session

Six steps. **Outcomes come second, before any triage**, because deciding what to
keep from last week without knowing what the week is for is triage with no
criterion — and once the outcomes exist, three later steps get their ordering
for free.

### 1. Check in — by correction, not questionnaire

The session opens with **what it already believes**, and takes corrections:

> Website Launch and Billing look active. Newsletter has not moved in five
> weeks — still going?
>
> Your last four planned weeks finished five, four, six and four.

Two of the three inputs the vision asks for are things the system either records
or derives. Asking for them makes the ritual longer and the answers worse.

**The per-project half is already built.** `brief_for` (`lists/projects.py:86`)
assembles what bears on a project in three sections — prior material, open
questions, dated commitments — which is the vision's *"Prepare me"* action
under another name. **The session reads it rather than growing a second
briefing**, and the only thing it lacks today is a caller outside the project
page.

**Capacity is derived, and the declared value is a modifier on this week only.**
`typical_week_for` is the authority; the person's input answers *"is this week
unusual?"* — a known-quiet fortnight, a week half gone to travel.
[`principles.md`](principles.md)'s one-rule-one-definition applies directly: a
declared capacity standing beside a derived one is two authorities for one
number, and the first time they disagree nobody will know which won.

### 2. Choose outcomes

Two or three, each with *why this week* as cited facts — a deadline, a count of
confirmed tasks, recent activity — and each **use · edit · skip**.

**Confirmed outcomes are snapshotted**, per
[`architecture-trajectory.md`](architecture-trajectory.md) §4 rule 3. An outcome
naming a project takes a copy of what gave it meaning, the way
`routines/models.py:134` copies `target_quantity` so that last month's *"4 of
5"* survives a target change. Without it, renaming a project silently rewrites
what you committed to three weeks ago — and this product's whole claim about
history is that it does not do that.

### 3. Carryover, triaged against the outcomes

Unfinished work with the evidence of where it came from, **ordered by connection
to what was just chosen**, each row keep / defer / drop. `loose_ends` already
assembles the pile — unanswered questions with `asked_on`, commitments never
accepted with `proposed_on`, overdue work. What is new is acting on a row in
place.

**This is [`product-stories.md`](product-stories.md) S7's open question arriving
as work**, and D5 below is where it gets decided.

**One row of it is a v1 leftover that has been sitting in plain sight.**
`names_worth_confirming` (`review/reads.py:191`) already puts recurring concept
candidates on the review, and `ReviewRoute.tsx:376` renders each as a label and
a mention count **with no action on it** — which is, word for word, the gap S7
was marked with: *the review surfaces concept candidates that have earned a
question by recurring, and confirming one from the review is not possible.*
Confirming a name is the cheapest possible instance of deciding in place: no new
read, no new concept, and the same services the knowledge core already uses.

### 4. Blockers that touch a chosen outcome

Only unresolved questions materially affecting an outcome — which is now a
filter rather than a judgement, because the outcomes exist. Each takes **link
answer · schedule decision · not relevant**, and *not relevant* persists as
suppression.

**The read this needs already exists and has never had a justified caller.**
`unresolved_questions_in_context` (`mind/queries.py:688`) reports how long a
question has been open **and which later notes came back to it**, each carrying
the terms that matched — which is exactly the vision's *"First asked August 8.
Two related notes found."* `loose_ends` deliberately calls the cheaper
`unresolved_questions` instead, because a weekly summary *"wants the questions
cheaply and says nothing about recurrence"* and the richer read runs one
retrieval per question.

**V2 is the first surface where that cost is worth paying**, because a question
that keeps coming back is a different kind of blocker from one asked once and
forgotten — and paying it for five questions inside a chosen ritual is not the
same as paying it for a summary nobody asked to compute.

### 5. Build the week

`draft_week` already proposes dated work, names routines apart from tasks and
flags `over_committed`. What is new: **the draft is scoped by the confirmed
outcomes**, arranged into day or focus blocks, each row taking accept / move /
edit / remove / show reasoning.

**No recommendation voice.** The vision's dialogue has the assistant saying *"I
recommend deferring two"*, and that is a verdict — the planner deciding
something the person has not, which is exactly what `draft_week` refuses when it
declines to pull from the someday pile. There is already a test asserting the
scolding phrasing is **absent** rather than merely that the neutral one is
present. Same information, no verdict: **show which work is least connected to
the chosen outcomes, and let the person cut.**

**Day sections, never calendar events.** `design-concept.md` starts calendar
read-only and defers two-way sync; recorded here so nobody re-opens it as a gap.

### 6. Stress-test, then confirm

Overloaded days against derived capacity, missing prerequisites, and **work with
no connection to any chosen outcome** — the last being nearly free, since step 2
made it a set difference.

Nothing is the week's plan until confirmed, and **the assistant may not rewrite
it afterwards.**

## How the session measures itself

Two mechanisms, one new and one already built, and between them they answer
*did the ritual happen* and *did it show the right things*.

### The session is a record, not a flow

**A planning session is a fact about whether the practice happened**, and it
gets a record for the same reason `WeeklyReview` (`review/models.py:4`) has no
delete path: *"I planned and had little to say"* and *"I never opened it"* are
different facts, and only one says the ritual lapsed.

Without it there is no way to answer whether v2 worked — attempted, abandoned
halfway, and confirmed are three different outcomes. This is not a later
refinement; it lands with the first increment that has a session to record.

### The planning miss

`RetrievalMiss` (`mind/models.py:950`) records *"where the person's own memory
beat the index"*, and it is described at the model as **the strongest evidence
available about whether semantic retrieval is needed, because the correct answer
is known.** It has two contexts today, `SEARCH` and `CAPTURE`, and
`record_retrieval_miss` already takes the context as an argument.

**A third context costs one enum value and answers the question this whole plan
is exposed to**: *I know I decided something about this and the session did not
show it.* A thin corpus and a bad retrieval both produce a quiet session, and
nothing else can tell them apart — which is precisely the failure the thin-corpus
section says would make the ritual unwelcome.

**Both feed `retirement_gate` (`mind/instrumentation.py:215`)**, whose three
conditions are confirmations recurring, accept rates holding, and the retrieval
miss trend falling. V2 is the first surface likely to move any of them, and a
gate computed from a denominator nobody records is a gate that cannot close.

## Live scenario planning

*"What if I only have three productive days?"* re-runs step 5 under an added
constraint and re-renders the diff. **The feature that will feel most like an
assistant contains no model at all** — it is `draft_week` with a parameter,
which is exactly why `draft_week` writing nothing was worth the discipline.

## What v2 needs to know that nothing records

Each measured against `architecture-trajectory.md` §4 — *a concept earns its own
model when it has a different life cycle, not when it has a different name.*

| Wanted | Verdict | Reasoning |
|---|---|---|
| Project status: active / paused / completed | **A field** | A paused project has a project's life cycle |
| A project's desired outcome | **A field**, beside `purpose` (`lists/models.py:450`) | Purpose is *why*; the outcome is *what done looks like*. Same record, same life cycle |
| *"This week is unusual"* | **A field on `WeeklyIntention`** (`review/models.py:94`) | One per owner per week, set before or during — exactly that model's life cycle |
| Weekly outcomes | **Open — D3** | Several per week, each independently confirmed, each carrying snapshotted evidence. That may be a facet's life cycle rather than an intention's |
| The session record | **A model** | Its existence is the fact; nothing else has that life cycle |
| Effort size, small / medium / large | **Not yet, and out of order** | D2 declined estimates, and `design-concept.md` names the next cheapest step as a **context tag** (phone / computer / errand), *then* estimates |
| The confirmed plan | **Reuse `DailyFocus`** (`daily/models.py:72`) | Already records what was pinned, when it was chosen, and whether it was released — the honest denominator S6 rests on |

## What v2 may not do

- invent commitments from ambiguous prose;
- prioritise work without showing its basis;
- create tasks or calendar events without confirmation;
- treat an unanswered proposal as accepted;
- rewrite the plan after the person confirms it;
- **assert anything a reader could not verify from the cited passages alone**;
- **grade the person** — state capacity, never performance;
- **speak below its evidence floor** — an empty section beats a confident one
  built on three data points;
- **put a model in the session loop**, until `design-concept.md` says otherwise.

## What it learns, and when it is allowed to

Confirmation history makes the session quieter, reusing `accept_rate`, which is
computed **per producer, never blended**, because a good detector and a bad one
average to a number describing neither.

**Gated on a minimum sample, and it may never fire.** With one user and a corpus
of 41 nodes, ranking pressure derived from three confirmations is noise wearing
personalisation's clothes. The floor is the same discipline `typical_week_for`
uses at two planned weeks.

Local and explainable, in the vision's own phrasing —

> Ranked highly because you selected this project as a weekly focus and accepted
> three related tasks.

— and never *"AI confidence: 87%"*, which is the number nobody can check that
`precision.md` refuses.

## Open decisions

1. **D1 reopened?** Not answerable yet by its own terms. **This plan assumes
   no** and builds the two prose slots as empty, named seams.
2. **Does the interactive-path rule bend for a scripted session?** This plan
   says it does not need to. **If v3 wants a free-text turn, that is a
   `design-concept.md` amendment and Vince's to make there.**
3. **Does a weekly outcome earn its own model?** *For:* several per week, each
   with its own confirmation state and snapshotted evidence. *Against:*
   `WeeklyIntention` already answers *what the week is for*, and two records
   answering one question is the drift §4 exists to prevent. **The likely
   resolution is that they are different questions** — the intention is a
   sentence about the week, an outcome is a thing that will be true by Friday.
4. ~~**Is "desired outcome" the same field as S10's abandonment condition?**~~
   **Answered August 22, 2026: two fields** (`804d6e8`), and taken by Claude at
   Vince's direction rather than by Vince.

   The worry was right — *deciding them apart risks two text areas nobody
   fills* — and it is answered by optionality rather than by merging, the way
   `purpose` already answers it. What decides it is that **a tripwire you
   cannot tell from an ambition can never be checked**: merged, nothing can
   ever ask whether the condition has been met, because nothing can tell which
   half of the text is the condition. They also have different readers —
   *are we there?* against *should we stop?*
5. **Does deciding in place open the review's read-only rule (S7)?** The
   read-only rule is *why* the numbers are trustworthy. Writing through the
   owning core's services — the resolution already found for pinning a task — is
   the shape any yes should take.
6. **Where does the session live, when its inputs span two rituals?** There are
   already two review surfaces — `/mind/review/` and `/app/review` — and v2
   reads from both. Three answers, and they are not equally cheap:

   - **One ritual per core, and v2 is the task core's forward half.** The
     cheapest, and it leaves blockers reached by a link, which is what step 3
     is already trying to stop doing.
   - **V2 merges the two review surfaces.** The most honest against the
     one-place rule and much the largest — `/mind/review/` owns the review
     window that stamps `first_surfaced_at`, so merging moves that machinery.
   - **Two surfaces, one declared owner of silence.** Name `/app/review` as the
     only place silence is interpreted and leave `/mind/review/` as an
     inspection surface that stamps nothing.

   **This is the decision that most changes increment 6**, and it is a design
   question spanning both cores — so `design-concept.md`'s account of the review
   ritual is a party to it, not just this file.
7. **Does the weekly intention duplicate the review's own "Next week" field?**
   **Found by building increment 1, not by planning it.** `WeeklyReview.plan`
   has always carried *"plan for next week"* in the person's own words, and the
   intention now sits on the same page asking a question a person could answer
   the same way twice. Two free-text boxes about next week, a few hundred pixels
   apart, is the near-identical-controls problem C2 found in the task UI — and
   the increment shipped both because collapsing them is a product decision and
   not a refactor.

   The distinction that would justify keeping both: an intention is *what the
   week is for* and survives into the week, where the plan is *what I said on
   Sunday* and stays part of the review's record of that Sunday. **If that
   distinction cannot be written on the page in a sentence, there is one field
   here and not two** — and the intention is the one with the life cycle, since
   the Day page reads it and nothing reads the plan.

   Bears directly on D3: if the intention and the review's plan collapse into
   one, an outcome is much more clearly a separate record than a rival phrasing
   of the same one.

## Increments, in order

**1 to 3 are worth doing whatever happens to the rest**, and none of them needs
a decision above answered.

1. **The weekly intention becomes writable and visible.** Its write path and the
   Day render. Closes S9, which is impossible today for want of a form — the
   model, the service, the read and the Day payload all shipped and nothing can
   write one. No new concepts, and the ritual cannot open without it.
2. **Capacity at day grain, on the day surface.** D2's actual sentence — *"you
   have pinned nine for Tuesday; you have finished more than five on two of the
   last thirty days"* — which v1 shipped at week grain on the review. Belongs on
   the Day page and is independent of the session entirely.
3. **Project status and desired outcome.** Two fields. Makes *"which projects
   are active"* answerable by the system, which is what lets step 1 confirm
   rather than ask, and gives retrieval a second anchor beside `purpose`.
4. **The check-in, and the session record.** The review's forward half opens
   with what it believes and takes corrections, including *"this week is
   unusual"*. The first increment with a session to record, so the record lands
   here.
5. **Outcomes.** Two or three, snapshotted at confirmation, each with cited
   *why this week*. Pending D3. This is where the ritual gains its spine, and
   every later increment reads from it.
6. **Carryover and blockers, triaged against the outcomes.** Keep / defer / drop
   in place, and questions filtered to those touching a chosen outcome, with
   dispositions that persist. Pending D5 and **shaped by D6**.

   **Three of its four parts are v1 leftovers rather than new work**: confirming
   a name, which `ReviewRoute.tsx:376` renders without an action;
   `unresolved_questions_in_context`, which has existed since increment 1
   without a caller that justified its cost; and the planning miss, which is one
   enum value on `record_retrieval_miss`. Only acting in place is genuinely new,
   and that is the part D5 governs.
7. **The draft, scoped and stress-tested.** `draft_week` filtered by outcomes,
   arranged into day blocks, overloaded days named against derived capacity, and
   work connected to nothing listed rather than cut.
8. **Scenario planning.** The draft under a constraint.
9. **Ranking by confirmation history, gated on a sample.** Last, and conditional
   — if the floor is never cleared, this never ships, and that is the correct
   outcome rather than a failure.

## Where the facts live

This plan owns none of them. What is active or open is
[`roadmap.md`](roadmap.md); what shipped and what it taught is
[`roadmap-history.md`](roadmap-history.md); the score is
[`product-stories.md`](product-stories.md); the charter is
[`architecture-trajectory.md`](architecture-trajectory.md) §4; delivery practice
is [`principles.md`](principles.md); and **the ML policy, the Attention Policy
and the assertion rule are `design-concept.md`'s**, in Second Mind's own `docs/`.
