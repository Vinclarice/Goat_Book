# Planning assistant — a proposal contract, then six increments

Vince · plan · written August 18, 2026 · **revised the same day after review,
and its six increments confirmed as the product the same day**

**Two increments are part-shipped, August 18, 2026, on `main` and undeployed.**
Both stop at the same line, and for the same reason: the navigation-and-identity
work owns the presentation layer this week.

- **Increment 1's read half** — `a302dee`, `queries.unresolved_questions` and
  thirteen tests. The section belongs on `/mind/review/`, and `mind/` templates
  were being re-themed the same afternoon, so it waits rather than being written
  twice.
- **Increment 3's model and API** — `0fc78d9`, `Project.purpose` with migration
  `0038`, twelve tests, contract and client regenerated. **No React text area**,
  so nothing can write a purpose yet except the API.
- **Increment 4's retrieval** — `9cfc16e`, `queries.material_bearing_on` and ten
  tests. Text-anchored, so this half needed no way to *write* a purpose; the
  blocker recorded above was about real use, and fixtures answer a test. What
  it still needs is the caller that turns a project into a statement, and an
  endpoint.

Increment 2 has not started and still waits on the design question its own
section names.

## What was asked for

An evidence-backed proposal inbox rather than a chatbot, helping at three
moments: **while writing** (a possible task, an unanswered question), **when
preparing for a project** (an on-demand briefing of relevant material), and
**during the weekly review** (what happened, loose ends, constraints, suggested
focus, a draft plan). Nothing is created or changed without confirmation.

## The correction this revision exists for

**The first draft of this plan claimed the project already had "one proposal
surface with five producers", and that the confirmation rules were therefore
already universal. That was wrong.** There are three proposal systems with three
record types, three lifecycles, three surfaces, and measurement on one of them.
Recorded rather than quietly fixed, because the false version made a universal
attention budget look like a rule that could be turned on, when it is a thing
that has to be built first.

| | `ConnectionHypothesis` | `Facet` (actionable) | `Mention` |
|---|---|---|---|
| **Producer** | `dormant_thread`, `shared_referent`, `semantic_echo`, `open_question` | the commitment parser (`commitments.py`) | `concept_assignment` |
| **When** | nightly batch, `run_detectors` via `run_mind_maintenance` | **synchronously, inside `capture`** (`services.py:221`) | nightly batch, and **first** in the run, because the others read what it feeds |
| **Surface** | `/mind/review/` | the capture page's accept surface (`views.py:211`) | `/mind/concepts/<id>/` |
| **Confirm** | `confirm_hypothesis` / `dismiss_hypothesis` | `confirm_actionable` / `dismiss_facet` | `confirm_mention` — and there is **no dismiss path** |
| **Evidence** | `HypothesisMember`: a **span**, plus `contribution_reason` | `Facet.reason`, free text, **no span** | span, plus `reason` |
| **Attribution** | `detector` column | none — the producer is implicit | `origin` only; which detector proposed it is not stored |
| **Silence** | `first_surfaced_at`, a review window, and `expire_stale_hypotheses` | none. A proposed commitment sits forever | none |
| **Dedupe** | `fingerprint`, unique per owner across **all** resolutions including dismissed | `get_or_create` on (node, kind, live) | unique (node, concept, span) |
| **Measured** | **yes** — `detector_performance` (`instrumentation.py:83`) | **no** | **no** |

Three consequences, and they set this plan's order:

- **`detector_performance` reads `ConnectionHypothesis` and nothing else.** So
  `concept_assignment` runs inside `run_detectors` beside four measured
  detectors and is itself unmeasured, which is easy to miss from the command
  and impossible to see from `/numbers/`.
- **Only one of the three treats silence as non-consent.** The actionable facet
  gets there differently and arguably more strongly — it is never applied at
  all until confirmed, so silence costs nothing forever. But "forever" is not a
  policy, and nothing counts the backlog. `commitments_without_tasks`
  (`services.py:656`) counts a broken invariant, not an unanswered proposal.
- **Dismissal cannot teach anything yet.** A dismissed hypothesis is counted; a
  dismissed commitment sets `retired_at` and is counted nowhere; a mention
  cannot be dismissed at all. A producer that gets quieter when rejected needs a
  decision record per producer, and two of three do not have one.

**So a universal confirmation budget and a retirement rule are not switches to
turn on. They are the first deliverable.**

## The shared proposal contract

Not a new table on day one, and not a rewrite of three working systems. It is
**six fields every producer must be able to answer**, which new producers
implement from the start and existing ones are brought to as they are touched:

