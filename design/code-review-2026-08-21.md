# Code review — August 21, 2026: the temporal substrate, twice over

**A record with a repair list.** Like [`code-review-2026-08-16.md`](code-review-2026-08-16.md)
it describes one review at one state of the tree; unlike it, everything it
found is in work that is days or hours old and half of it is not yet committed,
so this file doubles as the worklist for repairing it. When the repairs land,
the "open" markers below get struck with the fixing commit named, and the file
becomes a pure record.

**Reviewed at:** `main` at `cfa5c69`, plus the two untracked files of
[`temporal-substrate-plan.md`](temporal-substrate-plan.md) Track A increment 4 —
[`src/clarice/recall.py`](../src/clarice/recall.py) and
[`src/clarice/tests/test_recall_around.py`](../src/clarice/tests/test_recall_around.py).
The committed scope is Track A increments 1–3 (`0844d47` … `cfa5c69`, all
August 20).

**These findings are not production defects until promoted.**
`commercial-blueprint.md` Part 1 stays the sole authority for that list, and
promoting any of these is a separate decision — though C1–C4 are candidates the
moment the answer to the gate question below is "yes, the backfill ran".

---

## What was actually run

**Nothing.** This review is reading only, and it says so per `principles.md`
rather than implying otherwise: no test suite was executed, no command was run
against a database. Two evidence levels appear below:

- **Confirmed** — verified by an adversarial second pass tracing actual code
  paths, with the deciding lines quoted in the verifier's report.
- **Read** — from a single reviewing pass. Strong but unproven.

One reason no suite was run is itself finding R1: the increment-4 tests
**provably cannot execute** — their node factory constructs a model with fields
it does not have — so "the tests pass" was never available as evidence for
anything in `recall.py`.

## How findings were checked, and what refutation changed

Two independent reviews:

1. **Local, high effort** — eight parallel finder angles over the two untracked
   files (line-by-line, invariants, cross-file tracing, reuse, simplification,
   efficiency, altitude, conventions), ~40 raw candidates deduplicated to ten,
   with three adversarial verification passes.
2. **Ultrareview (cloud)** — the whole branch delta, 23 files. Its four
   findings are all in the *committed* increments 2–3 and none are in
   `recall.py`, which is the useful negative: the two reviews overlapped on
   scope and did not overlap on findings.

**The strongest local candidate was refuted, and that is worth recording.**
Four of the eight finders independently claimed `MACHINE_EVENTS` was missing
machine-written types (`EDGE_CREATED`, `EDGE_REMOVED`, `ALIAS_MERGED`,
`HYPOTHESIS_RESOLVED`). Caller tracing killed all four: the first two are
written only when a person confirms in `/review/` (or have no caller at all,
anywhere — `unlink` is dead code), and the latter two have **no reachable
production writer**. Four agents agreeing was consensus on a shared wrong
inference, not evidence; only the trace decided it. What survives is the
narrower R8.

---

## Part 1 — Committed code: four defects, one theme

All four write (or fail to write) rows in a table the database trigger refuses
to `UPDATE` or `DELETE`. Over-recording there is permanent; under-recording is
recoverable. That asymmetry — the plan's own *"under-recording is the safe
direction"* — is what ranks them.

### The gate question, answered August 21, 2026

**Has `backfill_life_log` been run against production without `--dry-run`?**
**Yes** — on August 20, immediately after the deploy that carried it, with all
four defects live.

**None of them fired, and the log is intact.** Checked against production
before any repair: zero `TASK_ARCHIVED` events and zero items with
`archived_at` set, zero recurring completions, one `DailyFocus` row with no
orphan, and no intention ever set. The four reconstructed events are exactly
the four that should exist.

**The reason is not that the defects were mild.** Production's task core held
almost nothing for them to reach — the same thinness that makes the substrate
hard to demonstrate is what kept the permanent record clean. The next recurring
task completed would have written C1's retirement into the record of a habit
being kept, and it could not have been removed.

So the remediation shape was the cheap one: fix, test, and the existing four
rows need no correction.

### C1 — ~~the backfill fabricates the event `complete_item` refuses to write~~ · **closed August 21, 2026 (`b839800`)**

