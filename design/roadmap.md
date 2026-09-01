# Clarice — Roadmap

Vince · active planning document · refreshed August 16, 2026

## Purpose

The forward-looking plan: what is active, what is next, what is deliberately
deferred, and what is still open. It is not the implementation spec for an
item; write a focused file in `design/` once work is ready to start.

What shipped — every release from Albatross through Heron, with its deployment
records and lessons — is in [`roadmap-history.md`](roadmap-history.md). The
standards used to deliver it are in [`principles.md`](principles.md). The
ordering behind releases, the charter every new model must satisfy, and the
directions this project has refused are in
[`architecture-trajectory.md`](architecture-trajectory.md). This file is the
authority on what is active and deferred; that one explains why.

The knowledge core's code lives in this repository; its **planning documents do
not**. `C:\dev\Clarice_secondmind` survives as documents only, and
`docs/design-concept.md` there remains the knowledge core's design authority.

## Where things stand — August 16, 2026

**Kept as a dated snapshot rather than rewritten**, because the baseline below
is still exactly right and only its first sentence went stale. Since August 16
the releases have been Ibis, Jackdaw, the navigation and identity work, signup
with the legal documents, and `kestrel` — the planning assistant, August 19,
which spent the letter K. ~~Left no active release again~~ — **release L opened on August 19 and closed
on August 20 as `lapwing`**; the snapshot below is what a
baseline looked like before it, and *Open now* carries the current state, as it
is supposed to.

**There is no active release.** Heron was the last, verified in production
August 15. What it leaves is a baseline rather than a backlog:

- **One capture surface.** `/mind/`, writing a `Node`, and that is where the
  knowledge core lives permanently. `/capture/`, `Capture` and `Idea` are gone;
  `/capture/` came free and was deliberately not taken.
- **One of everything.** One API at `/api/v1/`, one token table with scopes,
  one login. `/api/v1/capture` is the application's, served by
  `mind/api_v1.py`; both the phone and the Day page post to it.
- **Two cores, one tree, one database.** The knowledge core is `src/mind/`;
  the task core is **Superlists**. The merger's direction ran one way and still
  does: Clarice was worked into Second Mind rather than the reverse.
- **No maintenance freeze on the task core.** A priority replaces it, see
  `CLAUDE.md`. Knowledge core and commercial substrate are where work goes.
- **`commercial-blueprint.md` Part 1 is closed** — all ten defects, August 15.
  There is no open production defect list.
- `django_migrations` keeps eight inert rows for the deleted `capture` app,
  **deliberately not deleted**: hand-editing production's bookkeeping to tidy
  something nothing reads is the worse trade.

Long-horizon knowledge work that used to sit in this file — idea resurfacing,
the mind-map, search over retained material — is **superseded, not deferred**.
It is planned in the Second Mind documents and built in `src/mind/`; do not
re-add it here.

## Open now

- **The Money module shipped, and this file did not know it existed — August 27,
  2026.** Fourteen increments across sixteen commits in one day, from
  *"everything is still sort of in silos"*: Bills was a report on a thing you
  could not make, edit or delete, and `/money` is now a module with a landing
  page, income, categories, account balances and twelve months of history.
  [`money-module-plan.md`](money-module-plan.md) owns the narrative, every
  increment struck with its date, and is not restated here.

  **The plan was immaculate and the drift was entirely here.** `grep -i money`
  over this file returned nothing at all — the sole authority on *what is
  active* carried no entry for the largest body of work in the window, while
  [`README.md`](README.md) told readers the `product-stories.md` gap "is noted
  in `roadmap.md`", where it was not. **The strike-in-the-commit rule was
  followed inside the plan and skipped for the roadmap**, because the plan was
  where the work felt like it lived. **The measurable consequence: the closing
  ritual's step 2 had no item to strike**, so the module could not have been
  closed cleanly when its last increment landed.

  **What that gap hid, third instance.** The moorhen copy defect above sat open
  for seven days over a fix that shipped that morning. `CLAUDE.md` carries this
  same failure twice already — the defect list and the commercial substrate —
  and both entries say the cost was a false reason quoted in a recommendation.

  **First real use, August 31, 2026, and it did not work.** Vince opened
  `/money` four days after it shipped and hit four defects in one walkthrough
  — a landing page offering nothing to act on, and three dead ends around
  balances because `POST /money/accounts` had no caller anywhere in the SPA.
  All four are repaired; [`money-module-plan.md`](money-module-plan.md) owns
  the detail.

  **The score moved with it.** [`module-score.md`](module-score.md) read
  **works** and now reads **not yet**, on Vince's own sentence. That file owns
  the verdict *and* what it learned from being wrong, which is the part worth
  carrying to the next module: **a module is scored by using it, not by looking
  at it**, and the first verdict was taken three days after shipping by the
  person who built it, against a screen that already had data.

