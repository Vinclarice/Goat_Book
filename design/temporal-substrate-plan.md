# Temporal substrate and contextual retrieval — focused spec

Vince · focused spec · written August 20, 2026 · **widened twice the same day** ·
**not started, claimed by `roadmap.md` August 20**

## What this is

**Making memory a memory.** Four parts, which were four separate ideas for about
an hour before it became clear they are one claim:

1. **What memory can see** — the time axis, so a recollection can answer *what
   was going on around this* and *what developed afterward*, and so a
   resurfacing can be cued by a person's present rather than the sentence they
   just typed.
2. **How memory gives things back** — contextual retrieval. The central design
   problem, and the largest part of this brief.
3. **What memory notices** — structured observations proposed from the journal,
   because sleep, alcohol, mood and energy cannot be understood through textual
   similarity at all.
4. **What memory holds** — intake, because *Clarice stores it all* is a claim
   about getting material **in** before it is a claim about finding it again.
   **The brain dump lives here** and is the highest-bandwidth intake there is,
   at orientation and as an ongoing ritual.

**Widened twice, both Vince's call, both on the day it was written.** It began
as the time axis alone. The corrected model is that memory holds anything —
recipes, dream fragments, birthdays, fears, thoughts about people — and that
changes what retrieval owes, what the journal is for, and what intake must
reach.

**The heterogeneous memory is not the problem. It is the reason contextual
retrieval becomes the central design problem.**

## Part 1 — What memory can see

### What is already there, and what is not

**The knowledge core is a semantic index of thoughts.** Its twenty-one reads in
[`mind/queries.py`](../src/mind/queries.py) are adjacency in *meaning* —
`nodes_mentioning`, `confirmed_mentions_of`, `search_ranked`,
`confirmed_concept_labels`, similarity, threads. Two are already the shape
recollection wants: `material_bearing_on`
([`queries.py:580`](../src/mind/queries.py)) and `context_for_question`
([`queries.py:722`](../src/mind/queries.py)).

**The task core is a temporal index of a life**, and none of it reaches memory.
[`review/reads.py`](../src/review/reads.py) is week-grained end to end.
`DailyFocus` snapshots what was *chosen*, and `released_at`
([`daily/models.py:165`](../src/daily/models.py)) is how a pin ends, so a
decommitment can be told from a failure. `WeeklyReview` stamps the figure a
person concluded from.

**Neither can see the other, and the schema says so exactly:**

- **Memory has two intake pipes.** `Node` is created in exactly two places —
  `capture` ([`mind/services.py:204`](../src/mind/services.py)) and thread
  articulation ([`mind/services.py:1381`](../src/mind/services.py)). A `Facet`
  attaches to a `node`, a `daily.DailyEntry`, or a `lists` task.
- **`EventType` has 23 values and every one is about a note**
  ([`mind/models.py:775`](../src/mind/models.py)). Nothing about a task, a day,
  a week, a commitment, an outcome or a routine.
- **So the most carefully guarded structure in the codebase is a note log, not
  a life log.** `ActivityEvent` is append-only by database trigger with exactly
  one hole, for account erasure
  ([`0015_erasure_exemption`](../src/mind/migrations/0015_erasure_exemption.py)).
  The right structure with the wrong vocabulary.

**The one seam that exists runs the wrong way for this.** `confirm_actionable`
([`mind/services.py:662`](../src/mind/services.py)) has the knowledge core reach
into the task core, imported inside the function so the direction stays visible.
Under this work the dependency wants to run the other way — D1.

### What this inherits rather than rediscovers

- **A node-less event is already legal.** `MAINTENANCE_RAN`
  ([`mind/models.py:802`](../src/mind/models.py)) is owner-scoped and node-less,
  "unlike everything above it."
- **Adding a second cross-core foreign key is a move already made.**
  [`mind/models.py:335`](../src/mind/models.py): *"crossing into `daily` is the
  same move rather than a new kind of one."*