**[`backfill_life_log.py:123-136`](../src/mind/management/commands/backfill_life_log.py)** · Confirmed (cloud)

`complete_item` deliberately logs only `TASK_COMPLETED` for a recurring
completion — the simultaneous auto-archive is "mechanism, not a decision," and
`test_a_recurring_task_records_the_completion_and_not_the_archive` holds it.
The backfill checks each event type independently, so every recurring task
(always `completed_at` set, never a logged archive) gets a reconstructed
`TASK_ARCHIVED`: a retirement written into the permanent record of a habit
being kept.

**Fix:** skip the archive emit when `task.recurrence != NONE and
task.archived_at == task.completed_at`, mirroring `complete_item`'s scope
exactly; a genuinely ended-then-archived recurring task still gets its event.
Test both the live-then-backfill and the pre-live-completion shapes.

### C2 — ~~the dedup key is one-per-subject; two event families are many-per-subject~~ · **closed August 21, 2026 (`b839800`)**

**[`backfill_life_log.py:138-158`](../src/mind/management/commands/backfill_life_log.py)** · Confirmed (cloud)

Idempotency keys on `(subject, event_type)` — right for `TASK_COMPLETED`,
`WEEK_REVIEWED`, `INTENTION_SET`; wrong for `FOCUS_PINNED`/`FOCUS_RELEASED`
(one `DailyFocus` per task **per day**) and `OUTCOME_CHOSEN` (one
`WeeklyOutcome` per commitment). One live pin of a task after increment 2
shipped makes the backfill skip every pre-increment pin of that task, silently.
Under-recording, so recoverable — but only after the key is fixed.

**Fix:** key focus dedup on `(task_id, entry_id, event_type)`, the grain
`DailyFocus.unique_daily_focus_per_entry_task` already enforces; dedup outcomes
at row grain (carry `outcome.pk` in the payload, or count events against
`WeeklyOutcome` rows per week).

### C3 — ~~orphaned focus rows duplicate on every run~~ · **closed August 21, 2026 (`b839800`)**

**[`backfill_life_log.py:148-168`](../src/mind/management/commands/backfill_life_log.py)** · Confirmed (cloud)

Hard-deleting a pinned task sets `DailyFocus.task` to NULL; the dedup set is
built with `task__isnull=False`, so `(None, FOCUS_PINNED)` can never be in it
and the same orphaned focus re-emits **on every run** — the docstring's
"idempotent by subject" promise is false for exactly the rows whose loop
comment says "may be None." Duplicates are permanent.

**Fix:** C2's `(task_id, entry_id, event_type)` key resolves this too, since
`entry_id` survives the task's deletion; alternatively key the reconstruction
on `focus.pk`. Either way, add the orphaned-focus case to the idempotency
tests.

### C4 — ~~`set_intention` logs a no-op save as an event~~ · **closed August 21, 2026 (`b839800`)**

**[`review/services.py:149-165`](../src/review/services.py)** · Confirmed (cloud)

Every other emitter in increment 2 guards on state change (`pin_task`,
`set_recurrence`, `complete_item`, `archive_item`, `complete_review`);
`set_intention` records `INTENTION_SET` unconditionally — on an endpoint whose
own docstring promises "sending it twice leaves the same state." Every blur
re-save, retry and double-click writes a permanent duplicate.

**Fix:** gate on `created or intention.text != new_text`. Clearing to empty is
still a change and still emits, so the behaviour the inline comment defends is
preserved. Regression test: two identical calls, one event.

---

## Part 2 — Increment 4 (uncommitted): ten findings

The increment is a good design honestly documented — chronological never
ranked, counts never flags, per-side caps, the subject-outlives-the-row rule —
and none of that is in question. What is in question is that **none of it has
ever been executed** (R1), and the module's central classification rests on a
factually wrong comment (R2).

### R1 — ~~the test suite cannot run: `Node` factory uses fields `Node` does not have~~ · **closed August 21, 2026 (`0baf5a8`)**

**[`test_recall_around.py:72-73`](../src/clarice/tests/test_recall_around.py)** · Confirmed

`a_node()` calls `Node.objects.create(owner=…, title=…, body=…)`. `Node` has
`original_content`, plus `captured_at` and `source` required with no defaults;
`title`/`body` belong to `Revision`. Roughly 11 of 18 tests raise `TypeError`
at construction, and line 210 asserts `n.node.title`, which cannot exist even
after a rename. **Everything else in this part is unverified because of this.**