- **The module pattern is the active work, claimed August 27, 2026.**
  [`modules.md`](modules.md) is the charter for
  **surfaces**, the smaller sibling of
  [`architecture-trajectory.md`](architecture-trajectory.md) §4 — which governs
  **models** and is never overridden by it. **Money was the first instance of a
  shape this repository had no word for**, and got right by being described out
  loud, built sixteen times and looked at three; the second module should not
  pay for that again.

  **Its central finding is that an app and a module are independent axes.**
  Money has no Django app — it is `lists/money.py` and four models inside
  `lists`. `routines` is a full app with `models`, `reads`, `services`,
  `periods` and `api_v1`, and appears in the SPA's route table, `ViewNav` and
  `SideNav` **zero times**; a routine can only be met inside somebody else's
  page. One of each mismatch, and `startapp` gets you the code layout and no
  place.

  **Two decisions were taken and both are Vince's.** The shared rail **keeps**
  each module's surfaces rather than each module owning a column — the escape
  hatch in `SideNav.tsx` stands unfired, and what it costs is one docstring that
  currently claims contents-only. And **a module is measured in its own file,
  one line each**, against *is the domain's central question answered by looking
  rather than by arithmetic* — so [`product-stories.md`](product-stories.md)
  keeps its nineteen journeys and its denominator, which v4 refused to move for
  S19 on the same reasoning. **That answers the gap `README.md` had been
  pointing here for**: modules become a boundary of that score rather than a
  blind spot in it, and nothing goes unmeasured.

  **Three more decisions were taken on August 28, 2026**, and each is recorded
  in that plan rather than here. **The knowledge core stays a distinct core**,
  against the plan's own argument that it is simply the largest module — because
  **a core is a mode rather than a vocabulary**, committing and doing against
  capturing and connecting, which no amount of shared structure collapses. So
  **modules live inside a core**, and which core a module belongs to has a real
  answer. **A domain starts as an Area and earns a module when it needs nouns
  `Item` cannot express** — §4's test one level up, and the only thing that
  bounds how many modules there can be. And **a module differs from a project by
  termination, not longevity**: `Project` carries three fields describing how it
  ends and a module could not have one. And **a module links to work it does not
  own through its own create path, or not at all** — `create_bill` writes the
  `Item` and the `MoneyLine` in one transaction, so membership cannot be
  forgotten, where `paid_by` was attached afterwards, called by nothing, and
  deleted. Anything attached afterwards is a seam.

  **It stopped being a plan on August 28, 2026** and is now a standing authority
  — `module-pattern-plan.md` became [`modules.md`](modules.md), because a plan
  becomes a stub when its work ships and a charter must not. §4 has never
  stubbed; neither will this. **Each module keeps its own focused spec**, the way
  [`money-module-plan.md`](money-module-plan.md) is one.
  [`module-score.md`](module-score.md) opened the same day with Money's line.

  **The finding worth carrying out of the plan is the input ratio** — *how much
  typing per unit of answer*. This project has said it three times without
  naming it: Money refused bank feeds as *"too difficult to really use"*, the
  investments item asks *"whether balances would actually get typed in"*, and
  `routines` has zero rows in a development database with five users and fifty
  items. **A module survives when one entry keeps paying out for years, and dies
  when it needs feeding.** It is what set `routines` aside as the second module
  despite three documents arguing for it, and it ranks the six candidates that
  replaced it — Home, Documents and travel, Vehicle, Learning, Health, People.

  ~~**D2 is which of the six goes first.**~~ **Answered August 28, 2026:
  Learning**, and [`learning-module-plan.md`](learning-module-plan.md) is the
  focused spec. D1 — whether `ViewNav` shows a place differently from a lens —
  is cheap, still open, and **does not gate this one**: Learning is a
  knowledge-core module and `ViewNav` is the task core's.

- **Learning is the active module, claimed August 28, 2026.** The first built
  against the charter rather than to produce it, **and it corrected the charter
  twice on first contact, both times downward.** `mind.Source` wants fields
  rather than a sidecar — a sidecar spares a *general* record a special case,
  and `Source` is already the special case — so the module adds **no model at
  all**. And the `Source` → `Node` → `Facet` → `Item` → Area → `Project` chain
  the charter called unavailable is **live end to end**, with three hops already
  walked by `what_grew_from`, so *what work came out of this reading* is
  derivable with no new column.

  **The diagnosis is Bills' for the third time.** `/mind/sources/` is a list of
  things you started with no way to say you finished one: `Source` has no state,
  so *what am I in the middle of* is unanswerable, and `created_at` records when
  you added a thing rather than when you read it, so *what did I read this year*
  is too. Every part is built — `record_source`, `came_from`, `what_grew_from` —
  and none is joined to a read.

  **Its refusal is the part worth carrying.** **Progress through a thing —
  *page 120 of 400* — is refused on the input ratio**, being the one field
  everybody expects and the only one that must be fed forever. A status answers
  *what am I in the middle of* without it. That is Money refusing bank
  transactions, applied a second time by rule rather than by taste.

  **And the plan carries its own doubt**: it is the smallest thing that passes
  the charter, close enough to a surface repair that it says so in writing
  rather than being talked up. **What that decides is only whether
  [`module-score.md`](module-score.md) gains a second line**, and it is
  answerable when the landing page is on screen rather than now.

- **V1 is answered, and it closed three things and opened one — August 26,
  2026.** *Does anybody other than Vince ever use Clarice?* **One other person,
  and not the public**: his girlfriend has her own login, and Clarice is not a
  product for strangers now or later.
  [`clarice-v4-plan.md`](clarice-v4-plan.md) owns the decision and its
  consequences; this is the summary and not a second copy.

  **What closed.** Public signup is refused, so **S1 moved to *refused*** and
  invitation links stopped being a readiness gate and became the permanent
  entry. **Vince has no archive to import**, which struck v4's spine item and
  moved **S18 to *refused*** as well — leaving `mind/importers/` as declared
  dark code with a record rather than a plan behind it.
  [`product-stories.md`](product-stories.md) owns the score, which moved with no
  code changing.

  **What opened, and nobody had it on a list this morning.**
  [`staging-environment-plan.md`](staging-environment-plan.md) §6 revives on
  *"the project holding real user data"* and reasoned from that being false.
  **It is true now.** Still deferred there, on stated reasons — but a bad
  migration now loses somebody else's month, and she cannot restore it or know
  it happened. **The practical consequence is that re-running the restore drill
  matters more than it did yesterday**, and it is the same two hours.

- **The decision backlog — twelve answered August 26, 2026, one piece of work
  left behind.** After the sweep cut the *work* threads, the *decision* pile was
  the bigger one: seventeen, several standing since August 19. Twelve are now
  answered and each is recorded where it lives, not here.

  ~~**Only one produced work rather than a sentence — planning-assistant D7.**~~
  **Done August 26, 2026.** The review page had two free-text boxes about next
  week a few hundred pixels apart, and nobody wrote the sentence distinguishing
  them in six days of looking at both. **Collapsed to the intention**, which is
  the one with a life cycle — the Day page reads it all week, and nothing read
  the plan but the form that wrote it.

  **The write path is gone and the read is not**, which is a correction to how
  this was first written down: *retire the read path* and *keep existing rows
  readable* cannot both be true. A plan written before today still shows,
  read-only. [`planning-assistant-v2-plan.md`](planning-assistant-v2-plan.md)
  owns the detail. **Not live until the next deploy** — it changes the API
  contract, so the SPA and the schema move together.

  **Four are still open and three of them are yours alone**: security D5, which
  is an observation nobody has made yet; M1, gated on the Android keystore; the
  planning assistant's D1, gated on eight weekly summaries and firing around
  late October; and the two unadopted recommendations of August 21.