- **A quiet log reads as a quiet life, and this project has been caught twice.**
  `MAINTENANCE_RAN` exists so `/numbers/` can tell *ran and found nothing* from
  *never ran*; `retirement_gate`'s miss condition needs a non-zero baseline "or
  a quiet start reads as an improvement."

### The hard part: ingesting facts without building an event bus

`commercial-blueprint.md` Part 4 refuses domain events, an event bus and Django
signals, because they "create derived state that can drift, in a codebase whose
best property is that history cannot be silently rewritten." It is right, and
this must not quietly reverse it.

**The line: memory ingests facts, not derivations.** *"This commitment was
released on the 14th"* is a fact and belongs in an append-only row. *"This
project is stalling"* is a derivation and stays computed on demand, the way
`review` does today. **Nothing here may write a row that a read could have
produced.**

### Scope — what becomes an event

Slice 1 emits only where a durable decision already exists: `lists` when a task
is completed, released, or its commitment changes; `daily` when a focus is
pinned and released; `review` when a week is reviewed, an intention set, an
outcome chosen.

**Deferred by name**: routine occurrences, project pause and resume, area
changes, and every task-field edit that is not a change of commitment — a log
recording every keystroke of a task's text is a log nobody can read.

## Part 2 — Contextual retrieval

**Vince's architecture, August 20, 2026.** This part is the reason the brief was
widened and is larger than the other three together.

### The finding: several retrieval tricks, no retrieval architecture

Each existing mechanism is defensible for its original job:

- **Explicit search** uses PostgreSQL lexical ranking — right for *find that
  chicken recipe*.
- **`material_bearing_on`** ([`queries.py:580`](../src/mind/queries.py))
  retrieves notes sharing distinctive terms with a project purpose or outcome.
- **`semantic_echo`** finds similar sentences separated by enough time to be a
  dormant echo.
- **Concept and referent detectors** find material connected through confirmed
  names and aliases.
- **Part 1** adds what memory cannot currently see at all.

**They are individual retrieval tricks rather than one retrieval architecture,
and they share no understanding of intent.**

And the single implicit contract is tuned for the rarest mode.
`attention_tier`'s four tiers are decided entirely by actionability — *urgent*
and *active commitment* both require a confirmed actionable facet, *review
candidate* means due for review or cited in an open hypothesis, **and everything
else is "quiet knowledge."** A recipe, a birthday, a dream, a fear and every
thought about a person all land there. Under a corpus of decided things that
ladder was right; under a corpus that holds anything, quiet knowledge is not a
tier but the remainder, and it holds most of a life.

`detectors/dormant_thread.py`'s floors say the same thing in constants:
`MIN_DORMANCY` **548 days**, `MIN_LENGTH` **120 characters**,
`MIN_SHARED_TERMS` and `MIN_DISTINCTIVE_TERMS` 3 each, `MAX_PROPOSALS` 3. *"Mum's
birthday, 14 March"* can never surface. Neither can a recipe title or most dream
fragments. **These are correct settings for one mode** — the detector's own
reasoning is sound, precision over recall because "a stream of poor ones teaches
the person to skim past the review surface, and no later improvement recovers
that" — and there is only one set of them.

### The required shift: two independent axes

**Content type alone cannot decide relevance.** A chicken recipe is normally
irrelevant during weekly planning — but not if the week is a birthday dinner,
not if the intention was to cook at home, and not if the recipe came from the
person being remembered. The system must understand the *retrieval moment*, and
that is a separate question from what the memory is.

**Axis 1 — what kind of memory is this?** Roles, carried as **facets, not
exclusive folders**, because one memory holds several at once: a recipe that is
also *from Mum*, also *for Christmas*, also *something I want to try*.

> recipe or procedure · person · occasion or birthday · dream ·
> autobiographical episode · fear · desire · preference · observation ·
> question · decision · source · commitment · idea

**Capture stays frictionless. Clarice proposes the roles afterward and the
person corrects them.** This is not a new mechanism — `Facet` is already *"a
capability a node carries, without being filed as it,"* `capture never asks`,
`FacetKind` is *"open by design: new kinds are new values with their own
validation, not new tables, because the set is expected to keep growing,"* and
`origin` already separates a person's statement from a producer's guess.

