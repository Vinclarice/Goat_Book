# Clarice v3 — bringing the cores together, and making it usable

Vince · long-form plan · written August 20, 2026 · **claimed by `roadmap.md`
the same day**

## What v3 is

Two thrusts, in service of one destination.

- **Bring the two cores together.** The merger shipped on August 14 and unified
  the *plumbing* — one tree, one database, one API, one login, one deploy. It
  never unified the *model*. `Node` and `Item` remain two primitives joined by
  one seam running one direction, and the append-only event log speaks only
  about notes. The result is two good products sharing a login.
- **Make it actually usable.** [`product-stories.md`](product-stories.md) scores
  ten journeys as *bends* — the capability exists and the product fights the
  person. Until August 20 nothing in `principles.md` said a bend was work, so
  none of them ever competed for time.

**This is deliberately a long planning document.** Vince's call, August 20,
2026, overriding `commercial-blueprint.md` Part 8's refusal of exactly that.
The refusal was written for a product whose direction was settled and whose
remaining questions were commercial; this one's direction changed. **It replaces
`commercial-blueprint.md` Part 6's phases 2 through 5.** Part 1 (closed), Part 4
(architecture), Part 7's wedges (deferred, not withdrawn) and Part 8's other
refusals all stand; that file keeps them.

**This file is comprehensive about the plan and restates no implementation
detail it does not own.** [`temporal-substrate-plan.md`](temporal-substrate-plan.md)
is the focused spec for the substrate, contextual retrieval, observations and
intake; [`search-plan.md`](search-plan.md) owns literal retrieval. Releases
below name what they contain and link rather than copy.

## The destination

**Clarice is the instrument by which accumulated experience produces fewer,
more honest commitments.**

The split between the cores is what makes it buildable:

- **The knowledge core assembles memory into continuity** — a thread you can
  pick back up, restored with enough context that you do not have to begin
  again. Its question is *can I restore the unfinished thought faithfully?*
- **The task core assembles that continuity into present judgment** — a compact
  presentation of a situation ending in a decision only the person can make.
  Its question is *what does this memory change?*

The presentation is a briefing. The interaction is a question. The tempo is a
review ritual. The graph is machinery backstage. **The product is the resulting
judgment**, and the judgment becomes evidence for the next one.

Neither a map nor a narrative is the target form. Making a person navigate the
graph hands the assembly problem back to them, and a system that tells someone
who they are becomes flattering and self-sealing very quickly. Both remain
supporting views.

**And memory holds anything** — recipes, dream fragments, birthdays, fears,
thoughts about people. The heterogeneous memory is not a problem to be managed;
it is the reason contextual retrieval is the central design problem.

## What was decided on August 20, 2026

Vince's calls, recorded once because several documents are downstream:

1. **Clarice is a personal tool, with an intent to invite people.** Not a
   business — `commercial-blueprint.md` Part 9 #1. Billing, pricing, packaging
   and entitlements are refused while this stands, and **analytics is not
   needed**, which keeps `/privacy/`'s absolute no-analytics claim true for free.