- **The declare-or-refuse sweep — done August 26, 2026.** Roughly twenty threads
  were open across `design/`, which
  [`recommendations-2026-08-21.md`](recommendations-2026-08-21.md) §5 had called
  *"more than one person's landing rate"* five days earlier. Every one was asked
  `principles.md`'s question — **does this have a trigger, and can it fire?**

  **Two were refused** (S1, S18, above). **Three were feelings and are now
  numbers**: search's fifth increment fires at **ten recorded search misses**,
  the planning assistant's ninth at **twenty confirmed outcomes**, and D18 at
  **one neighbourhood that reads wrong**. Each plan owns its own and they are
  not restated here.

  **And it found a surface nobody had claimed, which is the most useful thing
  it produced.** `resolve_retrieval_miss` is declared dark and calls itself
  *"the strongest deletion candidate of the twelve"* — and it is the opposite.
  Nothing populates `RetrievalMiss.resolved_node`, so **a miss can be recorded
  and never answered**, and a resolved miss is the evidence under search's fifth
  increment *and* under D14, the semantic index.
  [`search-plan.md`](search-plan.md) carries the table. **One small page — your
  own misses, and what you were actually looking for — is the instrument beneath
  two gates**, and it reads as dead code only because no plan asked for it.

- **The invitation bar — v3's remaining readiness gate, claimed August 23,
  2026.** [`clarice-v3-plan.md`](clarice-v3-plan.md) lists three things *"the
  substrate somebody else's month would depend on"*, and invitations became real
  the same morning, so the bar stopped being hypothetical.
  [`security-and-resilience-plan.md`](security-and-resilience-plan.md) owns two
  of the three and **was unclaimed by this file until now**, which is its own
  small version of the seam problem.

  **Five of its seven ranked items are closed as of August 26, 2026** — MFA
  (August 23, as `petrel`), then dependency advisories, HSTS, the enforcing CSP,
  and the nginx trio of `/api/v1/capture`, `/admin/` and `server_tokens`. That
  plan owns the detail and it is not restated here.

  **What is left is three things and only one of them is code.** The restore
  drill re-run is Vince's — WSL, the ssh key and a paid scratch cluster. 1.7,
  *seeing that any of it fires*, got more urgent by being worked around: there
  are four rate limits now and still nothing reading the log they fire into.
  And 2.2, processor erasure, is gated on that plan's D1.

  ~~**The advisory job found something on its first look, and it is the most
  actionable thing here**: `django==5.2.16` carries PYSEC-2026-3717, CVSS 6.9,
  fixed in 5.2.17 — the framework serving production. The instrument shipped;
  the bump has not.~~ **Both shipped August 26, 2026** — the bump as `a9b8434`,
  taken as hygiene rather than as a security event, and live the same night.

  ~~**None of the nginx or HSTS work is live until the playbook runs**, and it is
  behind fourteen other commits.~~ **All of it went live August 26, 2026**
  (`DEPLOYED-2026-08-26/1945`), and three of the changes answer for themselves
  from outside: `Server: nginx` with no version, a year of HSTS, and a CSP that
  is no longer Report-Only. **Two of them had never met production traffic
  before that night** — the enforcing CSP and the two new rate limits — and
  that is what to watch rather than what to re-check.

  ~~**MFA on the admin is built and enrolled.** Ready to deploy.~~ **Closed
  August 26, 2026. Deployed and live August 23 as `petrel`**
  (`DEPLOYED-2026-08-23/1510`) — all four increments of
  [`admin-mfa-plan.md`](admin-mfa-plan.md), which **is now a stub**; the
  narrative is in [`roadmap-history.md`](roadmap-history.md) under *A second
  factor on the admin*, and this file does not restate it.

  **Three things it left, and two were answered August 26, 2026.**

  - ~~**One admin account or two.**~~ **Answered: keep both** — and it went
    against this file's own lean, which is why the reasoning is worth keeping.
    The argument for merging was that *a staff login used twice a month is one
    whose second factor will be missing at the moment it is needed*. **That was
    solved before the question was asked**: both accounts are enrolled, so the
    freshness risk it named is gone.

    **What is left points the other way.** `django-otp` marks the *session*
    verified, so a hijacked session on a staff account reaches `/admin/`.
    Keeping `Vrbeall01` non-staff means **the session left logged in all day is
    never the session that can reach the admin** — ordinary least privilege, and
    it survives the compromise the second factor does not.

  - ~~**M2 — where the recovery codes live.**~~ **Answered: the password
    manager**, and the cost is recorded rather than argued away. The manager is
    now **a single point of failure for both factors** — whoever opens the vault
    has the password and the recovery codes together, which is most of the way
    to no second factor at all.

    **Taken with that understood**, because the alternative was paper and paper
    is only better while it is findable. **What would change the answer** is the
    vault stopping being the strongest thing in the chain — and if a printed set
    is ever made, it belongs somewhere that is not the desk the laptop sits on.
  - **M1 — does `/api/v1/login` grow a `totp` field?** It refuses today, which
    was chosen because the Android keystore does not exist and the alternative
    was therefore unavailable rather than merely more work. **Its trigger is the
    keystore**, in
    [`android-release-signing-plan.md`](android-release-signing-plan.md) — worth
    revisiting the day a signed release can carry the field, and not before.

  ~~**The restore drill has still never been run**, and is the other one. The
  August 1 pass compared 18 tables at 53 migrations~~ — **wrong since the day
  it was written: the drill ran on August 19, 2026 and passed**, the first pass
  entitled to the word, with an empty step-4 diff across 42 tables and
  behavioural checks at step 5. Its checks were audited and repaired on August
  21, and `clarice/tests/test_restore_integrity_covers_the_schema.py` now fails
  if the checked list falls behind the declared constraints.
  [`MIGRATION.md`](../MIGRATION.md) owns that record and this file should not
  have carried a second copy of it.

  **What is true is narrower and still Vince's**: a drill certifies the schema
  it ran against, and that schema is now several migrations old. Re-running
  needs WSL, the ssh key and a paid scratch cluster — worth doing when the
  schema has moved enough to be worth re-proving, not on a calendar.