**Axis 2 — what kind of remembering is happening now?**

| Mode | The question | Failure that matters |
|---|---|---|
| **Lookup** | find what I asked for | a miss — the person goes back to Google |
| **Recollection** | restore the context around something | context too thin to resume |
| **Discovery** | show potentially meaningful connections | noise, which is unrecoverable |
| **Planning** | evidence relevant to active outcomes and constraints | an irrelevant suggestion at a decision |
| **Reflection** | compare experience across a period | a comparison that is not like for like |
| **Resurfacing** | bring this back because the present cues it | interrupting for nothing |

**These modes must not share one final ranking.**

### The pipeline

The existing lexical, semantic, concept and temporal indexes all stay. **They
become candidate generators rather than final judges.**

```
What moment is this?
        ↓
Gather candidates from lexical, semantic, concept and temporal indexes
        ↓
Understand each candidate's roles, people, dates and relationships
        ↓
Apply eligibility rules for this moment
        ↓
Rank within the eligible set
        ↓
Explain why each result appeared
```

Worked through:

- **Searching "lemon chicken recipe"** searches everything and returns the
  recipe directly. No dormancy floor, no length floor, no eligibility narrowing.
- **Planning a birthday week** considers dates, people, active outcomes,
  calendar constraints and relevant desires. **The recipe becomes eligible
  because it connects to that birthday** — not because of what kind of thing it
  is.
- **Reviewing a difficult week** retrieves prior weeks with similar sleep,
  drinking, mood, commitments and outcomes — *not documents with generally
  similar prose*. This mode is why Part 3 exists.
- **Writing about an old friend** may restore memories, birthdays, promises,
  fears, photographs and unfinished questions attached to that person.

**The same store supports all of these. What changes is the retrieval
contract.**

*Explain why each result appeared* is not a nicety. It is the only thing that
lets a person argue with an eligibility rule instead of learning to distrust the
surface — and it is the same discipline as the planning assistant citing the
passage that caused each proposal.

### Success is measured per mode, or not at all

`retirement_gate`'s three conditions are confirmed hypotheses, detector accept
rates, and retrieval misses falling; `producer_performance` reports which
proposer is worth hearing from. **Every one grades a machine that proposes links
between notes** — which is what the numbers described, which is what got built.

**A search miss, a dismissed resurfacing, and an irrelevant planning suggestion
are three different failures. They cannot share one metric.** And they fail
differently in kind: a lookup miss is loud and recordable, a bad resurfacing is
recordable because it was dismissed, and **a missed resurfacing leaves no trace
at all.** Any single number over the three will report health.

### The revised principle

> **Clarice may contain anything, but it should never retrieve without knowing
> why the person is asking — or why the system is interrupting.**

### This part proposes; it does not decide

The Attention Policy and salience are `design-concept.md`'s, in Second Mind's
own `docs/`. `principles.md` §Scope is explicit that this file is not design
authority for the knowledge core. **Part 2 is a proposal to that document**,
with the evidence attached.

## Part 3 — What memory notices: structured observations

Sleep, alcohol, mood, exercise, illness and energy **cannot be understood
reliably through textual similarity at all.** They are quantities and states
over time, and Reflection mode is worthless without them.

**Clarice preserves the original journal entry and proposes structured
observations beside it**, namespaced:

> `sleep.woke_late` · `sleep.bedtime` · `alcohol.consumed` · `mood.anxious` ·
> `energy.low` · `exercise.completed` · `social.person` · `health.symptom`

**Explicit statements are recorded as facts; parsed ones stay labeled inferences
until confirmed or supported.**

**This needs no new model.** `Facet` already attaches to a `daily.DailyEntry`,
already carries a `JSONField` for data, already separates `EXPLICIT` from
`INFERRED` origin, already records which `producer` proposed it, and already has
`confirmed_at` and `retired_at`. An observation is a facet — which is the
existing schema doing what it was built for, and it means `architecture-
trajectory.md` §4 has nothing to rule on.