**Fix:** use the factory the repo already has — `mind.services.capture` (as
`test_scheduled_work.py:139` in this same directory does) or the
`conftest.py` `make_node` shape — and change the cap-ordering assertion to
`original_content`. Then run the suite and watch it fail or pass for real
reasons.

### R2 — ~~a person's tagging act is classified as machine activity, and the rationale comment is wrong~~ · **closed August 21, 2026 (`0baf5a8`)**

**[`recall.py:37-58`](../src/clarice/recall.py)** · Confirmed

The comment says the excluded six are "written by `run_mind_maintenance` in
batch." Three of five are not: `FACET_PROPOSED` has **no batch writer at all**
(live capture and journal save only); `HYPOTHESIS_SURFACED` is written only
when a person opens `/review/`; `CONCEPT_PROPOSED`/`MENTION_PROPOSED` are
written on three live person paths as well as by batch. The concrete hole:
`tag_node` on an existing note with an already-confirmed label writes **only**
`MENTION_PROPOSED` — the person's username as actor, no `CAPTURED`, no
`CONCEPT_CONFIRMED` at that instant — and `around()` drops it. A deliberate
act of naming vanishes from its own morning.

The root cause is one layer down and predates this increment:
`propose_mention` stamps `confirmed_at` for an `EXPLICIT` mention yet logs the
event as `MENTION_PROPOSED` (`services.py:862` vs `:866`) — by the module's own
rule, a decision logged as a suggestion. Fixing the event written there is the
precise repair; editing the frozenset is the workaround. Either way, rewrite
the comment — as written it will steer the next maintainer wrong.

### R3 — ~~the after-side cap and both time boundaries have zero coverage~~ · **closed August 21, 2026 (`0baf5a8`)**

**[`test_recall_around.py:186-211`](../src/clarice/tests/test_recall_around.py)** · Confirmed

Three mutations each pass the whole suite green: inverting the after-slice to
keep the *farthest* events (`recall.py:159`), flipping the at-instant tie-break
`<` → `<=` (`:147`), narrowing the upper window edge `lte` → `lt` (`:137`).
Every cap test uses only negative offsets; the one event at exactly `NOON` is
removed by `excluding=` before the split runs; and
`test_two_things_at_the_same_instant…` places its events at −5 minutes despite
its name. The documented at-instant rule has no test at all.

**Fix:** one test truncating the after side and asserting which events
survive; one placing an un-excluded event at exactly `instant` and asserting it
lands in `after`; one at `instant + window`.

### R4 — ~~a naive `instant` crashes the split~~ · **closed August 21, 2026 (`0baf5a8`)**

**[`recall.py:147`](../src/clarice/recall.py)** · Confirmed

`USE_TZ = True`; the ORM filter merely warns on a naive datetime and
reinterprets it, then `event.occurred_at < instant` raises `TypeError` against
the aware value from the database — whenever the window holds at least one row,
which is the ordinary case. The most natural day-scoped call
(`datetime.combine(entry.date, time(9))`) is exactly the naive one.

**Fix:** normalize or reject at the top of `around()` —
`timezone.make_aware()` on naive input, or raise a `ValueError` naming the
caller's mistake. Either is fine; silent reinterpretation is not.

### R5 — ~~soft-deleted and archived nodes leak through the neighbourhood~~ · **closed August 21, 2026 (`0baf5a8`)**

**[`recall.py:140`](../src/clarice/recall.py)** · Read (latent)

`around()` resolves `event.node` straight off the join, bypassing
`queries.live_nodes` — the codebase's one node-visibility rule. Latent today
only because `delete_node`/`purge_node` currently have no production caller;
the day deletion is wired to a view, `around()` renders the content of the note
the person erased, against `delete_node`'s own promise. Same shape for
archived nodes and `ARCHIVED` items.

