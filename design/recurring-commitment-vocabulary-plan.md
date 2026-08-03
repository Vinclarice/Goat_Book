# The recurring commitment becomes a real template

Vince · brief · written August 3, 2026

## 1. What this finishes

`crane-plan.md` §3 split the recurring-commitment work in two. The **identity
half** shipped as Crane 0a: `RecurringCommitment` holds an owner and a
lifespan, `Item.commitment` points at it, and `_spawn_next_occurrence` writes
the link, so occurrence five of "Pay rent" is knowably the same commitment as
occurrence four. The **vocabulary half** — described there as moving `text`,
`list`, `cadence`, tags and notes off each occurrence and onto the template —
was deferred to release D because "a commitment template has to say what a
subtask template is, and D is where what a subtask *is* gets decided."

D decided it: a subtask is a Checklist Step. Dunlin shipped that, and this is
the last item Crane deferred and Dunlin did not pick up. `release-d-plan.md`
§7 left it explicitly un-sliced, saying it belonged in "its own follow-up
brief once §2 has actually shipped." This is that brief.

## 2. The spec contradicts itself, and this is the resolution

**§3 says the vocabulary half moves `text` onto the template.** §3's own
acceptance example says the opposite:

> "Pay rent" is monthly. It is completed in June, July and August; in
> September its title is edited to "Pay rent — new landlord" and completed
> again. A query for the series returns four occurrences in order, **the
> September one carrying the new text and the earlier three carrying the
> old.**

Both cannot hold. If `text` lives only on the template, the query returns
four rows all reading "Pay rent — new landlord", and the history of what the
commitment was called in June is gone — which is the exact failure
`principles.md`'s durable-records rule exists to prevent.

**The resolution is already in this project, twice over.** Charter rule 3
says a record snapshots whatever its meaning depends on; charter rule 8 says
a template holds *the rule* and dated occurrences hold *what happened*. And
`Routine`/`RoutineOccurrence` already ships exactly this: the routine holds
`target_quantity`, and each occurrence copies it at creation so that changing
a target from five to three does not rewrite last month's "4 of 5".

So the vocabulary half is not a move. **It is a template plus a snapshot:**

- `RecurringCommitment` gains the fields that decide **what the next
  occurrence starts as** — the rule.
- `Item` keeps its own `text`, `list`, `notes`, tags and due date as the
  record of **what that occurrence actually ran under** — the snapshot.

That is not the two-sources-of-truth drift §3 warned against. Drift is two
places claiming to answer the same question. Here they answer different
questions: the template answers "what will the next one be", the occurrence
answers "what was this one". `RoutineOccurrence.target_quantity` is the same
pair and has never been called drift.

**§3's phrasing was written before the pattern had shipped.** It described
the destination as a move because at the time `RecurringCommitment` was a
sketch and `Routine` was a brief. Rule 8's convention is now a real migration
in this repository, and applying it produces the template-plus-snapshot shape
rather than the move. Recorded here rather than silently corrected, because
§3's acceptance example is the better statement of intent and it is what this
brief satisfies.

## 3. What actually moves

Exactly one field genuinely leaves the occurrence:

**`cadence`.** Today `Item.recurrence` is on every task, and on a linked one
it is the rule rather than a fact about that occurrence. It belongs on the
template. A commitment is weekly; an occurrence is not weekly, it is one
instance of a weekly thing. This is also what closes §3's stated complaint
that "change its cadence and nothing records that it was ever weekly" —
once cadence is on the template, changing it is a change to one row with a
history, not a silent edit spread across a chain.

Everything else — `text`, `list`, `notes`, tags — gains a template copy that
seeds the next occurrence, and keeps its per-occurrence copy as the snapshot.

`due_date` does not move and does not seed: it is computed per occurrence by
`_advance_due_date`, which is already the correct behaviour.

Checklist Steps do not move either. `carries_forward` already answers "does
this step come back", and `_spawn_next_occurrence` already clones the flagged
ones onto the next occurrence. A step template would be a second mechanism
for a question the model answers.

## 4. The question this brief cannot answer

**When someone edits a recurring task's title, what did they mean?**

Today there is one answer because there is one place to write: `Item.text`.
Once a template exists there are two, and they are both reasonable:

- **This occurrence only** — the September instance is called something
  different; the commitment is unchanged and October reverts.