### What it lets Clarice say, and what it must not

> *Alcohol was recorded on 8 nights this quarter. Low energy was recorded the
> following morning on 6 of those 8, compared with 5 of 19 other recorded
> mornings.*

That is the honest-denominator discipline applied to a new domain — **recorded
mornings**, not all mornings, is the denominator, and it is stated.

**Two refusals, both load-bearing:**

- **It must not say drinking causes low energy.** The reading is a comparison of
  recorded rates and nothing more.
- **It must not read an unrecorded drink as sobriety.** A silent night is *not
  recorded*, never *did not happen* — the same absence problem as D5, in the
  place where it is most tempting to forget.

## Part 4 — What memory holds: intake

### The surface today

The capture box on `/mind/`; `/api/v1/capture`, which the phone and the Day page
both post to; the Android share target; the daily journal, producing facets on a
`DailyEntry` and never a `Node` — deliberately, because *"the same sentence
would live in two places and the journal would quietly become a second capture
surface"*; and importers for Markdown, `.docx` and JSONL.

### What is missing, and one thing that only looks present

**Attachments exist in the model and nothing can create one.** `Attachment`
carries a node foreign key and a `byte_size`; *"a node may be attachment-only"*
is a cross-table invariant; `capture()` takes an `attachments` sequence and
writes the rows. But **`FileField`, `ImageField` and `request.FILES` appear
nowhere in `src/`**. **The fifth un-switched-on seam in a fortnight**, after
`/healthz`, the uninvoked detectors, `Backends.isSplit` and
`resolve_retrieval_miss`. Switching it on is the smallest real win here, and it
is what makes images, audio and documents possible at all.

**No URL intake.** Recipes live at URLs, and saving one usefully means fetching
at least a title — see D7, that is not free. **No email intake**; Resend sends
and does not receive.

### The brain dump

**The highest-bandwidth intake surface there is, and it costs a text box.**
Empty your head — everything on your mind, no decisions about what any of it is.
Two uses, and they behave differently enough to be worth telling apart:

- **At orientation.** A new person arrives carrying years of material. A dump is
  how it gets in, and **it is also how the six invented concepts get taught** —
  Area, Project, Checklist Step, Compass, Focus, "call it enough" — by being
  demonstrated on the person's own sentences rather than explained in a tour.
  That converts `commercial-blueprint.md` Part 5's *"explain the six invented
  concepts somewhere in the product, once"* from a documentation task into the
  first thing the product does, and it is a better answer to S1's *"within four
  minutes he has captured a thought and planned a day"* than any tutorial.
- **As an ongoing ritual.** Periodic *what is on your mind that is not written
  down anywhere*. This is the counterweight to a real weakness named in the same
  session that produced this brief: **a memory fed only by deliberate capture
  inherits the biases of the brain doing the capturing**, because you chose what
  to write down under the same motivated cueing. A sweep gets what filtering
  missed.

#### A fragment is a submission, not a sentence

**Capture is atomic and the person draws the boundaries.** Each *keep and
continue* is one fragment and one `Node`. **No segmentation is involved, and an
earlier draft of this brief wrongly implied otherwise**: `services._SENTENCE`
splits a `DailyEntry` into passages so the journal commitment parser can cite
the sentence that caused a proposal — its only use is at
[`services.py:1727`](../src/mind/services.py) — and it has never created a
`Node`. A splitter exists; the splitting a dump would need does not.

**A multiline paste is a product decision, not a parsing one.** If several lines
should become several memories, **show a preview and ask.** Never split a
submission silently: a dump is precisely the surface where a person is least
able to predict what the system did with what they typed.

#### The session is its own record

**A dump is not a container node.** `NodeSource.THREAD` is a semantic conclusion
distilled from several memories — searchable content that participates in the
graph. **A dump is provenance**: an occasion during which several independent
memories were captured. Those are different things, and conflating them would
put a node that is not a thought into the graph.

So a small **`CaptureSession`**, with each `Node` carrying an optional reference
to it and **no `MEMBER_OF` edges at all**:

> owner · mode (orientation or ongoing) · started and finished timestamps ·
> state (finished, abandoned, timed out) · processing state · proposal budget ·
> optional prompt provenance

**It passes `architecture-trajectory.md` §4 on the strict reading** — a session
has a life cycle and behaviour that individual nodes do not. A shared timestamp
cannot represent duration, completion, a budget, which prompts were used, or
whether processing has run.

#### The hazard is two hazards, at two different times

- **Immediately, and synchronously.** `_propose_any_commitment`
  ([`services.py:314`](../src/mind/services.py)) runs **on the live path for
  every captured node**, deliberately — *"the parser is deterministic, rules and
  a regex, no model, no network, no per-call cost,"* which is what lets capture
  stay one box that returns immediately. Forty fragments therefore create **up
  to forty actionable facets before any detector job has run at all.**
- **Later, in batch.** The five connection detectors do **not** run in the
  capture request; they run through `run_mind_maintenance` → `run_detectors`.
  Three proposals each across forty nodes is a real bound on the eventual review
  flood, but it is a batch bound, and an earlier draft of this brief stated it
  as a live one.
- **And more is coming.** Part 2's role facets, and the concept and question
  producers, all add attention-demanding output.

`dormant_thread`'s reasoning is still the warning: *"a stream of poor ones
teaches the person to skim past the review surface, and no later improvement
recovers that."*

**So the budget must cover every attention-producing mechanism, not only the
five connection detectors.** That is the correction that matters most — a cap
scoped to the detectors would have left the synchronous commitment parser
completely uncapped, and it is the one that fires first.

#### Two budgets, and no backlog

- **A processing budget** — how many proposals are materialized from the session
  at all.
- **An attention budget** — how many are shown now.

The flow:

1. **Save every fragment immediately** as an ordinary node. *Capture is durable
   before it is clever*, and nothing here weakens that.
2. **During the dump, create nothing that requires attention.**
3. **When the session ends, run all producers in read-only mode.**
4. **Aggregate and deduplicate across the whole session.** Forty fragments about
   one project must not become forty findings about it.
5. **Materialize a small total** — five is the working number — with **no
   producer contributing more than two.**
6. **Show at most three immediately.**
7. **Mark the session processed**, so the next maintenance run cannot process its
   forty nodes independently and walk straight around the cap.
8. **Keep every fragment as a candidate** for future captures and retrievals.

**No slow-release queue.** A backlog dribbling out hundreds of session findings
is the Second Mind inbox this design refuses, wearing a schedule.

**And nothing valuable is discarded, because the person wrote memories, not
proposals.** Every fragment stays searchable and can produce a new finding the
moment a future context makes it relevant. **A stale inference from orientation
does not earn screen time later merely because it once ranked sixth.**

#### What can fire during orientation

**Not the flat "there is no corpus" an earlier draft claimed.**
`shared_referent`'s `DEFAULT_MIN_GAP` is `timedelta(0)` — it was built and
tested for two notes from one sitting, and it keys on confirmed mentions and
aliases rather than on age. So it is silent at the *start* of an orientation
dump and **can connect fragments from that same dump** once concepts or aliases
have been confirmed. **A sequencing dependency, not an unavailability.**

`dormant_thread` genuinely cannot fire: its floor is 548 days.

#### Orientation stays optional, and progressive

A dump can take far longer than S1's four-minute first-success target, so it must
not be the only door. **Two entrances:**

- **Quick start** — capture one thought, plan today.
- **Empty my head** — the deeper orientation dump.

And **explain only the concepts the person's own material actually
demonstrates.** No dump can be guaranteed to contain a Project, a Checklist
Step, a Compass, a Focus *and* a "call it enough" — and explaining one that is
not there turns personalised interpretation back into a tutorial, which is the
thing it was supposed to replace. Whatever the dump does not reach, something
else has to.

**And a dump invites more sensitive material than a task box does.** Fears,
resentments, things about other people. Nothing about the existing guarantees
changes — owner-scoped, `send_default_pii=False`, export and deletion — but the
surface should be honest that emptying your head is what it is for, and the
review of what it proposed should be as easy to reject wholesale as to accept.