- **Clarice v3 is the plan, claimed August 20, 2026.**
  [`clarice-v3-plan.md`](clarice-v3-plan.md) is the authority on **what order
  the work goes in and toward what**, replacing `commercial-blueprint.md` Part
  6's phases 2–5. Eight releases toward one destination — *Clarice is the
  instrument by which accumulated experience produces fewer, more honest
  commitments* — scored against [`product-stories.md`](product-stories.md) ~~with
  a reachable ceiling of 17 of 19.~~ **with a reachable ceiling of 15 of 19, not
  the 17 v3 claims** — [`clarice-v4-plan.md`](clarice-v4-plan.md) owns that
  correction, made August 22 and restated here unstruck for two days.

  **Three decisions of Part 9 were answered the same day** and are recorded
  there rather than here: personal tool with an intent to invite, the wedge
  deferred until invited people can say what they would miss, and mobile
  collapsing rather than resolving.
  [`temporal-substrate-plan.md`](temporal-substrate-plan.md) was claimed with
  it as the focused spec for the substrate, contextual retrieval, observations
  and intake, and **shipped entire on August 22 as `nightjar`** — see the entry
  below. Of v3's own releases, *Close L*, *Usable*, *The day*, *Capture*,
  *Unify*, *Contextual retrieval* and *Recollection* have delivered; ~~**four
  remain**: *The first question*, *The wider horizons*, *The invitation bar*
  and *Background repair*.~~ **Three remain** — *The wider horizons* **met its
  acceptance on August 23, 2026** as `osprey`, S10 and S12 on the 22nd and S8
  on the 23rd, and S8 needed no new model at all: `recent_weeks` took a horizon
  parameter and `over_weeks` summed above it, which is that release's own *one
  instrument parameterised by horizon* arriving literally. What is left is
  *The first question*, *The invitation bar* and *Background repair*, and the
  last two are standing tracks rather than releases.

  **Two of those seven delivered less than their own definition**, found by
  re-scoring on August 22 rather than by anyone noticing at the time. *Unify*
  lists four things and one shipped — its acceptance was *"S13 and S14 reach
  works"* and neither does; *Recollection* is two of five. The temporal
  substrate was delivered and called Unify. **What is missing is named in
  [`product-stories.md`](product-stories.md)'s re-score**, and it is three
  nouns rather than a vague remainder: typed node-to-day links,
  `FacetKind.GOAL` wired to `Project.outcome`, and search's fifth increment.

  **Two of the three closed the same day** (`a01a7b4`), and **S14 reached
  *works* — the first story to move since August 20.** The node-to-day
  relationship shipped as a **read** rather than stored links, because Part 1's
  *facts, not derivations* rules out storing what `captured_at` and the
  existing provenance chain already answer.

  ~~**The third is refused rather than pending.**~~ **The third is deferred,
  and *refused* was the wrong word — corrected August 26, 2026.** Search's fifth
  increment gates
  itself on *"the mechanism having been used against real material for long
  enough to say the sections are the right sections"* — two days against
  forty-seven notes is not that. **But a trigger that has not fired is not a
  trigger that cannot**, which is the distinction `principles.md` draws, and
  [`clarice-v4-plan.md`](clarice-v4-plan.md) counts this as one of four
  corpus-gated deferrals it requires to end **fired or written as a refusal**.
  Calling it refused here skipped that step by vocabulary.

  **And *Unify*'s acceptance was unreachable inside its own release**, which is
  an ordering error worth keeping: it asks for S13, whose require needs
  `Source`, which *Recollection* delivers **later**. A release cannot accept on
  a noun a later one provides.

- **Search's fifth increment is deferred on the corpus, not unbuilt.** Four of
  five shipped in `lapwing`; the fifth waits on material a corpus of 41 nodes
  has not produced. [`search-plan.md`](search-plan.md) owns it, and
  `principles.md`'s rule bears on it — a trigger that cannot fire is a refusal,
  and this is a candidate for that reading. **Promoted out of `lapwing`'s closed
  entry on August 28, 2026**, where it was invisible.

- **The planning assistant's ninth increment may correctly never ship.** Ranking
  by confirmation history, gated on a sample floor the same corpus has not
  cleared.
  [`planning-assistant-v2-plan.md`](planning-assistant-v2-plan.md) owns it.
  Three smaller pieces were deferred by name in `abcfc51`: confirming a
  recurring name in place, the planning-miss signal, and *schedule a decision*
  as a third disposition. **Promoted August 28, 2026.**

- **`/terms/` and `/privacy/` are published and deliberately not
  lawyer-reviewed.** The trigger named on August 19, 2026 was broader beta
  testing — **which V1 has since refused**, so it may never fire, and this is a
  third candidate for the refusal reading above. Still absent if it ever does:
  the LLC's state of formation and business address, a governing-law clause, and
  a considered answer on the minimum age (16 is asserted). **Promoted August 28,
  2026.**

- **The draft says *nothing at all* when it has candidates but no capacity
  figure.** The surviving half of the two copy defects `moorhen` left open; the
  other closed on August 27 as Money's first increment. **Carried forward
  unverified on August 28, 2026** — it was buried inside a struck entry, which
  is exactly how its sibling sat unstruck here for seven days over a fix that
  had already shipped.

- **Whether the Android client keeps growing.** Slices 1 and 2 shipped (Today
  read-only, then Agenda with read and act); later slices are undecided. Part 9
  recommends freezing native for responsive web, on the evidence that
  `android-full-client-plan.md`'s core assumption — mostly an Android build-out,
  not a backend rebuild — was falsified twice, and that iOS is absent entirely.
  ~~Nothing is scheduled.~~ That plan's stub points here for this question.

  **Answered in direction on August 31, 2026, and not in scope**: Vince intends
  **a complete overhaul of the Android app**, in its own session. That settles
  *keeps growing* against Part 9's freeze recommendation, and leaves everything
  else open — no date, no scope, no plan document yet. **Recorded as an
  intention rather than promoted to work**, which is the distinction this
  section exists to keep: an intention with no trigger is not a schedule.

  **Its one dependency outside itself is the entry below**, and the ordering is
  worth having written down before either starts: the overhaul is when a signed
  release would first exist, so the compatibility surface retires *with* it
  rather than before it.
- **Floating cadence is unbuilt.** ~~One defect to fix on the way in rather
  than port~~ — `_advance_due_date` spawning a successor already overdue —
  was fixed August 15, 2026 (`70bc6c8`), *after* the merger it was supposed to
  be fixed by, which is the argument for closing a defect where it lives rather
  than attaching it to a migration. What remains open is the mode: it is
  anchored-only, because Clarice has one cadence field and cannot say which
  mode a commitment is, while `design-concept.md` calls the distinction
  load-bearing. Deliberate, and recorded at the function.
