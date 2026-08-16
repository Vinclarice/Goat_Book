# `design/` — what each document is, and whether to trust it

Vince · index · August 13, 2026 · **thirty-one documents as of August 15**

Thirty documents accumulated here for a three-user application, and by August
12 they had drifted out of agreement with each other: four plans still
described themselves as forward-looking months after shipping, two files gave
the same release letter to different work, and 257 lines of shipped-work
narrative had piled up under a heading that instructed the reader to move it
elsewhere. **This file exists so that drift is visible in one place instead of
discovered one document at a time.**

The rule it enforces is small: **every document declares its own status in its
first six lines**, and this table agrees with what they say.

## Standing authorities — read these

| Document | Authority for |
|---|---|
| [`principles.md`](principles.md) | How work is designed, implemented and verified. **Clarice only** — it does not govern Second Mind |
| [`roadmap.md`](roadmap.md) | What is active, what is deferred, what is still open |
| [`daily-operating-system-vision.md`](daily-operating-system-vision.md) | Product direction for the productivity half. Its second-brain and AI sections are superseded |
| [`architecture-trajectory.md`](architecture-trajectory.md) | Release ordering, the charter for new models, and what this project refuses. §5's release arc is largely overtaken |
| [`commercial-blueprint.md`](commercial-blueprint.md) | The commercial decision, the production defect list, and the sequence. **Part 1 is the live defect list** |
| [`product-stories.md`](product-stories.md) | What the product is *for*, as behaviour. 19 journeys, 2 working |
| [`roadmap-history.md`](roadmap-history.md) | The record: every shipped release, its deployment, and what it taught |

**Second Mind is not indexed here.** It is a separate project at
`C:\dev\Clarice_secondmind` with its own `docs/`, and none of the above governs
it — see `roadmap.md`'s opening section.

## Records — shipped, kept for their reasoning

Status as recorded in `roadmap.md` and `roadmap-history.md`. Where a document
does not yet declare its own status, that is marked, because an undeclared
status is exactly how the drift above started.

| Document | Status | Declares it? |
|---|---|---|
| [`bittern-plan.md`](bittern-plan.md) | Shipped Aug 2, 2026 | yes |
| [`crane-plan.md`](crane-plan.md) | Shipped Aug 2, 2026 | yes |
| [`release-d-plan.md`](release-d-plan.md) | Shipped Aug 3, 2026 as Dunlin | yes |
| [`ui-second-pass-plan.md`](ui-second-pass-plan.md) | Closed Aug 6, 2026 — F1–F5 | yes |
| [`second-mind-discovery-plan.md`](second-mind-discovery-plan.md) | Shipped Aug 10; **superseded** Aug 13 | yes |
| [`subtasks-plan.md`](subtasks-plan.md) | Fully built, Jul 31, 2026 | yes |
| [`per-user-time-zones-plan.md`](per-user-time-zones-plan.md) | Deployed Aug 1; **verified in production Aug 1 at 07:00 WITA** | stale — says "not yet exercised" |
| [`task-list-redesign-plan.md`](task-list-redesign-plan.md) | Shipped and deployed Aug 10 | yes |
| [`agenda-redesign-plan.md`](agenda-redesign-plan.md) | Shipped and deployed Aug 10–11 | yes |
| [`archive-redesign-plan.md`](archive-redesign-plan.md) | Shipped Aug 11 | yes |
| [`android-full-client-plan.md`](android-full-client-plan.md) | Slices 1–2 shipped and deployed Aug 11; later slices **undecided** | yes |
| [`token-scopes-plan.md`](token-scopes-plan.md) | Shipped and deployed Aug 11 | no |
| [`project-workspace-plan.md`](project-workspace-plan.md) | Shipped Aug 10 with two follow-ups | no |
| [`recurring-commitment-vocabulary-plan.md`](recurring-commitment-vocabulary-plan.md) | Shipped and deployed Aug 3 | no |
| [`capture-tags-plan.md`](capture-tags-plan.md) | Shipped; deployed Aug 6 | no |
| [`android-login-plan.md`](android-login-plan.md) | Shipped; deployed Aug 6 | no |
| [`android-unlock-plan.md`](android-unlock-plan.md) | Shipped; deployed Aug 6 | no |
| [`capture-api-and-tokens-plan.md`](capture-api-and-tokens-plan.md) | Shipped (Albatross/Bittern era) | no |
| [`capture-triage-and-polish-plan.md`](capture-triage-and-polish-plan.md) | Shipped (Albatross era) | no |
| [`password-reset-plan.md`](password-reset-plan.md) | Shipped (Albatross era) | no |
| [`recurring-subtasks-addendum.md`](recurring-subtasks-addendum.md) | Shipped with `subtasks-plan.md` | no |

**Eleven documents do not declare their own status**, and the four dated
"Albatross era" above are inferred from the roadmap rather than read out of the
documents themselves. Adding a status line to each is a small job nobody has
done; until it is done, this table is the more reliable source.

## Open — work that is designed but not done

| Document | State |
|---|---|
| [`one-capture-surface-plan.md`](one-capture-surface-plan.md) | **Active — this is Heron, and all five steps are built.** 1–4a verified in production Aug 15 (`DEPLOYED-2026-08-15/1200`); **4b and 5 await one deployment together, and 4b carries an irreversible migration.** Step 5 settled `/mind/` as permanent rather than moving it. Declares its own status |
| [`staging-environment-plan.md`](staging-environment-plan.md) | Designed Aug 11, **deliberately deferred** Aug 12. The `is_debug()` fix shipped; the droplet waits for a trigger |
| [`android-release-signing-plan.md`](android-release-signing-plan.md) | Build is wired; **the keystore is Vince's to generate by hand.** One of the three open B/C/D items |

## Where a fact is allowed to live

Most of the drift came from one fact living in two documents and only one of
them being updated. The rule:

| Fact | Sole authority |
|---|---|
| Whether something is active, deferred or open | `roadmap.md` |
| What shipped, when, and how it was verified | `roadmap-history.md` |
| How work is done and verified | `principles.md` |
| What a new model must satisfy | `architecture-trajectory.md` §4 |
| What is refused, and why | `architecture-trajectory.md` §7 |
| Current production defects | `commercial-blueprint.md` Part 1 |
| A specific slice's acceptance criteria | that slice's own plan document |
| Anything about Second Mind | Second Mind's own `docs/` |

If a document needs to mention a fact it does not own, **link to the owner
rather than restating it.** A restated fact is a fact that will be wrong later.

## Closing a piece of work

The checklist that would have prevented every problem this file was written to
fix — also in `CLAUDE.md`, because that is what actually gets read:

1. **Update the plan document's status line** to say it shipped, and when.
2. **Move the narrative to `roadmap-history.md`**, keeping only the resulting
   baseline or the remaining consequence in `roadmap.md`.
3. **Close the roadmap item** — strike it, date it, and say what replaced it if
   anything did.
4. **Check this index** still tells the truth.

Step 2 is the one that gets skipped, and it is the one that compounds.