### Intake spends a security property, and that must be deliberate

`commercial-blueprint.md`'s verdict lists as a *positive*: **"No raw SQL, no
file upload, no SSRF, no open redirect: not merely no bugs, no attack
surface."** Two of those four are what this part proposes to add. Neither is a
reason to refuse; both are a reason to name the cost here rather than discover
it in review, and to do them one at a time.

**And both touch published promises.** `/privacy/` names DigitalOcean, Resend
and Sentry as the three processors, with a dozen tests holding the claims that
have a mechanical counterpart. File storage or inbound mail changes that list —
D9.

## Increments — four tracks

**One prerequisite outside this brief:** finish unified search as scoped
([`search-plan.md`](search-plan.md) increment 5). **The current search is not
what needs overhauling** — it is building the correct literal-retrieval
foundation, and its refusal to merge incomparable document sets is right. The
overhaul sits *above* it.

Track A and Track D can run in parallel. Track B wants A's temporal candidates
and D's material to be worth widening for. Track C feeds B's Reflection mode and
nothing else.

### Track A — the time axis

1. ~~**The vocabulary, emitting nothing.**~~ **Shipped August 20, 2026**
   (`0844d47`). Ten life events; `ActivityEvent` gained `task` and `entry`,
   non-constraining for the reason its `node` reference already gives in full.
   **No exactly-one-subject constraint, unlike `Facet`** — `confirm_actionable`
   turns a thought into a commitment and that event honestly has both, while a
   reviewed week has neither. `test_erasure.py` and `test_invariants.py` pass
   unchanged and on purpose.
2. ~~**The task core emits.**~~ **Shipped August 20, 2026** (`ffbd19a`). Ten
   emit sites through [`clarice/life_log.py`](../src/clarice/life_log.py), and
   **four deferrals held by tests rather than left as omissions**: an ordinary
   field edit, writing in the day, opening the planner, and the mechanical
   archive a recurring completion performs on itself. No backfill, no reads.
3. **Backfill what carries its own timestamp.** **Nothing invented** — no
   recorded time, no event; reconstructed events are marked so a reading can
   tell a record from a re-presentation.
4. **`around()`** — what else was in the log near an instant. The first read
   that crosses.
5. **`since()`** — what developed after a node, gated on D4. **If D4 cannot be
   answered honestly, stopping at four is the correct outcome.**

### Track B — roles and modes

6. **Multi-valued memory-role facets.** Proposed after capture, corrigible,
   never asked for. D6 settles how the kinds are shaped.
7. **Modes named in code**, each surface declaring which mode it is in and what
   its present context is. Lookup loses the dormancy and length floors it should
   never have had; Discovery and Resurfacing keep them.
8. **Candidate generators behind one contract.** Lexical, semantic, concept and
   temporal indexes stop being final judges; eligibility and ranking move above
   them.
9. **Every result explains why it appeared.**
10. **Per-mode measurement**, replacing one blended number. D8.

### Track C — observations

11. **Extraction proposing namespaced observation facets** from journal entries,
    explicit statements as facts and parsed ones as inferences.
12. **Reflection reads them with stated denominators**, and refuses both causal
    language and the sobriety inference.

### Track D — intake

13. **`CaptureSession`, and session-aware processing**, before any dump surface
    exists. The two budgets, the read-only producer pass at session end, the
    cross-session dedupe, and the processed flag that stops the next maintenance
    run walking around the cap. **Ordered deliberately**: ship the surface first
    and the first dump is the one that teaches a person to skim past the review
    surface, which is not recoverable.
14. **The brain dump surface.** Atomic fragments — one *keep and continue*, one
    node — with a preview-and-ask on multiline paste and no silent splitting.
    The ongoing ritual and the orientation flow are the same surface with
    different copy and a different corpus behind them.
15. **Orientation built on it, as one of two entrances** — *quick start* beside
    *empty my head* — explaining only the concepts the person's own material
    demonstrates. This carries the invitation bar's third item, and v3's
    *Usable* release holds it.
