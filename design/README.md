# `design/` — what each document is, and whether to trust it

Vince · index · rewritten August 16, 2026

## The rule

**A document that outlives its work has a status, and a status can be wrong.**
Twenty-two plans here were kept in full "for their reasoning", each with a
status line that could rot; eleven index rows said theirs had. **So a shipped
plan is now a stub** — four lines saying what it was, when it shipped, and where
its narrative went. *"Crane shipped August 2, 2026"* cannot drift.

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

## Open — designed but not done

| Document | State |
|---|---|
| [`staging-environment-plan.md`](staging-environment-plan.md) | Designed Aug 11, **deliberately deferred** Aug 12. The `is_debug()` fix shipped; the droplet waits for the trigger the plan names |
| [`android-release-signing-plan.md`](android-release-signing-plan.md) | Build is wired; **the keystore is Vince's to generate by hand**, with the `keytool` command the plan carries |
| [`mirrored-rules-brief.md`](mirrored-rules-brief.md) | Written Aug 18 **for the redesign, not for now.** Eight rules hand-ported across three languages; the divergence is demonstrated, and `bucket_for` turns out to be a payload gap rather than an architecture |
| [`security-and-resilience-plan.md`](security-and-resilience-plan.md) | Written Aug 19, **not started and not claimed by `roadmap.md`.** Sorts the surface into what nobody named, what has ripened, and what is settled — rather than a checklist. **Adding the adversary lens reordered it: MFA on the admin outranks the restore drill**, which is second and confirmed in scope. Five decisions open; nothing in it waits on staging |
| [`planning-assistant-v2-plan.md`](planning-assistant-v2-plan.md) | Written Aug 19, **shipped as part of `lapwing` on Aug 20** — the weekly planning session. **Eight of its nine increments have shipped**: the weekly intention made reachable, capacity at day grain, project outcome and pause, the check-in and its session record, outcomes, blockers answered in place, the week laid out and stress-tested, and scenario planning. **Increment 9 is ranking by confirmation history and may never ship** — it is gated on a sample floor the corpus has not cleared, and the plan says not shipping is then the correct outcome rather than a failure. **Nothing generated anywhere**, which was the finding that shaped it. Of six decisions, D3 is answered (outcomes earn their own model), D5 and D6 turned out narrower than posed and are recorded at the code; D1, D2, D4 and D7 remain |
| [`admin-mfa-plan.md`](admin-mfa-plan.md) | Written Aug 19, **not started.** The focused spec for that plan's §1.5. Shaped by four interactions a stock recipe gets wrong, chiefly that **`/api/v1/login` trades a password for a 90-day token and starts no session**, so a session-based gate misses it — and the Android keystore blocks the obvious fix. Four increments; **enrol before enforcing** is the ordering that matters |
| [`search-plan.md`](search-plan.md) | Written Aug 20, **built and shipped the same day as part of `lapwing`.** **Four of five increments are done and it is usable** — `/mind/search/` answers in three sections from one box, and `GET /api/v1/search` serves the same thing. **All four decisions were answered the same day.** **D3 and D4 are the ones worth reading, and both found something the question had not asked**: D3 asked whether `RetrievalMiss.resolved_node` should widen, and the answer is that nothing has ever populated that field — the fourth un-switched-on seam in a fortnight — while the actual defect was increment 3 having made the retirement gate's miss count ambiguous, fixed before the deploy because a miss cannot be re-interpreted afterwards. D4 said no to the command palette (a cleared precondition is not a trigger) and found that nothing in the task core linked to search at all. Increment 5, the nine deferred fields, is all that is left, and it wants real use first. **Deployed and verified Aug 20 as part of `lapwing`.** The focused brief Track D asks a candidate for, on the one candidate there whose trigger has fired. **Mostly an extension sideways rather than a build**: the knowledge core has had generated `tsvector` columns, `GinIndex`es and a ranked read since before the merger, and the task core has none — which is also how `roadmap.md`'s "no full-text search anywhere in the product" was found stale. **Sectioned results, not one merged ranking**, because `SearchRank` does not compare across two document sets and the failure is silent. Slice 1 is `Item` and `DailyEntry` only, with nine fields deferred by name; five increments, the first two invisible. Four decisions open, including where a cross-core endpoint lives when the one-API rule assumed every endpoint belongs to a core |
| [`clarice-v4-plan.md`](clarice-v4-plan.md) | Drafted Aug 22, **deliberately half a plan and not claimed by `roadmap.md`.** Short on purpose: half of it is undecided, so it does not claim Part 8's override the way v3 did. **What is decided is that commerce is refused rather than deferred** — and the four documents that carried it as live were rewritten as refusals on Aug 24. **What is open is V1, the fork**: whether anybody other than Vince ever uses Clarice. The spine is the work that is correct either way, which is what lets the question stay open honestly. Two findings carry it: **v3 executed exactly as written tops out at 15 of 19, not the 17 it claims**, because S13 is orphaned and S18 is named by no release; and **four corpus-gated deferrals wait on material one user will not produce**, which makes importing Vince's own archive a spine item rather than a guest one. Its most useful section is about the documents rather than the code — four things they called open and were not, and it acquired a fifth of its own within two days |
| [`temporal-substrate-plan.md`](temporal-substrate-plan.md) | Written Aug 20, **widened twice the same day**, **not started; claimed by `roadmap.md` alongside `clarice-v3-plan.md` the same day.** Making memory a memory, in four parts: **what it can see** (the time axis), **how it gives things back** (contextual retrieval — the largest part), **what it notices** (structured observations), **what it holds** (intake). It began as the time axis alone; the corrected model is that memory holds anything, and **the heterogeneous memory is not the problem, it is the reason contextual retrieval becomes the central design problem.** Two findings carry it: **`EventType` has 23 values and every one is about a note**, so the codebase's most guarded structure is a note log rather than a life log; and **there are several retrieval tricks and no retrieval architecture**, with `attention_tier` sorting by actionability so a recipe, a birthday and a dream are all "quiet knowledge". Two refusals keep older decisions standing — **facts, not derivations** (so Part 4's event-bus refusal holds) and **roles are proposed, never asked** (so the deleted `Capture → Idea → Task` pipeline is not rebuilt with fourteen nouns). Four tracks, ten decisions, and **Track A increment 5 may correctly stop at four**. **Part 2 proposes to `design-concept.md` and does not decide** — the Attention Policy is not this tree's to rule on. Named the correction `product-stories.md` then made the same day |

**The planning assistant's second version is active**, and its row says which
parts have shipped — the one document here allowed to be more than
designed-and-waiting. It becomes a stub like the others when it closes, and the
distinction disappears with it, which is the point of stubs.

## The rest of `design/` — one record, the stubs, and the mockups

**Two records:** [`code-review-2026-08-16.md`](code-review-2026-08-16.md), one
risk-based review at `305d1e7` with the suite counts actually run; and
[`code-review-2026-08-21.md`](code-review-2026-08-21.md), the double review of
Track A increments 1–4 with its repair list still open. Explicitly about the
past, so they cannot go stale; their findings are **not** production defects
until someone promotes them to `commercial-blueprint.md` Part 1.

**One advisory:** [`recommendations-2026-08-21.md`](recommendations-2026-08-21.md)
— five project-wide recommendations with named owners, written the same day.
Each item is struck when adopted or refused; an advisory that cannot close is
a nag.

**Twenty-five stubs**, each a few lines pointing at
[`roadmap-history.md`](roadmap-history.md), which holds the narrative. Not
listed individually — that list is the second copy this rewrite removed, and
`ls design/*.md` gives it.

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
