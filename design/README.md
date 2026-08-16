# `design/` — what each document is, and whether to trust it

Vince · index · rewritten August 16, 2026

## The rule

**A document that outlives its work has a status, and a status can be wrong.**

That was the drift engine. Twenty-two of the thirty-two files here were shipped
plans kept in full "for their reasoning" — each carrying a status line that could
rot, and an index row asserting whether that status line was honest. This file
used to have a column called *"Declares it?"*, and eleven rows said **no**.
Sixteen of the sixty commits before this rewrite touched documentation only, and
about half were corrections.

**So a shipped plan is now reduced to a stub**: four lines saying what it was,
when it shipped, and where its narrative went. A stub cannot drift, because
*"Crane shipped August 2, 2026"* is permanently true.

**Stubs rather than deletions**, and the reason is measurable rather than
sentimental: 251 comments across `src/`, `frontend/`, `android/` and `infra/`
cite these plans by name and section. Those citations are provenance for
reasoning each comment already states in full — so the file needs to resolve, and
its three hundred lines do not.

11,002 lines became roughly 4,000 without breaking one citation.

## Standing authorities — read these

| Document | Authority for |
|---|---|
| [`principles.md`](principles.md) | How work is delivered — **everywhere in this tree, knowledge core included.** Its *design* rules stop at the task core; see its §Scope |
| [`roadmap.md`](roadmap.md) | What is active, what is deferred, what is still open |
| [`roadmap-history.md`](roadmap-history.md) | The record: every shipped release, its deployment, and what it taught. **The one file that cannot go stale**, because it is explicitly about the past |
| [`architecture-trajectory.md`](architecture-trajectory.md) | §4's charter for new models and §7's refusals. §5's release arc was cut on August 16 — sequencing lives in `roadmap.md` |
| [`commercial-blueprint.md`](commercial-blueprint.md) | The commercial decision and its sequence. **Part 1's defect list is closed and empty**; Part 9's three open decisions are the live content |
| [`product-stories.md`](product-stories.md) | What the product is *for*, as behaviour, and **the only score measuring the product rather than the process** |
| [`daily-operating-system-vision.md`](daily-operating-system-vision.md) | Product direction for the task core. Its Crane slice plans and its second-brain sections came out on August 16 |

## Open — designed but not done

| Document | State |
|---|---|
| [`staging-environment-plan.md`](staging-environment-plan.md) | Designed Aug 11, **deliberately deferred** Aug 12. The `is_debug()` fix shipped; the droplet waits for a trigger |
| [`android-release-signing-plan.md`](android-release-signing-plan.md) | Build is wired; **the keystore is Vince's to generate by hand** |

## Stubs — shipped, kept only so their citations resolve

Twenty-two files. Each is four lines pointing at
[`roadmap-history.md`](roadmap-history.md), which holds the narrative. **They are
not listed individually here**, because a list of stubs is exactly the kind of
second copy this rewrite removed — `ls design/` is the list, and every one of
them says what it is in its first line.

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

There is no third step checking this index, and no fourth updating a status line.
Both existed only because plans kept their full text.
