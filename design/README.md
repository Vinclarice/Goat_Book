# `design/` — what each document is, and whether to trust it

Vince · index · rewritten August 16, 2026

## The rule

**A document that outlives its work has a status, and a status can be wrong.**
Twenty-two plans here were kept in full "for their reasoning", each with a
status line that could rot; eleven index rows said theirs had. **So a shipped
plan is now a stub** — four lines saying what it was, when it shipped, and where
its narrative went. *"Crane shipped August 2, 2026"* cannot drift.

### A header may state a decision. It may never state a tally.

**Added August 26, 2026**, after an audit found nine documents carrying a false
claim and every header among them was a **tally** — *not started*, *all nineteen
are answered*, *four of five done*. Three plans had read *not started* for six
days over shipped increments, which
[`recommendations-2026-08-21.md`](recommendations-2026-08-21.md) §5 had named as
it was happening; the same three shipped and nobody went back to line 3.

**A tally is a derived fact, and a derived fact written down is a second copy.**
The increments and decisions in a plan are the status. Counting them into the
header creates something that has to be re-counted every time one of them moves,
and the moving is what nobody remembers to follow.

**This is the stub rule, extended to open plans.** A stub cannot drift because
*it is* its status and there is nothing to update. An open plan gets the same
treatment: **a date, a subject, and nothing about progress.** Read the strikes.

**A decision is different and stays.** *Deliberately deferred*, *refused*, *for
the redesign and not for now*, *deliberately half a plan* — none of those can be
derived from the increments, and each is the single most useful thing its header
says. The test is whether counting the items below could produce the sentence.
If it could, delete the sentence.

**Stubs rather than deletions**, for a measurable reason: comments across
`src/`, `frontend/`, `android/` and `infra/` cite these plans by name and
section as provenance for reasoning each comment already states in full. The
file has to resolve; its three hundred lines do not. 11,002 lines became roughly
4,000 without breaking one citation — **that one is history and stays; the
citation count is not, and no longer lives here.** It read 251 until August 28,
2026, when a recount found 257 files and 631 mentions. `git grep -l` is the
count.

### A closed roadmap entry is evicted, not struck

**Added August 28, 2026**, and it is the stub rule one level down. The stub rule
fixed closed *plans* and was never applied to closed *roadmap entries*, so
`roadmap.md` could only grow: a strike marks an entry finished and then keeps it,
in full, forever.

**What that cost, measured.** *Open now* was **578 lines conveying twelve live
items.** Ten closed entries held 220 of those lines, and **all ten were already
narrated in [`roadmap-history.md`](roadmap-history.md)** — so the long versions
in `roadmap.md` were the second copy this file exists to prevent, sitting under a
heading that says *Open now*.

So, when work closes:

- **The entry becomes one line** in *Open now*'s `### Closed` roll-up — what it
  was, when it closed, its codename. `roadmap-history.md` holds the rest.
- **Anything that survives it is promoted to its own live entry**, never left as
  a paragraph inside a struck one.

**The promotion is the point and the eviction is what forces it.** A live
consequence buried in a struck entry is invisible, and three were: `moorhen`'s
copy defect sat seven days over a shipped fix, and two entries — Sentry/Resend
erasure and Part 9's decisions — sat as *live* for two and six days after
closing. The August 28 pass took the section to 403 lines and **raised the live
count from twelve to fourteen**, because promotion surfaces work that eviction
would otherwise have swept away with the narrative.

**What this does not touch**: [`roadmap-history.md`](roadmap-history.md), which
is an archive and cannot go stale by design, and the citation discipline, which
is why any of this is safe to move.

## Standing authorities — read these