- **A bill earns its own model, claimed August 31, 2026.** From Vince, after
  using the repaired module: *"there's a disconnect. Like it should be tied to
  the payments. So I really think we need to separate bills from a task."*
  [`bill-as-a-model-plan.md`](bill-as-a-model-plan.md) is the spec and owns the
  detail.

  **It overturns one written refusal and overrides no charter.**
  `money-module-plan.md` refused a bill as its own model on August 27 citing
  §4; §4 never named bills, and **its test is now met rather than waived** —
  the qualifying life-cycle difference is the entry directly below this one,
  written on August 28 and never connected to the model question until today.

  **Two things made it worth doing now rather than arguing about.** Production
  holds **one** `MoneyLine`, so the data migration is the cheapest it will ever
  be. And the plan's own reversal conditions were concrete: if reading two
  models in the agenda cost decision 4 — *bills stay ordinary tasks
  elsewhere* — then a product decision was spent to buy a modelling one, and
  the plan says stop.

  **The reversal condition was met, priced, and declined.** Reading two models
  on the daily surfaces cost a `bills` array on two payloads, a second query,
  and a section of their own on the day. Vince's call, August 31: pay it.
  Bills are still on the agenda and the day.

  ~~Increments 1–5.~~ **Shipped August 31 – September 1, 2026**, through the
  flip: `Bill` and `BillSeries` exist, the data is converted, every money read
  and write is on them, and the tasks that were bills are deleted. **What is
  open is 6–9** — replaying missed periods, `Bill.account`, deleting
  `MoneyLine`, and renaming the `task_id` key that now points at a bill.
  Increment 6 is the one that matters: it is the life-cycle difference in §2,
  which is the entire justification for the model, and until it ships the split
  has been argued and not demonstrated.

- **Should money skip a missed period at all? — promoted August 28, 2026 from
  the entry above.** *Missed periods are skipped, not replayed* is the task
  core's doctrine and it is right for tasks: five missed bin rounds are five
  things that did not happen, and inventing them is a fabricated history
  `principles.md` refuses. **A bill is not like that.** A payment you did not
  make is still owed, and the money is still owed whether or not a task exists
  saying so — so the doctrine that correctly declines to invent bin rounds
  quietly declines to remind you about a bill.

  **Concretely**: a monthly bill due June 1, paid on August 10, schedules
  September 1. The July and August payments are simply gone from the surface
  whose whole job is *how do I stand financially*, and nothing records that two
  were dropped. This is not the `>` boundary — that was answered above and was
  the last missed period rather than a special one. It is the doctrine itself,
  applied to a domain that arrived after it was written.

  **Not obviously a defect, which is why it is a question.** Replaying missed
  bills could equally produce a page full of arrears nobody will action, and
  `MoneyLine` already records what was actually paid, so the history is not
  lost even when the task is. **What is missing is any signal that a period
  went by unpaid** — and the honest first step is looking at whether that has
  ever happened in production, rather than building for it.
  [`money-module-plan.md`](money-module-plan.md) is where a repair would be
  specced; [`modules.md`](modules.md)'s input-ratio rule bears on it, since
  anything requiring the person to confirm a skipped period is feeding.

- **The keystore is now a dependency of the task core, not only of Android —
  promoted August 31, 2026.** [`android-release-signing-plan.md`](android-release-signing-plan.md)
  has said the keystore is Vince's to generate by hand since it was written,
  and until this week nothing but Android waited on it. It now gates a **single
  deletion in one commit**: `lists/api.py`, `lists/api_urls.py`, the `/api/`
  mount in `clarice/urls.py`, `TaskOut.url`, `AreaRefOut.create_item_url` and
  the four payload keys
  [`test_task_vocabulary.py`](../src/lists/tests/test_task_vocabulary.py)
  exempts.

  **Nothing is broken while it waits**, which is what makes this a dependency
  rather than a defect: the compatibility surface is declared, tested, and
  documented at the file that serves it. `android/` is already written against
  `/api/v1/`; what is missing is the ability to sign a build carrying it.

  **The trigger is a signed release actually on the phone**, not a keystore
  existing — the shipped binary is what pins these, and it stays pinned until
  it is replaced.

  ~~Which reads as a two-minute `keytool` run away.~~ **It is not, as of August
  31, 2026.** Vince is holding the keystore for the Android overhaul above, so
  this waits on that rather than on a manual step somebody could take this
  afternoon. **Nothing about the dependency changed — only how far away it
  is**, and that distinction is exactly what this entry would have got wrong by
  staying silent: a blocker described as trivial is one everybody assumes has
  been done.

  **Verified ready on August 31, 2026**, so the overhaul does not rediscover
  it: `assembleRelease` still builds after AGP 9 and the F2 changes, producing
  `app-release-unsigned.apk`; the signing config in `app/build.gradle.kts` still
  activates only when all four `local.properties` keys are present; `keytool`
  and `apksigner` (build-tools 36.1.0) are both on this machine.
  [`android-release-signing-plan.md`](android-release-signing-plan.md) §2 is why
  the key is Vince's and not an agent's, and it is a permanence argument rather
  than a policy one.

  **One thing the overhaul should know before installing anything**: a release
  APK is signed with a different key than the debug build now on the phone, so
  Android refuses to install over it. Uninstalling first clears the encrypted
  capture queue, which should be drained before the swap.

- **`product-stories.md` cannot see a seam, and that is a boundary rather than
  a fault — promoted August 31, 2026** out of the coherence repair, which is
  closed. That score read the task core at *works* for every journey it covers
  while nine seams sat inside those journeys, because **a journey that
  completes by two different mechanisms still completes.**

  **This is the second time a boundary of that score has been found from the
  outside**, and the first was answered with an instrument:
  [`modules.md`](modules.md) sent module quality to
  [`module-score.md`](module-score.md) rather than growing a journey per
  module. **This one deliberately gets no instrument**, and the reason is worth
  keeping: a seam is nameable one at a time and an audit finds it, where a
  module is a standing thing that needs a standing score. Recorded so nobody
  builds a seam-score, and so the next person who notices the blindness finds
  the answer rather than the question.

### Closed — one line each; the narrative is in `roadmap-history.md`

**The strikes used to stay here in full, and that is what made this section
unreadable**: 220 lines of finished work under a heading that says *Open now*,
against 356 of live work. Every narrative below was already in
[`roadmap-history.md`](roadmap-history.md), so the long versions were a second
copy. [`README.md`](README.md) owns the eviction rule this applies.