16. **Switch attachments on** — upload path, size limit, content-type handling,
    storage.
17. **URL intake**, if D7 says the SSRF surface is worth it.
18. **Email intake**, or a recorded deferral with a trigger.

## Open decisions — Vince's, not this document's

1. ~~**D1. Which direction does the seam run?**~~ **Answered August 20, 2026:
   a module in `clarice/` belonging to neither core** —
   [`clarice/life_log.py`](../src/clarice/life_log.py), the placement
   `clarice/search.py` has and `clarice/scheduled_mail.py` took a week later.
   **The payoff is an import that does not happen:** `lists`, `daily` and
   `review` name none of `mind`, `ActivityEvent` or `EventType`, because the
   vocabulary is re-exported there.

   **The cycle argument does not apply and was not the reason.** Both
   directions already exist — `lists/projects.py` imports `mind.queries` at
   module scope, and `mind` imports `lists` in three places. What decided it is
   that three apps creating rows would restate the emit rules three times, and
   two definitions of one thing is how they come to disagree.

   **A second answer travelled with it: both or neither.** `record` is called
   inside the caller's own atomic block and raises rather than swallowing, so a
   completion whose event could not be written is not a completion. Swallowing
   would make the log a sample and leave every read over it with a silent hole
   — the failure `MAINTENANCE_RAN` exists one layer up to prevent. This needed
   `complete_item` to become atomic, which it was not: two saves and a spawn,
   each committing alone.
2. **D2. How far back does backfill reach, and how is a reconstructed event
   marked?** The argument for it is that the task core already holds the
   history; the argument against inventing any is that this codebase left defect
   2's misdated routine records alone rather than guess at a durable record.
   `Facet.origin`'s split is the shape to copy.
3. ~~**D3. Payload snapshot, or foreign key only?**~~ **Answered for slice 1
   only, August 20, 2026: a foreign key where one exists, and the payload for
   what has none.** The week's Monday is the single payload key slice 1 has,
   because a week is neither a task nor a day's entry — and a subject column
   invented for one cadence is a column the monthly and quarterly horizons
   would not fit.

   **Nothing snapshots a subject it could join to.** `WeeklyOutcome` already
   keeps its own text and its project's title; `DailyFocus.task_text` already
   snapshots the one case where a snapshot is the point. A third copy in an
   append-only row is a copy that can never be corrected, which is the one
   place a wrong value would outlive its fix. **Still open for later slices**,
   where an event may genuinely have no row behind it.
4. **D4. What makes a later event *bear on* an earlier node?** The rule
   deciding whether *what developed afterward* is a recollection or a list of
   everything since.
5. **D5. Can the log answer absence?** *"Since then, nothing has been recorded"*
   is honest only if the log can prove it was looking. `MAINTENANCE_RAN` is the
   precedent. **Part 3's sobriety refusal is the same decision** in the place a
   person will feel it.
6. **D6. Are roles new `FacetKind` values, or one kind with typed data?**
   `FacetKind` says a new kind should be a value rather than a table — but
   fourteen kinds each with their own validation is a different proposition from
   three, and they are multi-valued by design. `design-concept.md` owns the
   Attention Policy this feeds.
7. **D7. Is URL intake worth reopening SSRF surface?** An allowlist or an egress
   proxy is the price. The alternative is storing a URL as text and fetching
   nothing — cheaper, and much less useful.
8. **D8. What are the four metrics?** Lookup, planning, recollection and
   resurfacing fail differently, and **a missed resurfacing leaves no trace at
   all.** If one of the four has no honest signal, say so rather than grading it
   by proxy.
9. **D9. Where do attachment bytes live, and what does that do to the published
   promises?** Storage adds a processor or a volume, and `/privacy/`'s named
   list is test-held. **Export and deletion shipped August 16 exporting every
   owned *row*** — files are not rows, so an attachment that cannot be exported
   or purged breaks a promise that currently holds.
