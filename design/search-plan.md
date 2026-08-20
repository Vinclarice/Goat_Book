# Unified search — focused spec

Vince · focused spec · written August 20, 2026 · **not started**

## What this is

Full-text search over everything this application holds for a person, across
both cores, from one place. It is the Track D candidate in
[`roadmap.md`](roadmap.md) whose trigger has fired, written up as a brief
because that file's own rule is that a candidate needs one before it becomes
work.

**The trigger, restated so it is not re-argued.** The old entry asked for
"enough retained material that finding something again is a felt problem" —
anticipated, never observed, and unreachable, because nobody accumulates in a
store they cannot search. Daily entries are already written, already numerous
and already unfindable. The problem exists today.

## What is already there, and what is not

**The knowledge core already has full-text search, and it is good.** Checked at
`3b613a4`:

- `Node.search_original` and `Revision.search_body` are `GeneratedField`s over
  `SearchVector(..., config="english")`, persisted, with `GinIndex` on each —
  [`mind/models.py:81`](../src/mind/models.py) and
  [`mind/models.py:142`](../src/mind/models.py).
- [`mind/queries.py:78`](../src/mind/queries.py) `search_ranked` ranks by the
  better of the two vectors, `Max` over the revision join collapsing the
  multi-row match.
- [`mind/views.py:474`](../src/mind/views.py) serves `/mind/search/`, counts
  before slicing, and labels a result that matched only in superseded text.
- `RetrievalMiss` ([`mind/models.py:950`](../src/mind/models.py)) records where
  the person's memory beat the index — with `MissContext` already
  distinguishing `search` from `capture`.

**The task core has none.** Zero hits for `SearchVector`, `GinIndex` or
`pg_trgm` across `lists`, `daily`, `review`, `routines` and `accounts`.

**A correction this brief owes `roadmap.md`.** That file's Track D entry says
there is *"no full-text search anywhere in the product — zero hits for
`SearchVector`, `GinIndex` or `pg_trgm`."* That was true when written on August
13 and stopped being true on the 14th, when the merger brought `src/mind/` into
this tree. The substance survives — a daily journal entry is unfindable by any
means — but the evidence sentence is now false and should be narrowed to the
task core. `roadmap.md` owns that fact; this file does not restate it.

## What this inherits rather than rediscovers

The knowledge core paid for two lessons that this work would otherwise pay for
again. Both are recorded at the code and are repeated here only as *inherit
this*, not as a second copy of the reasoning:

- **`GinIndex`, never `models.Index`.** The comment at
  [`mind/models.py:113`](../src/mind/models.py) is emphatic and expensive: a
  btree on a tsvector cannot serve `@@` at all, and its 2704-byte entry cap
  means **a note with a few hundred distinct lexemes fails to insert.** A
  400-word journal entry could not be saved. That is a write-path outage on
  exactly the material being indexed.
- **The two-argument `to_tsvector`.** Immutable, so it is legal in a generated
  column; the one-argument form is merely stable and is rejected.

Generated columns rather than a worker-maintained index, for the reason
`mind/models.py:78` gives: an index that cannot drift is worth more than one
that is cheaper to write.

## Scope — what gets indexed

**Slice 1 indexes what the trigger actually names**, and nothing else:

| Model | Fields |
|---|---|
| `lists.Item` | `text`, `notes` |
| `daily.DailyEntry` | `intentions`, `gratitude`, `happenings` |

**Deliberately not in slice 1**, listed so the omission is a decision rather
than an oversight: `Project.purpose` and `desired_outcome`, `WeeklyReview.
reflections` and `plan`, `WeeklyIntention.text`, `WeeklyOutcome.text`,
`ChecklistStep.text`, `RecurringCommitment.text` and `notes`, `List.title`,
`Routine.title`. Each is real text a person wrote and each deserves indexing
eventually. They wait because slice 1's job is to prove the mechanism against
the material the trigger fired on, and a nine-model migration proves the same
thing more slowly and with more to revert.

