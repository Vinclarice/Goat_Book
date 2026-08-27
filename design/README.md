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

**Stubs rather than deletions**, for a measurable reason: 251 comments across
`src/`, `frontend/`, `android/` and `infra/` cite these plans by name and
section as provenance for reasoning each comment already states in full. The
file has to resolve; its three hundred lines do not. 11,002 lines became roughly
4,000 without breaking one citation.

## Standing authorities — read these

| Document | Authority for |
|---|---|
| [`principles.md`](principles.md) | How work is delivered — **everywhere in this tree, knowledge core included.** Its *design* rules stop at the task core; see its §Scope |
| [`roadmap.md`](roadmap.md) | What is active, what is deferred, what is still open |
| [`roadmap-history.md`](roadmap-history.md) | The record: every shipped release, its deployment, and what it taught. **The one file that cannot go stale**, because it is explicitly about the past |
| [`architecture-trajectory.md`](architecture-trajectory.md) | §4's charter for new models and §7's refusals. Release sequencing lives in `roadmap.md` |
| [`commercial-blueprint.md`](commercial-blueprint.md) | The August 12 audit, its architecture verdicts (Part 4) and its refusals (Part 8). **Part 1's defect list is closed and empty.** **No longer the authority on the sequence** — Part 6's phases 2–5 were superseded on August 20 by `clarice-v3-plan.md`, and Part 9's #1 and #2 were answered the same day |
| [`clarice-v3-plan.md`](clarice-v3-plan.md) | **The sequence**, from August 20, 2026 — bringing the two cores together and making the product usable, in **eight named releases** toward one destination. Deliberately long, overriding Part 8's refusal of exactly that. **Claimed by `roadmap.md` the same day.** Carries the §4 argument for every model v3 proposes, in one place: `Decision`, `Event` and `CaptureSession` earn theirs, `Bill` does not and gets a sidecar, and observations need none. Scored against `product-stories.md` and not against itself |
| [`product-stories.md`](product-stories.md) | What the product is *for*, as behaviour, and **the only score measuring the product rather than the process** |
| [`daily-operating-system-vision.md`](daily-operating-system-vision.md) | Product direction for the task core: the premise, the thesis, and the rules the Daily Page must not break |

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
| [`admin-mfa-plan.md`](admin-mfa-plan.md) | **Finished — shipped August 23 as `petrel`; a candidate for a stub.** Kept for the four interactions a stock TOTP recipe gets wrong here, chiefly that **`/api/v1/login` trades a password for a 90-day token and starts no session**, so a session-based gate misses it entirely. **Enrol before enforcing** is the ordering that matters |
| [`search-plan.md`](search-plan.md) | **Live work.** Full-text search across both cores from one box. **Sectioned results, not one merged ranking**, because `SearchRank` does not compare across two document sets and the failure is silent. **Mostly an extension sideways rather than a build** — the knowledge core had the machinery before the merger and the task core had none. Its last increment is a corpus-gated deferral |
| [`clarice-v4-plan.md`](clarice-v4-plan.md) | Drafted Aug 22, **deliberately half a plan and not claimed by `roadmap.md`.** Short on purpose: half of it is undecided, so it does not claim Part 8's override the way v3 did. **What is decided is that commerce is refused rather than deferred** — and of the four documents that carried it as live, ~~all four were rewritten as refusals on Aug 24~~ — **three were**, the wedge and the roadmap section first and **`product-stories.md`'s S19 later the same day**, which is where the score grew a fourth pile: *refused* is not a lesser *impossible*, and the denominator deliberately did not move. **The fourth is this file's own call** — whether `commercial-blueprint.md` is renamed, split or headed, v4's V3 — and it is open. **What is open is V1, the fork**: whether anybody other than Vince ever uses Clarice. The spine is the work that is correct either way, which is what lets the question stay open honestly. Two findings carry it: **v3 executed exactly as written tops out at 15 of 19, not the 17 it claims**, because S13 is orphaned and S18 is named by no release; and **four corpus-gated deferrals wait on material one user will not produce**, which makes importing Vince's own archive a spine item rather than a guest one. Its most useful section is about the documents rather than the code — four things they called open and were not, and it acquired a fifth of its own within two days |

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

## The rest of `design/` — two records, the stubs, and the mockups

**Two records:** [`code-review-2026-08-16.md`](code-review-2026-08-16.md), one
risk-based review at `305d1e7` with the suite counts actually run; and
[`code-review-2026-08-21.md`](code-review-2026-08-21.md), the double review of
Track A increments 1–4, ~~with its repair list still open~~ — **its repair list
closed on August 21, 2026 and it is now the pure record it said it would
become**: all seven steps struck, R1–R10 closed except R7, which is deferred
with its reason in the module. Explicitly about the
past, so they cannot go stale; their findings are **not** production defects
until someone promotes them to `commercial-blueprint.md` Part 1.

**One advisory:** [`recommendations-2026-08-21.md`](recommendations-2026-08-21.md)
— five project-wide recommendations with named owners, written the same day.
Each item is struck when adopted or refused; an advisory that cannot close is
a nag.

**Twenty-six stubs**, each pointing at
[`roadmap-history.md`](roadmap-history.md), which holds the narrative. Not
listed individually — that list is the second copy this rewrite removed, and
`ls design/*.md` gives it.

**Twenty-five are a few lines; `temporal-substrate-plan.md` is a hundred**,
because it keeps all nineteen of its decisions with what each turned out to be.
That is deliberate and it is still a stub: what it does not keep is the
thousand lines of spec. **Eighteen of the nineteen are answered** — D18, whether
a neighbourhood is clock-bounded or episode-bounded, is open, and
`clarice/recall.py` still carries the ±6h proxy the question exists to doubt.

**Eight `.html` mockups** — `agenda`, `archive`, `dashboard`, `projects`,
`side-nav`, `tasks` from the Tailwind overhaul, and `landing`, `shell` from the
navigation and identity work. All eight are now records of shipped decisions,
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
