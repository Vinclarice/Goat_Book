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

  **Three things it leaves, and all three are Vince's.**

  - **One admin account or two.** Enrolment first landed on `Vrbeall01`, the
    account in daily use, which is not staff — while `vince-admin`, the only one
    the gate applies to, had none. Both carry a factor now, and the better end
    state is probably one account rather than two: **a staff login used twice a
    month is one whose second factor will be missing at the moment it is
    needed.** Not a thing to slip into a deploy.
  - **M2 — where the recovery codes live.** The plan called this *the decision
    most likely to be skipped and most likely to matter*, and it was written on
    August 19 and skipped. A password manager is the obvious answer and makes
    the manager a single point of failure for **both** factors; printed and
    physical is the honest alternative.
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

- ~~**The temporal substrate is the active work.**~~ **Closed August 22, 2026,
  shipped and verified in production as `nightjar`**
  (`DEPLOYED-2026-08-22/0101`, image `clarice:ec2c4cb7e084`, all five `mind`
  migrations applied and none pending). *Making memory a memory* — the time
  axis, contextual retrieval, structured observations and intake, across five
  tracks and thirty-one commits.

  The narrative, the thirteen decisions it answered and the seven things it
  taught are in [`roadmap-history.md`](roadmap-history.md); the spec is a stub.

  **What it leaves, and neither is a shortfall.** ~~**Six decisions stay
  open**~~ — **all six closed on August 22, 2026**, and four of them built
  something: the person's clock (D16), the cyclic axis and `Mode.RESURFACING`
  (D17), the log's answer to absence (D5), and the dormant review loop's
  missing caller (D15). Two were largely already decided and nobody had
  noticed. **Two were hiding live production defects.** The narratives are in
  [`roadmap-history.md`](roadmap-history.md). ~~**D16 is the one with a clock running**, since
  every observation Track C records is stamped UTC~~ — **answered August 22:
  the clock is the person's**, and the stated symptom was wrong. Track C's days
  were always local; the UTC date was in S14's note-to-day join, where it had
  been silently returning an empty section for every evening note west of UTC.
  Reasoning and the defect in
  [`roadmap-history.md`](roadmap-history.md). And ~~**`product-stories.md` has not
  been re-scored**~~ — **re-scored August 22, and the substrate moved nothing.**
  Every remaining require was a specific noun the substrate sits beneath rather
  than satisfies, and the re-score is what turned up that *Unify* had claimed
  an acceptance it did not meet. **Four stories moved later that day** on work
  aimed at those nouns; the score itself is in
  [`product-stories.md`](product-stories.md) and is deliberately not repeated
  here, which is a rule this line broke once already.

- ~~**Release M — *Usable*, v3's first delivery release.**~~ **Closed August 20,
  2026, shipped and verified in production as `moorhen`**
  (`DEPLOYED-2026-08-20/2030`, image `clarice:b8591ee507f0`, all six migrations
  applied and none pending). *The day you can actually use* — the day drafts
  itself and never pins, a brief that reports change rather than state, the
  closing ritual, a calendar, a bills month, priority and lead time.

  The narrative, the four things it taught and the verification actually run
  are in [`roadmap-history.md`](roadmap-history.md).

  **What it leaves open**: two copy defects found by the browser pass that
  should have run before the deploy and did not — the draft says *nothing at
  all* when it has candidates but no capacity figure, and the bills month says
  *"that total"* while showing one per currency. Both are the entry below.

- ~~**Release L is open, and its bird is not chosen.**~~ **Closed August 20,
  2026, shipped and verified in production as `lapwing`**
  (`DEPLOYED-2026-08-20/1132`, image `clarice:612e23415830`, all three
  migrations applied and none pending). *The week you can plan, and the material
  you can find* — the planning assistant's second version and unified search,
  across two deployments.

  The narrative, the six things it taught and the verification actually run are
  in [`roadmap-history.md`](roadmap-history.md).

  **What it leaves open, both deliberately**: search's fifth increment, nine
  fields deferred by name that want real use first, and the planning assistant's
  ninth, a ranking gated on a sample floor a corpus of 41 nodes has not cleared.
  Neither is a shortfall; `principles.md` now says a trigger that cannot fire is
  a refusal, and the second is a candidate for that reading.

- ~~**`/api/v1/login` is unthrottled.**~~ Fixed August 18, 2026 (`9eb9eea`),
  with `/accounts/password/reset/` alongside it — an exact-match `limit_req`
  block each, proved by running nginx against the rendered template rather than
  by reading it. **Not live until the next deploy**, because an nginx template
  changes nothing until the playbook runs. What replaces it is a test:
  `clarice/tests/test_unauthenticated_endpoints_are_throttled.py` reads the
  template and the API together, so the *next* `auth=None` endpoint cannot ship
  unthrottled the way this one did.
- ~~**No mail leaves production at all.**~~ Closed August 18, 2026 (`jackdaw`).
  DigitalOcean blocks outbound 25, 465 and 587 on every Droplet, which is why
  three Sentry reports read as a flaky relay and were a total outage. Sending
  moved to Resend's HTTPS API. The proof kept deliberately: SMTP is **still**
  blocked from that host and mail goes anyway, so the fix is not coincident with
  anything DigitalOcean did.
