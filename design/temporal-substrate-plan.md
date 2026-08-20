# Temporal substrate and contextual retrieval — focused spec

Vince · focused spec · written August 20, 2026 · **widened twice the same day** ·
**not started**

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

1. **The vocabulary, emitting nothing.** `EventType` gains its life-event
   values; `ActivityEvent` gains the nullable subject foreign keys `Facet`
   already carries. Acceptance: the append-only trigger still refuses `UPDATE`
   and `DELETE` on the widened table, and `purge_account` still clears an owner
   completely — `mind/tests/test_erasure.py` must keep passing on purpose.
2. **The task core emits**, at the service functions where something durable is
   already recorded. No backfill, no reads. D1 is answered in code here.
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

13. **Switch attachments on** — upload path, size limit, content-type handling,
    storage.
14. **URL intake**, if D7 says the SSRF surface is worth it.
15. **Email intake**, or a recorded deferral with a trigger.

## Open decisions — Vince's, not this document's

1. **D1. Which direction does the seam run?** `lists` importing `mind`, `mind`
   exposing a thin ingest function, or a module in `clarice/` belonging to
   neither. **`search-plan.md`'s own D1 predicted this** — it named
   `clarice/search.py` as where the question would be asked again. This is that
   second asking, one document later.
2. **D2. How far back does backfill reach, and how is a reconstructed event
   marked?** The argument for it is that the task core already holds the
   history; the argument against inventing any is that this codebase left defect
   2's misdated routine records alone rather than guess at a durable record.
   `Facet.origin`'s split is the shape to copy.
3. **D3. Payload snapshot, or foreign key only?** `ActivityEvent` has both, so
   there is precedent either way. The answer probably differs per event type,
   which is itself a decision.
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
