# Recommendations — August 21, 2026

Claude · advisory record · written after the day's examinations

**Advice, not a plan.** Nothing here is claimed by `roadmap.md`, and each item
names the document or decision that owns it. The evidence behind every claim
is [`code-review-2026-08-21.md`](code-review-2026-08-21.md) (the double review
and dead-code inventory) and the knowledge-core examination recorded there;
this file does not restate it. When an item is adopted it should be struck
here with a pointer to where it landed; when it is refused, struck with the
reason — an advisory list that cannot be closed is a nag.

The context in one sentence: the project's engineering is unusually strong,
and the five problems worth acting on are all shadows of the strengths — an
uncorrectable log with no structural guard, capability built ahead of its
surfaces, a green suite that keeps proving less than it appears to, deliberate
operational debt aging past its triggers, and more open work than one person's
landing rate.

---

## 1. Make emitter idempotency a tested invariant of the log

**The class of C1–C4, closed structurally rather than case by case.** All four
committed-code defects in the review are writes (or wrongly-skipped writes)
into `ActivityEvent`, where a wrong row is permanent by design. Review caught
them; nothing structural prevents the next one.

**Recommendation:** one contract-test module for the life log —
`clarice/tests/test_emitters_are_idempotent.py` — that, for every emitter of
the ten life events, performs the operation twice with identical input and
asserts exactly one event (naming honest exceptions where a second call is a
real second act, e.g. repinning after release). Add the same-spirit
exhaustiveness test from the review's R8: a partition assertion over
`EventType.values` so every new value forces the person/machine question.

**Fits:** the C1–C4 repair slice; `principles.md`'s "make behavior executable
first" applied to the one place a regression cannot be undone.

## 2. Extend the seam rule from plans to code

**The disease is recorded three times and keeps recurring** — the
un-switched-on seam count is now far past the six CLAUDE.md names, and the two
worst (`mark_reviewed`, `revise`) sat dark for weeks while reading as live.
`principles.md` already holds the rule for *plans*: a deferral needs a trigger,
and a trigger that cannot fire is a refusal.

**Recommendation:** add the code half of the same principle to
`principles.md` (per CLAUDE.md, the fix for a missing principle is an edit to
that file, not a restatement elsewhere): **a slice is not closed while nothing
calls it** — built-and-dark is a deferral, and it gets a named trigger or a
deletion. Apply it retroactively via the review's inventory: D15 already
covers the review loop; `services.unlink` (zero callers anywhere, ever) is a
deletion candidate today; the rest each get a trigger or go.

**Owner of the wording:** `principles.md`, Vince's yes required — this file
only recommends it.

## 3. Run the test you just wrote

**The cheapest lesson of the review:** increment 4's suite could never have
run — its node factory uses fields the model doesn't have — and it sat that
way because no run was ever attempted. The discipline that would have caught
it already exists in CLAUDE.md ("watch it fail for the reason you expect");
what lapsed was execution, not doctrine. The same review shape recurred from
August 16: every defect live against a green suite, and today three mutations
that pass green.

**Recommendation:** two habits, no tooling. (a) The write-a-test step is not
done until that file has been *executed* — `manage.py test
clarice.tests.test_recall_around` costs seconds and would have caught R1 the
day it was written. (b) When a review or an increment touches boundary logic,
spend ten minutes on hand mutation probes the way the August 16 review did —
today's three green mutations (R3) is exactly what that practice exists to
catch. CI cannot help with either: it never sees uncommitted work.

## 4. The operational debt has aged past its reasons

Every item here is already designed and already ranked — the issue is purely
that none is claimed while feature tracks multiply.

- **Admin MFA**: `security-and-resilience-plan.md` ranks it above the restore
  drill, the focused spec (`admin-mfa-plan.md`) exists, and neither is
  started. It is the cheapest remaining reduction of the worst realistic
  outcome (admin session compromise on a one-host production).
- **The restore drill** is the *only* undo for a bad migration — rollback
  covers code, not the database — and its value decays between exercises.
  Put it on a cadence (quarterly is enough) rather than a memory.
- **Deploy-from-ref**: the playbook builds from the working tree, which
  CLAUDE.md documents as a hazard and mitigates by tagging. The stronger
  answer it already sketches (CI-built images) is worth doing when convenient,
  not urgently — the tagging discipline is holding.

**Owner:** `security-and-resilience-plan.md` and `roadmap.md`; this item is a
sequencing nudge, not new design.

## 5. Close before opening

**The breadth is the risk.** Currently designed-and-open: temporal Tracks A–E,
v3's eight releases, security, MFA, staging's trigger, terms and
`commercial-blueprint.md` Part 9's three decisions. That exceeds one person's
landing rate, and the cost is exactly what this week showed — increment 4
written and abandoned one step short, docs drifting ("not started" beside
three shipped increments) because too many things were half-open at once.

**Recommendation:** a habit, not a rule: each session ends with the tree
clean and small things landed ("land small changes quickly" is already
CLAUDE.md's advice for a different reason). And one deliberate WIP question
at the start of anything new: *what does this leave half-open?*

**The concrete order for what is open today:**

1. Commit the day's documents (this file, the review record, the plan's
   Track E and decisions, the README index).
2. C1–C4, with recommendation 1's contract test in the same slice — they
   guard the table everything else stands on, and the gate question (has the
   backfill run in production?) decides the remediation shape first.
3. Repair and land increment 4 (the review's R-list), striking it in the
   plan.
4. Then one of: terms + Part 9 decisions, or MFA — a closing act from the
   commercial or the security column before any new track opens.
5. Track E's node page as the next *feature* work — the highest-leverage
   surface in the knowledge core, and the home of four already-registered
   pieces.

## What this file deliberately does not contain

The knowledge-core usefulness levers (intake first, the time-axis read,
embeddings, the review loop) — those were incorporated into
[`temporal-substrate-plan.md`](temporal-substrate-plan.md) on August 21 as
D14–D19 and Track E, which owns them now. The production-defect standard is
unchanged: nothing here or in the review record is a production defect until
promoted to `commercial-blueprint.md` Part 1.