- ~~**The planning assistant.**~~ **Closed August 19, 2026**, shipped and
  verified in production as `kestrel` (`DEPLOYED-2026-08-19/1339`). All six
  increments: commitments read out of the journal, unresolved questions with
  the notes that came back to them, a project that can say what it is for and a
  brief that retrieves what bears on it, the weekly review's loose ends, and
  next week drafted against observed capacity. Every proposal cites the passage
  that caused it and nothing is created without a confirmation.

  **`v1 shipped no generation at all`**, which is `design-concept.md`'s ML
  policy holding rather than a corner cut — D1 deferred generated prose with two
  firing conditions written down rather than a someday.

  Two of `product-stories.md`'s target-model items moved as prerequisites rather
  than as features: **S9's weekly intention** exists, and **S3 no longer
  requires `Item.effort`** — capacity is derived from `DailyFocus` history, so
  there are no estimates to go unentered. ~~Neither story's verdict moved~~ —
  **re-scored against this release later the same day, and three verdicts did**;
  that file owns the score and is not quoted here.

  ~~**What the re-score found and this file has to carry: S9's write path does
  not exist.**~~ **Built August 20, 2026** as v2's increment 1 — see the entry
  below, which is where that work continued.

  The narrative, the four decisions and the three silent-nothings that build
  turned up are in [`roadmap-history.md`](roadmap-history.md); the v1 plan is a
  stub.

- ~~**The planning assistant's second version is the active work.**~~ **Shipped
  and deployed; increments 1–8 went out August 19 and the release closed as
  `lapwing` on August 20. Increment 9 is all that remains and may never fire.**
  Designed and
  being built to
  [`planning-assistant-v2-plan.md`](planning-assistant-v2-plan.md): the weekly
  planning *session*, on the review's forward half rather than a second
  surface. **Eight of its nine increments are complete and live** — deployed
  August 19, 2026 as the first half of release L, see the entry above — the
  weekly intention made reachable (which closed the item
  struck above), capacity at day grain where D2 always specified it, a project
  that can say what done looks like and be parked, a check-in that opens with
  what the system believes, outcomes chosen from evidence, blockers answered
  where they are read, the week laid out by day and stress-tested, and scenario
  planning.

  **Nothing in it generates anything**, which is the finding that shaped it:
  twelve of fourteen elements needed no prose at all, and the two that do are
  the sites D1 already ranked. Scenario planning — the part that feels most like
  an assistant — is `draft_week` with one argument.

  **Increment 9 may never ship, and that is the correct outcome rather than a
  failure**: ranking by confirmation history is gated on a sample floor a corpus
  of 41 nodes has not cleared. Three smaller pieces were deferred and named in
  `abcfc51`: confirming a recurring name in place, the planning-miss signal, and
  "schedule a decision" as a third disposition.

  **Two decisions dissolved on contact with the code** and are recorded there
  rather than here: D5, whether the review may decide things, which it already
  did through the owning core's services; and D6, where the ritual lives, which
  does not bind while only questions are acted on because a question carries no
  review window. D1, D2, D4 and D7 remain open; the score is
  [`product-stories.md`](product-stories.md)'s and is not quoted here.

- ~~**Terms of service and a privacy policy.**~~ **Written and published
  August 19, 2026**, at `/privacy/` and `/terms/`, linked from a footer on
  every signed-out page and from the signup form. Owned by Vinclarice, LLC;
  hosting named as DigitalOcean's New York region. Every claim was checked
  against the source and a dozen tests hold the ones with a mechanical
  counterpart — the deletion window, the digest default, the four Sentry
  exclusions, the absence of analytics — so the code cannot drift away from a
  published promise silently. **The one claim no test can hold is the hosting
  region**, and the template says so at the paragraph.
  **Deliberately not lawyer-reviewed, and the trigger for changing that is
  named: broader beta testing.** Vince's call, August 19 — proportionate while
  the site is privately owned and invitation-only. What a professional read
  would want, and what is therefore still absent: the LLC's state of formation
  and business address, a governing-law clause, and a considered answer on the
  minimum age (16 is asserted).
- **Removing user data from Sentry and Resend when an account goes.** An
  account-level action in each, outside this application. Deletion and export
  inside Clarice shipped August 16.
- **Three genuinely open decisions in `commercial-blueprint.md` Part 9** — is
  this a business, which wedge, and mobile native versus responsive web. Two of
  its five are stale rather than open: #3 is answered but its reasoning predates
  the merger, and #5 was largely done by the August 15 documentation pass.
