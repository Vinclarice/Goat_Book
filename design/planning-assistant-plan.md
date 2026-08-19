# Planning assistant — a proposal contract, then six increments

Vince · plan · written August 18, 2026 · **revised the same day after review,
and its six increments confirmed as the product the same day**

**Five of the six increments are complete, August 18–19, 2026, on `main` and
undeployed** — and increment 1 finished last, having been first to start.
Only the weekly-plan draft remains, and S9 is its one blocker.

| # | State |
|---|---|
| 1 | **Complete.** The read, both decisions as epistemic facets, the age and recurrence context, and the section on `/mind/review/` |
| 2 | **Complete**, in four slices: `Facet` cites an entry, the journal producer, confirmation, and the card |
| 3 | **Complete.** `Project.purpose` end to end, model to text area |
| 4 | **Complete.** Retrieval, assembly, endpoint and the on-demand panel |
| 5 | **Complete.** Loose ends and upcoming constraints, read and rendered |
| 6 | Not started. Waits on S9 |

**All four decisions are answered** — D1, D4 and D3 on the 18th, D2 just after
midnight on the 19th. Nothing in this plan waits on one.

**The hold that shaped increments 1, 3 and 4 has expired.** Their server halves
were written while the navigation-and-identity work owned the presentation
layer, which is why each shipped without an interface and why 3 and 4 were
finished afterwards. Increment 1's is the only one still outstanding, and it
waits on design rather than on scheduling.

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

**Each surface's size is settled — see *D3, decided*.** The caps were never
missing; what was missing was anything acting on them, and a correct statement
of what each surface is actually rationing.

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
| 6 | A weekly-plan draft | weekly intentions (S9). Capacity no longer waits on anything — D2 |

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

### 6 — The weekly-plan draft · *waits on intentions*

**It cannot be honest without a way to say *you have committed more than the
week holds*.** A draft that cannot say that is a list, and the product has
lists.

**Half of that blocker is gone — D2, August 19, 2026.** Capacity comes from
observed throughput rather than from entered estimates, so this no longer waits
on `Item.effort` or on anybody's appetite for filling one in. What remains is
S9: intentions above the day, snapshotted the way `DailyFocus` snapshots a
commitment.

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
decisions gate 4, 5's successor, and 6. **All four are answered — D1, D4 and D3
on August 18, 2026 and D2 just after midnight on the 19th** — the sections below record each one and why. Nothing in this plan is
now waiting on a decision; what remains is work, and S9 is its only external
prerequisite.

1. ~~**D1. Is generated prose ever allowed?**~~ **Answered August 18, 2026:
   not yet, and the trigger is written below.** See *D1, decided* after this
   list — it is long enough to be its own section, and a deferral without a
   firing condition is the thing this document would be worst at.
2. ~~**D2. Does S3 get built?**~~ **Answered August 19, 2026: capacity yes,
   estimates no.** See *D2, decided* — the appetite question was dissolved
   rather than answered.
3. ~~**D3. What is each surface's budget?**~~ **Answered August 18, 2026: the
   caps stand, and the slots get rationed by accept rate.** The question was
   posed wrongly — see *D3, decided*.
4. ~~**D4. Does `sentence-transformers` enter the production image and the test
   requirements?**~~ **Answered August 18, 2026: test requirements yes,
   production image no.** It was two decisions wearing one number — installing
   it in tests makes the detector *measured* and costs CI time; installing it in
   the image makes it *run* and costs deploy size on every build plus droplet
   disk across the four images kept for rollback. The first is paid, the second
   waits for a corpus with something for the detector to say.

   **Verified, not assumed: 25 skipped became 0, and the knowledge core went
   from 652 passed to 677.** The naive version of this change would not have
   done that — `test_semantic_echo.py` sets `HF_HUB_OFFLINE=1` assuming a warm
   cache, and `encoder_available()` swallows every exception, so adding the
   package alone leaves the tests skipping while reporting the dependency
   "not installed". CI therefore fetches and caches the model before `pytest`,
   and installs CPU-only torch first, because the default Linux wheel is the
   CUDA build. `requirements-embeddings.txt` now exists, which resolves the two
   citations that had pointed at it for weeks — including an error message
   telling a person to install a file that was not there.