| Field | Why it is in the contract |
|---|---|
| **Producer** | Accept rates are per producer or they mean nothing — `retirement_gate` already refuses to blend them, and two producers currently cannot be named at all |
| **Cited evidence** | A span and its source record. `Facet.reason` is free text today, so a commitment proposal cannot be checked against the passage that caused it |
| **Proposed action** | **The genuinely new one.** Nothing today states what confirming will *do*. "Creates a task in Website Launch" is a different thing to agree to than "links these two notes" |
| **Confirmation state** | Pending, confirmed, dismissed, expired — and *shown-at*, because a window anchored to creation makes silence mean nothing |
| **Fingerprint** | Dedupe against everything seen, not against what was confirmed. Only hypotheses do this today, and it is the reason a nightly run does not re-propose a fortnight of dismissals |
| **Measurement** | Proposed / confirmed / dismissed / expired per producer, so rule 2 below has a number to fire on |

The card the person sees answers five questions, and the fourth is the one no
surface answers today:

| Field | Example |
|---|---|
| Proposal | Add "Ask Maya about venue" |
| Evidence | The exact journal passage |
| Reason | Commitment language detected |
| **Effect** | **Creates a task in Website Launch** |
| Decision | Confirm · Edit · Dismiss |

**Dismissal teaches locally, and only locally.** If "I should probably…"
statements are rejected repeatedly, that producer proposes them less. It must
never make the producer *more* inventive to compensate — the failure mode is a
system that responds to rejection by widening its guesses, which is how a
proposal surface earns being skimmed. Quieter, never more creative.

## Attention budgets stay separate

**One budget per surface until a unified feed is deliberately designed**, with
its own comps and its own decision. The three moments are genuinely different —
a suggestion beside the entry you are writing, a briefing you asked for, a
weekly ritual you opened — and collapsing them into one queue is a product
decision, not a refactor.

Two rules that do apply per surface today:

1. **A producer ships with its invocation and its `/numbers/` row**, or it is a
   seam that is not switched on. The detectors were built, green and uninvoked
   for weeks; that is written down twice and should not need a third time.
2. **A producer below 50% accept rate over a decided sample gets quieter, not
   tuned.** `retirement_gate` computes that number for hypotheses already.
   Nothing acts on it, and for two producers nothing can.

## Where AI belongs, and where it does not

The division of responsibility, which is the useful form of the answer:

- **Rules and retrieval find things** — dates, commitments, questions, projects,
  related passages. Deterministic, testable, cheap.
- **AI explains a relationship, condenses source material, and drafts readable
  prose** — over evidence that was already found, never as the thing that finds
  it.
- **The person confirms priorities, creates tasks, and decides what enters the
  plan.**

That split is not a compromise; it is what the measurements said.
`docs/precision.md` states the rule the detectors were rebuilt around:
**precision comes from requiring a *kind* of evidence, not from raising a
threshold.** Every measured failure was a threshold — lexical overlap at 11%,
whole-document embeddings at 0%. Every success came from structure or rarity. A
generative *finder* is structurally the tier where all of that failure lives; a
generative *explainer*, over evidence already retrieved, is not.

`design-concept.md` §*Machine Learning & LLM Usage Policy* is the authority: no
LLM in the interactive path, local embeddings the only ML dependency, and one
narrow carve-out — user-initiated, non-durable, entity-checked, event-logged.
Its v1 ships no generation at all, and **so do all six increments below** —
settled as D1 on August 18, 2026, with a firing condition rather than a
someday. See *D1, decided*.

**The assistant never silently:** creates a task · marks a question answered ·
alters a project · schedules calendar time · converts silence into approval ·
presents an inference as a fact.

## The blocker that is not code

As of August 16 the corpus was **41 nodes, 19 of them visible to the
detectors**, and `semantic_echo` is dark in production because
`sentence-transformers` is deliberately out of the image.

**It is worse than dark.** The dependency is in neither `requirements.txt` nor
`requirements-dev.txt`, so `test_semantic_echo.py:47` and
`test_detector_ensemble.py:29` skip in CI as well — one producer runs in no
automated environment at all, including the true/false pair corpus built
precisely to control its false positives
([`code-review-2026-08-16.md`](code-review-2026-08-16.md), unpromoted). Two
citations for it are also dead: `embeddings.py:105` and
`run_mind_maintenance.py:19` both name `requirements-embeddings.txt`, which does
not exist, and the first is an error message telling a person to `pip install -r`
it.

Prefer the increments that work from a **cold start**, because two of the six
asked-for things improve with no code at all, and building four producers over
nineteen notes would conclude that proposals do not work on evidence that was
never about the producers.

## The increments

**These six are the product, in this order — Vince, August 18, 2026.** Not a
menu of candidates and not a first phase with the rest left open: the practical
first version is all six, and steps 4 and 6 are last because of what they wait
on, not because anybody is undecided about them.

