# Clarice v3 — bringing the cores together, and making it usable

Vince · long-form plan · written August 20, 2026 · **not claimed by `roadmap.md`**

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
remaining questions were commercial; this one's direction changed, and a
sequence that spans both cores and five releases cannot be carried in a
roadmap bullet. **It replaces `commercial-blueprint.md` Part 6's phases 2
through 5.** Part 1 (closed), Part 4 (architecture), Part 7's wedges (deferred,
not withdrawn) and Part 8's other refusals all stand; that file keeps them.

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

## What was decided on August 20, 2026

Vince's calls, recorded once because several documents are downstream:

1. **Clarice is a personal tool, with an intent to invite people.** Not a
   business — `commercial-blueprint.md` Part 9 #1. Billing, pricing, packaging
   and entitlements are refused while this stands, and **analytics is not
   needed**, which keeps `/privacy/`'s absolute no-analytics claim true for free.
2. **The wedge is deferred** (Part 9 #2), decidable when invited people can say
   what they would miss — the one question that genuinely needed somebody else.
3. **Mobile (Part 9 #4) collapses rather than resolves.** "Responsive web serves
   iOS simultaneously" argues about a market that does not exist here.
4. **The second brain is the substrate, not a core beside the task core.** A
   conceptual inversion, explicitly **not** a merge of `Node` and `Item`.
5. **`principles.md` was rewritten** (`217243d`): a bend is a defect, the main
   surface can do the main thing, felt friction is evidence, automations act
   reversibly, and a trigger that cannot fire is a refusal.

## How v3 is scored

[`product-stories.md`](product-stories.md), and nothing else. It stands at
**3 works · 10 bends · 6 impossible** and that file owns the number; the
releases below name which stories each is trying to move, so the score can
contradict the plan rather than the plan grading itself.

Two of the six impossible are refused rather than pursued: **S1** wants the
approval gate removed, which is a policy decision already taken the other way,
and **S19** is billing. v3's reachable ceiling is therefore **17 of 19**.

## What v3 inherits, and why it is cheaper than it looks

The most important finding of the August 20 planning session: **`kestrel` and
the planning assistant's v2 already paid for these substrates.** Read the score's
own `Requires` lines rather than the verdicts:

- **S3** — *"the comparison the draft already makes, applied to the week being
  reviewed. No model, no field, no new read — an argument's difference."*
- **S9** — *"a retrospective that reads the intention beside the week's own days.
  No model, no service, no field."*
- **S14** — *"one relationship short rather than a model short"*, and it is
  **"still the differentiator — the graph accreting from what you were already
  doing rather than being built by hand."**
- **S12** — half-built, and **"still the story that makes the two cores one
  product"**; the link between projects and knowledge records already exists
  and is in daily use.
- **S11** — `Decision` as a record, and the story is not hypothetical:
  `architecture-trajectory.md` §7 and §8 **are** that practice, kept in Markdown
  because the product cannot hold it.

Four of the ten bends need no new model at all. That is the difference between
this being a year and being a quarter.

## The releases

**Named, never lettered in advance.** `roadmap.md` is explicit that letters are
never reserved for a subject — Vince's call, August 15, 2026, after
`architecture-trajectory.md` §5 attached commercial readiness to "release G" and
Godwit spent it on the merger. A letter is claimed by whatever ships next.

**Every release ends in something Vince uses daily, or it is wrong.** This is
the plan's largest risk written as a constraint: the substrate work is three
invisible increments followed by two invisible reads, and a programme of that
shape can run for months producing nothing anybody touches — which is exactly
what this conversation diagnosed, where fourteen increments of planning
machinery shipped while *move a task to another area* did not.

### Close L — finish what is already open

Release L has been open since August 19 and half-deployed since. Unified search
is on `main` and **undeployed**; the second factor is installed and enforcing
nothing.

Deploy, verify in production, tag the deployment, choose the bird. **Nothing new
ships.** It is first because the letters stopped meaning anything once already —
six of seven work items shipped outside the release structure between August 6
and 12 — and a release that never closes is how that starts.
[`roadmap.md`](roadmap.md) owns what L contains.

### Usable — the bends that need no substrate

The release that answers *"it serves a purpose but it isn't really useful."*
Nothing here waits on anything else, and most of it is small.

- **The Day page gets verbs.** [`DayRoute.tsx:120`](../frontend/src/app/routes/DayRoute.tsx)
  declines a Complete button to avoid reimplementing the agenda's mutation
  beside it. That cost is real and it is not a veto: *one rule, one
  authoritative definition* says how to pay it. The vision document calls the
  Daily Page **the main working surface** and it cannot do the main thing.
- **A closing ritual with a time-aware nudge** — S5's whole requirement.
- **Date navigation.** `/day/:date` has no UI entry point at all; the review has
  no week jump. Reaching a day twelve weeks back means clicking "the week
  before" twelve times.
- **The weekly retrospective reads the intention beside the week's own days** —
  S9, no model, no service, no field.
- **The draft's own comparison applied to the week being reviewed** — S3, an
  argument's difference.
- **The other two rows of the review act in place** — S7, through the owning
  core's services, the shape the questions and pinning already take.
- **Task priority.** A to-do core with recurrence, routines, pauses and
  snapshot denominators and no priority field is unbalanced.
- **Moving a task between areas.** [`lists/api.py:197`](../src/lists/api.py)
  accepts six fields and `list` is not among them, so a misfiled task stays
  misfiled.
- **Links in the digest email**, which presently ends "Open Clarice to work
  through them." with nothing clickable.
- **The 44px floor into the link primitive**, finishing August 18's half-fix —
  "Edit your compass" is still a 20px anchor.
- **The six invented concepts explained in-product, once** — Area, Project,
  Checklist Step, Compass, Focus, "call it enough." Also the invitation bar's
  third item.

**Acceptance: S2, S3, S5, S7 and S9 reach *works*.** Five of the ten bends, in
the release with the least new machinery in it.

### Unify — the two cores become one product

The architectural half, and the one everything downstream needs.

- **The temporal substrate**, increments 1–4 of
  [`temporal-substrate-plan.md`](temporal-substrate-plan.md). `EventType` gains
  life-events; `lists`, `daily` and `review` emit facts; backfill takes only
  what carries its own recorded timestamp; `around()` becomes the first read
  that crosses. **Facts, not derivations** — nothing may write a row a read
  could have produced, which is what keeps Part 4's refusal of an event bus
  standing.
- **S14's one missing relationship** — typed links from a node into the day and
  project domain objects. The differentiator: a graph that accretes from what
  you were already doing rather than being built by hand.
- **`FacetKind.GOAL` wired to `Project.outcome`.** Declared since the merger and
  inert, exactly as `EPISTEMIC` was until [`mind/services.py:358`](../src/mind/services.py)
  revisited it. This is how *what you said mattered* reaches memory as a facet
  and not only as an event.
- **Search reaches across content** — increment 5 of
  [`search-plan.md`](search-plan.md), the nine fields deferred by name. With one
  substrate the sectioning question can finally be re-asked honestly; until
  then it stays sectioned, because `SearchRank` means nothing across two
  document sets and the failure is silent.

**Acceptance: S13 and S14 reach *works*.** The visible payoff is small on
purpose — a note that can say which day and which project it belongs to — and
the invisible payoff is that everything after this becomes possible.

### The first question — Clarice starts behaving like an instrument

- **The discrepancy reading.** Intention joined to attention across time: *you
  intended these three outcomes; two received attention; one has been displaced
  for the third week.* This is what `around()` was for, and it is the reading
  that separates an instrument from a report.
- **`Decision` earns its own model.** *"The answer becomes part of the evidence
  available next time"* is the recursion the whole product hangs from, and it
  needs a durable record of what was asked, what evidence was shown, what was
  decided, and **under what condition it returns.** It passes
  `architecture-trajectory.md` §4 on the strict reading — *decided → held →
  returns on condition → revisited or superseded* is unlike `Item`, unlike
  `Facet`, unlike `Node`. **It must cite a `Revision`, not a `Node`**, or a note
  edited in October silently changes what was on screen in August.
- **One weekly briefing that ends in a question**, with real dispositions:
  continue, change, release, investigate, defer until a named condition,
  schedule a decision. `release` already exists in the model
  ([`daily/models.py:165`](../src/daily/models.py)); *defer until a named
  condition* is the reconsideration-trigger idea modelled in code for the first
  time; *schedule a decision* was deferred by name in `abcfc51`; only
  *investigate* is new.

**Predicates before ranking.** "A project paused twice after the same pattern"
is a rule — enumerable, checkable, arguable. Ranking becomes necessary only when
more questions qualify than there are slots, and `principles.md`'s narrowed
*measure behavior* gates it until then. Deliberate staging, and the same
discipline that made increment 9 refuse to ship.

**Acceptance: S11 reaches *works*.**

### The wider horizons — monthly, quarterly, at a decision

**One instrument parameterised by horizon, not five instruments.** The readings
are the same at every cadence; only the window and the threshold for *too
repeated to call incidental* move. Building it five times is how a product
becomes five features.

- **Longer-horizon reviews reusing the weekly model** — S8, and *"the
  null-not-zero discipline already exists in `review/reads.py` and must carry
  up."*
- **What completing a project produces** — S12: a retrospective read over its
  life, and somewhere to keep Vince's own account of it. **The story that makes
  the two cores one product.**
- **S10's remaining two** — notes, and an abandonment condition as its own
  field unless the outcome absorbs it.

`review/reads.py` is week-grained end to end today, so this is where that
generalises: `week_bounds`, `completed_in_week`, `planned_in_week`,
`habits_in_week`, `recent_weeks`, `typical_week_for`.

**Acceptance: S8, S10 and S12 reach *works*.**

### Recollection — the second brain feels like one

- **Substrate increment 5, `since()`** — what developed afterward, gated on its
  D4 bearing rule. **If D4 cannot be answered honestly, stopping at four is the
  correct outcome** rather than shipping a read that pads a recollection with
  everything that happened since.
- **The recollection surface**: the fragment, its original context, what was
  nearby, what changed after, present relevance, and a way to resume — add a
  thought, answer an old question, revise a conclusion, connect current
  evidence, or close the thread explicitly. Threads already exist as objects:
  `NodeSource.THREAD`, members joined by `EdgeRelation.MEMBER_OF`.
- **`Source`, and links from it to what grew out of it** — S15. There is
  currently nothing to attach an article to.
- **Prospective recall re-cued.** `dormant_thread` already works and already
  knows the hard lesson: precision over recall, because "a stream of poor ones
  teaches the person to skim past the review surface, and no later improvement
  recovers that." What changes is only its input — today it fires on the
  sentence just captured, and after the substrate it can fire on a present that
  includes what you committed to, what is overdue, and what you have open.
- **Layers, not conclusions.** Earlier beliefs, contradictions, abandoned
  explanations, changes of mind. `Revision` and append-only `ActivityEvent` are
  already this codebase's deepest instinct — but **a living summary is derived
  state**, and must be a read computed from the layers rather than a row that
  drifts from them.

**Acceptance: S15 and S16 reach *works*.** S16 is *"the story that makes a
second brain feel like one, and it is worthless before the corpus exists"* —
which is precisely why it is last, and why the substrate is what fills the
corpus rather than more discipline about capturing.

## Two standing tracks

### The invitation bar

Vince intends to invite people; an intent needs a bar or it is a someday. Not
features — **the substrate somebody else's month would depend on:**

1. **The restore drill run once, end to end.** Never run, and `CLAUDE.md`
   records that it would have died at step 5 on the executable-bit bug,
   mid-drill, with a paid scratch cluster running.
2. **MFA enforced on the admin.** Machinery deployed and inert;
   [`admin-mfa-plan.md`](admin-mfa-plan.md) is written and not started.
3. **The six concepts explained** — carried by the *Usable* release.

The first two are [`security-and-resilience-plan.md`](security-and-resilience-plan.md)'s,
still unclaimed by `roadmap.md`. Everything else Part 6's Phase 3 wanted has
either shipped or died with the wedge deferral.

### Background repair

The bends not named in a release above, plus whatever daily use turns up. A bend
is a defect now; it does not need a release to be fixed in.

## What v3 refuses

- **Billing, pricing, packaging and entitlements**, while the personal-tool
  answer stands. S19 stays impossible and is not a gap.
- **Removing the approval gate.** Invitation-only is deliberate; S1 stays
  impossible on that one point and says so.
- **Analytics.** Its only job was telling whether a wedge landed. For a handful
  of invited people, ask them.
- **A rewrite, or merging `Node` into `Item` or the reverse.** Part 8 and
  `architecture-trajectory.md` §7 both stand. The inversion is conceptual.
- **An event bus, domain events, or Django signals.** Facts, not derivations.
- **The graph as the primary surface, and generated narrative as the primary
  voice.** Both are supporting views.
- **Building the briefing or the recollection surface before the substrate.**
  Both would be built on reads that do not exist, and would silently be search
  results wearing a better layout.
- **A second event log, and a second API.** `ActivityEvent` gains a vocabulary,
  not a sibling; a knowledge-core endpoint is a router in `mind/api_v1.py`.

## Three risks with no answer yet

Named because each will look like a bug much later than it starts.

1. **Question quality has no metric, and the machinery that exists will
   mislead.** `producer_performance` and `retirement_gate` measure accept rates.
   A question rejected because it stung and a question rejected because it was
   irrelevant are identical in an accept rate — and the confrontational
   questions are the valuable ones. This needs a different instrument and
   nobody has designed it.
2. **Prospective recall fails silently.** `RetrievalMiss` records *I went
   looking and did not find*, because you noticed. A bad surfacing is
   recordable — you dismissed it. **A missed surfacing leaves no trace at all.**
   The instrumentation is structurally one-sided and will report health.
3. **Absence claims.** *"Since then, nothing has been recorded"* cannot
   distinguish *nothing happened* from *I stopped recording*. `MAINTENANCE_RAN`
   exists because this project has been caught by that twice already; the third
   time is user-facing. Substrate D5.

## Where the facts live

Whether any of this is active, deferred or open is
[`roadmap.md`](roadmap.md)'s — **nothing here is claimed by it yet.** What
shipped and how it was verified is [`roadmap-history.md`](roadmap-history.md)'s.
How the product scores is [`product-stories.md`](product-stories.md)'s, which
also owes itself one correction from August 20: **the second brain is not the
memory of the third loop** — it is the substrate, and the three loops are tempos
of reading and writing it. The charter every new model answers to is
`architecture-trajectory.md` §4, and the knowledge core's design authority
remains `design-concept.md` in Second Mind's own `docs/`. How work is delivered
and verified is [`principles.md`](principles.md)'s.
