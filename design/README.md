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
| [`commercial-blueprint.md`](commercial-blueprint.md) | The commercial decision and its sequence. **Part 1's defect list is closed and empty**; Part 9's three open decisions are the live content |
| [`product-stories.md`](product-stories.md) | What the product is *for*, as behaviour, and **the only score measuring the product rather than the process** |
| [`daily-operating-system-vision.md`](daily-operating-system-vision.md) | Product direction for the task core: the premise, the thesis, and the rules the Daily Page must not break |

## Open — designed but not done

| Document | State |
|---|---|
| [`staging-environment-plan.md`](staging-environment-plan.md) | Designed Aug 11, **deliberately deferred** Aug 12. The `is_debug()` fix shipped; the droplet waits for the trigger the plan names |
| [`android-release-signing-plan.md`](android-release-signing-plan.md) | Build is wired; **the keystore is Vince's to generate by hand**, with the `keytool` command the plan carries |
| [`mirrored-rules-brief.md`](mirrored-rules-brief.md) | Written Aug 18 **for the redesign, not for now.** Eight rules hand-ported across three languages; the divergence is demonstrated, and `bucket_for` turns out to be a payload gap rather than an architecture |
| [`navigation-and-identity-plan.md`](navigation-and-identity-plan.md) | Designed Aug 18, **not started.** One app bar replacing three navigations, a full re-theme, and a signed-out page that is not the login form. Carries its design in two comps rather than in prose; **not claimed by `roadmap.md`** |

## The rest of `design/` — one record, the stubs, and the mockups

**A record:** [`code-review-2026-08-16.md`](code-review-2026-08-16.md), one
risk-based review at `305d1e7` with the suite counts actually run. Explicitly
about the past, so it cannot go stale; its findings are **not** production
defects until someone promotes them to `commercial-blueprint.md` Part 1.

**Twenty-three stubs**, each four lines pointing at
[`roadmap-history.md`](roadmap-history.md), which holds the narrative. Not
listed individually — that list is the second copy this rewrite removed, and
`ls design/*.md` gives it.

**Eight `.html` mockups.** Six from the Tailwind overhaul — `agenda`, `archive`,
`dashboard`, `projects`, `side-nav`, `tasks` — kept for the same reason the
stubs are: `SideNav.tsx`, `AgendaWorkspace.tsx` and `test_project_api.py` cite
them for a visual decision the code cannot show. Two from August 18 —
`landing`, `shell` — which are not a record of a decision but the **live
proposal** owned by
[`navigation-and-identity-plan.md`](navigation-and-identity-plan.md), and are
the only comps here describing something not yet built. Not documents; do not
look for a status in them.

## Where a fact is allowed to live

Most drift came from one fact in two documents and only one being updated.

| Fact | Sole authority |
|---|---|
| Whether something is active, deferred or open | `roadmap.md` |
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