- ~~**The temporal substrate**~~ — closed August 22, 2026 as `nightjar`; all six of its remaining decisions closed the same day.
- ~~**Release M — *Usable***~~ — closed August 20, 2026 as `moorhen`. One copy defect survives it, promoted above.
- ~~**Release L**~~ — closed August 20, 2026 as `lapwing`. Its two deliberate deferrals are promoted above.
- ~~**`/api/v1/login` is unthrottled**~~ — fixed August 18, 2026 (`9eb9eea`); `clarice/tests/test_unauthenticated_endpoints_are_throttled.py` is what replaced it.
- ~~**No mail leaves production at all**~~ — closed August 18, 2026 (`jackdaw`). Outbound SMTP is still blocked on the Droplet and mail goes anyway, over Resend's HTTPS API.
- ~~**The planning assistant**~~ — closed August 19, 2026 as `kestrel`, all six increments, and it shipped no generation at all.
- ~~**The planning assistant's second version**~~ — increments 1–8 shipped August 19, 2026 within `lapwing`. The ninth is promoted above.
- ~~**Terms of service and a privacy policy**~~ — published August 19, 2026. Their un-reviewed status is promoted above.
- ~~**Unified search**~~ — four of five increments, deployed August 20, 2026 within `lapwing`. The fifth is promoted above.
- ~~**Three navigations, three identities, and a login form for a home page**~~ — closed August 18, 2026. ~~What it left open was S1~~ — **S1 was refused on August 26, 2026 when V1 was answered**, so nothing survives it.
- ~~**Removing user data from Sentry and Resend when an account goes**~~ — **closed August 26, 2026** as [`security-and-resilience-plan.md`](security-and-resilience-plan.md) §2.2. It sat here as live work for two days afterwards.
- ~~**Three genuinely open decisions in `commercial-blueprint.md` Part 9**~~ — **Part 9 closed August 22, 2026, all five answered.** It sat here as live work for six days afterwards, and `commercial-blueprint.md`'s own header said so the whole time.
- ~~**The task core's coherence**~~ — closed August 31, 2026, all six repairs, from *"developed more in bits and pieces"*; the record is [`coherence-audit-2026-08-30.md`](coherence-audit-2026-08-30.md) and its two survivors are promoted above.
- ~~**A recurrence falling due exactly today is skipped**~~ — answered August 28, 2026, the day it was raised: `>` is correct and the docstring was wrong. The reasoning lives in `_advance_due_date` and in `test_the_slot_the_completion_lands_on_is_not_respawned`, which is where code cites its own decisions; production behaviour never changed. The money question it turned up is promoted above.


## Carried in from B / C / D — not schedulable work

Fourteen items came out of Bittern; eleven closed through Crane and Dunlin.
`crane-plan.md` §2 stays the authority on the full checklist. These three
remain, and none of them is a task:

- ~~**A real production 500 reaching Sentry.**~~ **Closed August 18, 2026.**
  Three incidents in three days answered it: an SMTP timeout in
  `send_due_digest` (Aug 16, the excepthook path), the nullable-Area
  `AttributeError` in the same command (Aug 18), and an SMTP timeout in the
  `contact` **view** (Aug 18) — the last of which is the web 500 this item was
  waiting on, arriving through the WSGI integration rather than the excepthook.
  Breadcrumbs on all three, and a query breadcrumb reading `[Filtered]`, which
  is the `EventScrubber` working on live data. B4's monitoring is proven end to
  end; what the incidents cost is in
  [`roadmap-history.md`](roadmap-history.md).
- **No Android emulator run.** This SDK install has no AVD and no way to build
  one without a multi-gigabyte download better done through Android Studio.
  Low priority: everything M4 wanted a device for is answered twice over on
  real hardware.
- **Release signing.** `app/build.gradle.kts` is wired for it; the keystore is
  deliberately left for Vince to generate by hand, because a non-rotatable
  credential is the wrong thing for an agent to generate and momentarily hold.
  The command is in
  [`android-release-signing-plan.md`](android-release-signing-plan.md).

## Track D — Postgres-enabled features

Candidates. Each needs its own product trigger or focused brief before it
becomes work.

- ~~**Full-text search over Clarice's own material.**~~ **Stopped being a
  candidate on August 20, 2026** — briefed as
  [`search-plan.md`](search-plan.md), started the same day, and now carried
  under *Open now* above, which is where active work lives. The trigger that
  fired and the argument for it are in the brief; this section's job was to
  hold the candidate until one of those existed, and it is done.

- **Audit log and general undo.** Structured change records making more than
  task completion safely reversible. **No trigger.**
- **Time blocking.** Model calendar ranges and prevent a user's blocks from
  overlapping at the database layer. **No trigger.**

This section has asked every candidate for a trigger since August 2, 2026,
which is how a future candidate quietly becomes a plan. Two of the three above
have gone two weeks without one. **A candidate with no trigger is a candidate
nobody wants yet**; the honest options are to find the trigger or drop it, not
to let it accrue significance by sitting in a list.

## Later — visible, not scheduled

### Sharing

Shared lists with real-time updates, and conflict handling for concurrent
edits. These belong together. **Do not start either until list sharing itself
is a deliberate product decision.**

Two mechanism notes, recorded August 2, 2026 so they are not rediscovered from
scratch; both proposed rather than evaluated, neither a commitment. **Real-time
without Redis:** Postgres `LISTEN`/`NOTIFY` driving Server-Sent Events would
suit one small deployment better than adding a broker. **Granularity:** viewer
/ editor / co-owner is the obvious first split, and naming it early decides
whether permission is a column or a table. That sits close to row-level
security, whose trigger in
[`architecture-trajectory.md`](architecture-trajectory.md) §6 is this same
sharing work.

### Remaining public-readiness work

- ~~Self-service signup with email verification.~~ **Shipped and deployed
  August 19, 2026, and it does not close S1.** Confirming an address is
  self-service now — a single-use signed link, the applicant finally told
  something, a resend for when the mail is lost, and the two waits told apart
  at the login form. An account being approved now writes to the person too,
  which three surfaces had been promising for a day before anything sent it.
  What stays is approval, which is still a person: `is_active` is approval and
  `email_confirmed_at` is confirmation, kept separate so opening the doors is
  later a policy change rather than a redesign. **Deliberate** — the site is
  invitation-only, and the privacy policy that made this publishable is the
  item struck above. [`product-stories.md`](product-stories.md) owns the score;
  [`roadmap-history.md`](roadmap-history.md) has the narrative.
- Rate limiting for capture. `/api/v1/capture` falls through nginx's catch-all;
  signup and login are throttled at 5r/m and this is not.
- ~~Account export and deletion.~~ **Shipped August 16, 2026** — self-service,
  a thirty-day grace period rather than immediate purge, and an export of every
  owned row as JSON beside readable Markdown.
- ~~Privacy policy and terms of service.~~ Tracked under *Open now* above.

Password recovery, adversarial per-user isolation tests, transactional email
via Resend and edge rate limiting for signup are all done.

### ~~Support for people who are signed in~~ — shipped August 30, 2026