2. **The wedge is deferred** (Part 9 #2), decidable when invited people can say
   what they would miss — the one question that genuinely needed somebody else.
3. **Mobile (Part 9 #4) is answered: "on a phone" means the Android app too.**
   Not a freeze and not a full client — the app grows where a journey needs it.
   The market argument ("responsive web serves iOS simultaneously") was about a
   market that does not exist here; what settled it was that S2's Android half
   needed **no backend work at all**. The 13-of-40 token-reachability figure is
   a warning about particular journeys, not a general bar.
4. **The second brain is the substrate, not a core beside the task core.** A
   conceptual inversion, explicitly **not** a merge of `Node` and `Item`.
5. **`principles.md` was rewritten** (`217243d`): a bend is a defect, the main
   surface can do the main thing, felt friction is evidence, automations act
   reversibly, and a trigger that cannot fire is a refusal.
6. **A drafted day proposes; it never pins.** The moat is that `DailyFocus`
   records what a person *chose*, and an auto-pinned focus would quietly change
   what the finish rate measures.

## How v3 is scored

[`product-stories.md`](product-stories.md), and nothing else. It stands at
**3 works · 10 bends · 6 impossible** and that file owns the number; the
releases below name which stories each is trying to move, so the score can
contradict the plan rather than the plan grading itself.

Two of the six impossible are refused rather than pursued: **S1** wants the
approval gate removed, which is a policy decision already taken the other way,
and **S19** is billing. v3's reachable ceiling is therefore **17 of 19**.

## What v3 inherits, and why it is cheaper than it looks

**`kestrel` and the planning assistant's v2 already paid for these
substrates.** Read the score's own `Requires` lines rather than the verdicts:

- **S3** — *"the comparison the draft already makes, applied to the week being
  reviewed. No model, no field, no new read — an argument's difference."*
- **S9** — *"a retrospective that reads the intention beside the week's own days.
  No model, no service, no field."*
- **S14** — *"one relationship short rather than a model short"*, and **"still
  the differentiator — the graph accreting from what you were already doing
  rather than being built by hand."**
- **S12** — half-built, and **"still the story that makes the two cores one
  product"**.
- **S11** — `Decision` as a record, and not hypothetical:
  `architecture-trajectory.md` §7 and §8 **are** that practice, kept in Markdown
  because the product cannot hold it.

Four of the ten bends need no new model at all. That is the difference between
this being a year and being a quarter.

## New models, and what each answers to

`architecture-trajectory.md` §4's test is the strict one — **a concept earns its
own model when it has a different life cycle, not when it has a different
name.** Every model v3 proposes is argued against it here, in one place, so the
charter can be pointed at rather than paraphrased.

| Proposed | Verdict | Why |
|---|---|---|
| **`Decision`** | **Earns it** | *decided → held → returns on condition → revisited or superseded* is unlike `Item` (open→done), `Facet` (proposed→confirmed→retired) or `Node`. S11 |
| **`Event`** (calendar) | **Earns it** | **It happens at a time whether or not you act, and is never completed.** No task has that life cycle |
| **`CaptureSession`** | **Earns it** | A session has duration, completion state, a budget, prompt provenance and a processing flag. A shared timestamp carries none of them |
| **`Bill`** | **Fails — sidecar instead** | *arrives → due → paid → next occurrence* **is** a recurring task's life cycle, and `daily-operating-system-vision.md` uses **"pay rent every month"** as its canonical example of one. A one-to-one `Bill(item, amount, currency, payee)` adds attributes without claiming a life cycle, and keeps a column that is null for 99% of rows off the hottest model in the application |
| **Observations** | **Needs no model** | `Facet` already attaches to a `DailyEntry`, already has a `JSONField`, already separates `EXPLICIT` from `INFERRED`, and already records its producer |

**Not a facet, for the bill amount.** `Facet` carries *inferred capabilities*
with a confirmation flow; a number a person typed is a fact, and putting it in
the proposal table muddies both.

## What v3 needs that does not exist at all

Three absences found by checking rather than assuming, each cheap to miss:

- **No lead time, anywhere.** No `days_before`, no `notify_before`. Nothing in
  Clarice can remind you of anything *in advance* of its due date.
- **No annual or quarterly recurrence.** `Item.Recurrence` is `WEEKLY` and
  `MONTHLY` only, so a property tax bill is not expressible.
  [`lists/models.py:16`](../src/lists/models.py) warns this enum has a known
  ripple; adding values is not a one-line change.
- **No notification surface.** The only outbound channel is the 07:00 digest,
  which *"ends 'Open Clarice to work through them.' with nothing clickable."*
  **An advance reminder needs somewhere to arrive**, and that is a larger cost
  than the amount field it serves.

## The releases

**Named, never lettered in advance.** `roadmap.md` is explicit that letters are
never reserved for a subject — Vince's call, August 15, 2026, after
`architecture-trajectory.md` §5 attached commercial readiness to "release G" and
Godwit spent it on the merger.

**Every release ends in something Vince uses daily, or it is wrong.** This is
the plan's largest risk written as a constraint: the substrate work is three
invisible increments followed by two invisible reads, and a programme of that
shape can run for months producing nothing anybody touches — which is exactly
what this conversation diagnosed, where fourteen increments of planning
machinery shipped while *move a task to another area* did not.

### Close L — finish what is already open

Open since August 19 and half-deployed since. Unified search is on `main` and
**undeployed**; the second factor is installed and enforcing nothing. Deploy,
verify, tag the deployment, choose the bird. **Nothing new ships.** It is first
because the letters stopped meaning anything once already — six of seven work
items shipped outside the release structure between August 6 and 12 — and a
release that never closes is how that starts.

### Usable — the bends

The release that answers *"it serves a purpose but it isn't really useful."*
Nothing here waits on anything else, and most of it is small.

- **The Day page gets verbs.** [`DayRoute.tsx:120`](../frontend/src/app/routes/DayRoute.tsx)
  declines a Complete button to avoid reimplementing the agenda's mutation
  beside it. Real cost, not a veto: *one rule, one authoritative definition*
  says how to pay it. The vision document calls the Daily Page **the main
  working surface** and it cannot do the main thing.
- **The draft's own comparison applied to the week being reviewed** — S3, an
  argument's difference.
- **The other two rows of the review act in place** — S7, through the owning
  core's services.
- **The weekly retrospective reads the intention beside the week's own days** —
  S9, no model, no service, no field.
- **Task priority.** A to-do core with recurrence, routines, pauses and
  snapshot denominators and no priority field is unbalanced.
- **Moving a task between areas.** [`lists/api.py:197`](../src/lists/api.py)
  accepts six fields and `list` is not among them.
- **Links in the digest email.**
- **The 44px floor into the link primitive**, finishing August 18's half-fix.

~~**Acceptance: S2, S3, S7 and S9 reach *works*.**~~ **Met August 20, 2026,
and the release is complete** — all four stories, plus task move between areas,
the digest's links, the 44px floor on the links that were left, and task
priority. The score went 3 · 10 · 6 to **7 · 6 · 6**
in a day, after two releases moved one verdict between them, and the reason is
this plan's own §*What v3 inherits*: three of the four were an argument's
difference, a read nobody had written, and the same treatment applied twice.

### The day — planning and review stop being manual

The daily loop's whole write surface is three functions — `write_entry`,
`pin_task`, `unpin_task`. **The weekly loop got fourteen increments of assistant
and the daily loop got a form**, and daily runs seven times as often.

- **`draft_day`.** `typical_day_for`'s docstring settles the shape: *"D2 is
  explicit that the daily grain is the same computation as the weekly one and
  that two definitions of 'what I got through' would drift."* So this is
  `draft_week`'s selection rule at a one-day window — **not a new planner** —
  including its refusals: dated work only, overdue first, routines named apart
  because a routine never spawns a task, and the someday pile left alone.
  - **It proposes; one click accepts the set.** `draft_week` already *"writes
    nothing… opening the planner twice changes nothing either time."*
  - **Computed on read, never stored**, following `attention_tier`. The accept
    therefore **pins what was shown**, carrying the ids it displayed rather than
    re-deriving — Bittern's `Idempotency-Key` contract is the reference.
  - **Capacity marks, it does not truncate.** `typical_day_for` returns a median
    and **`None` below the sample floor rather than zero**, so the draft has
    three states: bounded by a known capacity, honest about not having one, or
    marking the overflow.
  - **Record that a day's set came from an accepted draft.** Without it,
    rubber-stamping and genuine agreement are indistinguishable, and the finish
    rate quietly becomes a measure of how good the draft is. It is the same
    instinct as `typical_day_for` refusing to let a day be its own evidence.
- **The daily brief.** Two halves with different contracts. **The plan half** is
  bounded by capacity and ends in the accept. **The awareness half reports
  change, not state** — *what changed, and does today still make sense?* — which
  is what keeps seven sections from becoming a dashboard, the thing the
  destination explicitly refuses. On a quiet day it is two lines, and short is
  the correct output rather than a failure.
  - **A someday item may be surfaced, never planned.** *"Take a look at this"*
    is Resurfacing, a different mode with a different contract, so
    `draft_week`'s refusal is respected rather than amended.
  - **No ranking across the sections.** A bill against a routine against a
    resurfaced note is `SearchRank` across two document sets again, and the
    failure is silent.
  - Reading 4 — where intention and attention disagree — **stays absent until
    the substrate**.
- **The closing ritual** — S5's entire requirement, *"a closing ritual with a
  time-aware nudge."* Reachable today: `focus_for` already gives pins with their
  `released_at`, so it can say *you chose four; two are done, one you released,
  one is still open.*
  - **It cannot close days retroactively.** *"I wrote nothing on the 3rd"* and
    *"I have never opened the 3rd"* are different facts — which is why
    `DailyEntry` has no deleted or archived state. A day you do not answer
    closes unclosed, and that is itself a record.
  - **Nudges do not stack.** Four missed days is one observation in the weekly
    review through `loose_ends`, not four prompts.
  - **An unfinished pin gets three legal moves offered**: leave it, release it,
    or re-pin it when tomorrow is drafted. **Never move its due date.**
- **Bills.** The sidecar, the two new `Recurrence` values, a lead time, and a
  dedicated section answering *what is due this month and what it comes to*.
- **The calendar, size one** — a view over what Clarice already knows: tasks by
  due date, routines, bills. No new model, and **it closes S13's "a way to land
  on a date,"** since `/day/:date` has no UI entry point at all. Worth shipping
  even if events never follow.
- **A real notification surface**, because an advance reminder needs somewhere
  to arrive.

~~**Acceptance: S5 reaches *works*; S13 gets its land-on-a-date half.**~~
**S5 reached *works* on August 20, 2026**, with `draft_day` and the closing
ritual. **The calendar view shipped the same day** — a month over what Clarice already
knows, closing S13's *land on a date* require without closing the story, which
still wants sources and reviews. **The notification surface shipped the same day** — `send_closing_nudge`,
built on a scheduler extracted out of the digest first so the six behaviours
that loop had learned could not be copied into a second one. It closes S5's
last absence and is where bills' advance reminders will arrive. **Bills shipped the same day**, in four pieces: quarterly and annual cadences
(without which a property tax bill could not be expressed at all), the
one-to-one sidecar §4 argued for instead of a primitive, a lead time on `Item`
rather than on the sidecar because *"remind me before the MOT"* is the same
sentence, and a month's-bills read that **totals per currency and never across
them**. **Still open in this release:** the daily brief's awareness half — which
S5's own entry now names as what a nudge that *reaches* somebody would need,
and which the digest's advance reminders need too.

### Capture — the brain dump and what it holds

- **`CaptureSession` and session-aware processing, first.** Two budgets — what
  gets materialized, and what gets shown now — covering **every
  attention-producing mechanism**, because `_propose_any_commitment` runs
  *synchronously on the live path for every node*, so forty fragments is forty
  actionable facets before a detector job runs. A cap scoped to the five
  connection detectors would miss the one that fires first. **No backlog**: a
  queue slowly releasing session findings is the inbox this design refuses.
- **The brain dump surface.** Fragments are atomic — one *keep and continue*,
  one node — with a preview-and-ask on multiline paste and **no silent
  splitting**. The ongoing ritual is the counterweight to a memory fed only by
  deliberate capture inheriting the biases of the brain doing the capturing.
- **Orientation as one of two entrances** — *quick start* beside *empty my
  head*, because a dump takes far longer than S1's four minutes. **This is how
  the six invented concepts get explained**, demonstrated on the person's own
  material and **only the ones it actually demonstrates**; explaining a Compass
  that is not there turns personalisation back into the tutorial it replaced.
  Carries the invitation bar's third item.
- **Attachments switched on** — the model exists and nothing can create one.

Detail in [`temporal-substrate-plan.md`](temporal-substrate-plan.md) Part 4.

### Unify — the two cores become one product

- **The temporal substrate**, Track A increments 1–4. `EventType` gains
  life-events; `lists`, `daily` and `review` emit facts; backfill takes only
  what carries its own recorded timestamp; `around()` becomes the first read
  that crosses. **Facts, not derivations** — nothing may write a row a read
  could have produced, which is what keeps Part 4's refusal of an event bus
  standing.
- **S14's one missing relationship** — typed links from a node into the day and
  project domain objects. The differentiator: a graph that accretes from what
  you were already doing.
- **`FacetKind.GOAL` wired to `Project.outcome`**, as `EPISTEMIC` was.
- **Search reaches across content** — `search-plan.md` increment 5.

**Acceptance: S13 and S14 reach *works*.**

### Contextual retrieval — memory learns why it is being asked

Track B of the substrate brief, and the largest single body of design work here.
Clarice has **several retrieval tricks and no retrieval architecture**. Above
them sit two axes that do not exist: **what kind of memory is this** (roles as
multi-valued facets, proposed after capture, never asked for) and **what kind of
remembering is happening now** (lookup, recollection, discovery, planning,
reflection, resurfacing). Existing indexes become candidate generators rather
than final judges; eligibility and ranking move above them; every result
explains why it appeared.

**The principle it establishes:** *Clarice may contain anything, but it should
never retrieve without knowing why the person is asking — or why the system is
interrupting.*

**Acceptance: none directly**, which is worth saying plainly — the payoff is
entirely in the releases after it.

### The first question — Clarice starts behaving like an instrument

- **The discrepancy reading.** Intention joined to attention across time: *you
  intended these three outcomes; two received attention; one has been displaced
  for the third week.*
- **`Decision` earns its own model.** *"The answer becomes part of the evidence
  available next time"* is the recursion the product hangs from. **It must cite
  a `Revision`, not a `Node`**, or a note edited in October silently changes
  what was on screen in August.
- **One weekly briefing that ends in a question**, with real dispositions:
  continue, change, release, investigate, defer until a named condition,
  schedule a decision. `release` already exists in the model; *defer until a
  named condition* is the reconsideration-trigger idea modelled in code for the
  first time; only *investigate* is new.

**Predicates before ranking.** "A project paused twice after the same pattern"
is a rule — enumerable, checkable, arguable. Ranking becomes necessary only when
more questions qualify than there are slots.

**Acceptance: S11 reaches *works*.**

### The wider horizons — monthly, quarterly, at a decision

**One instrument parameterised by horizon, not five instruments.** The readings
are the same at every cadence; only the window and the threshold for *too
repeated to call incidental* move.

- **Longer-horizon reviews reusing the weekly model** — S8, and *"the
  null-not-zero discipline already exists in `review/reads.py` and must carry
  up."*
- **What completing a project produces** — S12: a retrospective read over its
  life, and somewhere to keep Vince's own account of it.
- **S10's remaining two** — notes, and an abandonment condition.
- **Structured observations** — Track C, and what makes Reflection worth having.
  Two refusals travel with it and are not negotiable: **no causal language**,
  and **an unrecorded night is never a sober one.**
- **Calendar events**, if scoped — the `Event` model and overlap prevention at
  the database layer, which suits this codebase's habit of pushing invariants
  into SQL (`tstzrange` exclusion constraints, needing `btree_gist`).

**Acceptance: S8, S10 and S12 reach *works*.**

### Recollection — the second brain feels like one

- **Track A increment 5, `since()`**, gated on D4. **If D4 cannot be answered
  honestly, stopping at four is the correct outcome.**
- **The recollection surface**: the fragment, its original context, what was
  nearby, what changed after, present relevance, and a way to resume.
- **`Source`, and links from it to what grew out of it** — S15.
- **Prospective recall re-cued** on a present that includes what you committed
  to and what is overdue, rather than the sentence just typed.
- **Layers, not conclusions**, with a living summary as a *read* computed from
  the layers rather than a row that drifts from them.

**Acceptance: S15 and S16 reach *works*.** S16 is *"the story that makes a
second brain feel like one, and it is worthless before the corpus exists"* —
which is why it is last.

## Two standing tracks

### The invitation bar

An intent needs a bar or it is a someday. Not features — **the substrate
somebody else's month would depend on:**

1. **The restore drill run once, end to end.** Never run, and `CLAUDE.md`
   records it would have died at step 5 on the executable-bit bug, mid-drill.
2. **MFA enforced on the admin.** Machinery deployed and inert.
3. **The six concepts explained** — carried by *Capture*.

The first two are [`security-and-resilience-plan.md`](security-and-resilience-plan.md)'s,
still unclaimed by `roadmap.md`.

### Background repair

The bends not named in a release, plus whatever daily use turns up. A bend is a
defect now; it does not need a release to be fixed in.

## What v3 refuses

- **Billing, pricing, packaging and entitlements**, while the personal-tool
  answer stands. S19 stays impossible and is not a gap.
- **Removing the approval gate.** Invitation-only is deliberate.
- **Analytics.** Its only job was telling whether a wedge landed.
- **A rewrite, or merging `Node` into `Item` or the reverse.**
- **An event bus, domain events, or Django signals.** Facts, not derivations.
- **A `Bill` primitive.** The vision document's own example says a bill is a
  recurring task.
- **Auto-pinning a drafted day.** It would change what the finish rate measures,
  and that is not reconstructible afterwards.
- **Automatic carry-forward.** *"Never automatically reschedule everything left
  incomplete"* is a product rule that reversibility does not buy.
- **Closing a day retroactively**, and stacking nudges.
- **Asking what a thing is at capture**, silently splitting a submission, and a
  proposal backlog.
- **The graph as the primary surface, and generated narrative as the primary
  voice.**
- **Building the briefing or the recollection surface before the substrate.**
- **Inbound calendar sync**, for now — OAuth, a new processor in `/privacy/`'s
  test-held list, and a sync path that fails quietly. The scenario planner
  already takes `unavailable` as an argument, so *"I have four hours today"* can
  be told rather than discovered.

## Three risks with no answer yet

1. **Question quality has no metric, and the machinery that exists will
   mislead.** A question rejected because it stung and one rejected because it
   was irrelevant are identical in an accept rate — and the confrontational
   questions are the valuable ones.
2. **Prospective recall fails silently.** A bad surfacing is recordable; **a
   missed surfacing leaves no trace at all.**
3. **Absence claims.** *"Since then, nothing has been recorded"* cannot
   distinguish *nothing happened* from *I stopped recording*. `MAINTENANCE_RAN`
   exists because this project has been caught by that twice.

**And one that is new with the daily loop: accepting is a weaker act than
choosing.** If the draft is usually right you will stop reading it. The capacity
bound and the cited reasons are the mitigation; the drafted-versus-composed
record is what would let you find out rather than assume.

## Where the facts live

Whether any of this is active, deferred or open is
[`roadmap.md`](roadmap.md)'s — **nothing here is claimed by it yet.** What
shipped and how it was verified is [`roadmap-history.md`](roadmap-history.md)'s.
How the product scores is [`product-stories.md`](product-stories.md)'s, which
**corrected its own three-loop model on August 20**: the second brain is not the
memory of the Decide loop, it is the substrate, and the loops are tempos of
reading and writing it. The charter every new model answers to is
`architecture-trajectory.md` §4 — argued against, above, rather than
paraphrased. The knowledge core's design authority remains `design-concept.md`
in Second Mind's own `docs/`. Substrate, retrieval, observations and intake
detail is [`temporal-substrate-plan.md`](temporal-substrate-plan.md)'s; literal
retrieval is [`search-plan.md`](search-plan.md)'s. How work is delivered and
verified is [`principles.md`](principles.md)'s.