## D2, decided — capacity without estimates

**Vince, August 19, 2026** — just after midnight, where D1, D3 and D4 all landed
on the 18th. Dated from the commit rather than from the sitting. D2 asked whether S3 gets built, and
[`product-stories.md`](product-stories.md) framed it as the sharpest test of
appetite in the whole set: *if estimates would go unentered, this story dies and
takes the capacity model with it.* **The answer dissolves the test rather than
taking it.** Capacity is derived from what has already happened, so there are no
estimates to go unentered.

**The data is already there, and was captured on purpose.** `DailyFocus` records
what was pinned to a day, when it was chosen, and whether it was released;
completion lives on the task. `daily-operating-system-vision.md` requires that
denominator be recorded at the moment of choosing precisely because it *"cannot
be reconstructed after the fact from a mutable due date"* — so the planning-time
signal this needs is a read over records the product already keeps deliberately.

*"You have pinned nine for Tuesday; you have finished more than five on two of
the last thirty days"* costs nothing to say and asks nothing of the person.

**Two existing decisions this agrees with.** `design-concept.md` already held
numeric time and energy estimates back as *"their own source of friction"*, only
worth adding if a cheaper signal proves insufficient — S3 asked for exactly what
that paragraph deferred. And the whole product prefers derived history to stored
state; a capacity number entered by hand would be the mutable field the honest
denominators exist to avoid.

### What this deliberately does not buy

**It is count-based, so nine small things read the same as nine large ones.**
That is a real loss against S3 as written and is accepted: a signal that is
always available beats a better signal that depends on somebody maintaining
estimates for a year. If the count proves too blunt, `design-concept.md`'s
context tag is the next cheapest step and numeric estimates remain available
after that — the order is unchanged, this decision just declines to start at the
expensive end.

**It must not become a scold.** `daily-operating-system-vision.md` asks that
history be useful *without making missed work feel like punishment*, and "you
never finish what you plan" is exactly that failure. The signal states capacity,
never performance.

**Reuse, do not reimplement.** `review/reads.py` already computes planned
against completed for a week with the honest-denominator discipline intact. The
daily grain is the same computation, and two definitions of "what I got through"
would drift.

### What it does to S3

It delivers S3's *capacity* and its *planning-time signal* by a different route
than S3's `Requires` line names, and delivers no `Item.effort` at all. **Whether
that moves S3's verdict is [`product-stories.md`](product-stories.md)'s call and
not this document's** — that file owns the score and it is quoted nowhere else.
Recorded here only as the thing that changed underneath it.

## D3, decided — the caps stand; the slots get earned

**Vince, August 18, 2026.** D3 asked what each surface's weekly budget should
be, and both halves of that question were wrong.

**The numbers were never missing.** Six caps already exist, each chosen with its
reason written beside it:

| Cap | Value | Where |
|---|---|---|
| `REVIEW_LIMIT` | 5 | `mind/views.py` — proposals per visit to the review |
| `COMMITMENT_LIMIT` | 3 | `mind/views.py` — "the one kind that asks for a decision rather than offering a label" |
| `CANDIDATE_LIMIT` | 8 | `mind/views.py` — concept candidates |
| `BRIEF_LIMIT` | 8 | `mind/queries.py` — items in a project brief |
| `DEFAULT_MAX_PROPOSALS` | 3 | each detector — per node, per run |
| `open_review(limit=)` | 5 | `mind/services.py` |

**All six are ratified as they stand.** None was picked carelessly and none has
evidence against it yet.

**"Proposals per week per surface" is the wrong unit for two of the three.**
Only a queue is measured in throughput:

- **The review is a queue**, and the scarce thing is *five slots per visit*.
  How often it is opened is the person's business, not a quota.
- **The writing surface is inline, not a queue** — its unit is *per entry*, and
  three is already that number.
- **The brief spends no budget at all**, because it is asked for. A thing you
  opened deliberately cannot interrupt you, which is the Attention Policy's own
  test.

### What was actually broken

**Confidence is not comparable across detectors, and the queue is ordered by
it.** `shared_referent` emits a flat `0.9`, `open_question` a flat `0.55`,
`dormant_thread` a computed `shared_count / 8`. Those are not the same
quantity — one states an evidence *class*, another normalises a term count. Since
`queries.pending_hypotheses` and the `hypothesis_open` index both order by
`-confidence`, **the five slots are rationed by whichever constants somebody
picked**, while the measurement of what is actually useful — per-detector accept
rate, already computed in `instrumentation.detector_performance` — feeds into
nothing at all.

That is the real content of rule 2 above. "Gets quieter" now means something
specific: **a producer below 50% accept rate over a decided sample loses
priority for the five slots**, rather than being tuned, and rather than keeping
its claim on them because its author chose a high constant.

### What this waits on

**Two of the three producers still cannot be measured**, so this is specified
now and built with the shared contract in increment 2. Ordering by accept rate
before facets and mentions have decision records would ration the slots on one
producer's evidence and two producers' silence, which is worse than the constants
it replaces.

Not a threshold to invent later: 50% is already `retirement_gate`'s number, and
reusing it beats choosing a second one.

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

**Hardware recorded against the local side, August 18, 2026.** The argument
against local was that small models reach for unsupported generalities — exactly
what the assertion rule forbids — so privacy protection bought an accuracy risk.
Two machines change that, and the second changes it more than the first:

- The development laptop has an **RTX 4080 Laptop, 12 GB** (`nvidia-smi`, driver
  596.08). Runs a quantised 7–8B model, which is already not the class of model
  the concern was about.
- There is also an **RTX 3090, 24 GB, on a home desktop Vince could leave running
  at weekends**. That is a different proposition: 24 GB comfortably holds models
  well past the size where "reaches for unsupported generalities" was the
  objection, and *a machine that can be left running on a schedule is a batch
  host*.

**This fits the path the design document already permits, not the carve-out.**
The articulation carve-out is a *serving* path — user-initiated, on demand, with
a spinner — and production is a Droplet with no GPU, so no laptop or desktop can
serve it. But `design-concept.md` explicitly allows a heavier model **confined to
the batch job**, "invoked only by the periodic consolidation job", and puts that
job's cadence at nightly *or weekly*. A weekend run is inside the design as
written. In this configuration the privacy objection to local disappears
entirely: the payload — which is selected for being the most charged material in
the corpus — never leaves hardware Vince owns.

**So if D1 fires, "local" means batch and not on-demand**, which is a different
product decision rather than a smaller version of the same one. Proposals would
arrive weekly and be read in a ritual, which is what the Attention Policy asks
for anyway.

**The blocker moves rather than disappearing.** It is no longer "can a local
model be good enough" but **"how does a machine outside the deployment write to
it safely"** — production Postgres is not reachable from a home IP by design, so
this needs either an authenticated batch endpoint on `/api/v1/` or a deliberate
network decision, and it needs a visible failure mode: a desktop that is switched
off is a batch job that silently does not run, which is this repository's
most-repeated failure. `instrumentation.last_maintenance_run` already exists and
reports exactly that, which is the hook to use rather than a new one.

**None of this touches the encoder.** `all-MiniLM-L6-v2` is ~22M parameters and
the whole corpus encodes in seconds on CPU; no GPU accelerates anything that is
slow today. Recorded under D1 rather than D4 precisely because it is irrelevant
to D4 and would otherwise be filed against the wrong decision.

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