**No new model.** Search results are derived, and
[`architecture-trajectory.md`](architecture-trajectory.md) §4's test — *a
concept earns its own model when it has a different life cycle, not when it has
a different name* — is not met by a result list. Charter rule 1 still binds
every query: filtered by owner, always, the way `live_nodes(owner)` already
does.

## The hard part: ranking across two cores

`SearchRank` produces a number that is meaningful *within* one document set and
is not comparable across two. Ranking an `Item` against a `Node` by putting
their ranks in one `ORDER BY` invents a comparison the data does not support,
and the failure is silent — a plausible-looking list, ordered by nothing.

**Recommendation: sectioned results, ranked within each section.** Notes,
Tasks, Journal — each ordered by its own rank, each with its own honest count.
The person scans three short lists instead of one long one, and no number is
invented. It also degrades correctly: a section with no index yet simply is not
there, which is what makes the increments below shippable one at a time.

**Rejected: one merged list with normalized ranks.** It requires a weighting
nobody can validate, and validating it would need exactly the retrieval
evidence that does not exist yet. If `RetrievalMiss` ever accumulates enough to
say which core a person meant, that is the moment to revisit — not before.

## Increments, in order

1. **Index the task core's own material.** Generated columns and `GinIndex` on
   `Item` and `DailyEntry`, one migration, plus the per-user isolation tests
   the charter's rule 1 asks for. Nothing user-visible ships; the failing test
   is a query returning a row it should not yet find.
2. **A ranked read.** The task core's equivalent of `search_ranked`, in a reads
   module rather than a service — charter rule 4, and `agenda.py` is the
   precedent. Query-only, no mutation, no view yet.
3. **One surface, sectioned.** The three lists, counted before slicing the way
   `mind/views.py` already does. This is the first increment a person can use.
4. ~~**The miss button, on the unified surface.**~~ **Done August 20, 2026**,
   and not as written. The button needed no change; what needed one was what a
   miss *means* once three sections sit above it. See D3, which turned out to
   be a signal-integrity fix rather than a schema decision.
5. **The wider field set** — the nine deferred above, once the mechanism has
   been used against real material for long enough to say the sections are the
   right sections.

Increments 1 and 2 are invisible and low-risk; 3 is where this becomes a
feature. **Nothing here needs staging**, and nothing here generates anything.

## Open decisions — Vince's, not this document's

1. ~~**D1. Where does the endpoint live?**~~ **Answered August 20, 2026:
   `mind/api_v1.py`, beside capture.** Vince's call. `CLAUDE.md`'s rule holds
   rather than bending — one API, and a knowledge-core router carries it — and
   `clarice/` does not grow its first router, which was the alternative and the
   larger precedent. What the rule did not anticipate is still true and is
   recorded here rather than smoothed over: **search belongs to neither core**,
   and it reads `Item`, `DailyEntry` and `Node`. The next thing shaped like
   this gets the same question, and `clarice/search.py` — which does hold a
   rule for both cores — is where it will be asked again.
2. ~~**D2. Which surface?**~~ **Answered August 20, 2026: the existing
   `/mind/search/` page.** Vince's call, and the cheapest of the three. It puts
   task and journal search under a prefix naming the smaller half, which is the
   `/capture/` shape again and is accepted for the same reason it was there:
   the prefix lives in one line of `clarice/urls.py` and everything under it is
   relative, so this is settled rather than welded. **What it buys is the miss
   button** — an SPA route would have split search from the only instrument
   this project has for judging whether search works.