**All three parts of it**, and the entry is kept struck rather than deleted
because its middle paragraph was the design: the link, the form no longer
asking somebody with a session who they are, and the rate limit keyed on the
account rather than the address. Adapted rather than forked, as
[`bittern-plan.md`](bittern-plan.md) argued.

**What it cost by sitting here**: the promoter fired when B4 shipped and
nobody noticed, so this read as *promotable, not deferred* for weeks and moved
only when [`coherence-audit-2026-08-30.md`](coherence-audit-2026-08-30.md)
found it again from the other direction, as F7. **An entry that says it is
ready to start is not a trigger** — nothing was watching this one, and that is
the transferable part.

### Public updates page

An unauthenticated page announcing what has shipped, written for people rather
than the repository — closer to a short press release per release than to a
changelog. No account, no login wall.

**No broad roadmap preview.** The page does not publish tracks, Later items, or
what the next release might contain. The single exception is a specific named
feature already in development, and it needs a definition or it drifts back
into promising: a feature qualifies when it has a focused spec in `design/` and
work has actually begun. A candidate sitting in a Later list never qualifies.

Two things to settle. **Where the text comes from:** the annotated release tags
and `roadmap-history.md` are both written for the developer, so expect to write
the public version by hand and treat those as sources, not drafts. **Which
stack renders it:** unauthenticated, cacheable and wanting to be indexable, so
a Django-rendered page rather than an SPA route, in keeping with the settled
boundary that only the task UI is SPA-only.

**What would promote it:** somebody unauthenticated to read it — realistically
alongside self-service signup.

### Mobile web experience

Making the browser application genuinely usable on a phone, as opposed to
merely surviving a narrow window. This is not the Android client: everything
beyond capture and the two shipped Android slices happens in the browser, and
"the app captures, the web app reviews" assumes the web app is reachable from a
phone. It is not really.

**Measured, not guessed.** Both shells set
`<meta name="viewport" content="width=device-width, initial-scale=1">`.
~~Beyond that there are exactly two layout breakpoints — side navigation
collapses at 760px, the workspace input row stacks at 768px. Those two numbers
should agree and do not.~~ **Fixed August 18, 2026** by
`navigation-and-identity-plan.md` step 4: the rail's collapse is Tailwind's
`md` on both sides now, and `test_frontend_style_contract.py` fails if the CSS
and the JavaScript drift apart, which is what the comment asking the next
person to remember was standing in for. Everything else is still desktop-first.

**Touch targets are the largest thing in this entry**, found with numbers
attached during Crane 1 slice 7's phone pass. At 375px the Daily Page itself is
sound — no horizontal overflow, everything works — but its buttons measure
32px and its "Edit your compass" link 20px, against the ~44px both platform
guidelines and WCAG 2.5.8 ask for; the Agenda, untouched by Crane, is worse at
19–31px. ~~The height lives on the shared `Button` primitive, which is still `h-8`.~~
**Half-closed August 18, 2026.** The primitive now carries a `touch-target`
utility that grows the *hit area* to 44px under a coarse pointer while leaving
the drawn control where it is — raising the real height would have fixed phones
and wrecked the dense desktop layouts this is mostly used in. So every button
in the application clears the floor, and every new call site inherits it rather
than needing its own override.

**What remains is the links.** "Edit your compass" is still a 20px anchor, and
the utility is available to it — this was a fix to the primitive, not a sweep
of every control. The overlap tradeoff is recorded at the utility: two controls
closer than ~12px apart now overlap targets on touch and the later one wins.

**One responsive application, not a mobile site.** No `m.` host, no second
codebase, no divergent templates. One API, one SPA. Said once so it is not
reopened.

**The overlap with native should be decided, not discovered.** Native earns its
cost through launch speed, Keystore-backed token storage, WorkManager retries
and the Android share target. A capable installable web app can approximate the
share target and an offline queue, less reliably. If mobile web lands well, M5
and parts of M3 deserve a fresh look rather than being finished out of
momentum.

**What would promote it:** daily phone use producing observable triage
friction. One device pilot is not that. Crane made its own new surfaces
mobile-aware — the Daily Page and the weekly review were each measured at
375x812 against the built bundle, both clean — and did not close this entry.
The older surfaces, the two disagreeing breakpoints and the touch targets are
all still here. Watch real failures rather than redesigning from a hunch.

### Recorded candidates with no trigger yet

Three ideas salvaged August 2, 2026 from an abandoned review branch. They were
generated by an outside review of the codebase, not by using Clarice and
wanting them, and none has a trigger — recorded as ideas rather than promoted
to Track D, because writing something down is not deciding to build it.

- **A calendar feed.** An authenticated read-only ICS endpoint so due dates
  appear in Google, Apple or Outlook calendars. It points the opposite way from
  time blocking: that models calendar ranges *inside* Clarice, this publishes
  what exists to a calendar someone already reads. Cheaper, and possibly the
  only one of the two ever wanted.
- **Natural-language due dates.** "Next Friday", "tomorrow at 3pm" parsed on
  input. The server owns date meaning, so parsing belongs server-side with the
  client showing what was understood before it is committed — an automation
  that proposes rather than silently decides.
- **A command palette.** `Ctrl+K` over tasks, lists and nodes. ~~Genuinely
  premature: it is a *retrieval* affordance, and full-text search above is the
  thing that earns retrieval work first. Revisit it with that, not before.~~
  **Revisited August 20, 2026 when search shipped, and still no** — the answer
  is `search-plan.md`'s D4 and the reasoning is there. In short: that condition
  was a *precondition*, and clearing it removes an objection without supplying
  demand. A candidate with no trigger is a candidate nobody wants yet, which is
  this section's whole standard.

  **The trigger to watch is friction in reaching or repeating a search**, now
  that one is a click away from both cores — and it **fires on felt friction**,
  which `principles.md` makes admissible evidence. That matters: nothing
  instruments how long it takes to open a search box, so a trigger requiring a
  measurement could not fire, and this entry would be a deferral pretending to
  be one. **`RetrievalMiss` cannot supply it** — it measures whether search
  succeeded, not how long it took to ask — so nobody should watch the miss
  count for this.

### Longer-term product direction

- Build out the Daily Page's weekly, monthly and quarterly review cadence from
  the direction set for Crane. Weekly exists — its honest denominators are the
  single strongest thing built here — and the wider horizons do not.
- ~~Idea resurfacing, a mind-map view, an append-only idea log, and AI as a
  confirm-before-write planning assistant.~~ **All moved to the knowledge core,
  August 13, 2026**, and built further there than these lines imagined. Its ML
  policy is stricter than the AI line was; v1 ships no generation at all.