| # | Increment | Waits on |
|---|---|---|
| 1 | Unresolved-question review with cited passages | nothing — promotable now |
| 2 | Commitment suggestions from journal entries | one design question, below, answered before code |
| 3 | A short purpose / desired-outcome field for projects | nothing — task core, charter §4 |
| 4 | Project preparation briefs that retrieve relevant material | step 3; its retrieval needed no way to *write* a purpose, but a brief worth opening does |
| 5 | Extractive weekly summaries with citations | nothing |
| 6 | A weekly-plan draft | the product collecting capacity and weekly intentions (S3, S9) |

**Step 5 is unblocked and holds its place by choice.** It depends on nothing
above it, so if 3 or 4 stall it can move forward without disturbing the order —
worth knowing, and not a reason to reorder now.

### 1 — Unresolved questions, as a read view

Question-shaped nodes with no `answers` edge, no confirmed answer and no pending
proposal against them. Oldest first, with the passage and the dates.

> **Still unanswered:** Which payment provider should we use?
> First asked 12 days ago. Mentioned again in two later entries.
> **Keep open · Mark answered · Not a question**

- **Explicitly not a detector.** No new rows, no batch job, no fingerprint, no
  review window. It is a query over data that already exists — a *view of the
  corpus*, not a claim about it, which is why it needs none of the contract's
  machinery to be honest.
- **Every part exists.** `looks_like_a_question` (`detectors/open_question.py:76`)
  is written and tested; `answers` is already the relation, chosen because the
  direction *is* the finding.
- **It is not the shipped detector.** That one fires when an answer arrives, and
  is therefore silent about everything still hanging.
- **"Not a question" is the correction signal** for `looks_like_a_question`, and
  the first place dismissal-teaches-locally has somewhere to go.
- **Works from a cold start.** A first dump is mostly unresolved questions.

### 2 — Commitments from journal entries

Scan a `DailyEntry` when it is saved, show suggestions beside the entry, and
write nothing until confirmed.

> **Possible task:** Ask Maya whether the venue is available
> **Why:** "I still need to ask Maya about the venue."
> **Source:** Tuesday's journal entry
> **Add to tasks · Edit · Not a task**

- **Why.** "Tasks implied by writing" ships for captures and is absent for the
  surface where most writing happens. The parser has never seen a word of
  `DailyEntry`.
- **Beside the entry, at save time** — matching where the person already is,
  and matching the parser's existing synchronous lifecycle rather than inventing
  a fourth one.
- **Nothing is written until confirmed**, including the node. The design
  question is *what confirmation creates*: a capture and a task, or a task
  citing the entry. `architecture-trajectory.md` §4 governs, and the wrong
  answer is a second capture surface — the thing Heron deleted. **Answer it
  before work starts, not during.**
- **Idempotent under editing.** A journal entry is edited all day; a fingerprint
  over (entry, span, text) is the contract's field, doing real work the first
  time it is needed.
- **This is where the contract gets built**, because it is the first producer
  that has to carry Effect, a span, and a dismissal record from day one.

### 3 — A purpose field for projects

`Project` is `title`, `due_date`, `is_completed` (`src/lists/models.py:394`) —
no text at all. A short outcome-or-purpose field, task-core work under
`architecture-trajectory.md` §4.

Small, independently useful (it is half of S10), and the prerequisite for 4: a
project with only a title gives a matcher nothing to anchor against.

### 4 — Project preparation briefs · *waits on step 3*

On-demand, from the project page: prior material with the passage that selected
it. Reuses `concept_assignment`'s Tier-2 shape, where one end is a decision a
person made — a stated purpose being exactly such a decision.

**Last but not parked.** It needs step 3, and it is the first increment whose
value depends on accumulation rather than on the code being right — which is why
it sits behind the two that work from a cold start rather than behind a decision.

### 5 — An extractive weekly summary with citations

The week's confirmed connections, resolved questions, accepted commitments,
loose ends and concept candidates — each carrying the citation it already has,
grouped as *what happened · loose ends · upcoming constraints*. Additive to a
review whose honest denominators already work, and needing no ML decision at
all.

**Suggested focus and a draft plan are not in this increment.** Sections are
accepted, edited or dismissed independently when they arrive.

### 6 — The weekly-plan draft · *waits on capacity and intentions*

**It cannot be honest before the product collects what it needs.** A draft week
that cannot say *you have committed more than the week holds* is a list, and the
product has lists. It needs intentions above the day (S9) and effort/capacity
(S3) — and [`product-stories.md`](product-stories.md) calls S3 the sharpest test
of appetite in the whole set: if estimates go unentered, the story dies and takes
the capacity model with it.

Deterministic when it comes: cadence math, milestone pace, overdue and pinned
work, one discretionary rotation. A drafted week is confirmed, edited or
discarded, and a discarded draft is retained, because *"the planner proposed a
week I rejected"* is a signal about the planner.