3. ~~**D3. Does `RetrievalMiss` widen to cover both cores?**~~ **Answered
   August 20, 2026 — and it was the wrong question, which is the useful part.**

   **`resolved_node` should not widen, because nothing has ever populated it.**
   `services.resolve_retrieval_miss` is its only writer, has no caller outside
   its own tests, and no reader anywhere. This decision was framed around
   widening a seam that was never switched on — the fourth instance of that
   shape in a fortnight, after `/healthz`, the uninvoked detectors and
   `Backends.isSplit`. **The check is cheap and was not done here until it was
   asked for directly**; `CLAUDE.md` already says to check the build
   configuration rather than the branch, and this generalises it to *check for a
   caller rather than a field*.

   **The real problem was one increment 3 created**, and it is fixed rather than
   decided. `retrieval_miss_trend` counted every miss an owner had, which was
   exact while this page searched only notes — every miss was a note-retrieval
   failure by construction. Three sections made a bare miss ambiguous, and it
   feeds the retirement gate's *"retrieval misses fall"*, the one condition its
   own comment calls measurable without interpretation.

   So a miss now records what each section returned (`notes_found`,
   `tasks_found`, `days_found`, recomputed server-side rather than posted by the
   form), and the gate counts the ones where the note index returned nothing —
   the form the embeddings question actually takes. **The rule is narrower than
   it was, and the code says so**: a fall across August 20 is a changed
   denominator before it is an improvement. Misses where notes did return
   results are kept in full and excluded from that gate, because they are the
   only evidence available about whether task and journal search fail anybody.

   **Fixed before the deploy, deliberately.** A miss cannot be re-interpreted
   afterwards; had this shipped first, every miss recorded in the gap would be
   permanently ambiguous.
4. ~~**D4. Does this promote the command palette?**~~ **Answered August 20,
   2026: no.** Vince's call.

   **A cleared precondition is not a trigger.** The candidate's blocker was that
   search "earns retrieval work first"; search shipping removes an *objection*
   and supplies no demand. Track D's own standard is that a candidate with no
   trigger is a candidate nobody wants yet — and this file has already paid for
   the other answer once, in the Reference/Idea search entry that was
   *anticipated, never observed*.

   **And building it now would cost the instrument D2 just protected.** A
   `Ctrl+K` palette lives in the SPA; search lives at `/mind/search/` with the
   miss button, which is exactly why D2 chose that surface. A palette that
   became the primary retrieval path would route people away from the only
   signal that judges whether search works.

   **What the question was really pointing at, and it is fixed.** Search shipped
   and *nothing in the task core linked to it* — four navigation surfaces
   checked, and only the knowledge core's own sub-nav had it. Reaching search
   from the task core meant opening the other core's capture page and using its
   sub-nav: two hops, for a feature built partly to search tasks. One link in
   the shared app bar, in the utility group rather than the Cores nav, because
   search belongs to neither core.

   **The trigger that would promote the palette**, named so nobody waits on the
   wrong signal: friction in *reaching or repeating* a search, now that one is a
   click away from both cores. **`RetrievalMiss` cannot supply it** — it
   measures whether search succeeded, not how long it took to ask — so watching
   the miss count for this would be waiting for a signal that cannot arrive.

   **This fires on felt friction, and that is deliberate rather than vague.**
   `principles.md` gained two rules the same day this was decided: *a trigger
   that cannot fire is a refusal, and should be recorded as one*, and *felt
   friction is evidence*. Nothing instruments how long it takes to open a search
   box and nothing should be built to — so if this trigger required a
   measurement, it could not fire and this entry would be a deferral pretending
   to be one. Vince noticing that he is going the long way round is the
   evidence, and it is admissible.

## What this refuses

- **Semantic or vector search in this work.** `SentenceEmbedding` and pgvector
  exist in the knowledge core; this is lexical search and is scoped that way
  deliberately. `RetrievalMiss` is the instrument that would argue for more,
  and it argues from evidence rather than from ambition.
- **Search over another person's material.** Not a feature to defer — a thing
  this does not do.
- **A second index mechanism.** Whatever the knowledge core does, this does,
  for the reason `principles.md` gives as *one rule, one authoritative
  definition*.

## Where the facts live

[`roadmap.md`](roadmap.md) owns whether this is active or deferred, and owns
the Track D entry this brief asks it to correct.
[`product-stories.md`](product-stories.md) owns the score, and S13 is the
journey this bears on — quoted nowhere, here included.
[`architecture-trajectory.md`](architecture-trajectory.md) §4 owns the charter.
When this ships, it becomes a stub and its narrative moves to
[`roadmap-history.md`](roadmap-history.md).