10. **D10. Email intake — scope it, or defer with a trigger?** Deferring without
    one is what `roadmap.md`'s Track D refuses, and `principles.md` now says a
    trigger that cannot fire is a refusal.
11. ~~**D11. What shape is a per-occasion proposal budget?**~~ **Answered
    August 20, 2026: two budgets, and no backlog.** A *processing* budget
    bounding what is materialized at all, and an *attention* budget bounding
    what is shown now — see Part 4's flow. **The slow-release option was
    rejected on principle rather than on cost**: a queue dribbling out hundreds
    of findings is the Second Mind inbox this design refuses. And the scoping
    correction is the load-bearing half — **the budget covers every
    attention-producing mechanism**, including the synchronous commitment
    parser, not only the five connection detectors. The per-capture caps stay;
    they are correct for a capture.
12. ~~**D12. Is a dump a container node?**~~ **Answered August 20, 2026: no —
    a `CaptureSession` record.** `NodeSource.THREAD` is a semantic conclusion
    that participates in the graph; a dump is provenance. The session earns its
    own model under §4 because it has a life cycle and behaviour nodes do not,
    and a shared timestamp cannot carry duration, completion, a budget, prompts
    or processing state. Each node gets an optional session reference and no
    graph edges.
13. ~~**D13. Is voice intake in scope?**~~ **Answered August 20, 2026: not in
    the first slice, and the path is preserved.** Typed dumping validates the
    interaction first. Audio needs attachment storage, export, deletion and a
    privacy disclosure before it needs transcription — and **storing audio
    without searchable text does not deliver the assembly a dump is for.**
    Transcription remains an ML-policy question for `design-concept.md`, not an
    engineering one.

## What this refuses

- **An event bus, domain events, or Django signals.** Facts, not derivations.
- **Moving `Item` into `Node`.** The inversion is conceptual;
  `architecture-trajectory.md` §7 is untouched.
- **Asking what a thing is at capture.** Roles are proposed and corrigible.
  Anything else rebuilds the `Capture → Idea → Task` pipeline Heron deleted,
  with fourteen new nouns instead of three.
- **Exclusive folders.** Roles are multi-valued; a recipe from Mum for Christmas
  is three roles and not a filing conflict.
- **One final ranking across modes**, and one blended metric over them.
- **A stored attention tier.** It is derived at read time on purpose, because "a
  stored tier is a second source of truth for something that changes with every
  capture."
- **Deciding the Attention Policy.** Part 2 proposes to `design-concept.md`.
- **Causal language over observations**, and reading an unrecorded night as a
  sober one.
- **Overhauling unified search.** It is the correct foundation; this sits above
  it.
- **A brain dump surface before session-aware budgeting exists.** The order is
  the whole safety of the feature.
- **Splitting a submission silently.** A fragment is what the person submitted.
  Multiline paste gets a preview and a question, never a guess.
- **A proposal backlog.** No queue slowly releasing session findings — that is
  the inbox this design refuses, on a timer.
- **A dump as a container node.** Provenance is a session record, not graph
  content.
- **Inventing history.** No event without a recorded timestamp on the source row.
- **A second event log.** `ActivityEvent` gains a vocabulary, not a sibling.

## A correction this brief owed `product-stories.md`, since made

That file's three-loop table said *"The second brain is not a fourth loop. It is
the memory of the third one."* Vince's call, August 20, 2026: **that was wrong**
— memory is the substrate, and the three loops are tempos of reading and writing
it. **Corrected in `product-stories.md` the same day**, which owns the fact.

## Where the facts live

Whether this is active, deferred or open is [`roadmap.md`](roadmap.md)'s. What
order the work goes in and toward what is
[`clarice-v3-plan.md`](clarice-v3-plan.md)'s. What shipped and how it was
verified is [`roadmap-history.md`](roadmap-history.md)'s. **The Attention
Policy, salience, and what each core owns are `design-concept.md`'s**, in Second
Mind's own `docs/` — Part 2 proposes to it and does not restate it. Literal
retrieval is [`search-plan.md`](search-plan.md)'s. How the product scores is
[`product-stories.md`](product-stories.md)'s.