## What this plan refuses

- **A generative finder.** AI explains and condenses; rules and retrieval find.
- **An LLM on the live path**, the weekly draft included.
- **A producer whose evidence is a score.** A confidence number is not a reason
  a person can read.
- **A producer without its invocation and its `/numbers/` row.**
- **A single merged proposal feed**, until one is deliberately designed rather
  than arrived at by adding producers to whichever surface is nearest.
- **A producer that answers rejection with wider guesses.**
- **Notifications.** Opt-in ritual only. The right to interrupt is earned after
  the surfaces prove useful, and they have not yet.

## Open decisions — Vince's, not this document's

**Increments 1, 2 and 3 depend on none of these and can start now.** The
decisions gate 4, 5's successor, and 6. **D1 is answered; three remain.**

1. ~~**D1. Is generated prose ever allowed?**~~ **Answered August 18, 2026:
   not yet, and the trigger is written below.** See *D1, decided* after this
   list — it is long enough to be its own section, and a deferral without a
   firing condition is the thing this document would be worst at.
2. **D2. Does S3 get built?** Gates increment 6, and the answer is about
   appetite for entering estimates, not about code.
3. **D3. What is each surface's budget?** Proposals per week per surface that a
   person will actually adjudicate. Without numbers, "gets quieter" has no
   threshold to fire at.
4. **D4. Does `sentence-transformers` enter the production image and the test
   requirements?** One producer is unrun and unmeasured today, so every
   accept-rate reading describes four producers while naming five. Fix the two
   dead `requirements-embeddings.txt` citations with whichever way it goes.

## D1, decided — not yet, and here is what would change it

**Vince, August 18, 2026. This is a deferral, not a refusal**, and the
distinction is load-bearing: refusals live in
[`architecture-trajectory.md`](architecture-trajectory.md) §7 and this does not
go there. Nothing is closed. What is decided is that **the assistant ships
extractive first and generation waits for evidence it is needed.**

**Cost was never the constraint.** `design-concept.md` priced the carve-out at a
few hundred calls a year against the eleven thousand it rejected, and a weekly
summary is fifty-two. Privacy and fidelity decide this, and they pull opposite
ways: a hosted model receives a payload selected for being the most charged
material in the corpus, and a local one trades that for small models reaching
for unsupported generalities — which is exactly the failure the assertion rule
forbids, so the privacy protection buys an accuracy risk rather than being free.

**The three candidate sites are not one question, and the plan had lumped
them.** In increasing order of what they hand a model:

| Site | Payload | Fit with the carve-out |
|---|---|---|
| Explaining one brief item | a purpose and a few cited spans | closest — per-item, bounded, on demand |
| Thread articulation | a handful of spans, selected for recurrence | the original carve-out itself |
| The weekly summary | **everything written that week** | **worst** — recurring, and arguably a standing pipeline stage wearing an on-demand coat |

The site that motivated D1 is the one that fits least. If this is ever reopened,
**the brief explanation is the defensible first site and the summary is not
carried along with it.**

### The trigger

Either condition fires it, and both are observable rather than felt:

1. **The extractive label degenerates.** A summary or brief section whose
   connection has no mediating concept and no distinguishing terms — the
   motif-mediated case `design-concept.md` says prose is *structurally*
   necessary for, since everything entity-mediated names itself. This is
   checkable in code: the extractive labeller returns nothing to show.
2. **A named miss.** After at least eight weekly summaries — a quarter's worth
   — **one specific week** where the citations were all present and it still was
   not possible to tell what had happened. Recorded as that week, not as an
   impression. Fewer than eight and there is no evidence, only impatience.

**Neither can fire before increment 5 exists**, which is the point: the carve-out
was designed to measure its own necessity, and an extractive summary nobody has
read yet cannot have failed anybody.

### What is still open if it fires

Local versus hosted stays deferred to implementation time on
`design-concept.md`'s own terms — evaluated against real material, not chosen in
advance. And **hosted has a dependency nobody has paid yet**: this project
commits to a plain statement of what AI processing does with your material, and
the terms and privacy policy that statement belongs in are still unwritten
(`roadmap.md`, *Open now*). Answering "yes, hosted" makes a document that does
not exist harder to write.

## Relationship to other documents

- Journey verdicts are owned by [`product-stories.md`](product-stories.md) and
  quoted nowhere else.
- The ML policy, the Attention Policy, the precision rule and the planning
  system's determinism are owned by the Second Mind documents at
  `C:\dev\Clarice_secondmind\docs\` — `design-concept.md` and `precision.md`.
- New models and fields, in either core, are governed by
  [`architecture-trajectory.md`](architecture-trajectory.md) §4.
- This plan is **not claimed by [`roadmap.md`](roadmap.md)**. Increments 1–3 are
  promotable; nothing is scheduled.