| Document | Authority for |
|---|---|
| [`principles.md`](principles.md) | How work is delivered — **everywhere in this tree, knowledge core included.** Its *design* rules stop at the task core; see its §Scope |
| [`roadmap.md`](roadmap.md) | What is active, what is deferred, what is still open |
| [`roadmap-history.md`](roadmap-history.md) | The record: every shipped release, its deployment, and what it taught. **The one file that cannot go stale**, because it is explicitly about the past |
| [`architecture-trajectory.md`](architecture-trajectory.md) | §4's charter for new models and §7's refusals. Release sequencing lives in `roadmap.md` |
| [`commercial-blueprint.md`](commercial-blueprint.md) | The August 12 audit, its architecture verdicts (Part 4) and its refusals (Part 8). **Its title is the stalest thing in it and it carries a header saying so** — headed rather than renamed on Aug 26 (v4's V3) because code across `src/`, `frontend/` and `infra/` cites it by name and part number — ~~thirty~~ **fifty files, recounted August 28, 2026**, which makes the case against renaming stronger than it was argued. **Part 1's defect list is closed and empty.** **No longer the authority on the sequence** — Part 6's phases 2–5 were superseded on August 20 by `clarice-v3-plan.md`, and Part 9's #1 and #2 were answered the same day |
| [`clarice-v3-plan.md`](clarice-v3-plan.md) | **The sequence**, from August 20, 2026 — bringing the two cores together and making the product usable, in **eight named releases** toward one destination. Deliberately long, overriding Part 8's refusal of exactly that. **Claimed by `roadmap.md` the same day.** Carries the §4 argument for every model v3 proposes, in one place: `Decision`, `Event` and `CaptureSession` earn theirs, `Bill` does not and gets a sidecar, and observations need none. Scored against `product-stories.md` and not against itself |
| [`product-stories.md`](product-stories.md) | What the product is *for*, as behaviour, and **the only score measuring the product rather than the process** |
| [`daily-operating-system-vision.md`](daily-operating-system-vision.md) | Product direction for the task core: the premise, the thesis, and the rules the Daily Page must not break |
| [`modules.md`](modules.md) | **The charter for surfaces**, from August 27–28, 2026 — the sibling of `architecture-trajectory.md` §4, which governs models and is **never overridden by it.** What a module is, the five things it is not, and the input ratio that decides whether one survives. **Not a plan and never a stub**: each module gets its own focused spec, and this outlives all of them |
| [`module-score.md`](module-score.md) | **How each module scores**, one line each, against one question. Exists so `product-stories.md` does not have to grow a journey per module and move a denominator v4 deliberately froze |

## Open — the plans that are not yet stubs

**The `State` column says what a plan cannot say about itself** — why it is
deferred, whose trigger it waits on, what it is for, whether to trust it. It
**does not say how far along it is**, and that is deliberate as of August 26,
2026: it used to, and it was wrong in four of its eight rows, in both
directions. **How far along a plan is, is the plan's own strikes**, and the
answer to *is this current?* is now *open the file*, one click away, rather than
a copy here that has to be re-read every time an increment moves.

| Document | State |
|---|---|
| [`staging-environment-plan.md`](staging-environment-plan.md) | Designed Aug 11, **deliberately deferred** Aug 12. The `is_debug()` fix shipped; the droplet waits for the trigger the plan names |
| [`android-release-signing-plan.md`](android-release-signing-plan.md) | Build is wired; **the keystore is Vince's to generate by hand**, with the `keytool` command the plan carries |
| [`mirrored-rules-brief.md`](mirrored-rules-brief.md) | Written Aug 18 **for the redesign, not for now.** Eight rules hand-ported across three languages; the divergence is demonstrated, and `bucket_for` turns out to be a payload gap rather than an architecture |
| [`security-and-resilience-plan.md`](security-and-resilience-plan.md) | **Live work, and it is the one to read before touching production.** Ranks the surface by adversary rather than by checklist, and that reordering is the useful part — MFA outranked the restore drill. **Two of its open items are not code**: the restore drill re-run is Vince's, and 2.2 waits on its own D1 |
| [`planning-assistant-v2-plan.md`](planning-assistant-v2-plan.md) | **Live work.** The forward half of the weekly ritual — v1 finds loose ends, v2 decides what to do about them. **Its measure is decisions removed, not material produced**, and **nothing in it generates anything**, which was the finding that shaped it. Its last increment is gated on a sample floor and may correctly never ship |
| [`search-plan.md`](search-plan.md) | **Live work.** Full-text search across both cores from one box. **Sectioned results, not one merged ranking**, because `SearchRank` does not compare across two document sets and the failure is silent. **Mostly an extension sideways rather than a build** — the knowledge core had the machinery before the merger and the task core had none. Its last increment is a corpus-gated deferral |
| [`money-module-plan.md`](money-module-plan.md) | **Live work, and the first repair aimed at a feeling rather than a journey** — *"everything is still sort of in silos"*. Bills was a report on a thing you could not make, edit, delete or see the cost of; it is now the Money module, and income is next. **`product-stories.md` cannot see this work** — there is no journey for managing money — which is the first time the score has been unable to measure a repair. ~~noted in `roadmap.md` rather than here~~ — **it was not, for the whole of August 27, and this row pointed at an owner that never took ownership.** Corrected the same day: `roadmap.md` carries it now, and **the gap itself is answered** — [`modules.md`](modules.md) sends module quality to [`module-score.md`](module-score.md) rather than growing this file a journey |
| [`learning-module-plan.md`](learning-module-plan.md) | Written Aug 28, **the first module specced against [`modules.md`](modules.md) rather than to produce it** — and it corrected that charter twice on contact, both times downward: `Source` wants fields rather than a sidecar, so the module adds **no model at all**, and the project-to-source chain it called unavailable is live end to end. A knowledge-core module, behind the nav entry that already says *Read*. **Its refusal is the interesting part** — no progress-through-a-thing, because that is the routines trap in a book jacket. **It carries its own doubt in writing**: it is the smallest thing that passes the charter, and says so |
| [`bill-as-a-model-plan.md`](bill-as-a-model-plan.md) | **Live work, claimed Aug 31, 2026**, and the first plan here to **overturn a written refusal**. `money-module-plan.md` refused a bill as its own model; this does not override `architecture-trajectory.md` §4 but **satisfies it** — the qualifying life-cycle difference had been sitting in `roadmap.md` since Aug 28, a day after the refusal, and nobody put the two side by side. **Its most useful sections are 5 and 7**: decision 4 is preserved as a default rather than dropped as a side effect, and the plan names the two outcomes that would reverse it |
| [`clarice-v4-plan.md`](clarice-v4-plan.md) | Drafted Aug 22, **deliberately half a plan and still not claimed by `roadmap.md`.** Short on purpose: ~~half of it is undecided~~ — **it was, until August 26, 2026, and that is why it never claimed Part 8's override the way v3 did.** The shortness is now a historical reason rather than a current state. **What is decided is that commerce is refused rather than deferred** — and of the four documents that carried it as live, ~~all four were rewritten as refusals on Aug 24~~ — **three were**, the wedge and the roadmap section first and **`product-stories.md`'s S19 later the same day**, which is where the score grew a fourth pile: *refused* is not a lesser *impossible*, and the denominator deliberately did not move. ~~**The fourth is this file's own call** — whether `commercial-blueprint.md` is renamed, split or headed, v4's V3 — and it is open.~~ **It was not open, and had not been since August 26, 2026: v4 struck V3 that day, answered *headed*, and the header is the first thing in the file.** This row said *open* for two days while the row four above it, in this same table, said *headed rather than renamed on Aug 26*. **A document contradicting itself across two rows is the failure this file exists to prevent**, and it took an outside recount to see it. Corrected August 28, 2026. ~~**What is open is V1, the fork**: whether anybody other than Vince ever uses Clarice. The spine is the work that is correct either way, which is what lets the question stay open honestly.~~ **Nothing in it is open — all four of V1–V4 were struck and answered on August 26, 2026**, and this row carried two of them as live for two days. V1 is *one other person, never the public*; V2 refuses all three unanswerable questions; V3 is *headed*; V4 keeps the denominator and bans the fraction. **The plan is no longer half a plan, and the reason it was short has expired** — what is left undecided is not a decision but a consequence: the four corpus-gated deferrals below. Corrected August 28, 2026. Two findings still carry it: **v3 executed exactly as written tops out at 15 of 19, not the 17 it claims**, because S13 is orphaned and S18 is named by no release; and **four corpus-gated deferrals wait on material one user will not produce**, which makes importing Vince's own archive a spine item rather than a guest one. Its most useful section is about the documents rather than the code — four things they called open and were not, and it acquired a fifth of its own within two days |

**Some of these are live work and some have never been started, and this table
deliberately does not say which.** That was the change of August 26, 2026: the
distinction is real but it moves weekly, and a weekly fact in a monthly document
is a fact that will be wrong. Each becomes a stub when it closes, and the
question disappears with it — which is the point of stubs.

~~**`temporal-substrate-plan.md`** had a row here reading **not started**~~ —
**removed August 26, 2026. It shipped entire on August 22 as `nightjar`** and
had been a stub for four days while this table called it unstarted, which is
the exact failure the rule at the top of this file describes, committed by the
file that states it.

## The rest of `design/` — the records, the stubs, and the mockups

**The records** — ~~two~~ **counted in neither the heading nor here, August 30,
2026.** Both said *two* until a third arrived, and a count of the documents in
a directory is exactly the derived fact the rule at the top of this file
forbids. `ls design/*-review-*.md design/*-audit-*.md` is the count.

[`code-review-2026-08-16.md`](code-review-2026-08-16.md), one
risk-based review at `305d1e7` with the suite counts actually run;
[`code-review-2026-08-21.md`](code-review-2026-08-21.md), the double review of
Track A increments 1–4, ~~with its repair list still open~~ — **its repair list
closed on August 21, 2026 and it is now the pure record it said it would
become**: all seven steps struck, R1–R10 closed except R7, which is deferred
with its reason in the module; and
[`coherence-audit-2026-08-30.md`](coherence-audit-2026-08-30.md), the task
core's surfaces read for seams rather than for risk — **the first of these
asked for by a feeling rather than by a risk model**. ~~It carries its own
repair list open in the shape the August 21 one used.~~ **All six closed on
August 31, 2026**, so it is a pure record too; what survives it is one
dependency, which `roadmap.md` owns. Explicitly about the
past, so they cannot go stale; their findings are **not** production defects
until someone promotes them to `commercial-blueprint.md` Part 1.

**Its most useful finding is about this score rather than that code**:
[`product-stories.md`](product-stories.md) reads the task core at *works* for
every journey it covers and is blind to all nine seams, because a journey that
completes by two different mechanisms still completes. **That is a boundary of
that score, not a fault in it** — the same shape [`modules.md`](modules.md)
found and answered with [`module-score.md`](module-score.md), arrived at from
the opposite direction.

**One advisory:** [`recommendations-2026-08-21.md`](recommendations-2026-08-21.md)
— five project-wide recommendations with named owners, written the same day.
Each item is struck when adopted or refused; an advisory that cannot close is
a nag.

**The stubs** each point at [`roadmap-history.md`](roadmap-history.md), which
holds the narrative. Not listed individually, and **not counted either** — that
list is the second copy this rewrite removed, and `ls design/*.md` gives both it
and its length. ~~Twenty-seven stubs~~, ~~twenty-five are a few lines, two are
longer~~: **struck August 28, 2026.** Both were still accurate, and both were
tallies this file's own rule forbids — they drift the moment a plan stubs, which
`money-module-plan.md` and `learning-module-plan.md` will each do.

**What makes a stub a stub is dropping the spec, not hitting a line count**, and
that is the part worth keeping. Two are much longer than the rest:

`temporal-substrate-plan.md`, because it keeps every one of its decisions with
what each turned out to be; it dropped a thousand lines of spec to get there.
**Whether they are all answered is that file's own strikes to say** — it read
*"eighteen of the nineteen"* here until August 28, 2026, which is this file
keeping a second copy of another document's status. What is worth knowing from
outside it: `clarice/recall.py` still carries the ±6h proxy that D18 exists to
doubt.

`admin-mfa-plan.md`, stubbed August 26, 2026, because code cites it by several
different sections and the stub says which — a reader arriving from
`settings.py` on `§2.4` should not have to guess where the reasoning went.
(~~Eleven code comments~~ — sixteen files at the August 28 recount.)

**The `.html` mockups** — `agenda`, `archive`, `dashboard`, `projects`,
`side-nav`, `tasks` from the Tailwind overhaul, and `landing`, `shell` from the
navigation and identity work. All of them are now records of shipped decisions,
kept for the same reason the stubs are: `SideNav.tsx`, `AgendaWorkspace.tsx`,
`test_project_api.py` and `accounts/templates/accounts/landing.html` cite them
for visual decisions the code cannot show. Not documents; do not look for a
status in them.

## Where a fact is allowed to live

Most drift came from one fact in two documents and only one being updated.

| Fact | Sole authority |
|---|---|
| Whether something is active, deferred or open | `roadmap.md` |
| **What order the work goes in, and toward what** | `clarice-v3-plan.md` — from August 20, 2026; it replaced `commercial-blueprint.md` Part 6's phases 2–5 |
| What shipped, when, and how it was verified | `roadmap-history.md` |
| How work is delivered and verified | `principles.md` |
| What a new model must satisfy | `architecture-trajectory.md` §4 (task core), `design-concept.md` (knowledge core) |
| **What a new surface must satisfy** | `modules.md` — from August 28, 2026. It governs *places*; §4 governs *models*, and the two never overlap |
| **Whether a module works** | `module-score.md` — one line each, and quoted nowhere else, exactly as `product-stories.md` is not |
| What is refused, and why | `architecture-trajectory.md` §7 |
| Production defects, when there are any | `commercial-blueprint.md` Part 1 |
| **How the product scores against its journeys** | `product-stories.md` — quoted nowhere else |
| Second Mind's **design** | Second Mind's own `docs/`, at `C:\dev\Clarice_secondmind` |
| The knowledge core's **code** | this repository, like everything else |

If a document needs a fact it does not own, **link to the owner rather than
restating it.** `CLAUDE.md` carried a copy of the defect list for four days and
twice described finished work as open; that is the cost, measured.

## Closing a piece of work

Also in `CLAUDE.md`, because that is what actually gets read:

1. **Move the narrative to `roadmap-history.md` and reduce the plan to a stub.**
2. **Close the roadmap item** — strike it, date it, name what replaced it.

There is no third step checking this index, and no fourth updating a status
line. Both existed only because plans kept their full text.