- ~~**Unified search is active and usable, and undeployed.**~~ **Deployed and
  verified August 20, 2026 as part of `lapwing`.** Four of five increments;
  the fifth is the only thing left. Designed and built
  to [`search-plan.md`](search-plan.md). **Three of its five increments are
  done**, and the third is the one a person can use: `/mind/search/` now
  answers in three sections — notes, tasks and days — from one box.

  What landed August 20, 2026, ~~all on `main` and **none of it deployed**~~ —
  **live since `DEPLOYED-2026-08-20/1132`**:
  generated `tsvector` columns with a `GinIndex` on `Item` and `DailyEntry`
  and two migrations; `lists/search.py` and `daily.reads.search_entries`;
  `clarice/search.py`, holding the one definition of how typed text becomes a
  query, because sectioned results have a quiet dependency on every section
  having asked the same question; `GET /api/v1/search`, session-only; and the
  page. 42 new tests.

  **All four decisions are answered and the brief records them** — the endpoint
  went in `mind/api_v1.py` beside capture, and the surface is the page that
  already existed, which is what keeps search attached to the miss button.

  **D4 said no to the command palette and found the real gap instead: nothing
  in the task core linked to search at all.** Four navigation surfaces were
  checked and only the knowledge core's own sub-nav had it, so reaching search
  from the task core meant two hops through the other core's capture page — for
  a feature built partly to search tasks. One link in the shared app bar,
  in the utility group rather than the Cores nav, because search belongs to
  neither core. The palette entry below carries the trigger to watch.

  **D3 turned out to be the wrong question, and answering it caught a defect
  this work had just created.** It asked whether `RetrievalMiss.resolved_node`
  should widen to reach a task; it should not, because nothing has ever
  populated that field — **the fourth un-switched-on seam found in a
  fortnight.** What did need fixing is that the retirement gate's *"retrieval
  misses fall"* counted every miss, which was exact only while this page
  searched notes alone. A miss now records what each section returned and the
  gate counts the ones where the note index returned nothing. **Fixed before
  the deploy on purpose**: a miss cannot be re-interpreted afterwards, so every
  one recorded in the gap would have been permanently ambiguous.

  **Sectioned, never merged, and that is a refusal rather than a first
  version.** `SearchRank` compares documents within one set and means nothing
  across two, so one ordered list would present a number that does not exist as
  relevance. Validating a weighting would need the retrieval evidence that does
  not exist yet — which is what the miss button is for.

  Two things were decided at the keyboard and are recorded at the code rather
  than here: search returns every status, where the agenda hides finished work,
  because the older a task is the more likely it is both done and the one being
  looked for; and `Item` weights its text above its notes, which is safe within
  one model in a way ranking across two is not.
- **Whether the Android client keeps growing.** Slices 1 and 2 shipped (Today
  read-only, then Agenda with read and act); later slices are undecided. Part 9
  recommends freezing native for responsive web, on the evidence that
  `android-full-client-plan.md`'s core assumption — mostly an Android build-out,
  not a backend rebuild — was falsified twice, and that iOS is absent entirely.
  Nothing is scheduled. That plan's stub points here for this question.
- **Floating cadence is unbuilt.** ~~One defect to fix on the way in rather
  than port~~ — `_advance_due_date` spawning a successor already overdue —
  was fixed August 15, 2026 (`70bc6c8`), *after* the merger it was supposed to
  be fixed by, which is the argument for closing a defect where it lives rather
  than attaching it to a migration. What remains open is the mode: it is
  anchored-only, because Clarice has one cadence field and cannot say which
  mode a commitment is, while `design-concept.md` calls the distinction
  load-bearing. Deliberate, and recorded at the function.
- ~~**Three navigations, three identities, and a login form for a home page.**~~
  **Closed August 18, 2026**, shipped in two deploys and verified in
  production. What replaced it: one server-rendered app bar on all three
  surfaces, a per-core sub-nav, the rail demoted to contents, the ledger
  palette and three self-hosted typefaces in both cores, and `/` as a landing
  page rather than the login form. The narrative and its six lessons are in
  [`roadmap-history.md`](roadmap-history.md); the plan is a stub.
  **The codename was deliberately held** to ship with the planning-assistant
  work, and was spent on `kestrel` on August 19. **What this did *not* close is S1**, which also wants self-service
  signup with email verification — still an admin checkbox, and
  `accounts/emails.py` still has no message telling the applicant it happened.
  [`product-stories.md`](product-stories.md) owns that score.

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

### Support for people who are signed in

B3 gave strangers a contact path and left users without one: the link is in the
Django shell's nav, and users live in the SPA. The person most likely to have
something worth reporting has the worst route to reporting it. Not merely a
missing link — asking someone with a session to retype their name and email
invites an address that isn't the one on their account, and per-IP rate
limiting is the wrong key once there is an identity to use. The argument for
adapting `/contact/` rather than forking it is in
[`bittern-plan.md`](bittern-plan.md).

**Its promoter has already fired and nobody noticed.** The stated condition was
B4, production error monitoring, so that a signed-in report could carry its own
context. B4 shipped. This is promotable, not deferred.

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
Fourteen of thirty-six deploys carry a bird. The other twenty-two are
follow-ups, corrections and infrastructure, and nobody ever thought they were
releases — but with nothing written down, the question came up fresh each time
and was answered by whoever was tagging.

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
instruction has been in this file since August 1 and has been ignored twice —
257 lines migrated out on August 13, and 272 more on August 16, by which point
the file was contradicting itself about work it recorded as both open and
closed. If a section here is describing the past at length, it is in the wrong
file.
