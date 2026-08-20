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
| [`clarice-v3-plan.md`](clarice-v3-plan.md) | **The sequence**, from August 20, 2026 — bringing the two cores together and making the product usable, in five named releases toward one destination. Deliberately long, overriding Part 8's refusal of exactly that. Scored against `product-stories.md` and not against itself |
| [`product-stories.md`](product-stories.md) | What the product is *for*, as behaviour, and **the only score measuring the product rather than the process** |
| [`daily-operating-system-vision.md`](daily-operating-system-vision.md) | Product direction for the task core: the premise, the thesis, and the rules the Daily Page must not break |

## Open — designed but not done

| Document | State |
|---|---|
| [`staging-environment-plan.md`](staging-environment-plan.md) | Designed Aug 11, **deliberately deferred** Aug 12. The `is_debug()` fix shipped; the droplet waits for the trigger the plan names |
| [`android-release-signing-plan.md`](android-release-signing-plan.md) | Build is wired; **the keystore is Vince's to generate by hand**, with the `keytool` command the plan carries |
| [`mirrored-rules-brief.md`](mirrored-rules-brief.md) | Written Aug 18 **for the redesign, not for now.** Eight rules hand-ported across three languages; the divergence is demonstrated, and `bucket_for` turns out to be a payload gap rather than an architecture |
| [`security-and-resilience-plan.md`](security-and-resilience-plan.md) | Written Aug 19, **not started and not claimed by `roadmap.md`.** Sorts the surface into what nobody named, what has ripened, and what is settled — rather than a checklist. **Adding the adversary lens reordered it: MFA on the admin outranks the restore drill**, which is second and confirmed in scope. Five decisions open; nothing in it waits on staging |
| [`planning-assistant-v2-plan.md`](planning-assistant-v2-plan.md) | Written Aug 19, **active since Aug 20 and claimed by `roadmap.md`** — the weekly planning session. **Eight of its nine increments have shipped**: the weekly intention made reachable, capacity at day grain, project outcome and pause, the check-in and its session record, outcomes, blockers answered in place, the week laid out and stress-tested, and scenario planning. **Increment 9 is ranking by confirmation history and may never ship** — it is gated on a sample floor the corpus has not cleared, and the plan says not shipping is then the correct outcome rather than a failure. **Nothing generated anywhere**, which was the finding that shaped it. Of six decisions, D3 is answered (outcomes earn their own model), D5 and D6 turned out narrower than posed and are recorded at the code; D1, D2, D4 and D7 remain |
| [`admin-mfa-plan.md`](admin-mfa-plan.md) | Written Aug 19, **not started.** The focused spec for that plan's §1.5. Shaped by four interactions a stock recipe gets wrong, chiefly that **`/api/v1/login` trades a password for a 90-day token and starts no session**, so a session-based gate misses it — and the Android keystore blocks the obvious fix. Four increments; **enrol before enforcing** is the ordering that matters |
| [`search-plan.md`](search-plan.md) | Written Aug 20, **active the same day and claimed by `roadmap.md`.** **Four of five increments are done and it is usable** — `/mind/search/` answers in three sections from one box, and `GET /api/v1/search` serves the same thing. **All four decisions were answered the same day.** **D3 and D4 are the ones worth reading, and both found something the question had not asked**: D3 asked whether `RetrievalMiss.resolved_node` should widen, and the answer is that nothing has ever populated that field — the fourth un-switched-on seam in a fortnight — while the actual defect was increment 3 having made the retirement gate's miss count ambiguous, fixed before the deploy because a miss cannot be re-interpreted afterwards. D4 said no to the command palette (a cleared precondition is not a trigger) and found that nothing in the task core linked to search at all. Increment 5, the nine deferred fields, is all that is left, and it wants real use first. Undeployed. The focused brief Track D asks a candidate for, on the one candidate there whose trigger has fired. **Mostly an extension sideways rather than a build**: the knowledge core has had generated `tsvector` columns, `GinIndex`es and a ranked read since before the merger, and the task core has none — which is also how `roadmap.md`'s "no full-text search anywhere in the product" was found stale. **Sectioned results, not one merged ranking**, because `SearchRank` does not compare across two document sets and the failure is silent. Slice 1 is `Item` and `DailyEntry` only, with nine fields deferred by name; five increments, the first two invisible. Four decisions open, including where a cross-core endpoint lives when the one-API rule assumed every endpoint belongs to a core |
| [`temporal-substrate-plan.md`](temporal-substrate-plan.md) | Written Aug 20, **not started and not claimed by `roadmap.md`.** Teaching memory what happened, so a recollection can answer *what was going on around this* and *what developed afterward*, and so a resurfacing can be cued by a person's present rather than the sentence they just typed. **Written because three separate lines of thinking hit the same missing piece on one afternoon** — contextual recall, prospective recall's present-context cue, and the weekly instrument's intention-versus-attention reading — which is what makes it one piece of work rather than three. The finding it rests on: **`EventType` has 23 values and every one is about a note**, so the most carefully guarded structure in the codebase is a note log rather than a life log, while the task core is a temporal index of a life that memory cannot see. **The line that keeps Part 4's event-bus refusal standing is *facts, not derivations*** — an append-only row for what happened, never for what a read could have produced. Six increments, **the first three invisible**, and **increment 5 may correctly stop at four** if D4 cannot be answered honestly. Five decisions; **D1 is the question `search-plan.md`'s own D1 predicted would be asked again**. Carries one correction it owes `product-stories.md`: the second brain is not the memory of the third loop, it is the substrate, and the loops are tempos of reading and writing it |

**The planning assistant's second version is active**, and its row says which
parts have shipped — the one document here allowed to be more than
designed-and-waiting. It becomes a stub like the others when it closes, and the
distinction disappears with it, which is the point of stubs.

## The rest of `design/` — one record, the stubs, and the mockups

**A record:** [`code-review-2026-08-16.md`](code-review-2026-08-16.md), one
risk-based review at `305d1e7` with the suite counts actually run. Explicitly
about the past, so it cannot go stale; its findings are **not** production
defects until someone promotes them to `commercial-blueprint.md` Part 1.

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