### ~~Only if Clarice becomes a business~~ — refused August 22, 2026

~~Billing, support operations, deeper legal requirements and horizontal scaling
remain out of scope until the public-readiness bar is genuinely met.~~

**Clarice is not going to be pushed toward commercialization.** Vince's call,
August 22, 2026, recorded in full at `commercial-blueprint.md` Part 9 #1 and
[`clarice-v4-plan.md`](clarice-v4-plan.md). Billing, pricing, packaging,
entitlements, a wedge and a market are **refused rather than deferred** — the
public-readiness bar is no longer the gate, because the answer is no rather
than not yet.

**This heading was a deferral whose trigger can never fire**, which
`principles.md` says is a refusal and should be recorded as one. Kept as a
struck heading rather than deleted, so the reasoning survives for anyone who
remembers the section.

**The guest question is separate and open** — whether anybody other than Vince
ever uses Clarice is V1 in `clarice-v4-plan.md`, and it is not answered here in
either direction.

## Settled boundaries

- Notes remain plain text; no Markdown renderer.
- Subtasks are one level deep only.
- Completing every subtask does not auto-complete its parent.
- Only top-level tasks recur.
- `/mind/` is where the knowledge core lives, permanently — settled August 15,
  2026, not left temporary. Cheap to revisit: the prefix appears in one line of
  `clarice/urls.py` and everything under it is relative.
- **SSL expiry alerting is refused, not missing.** UptimeRobot paywalls it,
  certbot renews automatically. Recorded so nobody re-investigates and reaches
  the same paywall.

## Release practice

Production releases use alphabetic bird codenames. **Tag only after production
is verified.** The letter carries; the bird is chosen when the release ships.
The sequence skips E — Vince's call, August 3, 2026. ~~Since then `ibis`,
`jackdaw`, `kestrel` and `lapwing` have taken I, J, K and L, so **M is the
current letter**~~ — **`petrel` took P on August 23, 2026, so Q is the current
letter** and is unclaimed. A letter is never reserved for a subject in advance.

### Which deploys earn a bird, and which do not

**Not every deploy is a release.** Added August 26, 2026, at Vince's direction,
because the convention had never said so and one document read as though it
had — `roadmap-history.md` said *"a release receives three tags after it is
verified in production"*, which describes every deploy that has ever happened.

**The practice was already selective and only the criterion was missing.**
Well under half of all deploys carry a bird; the rest are follow-ups,
corrections and infrastructure, and nobody ever thought they were releases —
but with nothing written down, the question came up fresh each time and was
answered by whoever was tagging.

~~Fourteen of thirty-six deploys carry a bird. The other twenty-two are...~~ —
**struck August 28, 2026, having drifted to fifteen and thirty-seven.** `git
tag` is the count and this file does not keep a second copy of it; the ratio is
what the paragraph was ever about.

A deploy is a release, and takes the next letter, when **both** hold:

1. **It has a subject** — one sentence naming what shipped, written before the
   tag rather than assembled from the diff. A batch of whatever was ready is
   not a subject, however large. `nightjar` is thirty-one commits and one
   sentence; the August 26 deploy is twenty-one commits and a list.
2. **It moves something a document tracks** — a verdict in
   [`product-stories.md`](product-stories.md), a stated acceptance in
   [`clarice-v3-plan.md`](clarice-v3-plan.md), or an item closing in this file.

**Infrastructure is excluded by an older rule and this does not reopen it.**
[`architecture-trajectory.md`](architecture-trajectory.md) §6: *infrastructure
work does not ship features and should not be numbered as a release; it runs
alongside.* So a deploy that closes five ranked security items is still not a
release — which is exactly the August 26 case, and the reason it has no bird.

**Everything else still gets `LIVE` and a `DEPLOYED-` tag, with its verification
in the tag message.** Nothing about the record changes; a deploy without a bird
is fully accounted for. What the bird adds is a claim that a body of work
finished, and **that claim is what should be scarce** — fourteen birds across
five weeks is a legible history, and thirty-six would be a log.

**When it is genuinely arguable, it is not a release.** A release announces
itself; a deploy you have to argue into being one is a batch you are fond of.

- `LIVE` is a moving tag for the code currently running. It is the only tag
  ever overwritten, which is safe precisely because the position it leaves is
  kept by the `DEPLOYED-` tag that marked it.
- `DEPLOYED-<date>/<HHMM>` is a permanent deployment-event tag.
- The bird codename is a permanent annotated release tag describing what
  shipped and how it was verified.

**Letters are never reserved for a subject** — Vince's call, August 15, 2026,
after `architecture-trajectory.md` §5 speculatively attached commercial
readiness to "release G" and Godwit spent that letter on the merger. A letter
is the next position in a sequence, claimed by whatever ships next.

**A release is a coherent body of work with a finish line.** The letters lapsed
between August 6 and 12, when six of seven lines of work shipped outside the
release structure, and were deliberately restored on August 15 — the merger was
exactly the coherent body of work the letters had stopped naming. Fulmar and
Godwit were assigned belatedly to close the gap, and Fulmar's annotation admits
its verification was piecemeal.

**Tagging is a step in the deploy, not something remembered afterwards.** It
drifted badly through August because it was written down here as a convention
and nowhere as a step. The step is in `CLAUDE.md`.

## Keeping this current

Update this file when work begins, changes scope, ships, or is explicitly
deferred. When an idea from Later earns work, give it a one-line reason and a
focused spec before it joins an active track.

**Move completed detail into [`roadmap-history.md`](roadmap-history.md) and
keep only the resulting baseline or remaining consequence here.** That
instruction has been in this file since August 1 and has been ignored three
times — 257 lines migrated out on August 13, 272 more on August 16, and 175 more
on August 28, by which point *Open now* was 578 lines carrying twelve live items
and two entries it wrongly called live. If a section here is describing the past
at length, it is in the wrong file.

**It was ignored three times because it was advice, and it is now a step.**
[`README.md`](README.md) owns the rule — *a closed roadmap entry is evicted, not
struck* — and `CLAUDE.md`'s closing ritual carries it as step 2, with promotion
of any surviving consequence as step 3. **The two are one mechanism**: eviction
alone would bury live work along with the narrative, and promotion is what stops
that. Both go in the commit that closes the work, for the same reason the strike
does.

**What lives here now**: live entries first, then a `### Closed` roll-up of one
line each. A closed entry that has grown a paragraph is a bug in the same way a
tally in a header is.