**Fix:** decide the rule *now* and test it: the event stays (a person's act),
the subject is withheld (`node=None` when `deleted_at`/`archived_at` is set),
which is exactly the shape the dangling-FK path already returns.

### R6 — ~~`excluding` accepts anything and misbehaves per type~~ · **closed August 21, 2026 (`0baf5a8`)**

**[`recall.py:131`](../src/clarice/recall.py)** · Confirmed mechanism

`getattr(excluding, "pk", excluding)` with no type check: a `Neighbour` — this
module's own return type, which carries `event_id` and no `pk` — raises deep in
`AutoField.get_prep_value` on the natural chained call; any other model
instance silently excludes an unrelated event sharing its integer pk. The
docstring's bare-pk form has no test.

**Fix:** accept one type (`excluding.pk if excluding is not None else None`,
documented as taking an event), or guard with `isinstance`. Test whichever
contract stays.

### R7 — the fetch is unbounded and hydrates tsvectors nothing reads · **deferred August 21, 2026, with its reason in the module** (`0baf5a8`)

**[`recall.py:133-146`](../src/clarice/recall.py)** · Confirmed

No DB-level limit — the whole window is fetched, joined and hydrated before
the Python cap — and `select_related("node", "task")` drags in
`Node.search_original` and `Item.search_document`, persisted `tsvector`
columns, violating the module's own `entry_id` rationale verbatim.
`limit_each_side` reads as a cost bound and bounds only the output, while the
module invites wide windows by design.

**Fix:** two `LIMIT n+1` queries walking `event_timeline` in each direction
(the sentinel row decides whether to pay for a `count()` per side), plus
`defer()` on the two tsvector columns. Fine to defer until a surface calls
this, but record it here so the parameter is not mistaken for a bound.

### R8 — ~~`MACHINE_EVENTS` is a denylist over an open enum, untied to it~~ · **closed August 21, 2026 (`0baf5a8`)**

**[`recall.py:49-58`](../src/clarice/recall.py)** · Confirmed shape

What survived the refutation: the next `EventType` value is admitted to every
neighbourhood by default; the exclusion test restates the six literals so it
fails on removal, never on omission; `expire_stale_hypotheses` (currently
uncalled, `actor="system"`) shares `HYPOTHESIS_RESOLVED` with person decisions
the day it is wired to cron, and type granularity cannot tell them apart; and
the module docstring promises `since()` will need this same set, inviting a
second copy. `life_log.py` solved the identical problem with an allowlist and
a raise.

**Fix:** partition the whole vocabulary — a `MACHINE ∪ PERSON ==
EventType.values` assertion so every new value forces the question — and keep
the set beside the vocabulary it partitions, where `since()` can share it.

### R9 — ~~`has_anything` contradicts the omitted counts at `limit_each_side=0`~~ · **closed August 21, 2026 (`0baf5a8`)**

**[`recall.py:108`](../src/clarice/recall.py)** · Confirmed arithmetic

With `limit_each_side=0` (legal, unvalidated) a thirty-event neighbourhood
returns `has_anything == False` beside non-zero omitted counts — "nothing is
dropped in silence" inverted on the one flag callers will branch on.

**Fix:** one line — or the omitted counts into `has_anything`, or reject
`limit_each_side < 1`.

### R10 — ~~three test helpers re-implement what the repo has~~ · **closed August 21, 2026 (`0baf5a8`)**

**[`test_recall_around.py:51-76`](../src/clarice/tests/test_recall_around.py)** · Confirmed

`event()` near-copies `an_event()` from
`mind/tests/test_the_log_learns_life_events.py:49`; `a_task()` bypasses
`lists.services.create_item` unlike both sibling files in this directory;
`setUp` is the third byte-for-byte copy of the same user-and-list setup, with
`since()` poised to make a fourth.

**Fix:** a shared helper for `clarice/tests/` (and lift `an_event` somewhere
both apps' tests can reach). Fold into the R1 repair, which touches the same
lines.

---

## Part 3 — Housekeeping the review surfaced

- ~~**`temporal-substrate-plan.md`'s header**~~ — corrected August 21 when
  Track E was added, and increment 4 struck when it landed (`0baf5a8`).
- ~~**The unnamed citation**~~ — `test_recall_around.py` now names
  `clarice-v3-plan.md` (`0baf5a8`).
- **Dead code, the full inventory** — recorded so nobody re-traces it. A
  follow-up examination of `src/mind/` on August 21 confirmed by grep
  (excluding tests) that the following have **no production caller**:

  | Symbol | Consequence |
  |---|---|
  | `services.unlink` | none — `EDGE_REMOVED` is unwritable |
  | `services.merge_concept` | the alias depth-one trigger guards a path nothing takes |
  | `services.delete_node`, `purge_node` | no deletion surface; R5's leak is latent because of this |
  | `services.expire_stale_hypotheses` | R8's latent hazard; `actor="system"` default |
  | `services.mark_reviewed` | **the only writer of node-level `reviewed` events** — so `review_state` always returns zero, `is_due_for_review` is always false, `attention_tier`'s review-candidate tier is reachable only via the open-hypothesis branch, and the whole spaced schedule (`KEPT_GROWTH`, `BURIED_GROWTH`) has never run in production |
  | `services.revise` | no edit surface — `Revision` is empty in production; `search_ranked`'s revision branch and the "superseded" label are defensive-only |
  | `services.confirm_mention` | dead because `record_typed_tags` stamps `confirmed_at` directly — the same root cause as R2 |
  | `services.reopen_question`, `archive_node` | no route; `archive_node`'s named first caller (the Inbox migration) no longer exists |
  | `queries.confirmed_mentions_of` | dead read |

  Downstream: **`HypothesisResolution.EXPIRED` is unreachable** (all three of
  its writers are dead), so `/numbers/`'s `expired` and `unseen_rate` are
  structurally always zero on live data. Declared-but-never-written
  vocabulary: `THREAD_ARTICULATED` (since migration 0001),
  `HypothesisResolution.RENAMED`, `EdgeRelation.CONTRADICTS`/`SUPERSEDES`/
  `DEVELOPED_FROM`, `FacetKind.MEDIA`/`GOAL`/`CONCEPT`, every `ConceptType`
  but `UNKNOWN`, `MissContext.CAPTURE`, `RetrievalMiss.resolved_node`,
  `ConnectionHypothesis.claim_text`. Known dark seams confirmed: sentence
  embeddings complete and tested but `sentence-transformers` is dev-only so
  `semantic_echo` never runs live; `Attachment` reachable from the importer
  but no HTTP surface. One doc drift: `detectors/__init__.py:32` says "all
  three are complementary" while exporting five, and its `open_question`
  paragraph still describes facets as not existing.

  Whether each symbol is a seam waiting or a leftover is a decision for the
  knowledge-core docs, not this file — but `mark_reviewed` and `revise` are
  the two where a reader would most confidently assume live behaviour that
  does not exist.

## The repair order

1. ~~**C1–C4 first**~~ — **done August 21, 2026 (`b839800`)**, gate question
   answered first and the log confirmed intact. 16 tests in
   `clarice/tests/test_life_log_repairs.py`, 7 of them failing for the
   predicted reasons before the fixes; both runners green afterwards.
2. ~~**R1 + R10 together**~~ — **done** (`0baf5a8`). The suite was run before
   being repaired: `TypeError: Node() got unexpected keyword arguments:
   'title', 'body'`, eleven of eighteen. `clarice/testing.py` now holds the
   factories all three files share.
3. ~~**R3, R4, R6, R9**~~ — **done** (`0baf5a8`). All three of R3's mutations
   turned out to be *correct behaviour, uncovered* — the tests are regression
   guards rather than bug fixes, which is the honest reading.
4. ~~**R2**~~ — **fixed at the root** (`0baf5a8`), in `mind/services.py`, not
   worked around in the frozenset. Safe because nothing reads either event: the
   only readers are writers. The pytest suite passed unchanged through the
   behaviour change, so a test was added on that side too.
5. ~~**R5, R8**~~ — **done** (`0baf5a8`). R5 withholds a deleted or archived
   node and **not** an archived task, because the task core has an archive
   somebody browses and `queries.live_nodes` has no equivalent; the asymmetry
   is tested rather than assumed.
6. ~~**R7**~~ — **deferred, recorded in the module** (`0baf5a8`). The cheap
   half is done (`defer()` on the two tsvector columns); the `LIMIT n+1`
   rewrite waits for a surface that can say what windows it asks for.
7. ~~Then commit increment 4~~ — **done** (`0baf5a8`).