- **This and every future one** — the commitment has been renamed; September
  and everything after it carry the new name, June to August keep the old.

§3's acceptance example implies the second (September's edit persists into
the series going forward). But it is stated as a query result, not as an
interface decision, and it never says what happens in October.

This is not a detail that can be settled while implementing. It decides
whether `edit_item` writes to one row or two, whether the interface needs a
choice at the point of editing, and whether the migration can be additive.
Every calendar application that has faced this question answers it with a
prompt, which is a real interface addition rather than a field.

**Recommendation: "this and future", with no prompt, for now.** It matches
§3's example, it is what renaming a commitment almost always means, and it is
the reversible choice — adding a prompt later is additive, while teaching
people that edits are per-occurrence and then changing it is not. State it in
the interface ("Renaming this renames the commitment") rather than asking.

## 5. Proposed slices

Written on the recommendation above; slice 1 is independent of it.

1. **Expand — the template gains its fields — done, August 3, 2026.**
   `RecurringCommitment` grew `text`, `list`, `cadence`, `notes` and a tag
   relation, all optional, in `0031_commitment_template`, whose backfill
   seeds each existing commitment from its most recent occurrence and prints
   `seeded=` / `empty=`. Nothing reads them: `_spawn_next_occurrence` still
   copies from the completed item, and a test asserts that rather than
   claiming it, so an empty template cannot empty a task. Six new tests, full
   required suite green at 778, frontend at 225, and `openapi.json` did not
   move — which is what an inert expand step should look like.

   **`Recurrence` moved to module level** so `RecurringCommitment`, declared
   above `Item`, can share the choices. `Item.Recurrence` remains an alias, so
   no call site changed.

   **The newest occurrence is the seed**, because the template says what the
   *next* one starts as and the newest occurrence is what the commitment
   currently is. Earlier occurrences are untouched, which is what makes §2's
   acceptance example possible.

   **One thing this cost, worth recording.** The new migration test broke two
   existing ones by ordering: a target naming only `lists` let the next test
   ask for a plan running `lists` backwards and `capture` forwards, which
   Django refuses outright. Every migration test in this app now names both
   apps, and the reason is in a comment rather than in someone's memory.
2. **`_spawn_next_occurrence` reads the template.** The next occurrence is
   built from the commitment rather than copied from the completed item.
   Observable acceptance: rename a commitment's template row directly in the
   shell, complete the current occurrence, and the new one carries the new
   name while the completed one keeps the old — §3's acceptance example,
   executed.
3. **Editing a linked task writes through to the template.** `edit_item`,
   `set_item_notes`, `set_item_tags` and the list move update both the
   occurrence and its commitment when one exists. The interface says so.
4. **Cadence moves.** `set_recurrence` writes `commitment.cadence`;
   `Item.recurrence` becomes a snapshot written at spawn, and the API
   exposes the commitment's cadence as the editable one. This is the slice
   with a real contract change in it.
5. **Contract — retire what is now duplicated.** Only whatever step 4 leaves
   genuinely dead, and only once nothing reads it, per the expand/migrate/
   contract discipline Dunlin used for `Item.parent`.

## 6. What this does not touch

Routines and their occurrences, which are the sibling of this pattern and
already correct. Projects. Anything in `ui-second-pass-plan.md`, which is
blocked on its own evidence. And `Item.recurrence` stays on unlinked tasks —
a non-recurring task has no commitment and needs no template.

## 7. Is this worth doing now?

**Stated honestly, because the answer is not obviously yes.** The identity
half bought answerable history and shipped for a reason with a clock behind
it. This half buys model cleanliness — §3 says so itself: "That buys model
cleanliness rather than answerable history."

What has changed since that assessment is small: the blocker is gone, and
Dunlin proved the expand/migrate/contract pattern twice. What has not changed
is the demand. No feature is waiting on it, no metric is wrong without it,
and the series query Crane 3's review needs already works.

**The case for doing it anyway** is that `Item.recurrence` on a linked
occurrence is a field whose meaning is now wrong — it describes the series,
not the row it sits on — and every future feature that reads it inherits that
confusion. That is the same class of problem the parent–child redesign
existed to fix, caught earlier.

**The case for waiting** is that Clarice has three users and two recurring
commitments in production, and `ui-second-pass-plan.md` §6 is waiting on one
sitting with a real project. Doing that sitting first costs an evening and
might reorder everything after it.
