# Three languages, one rule: what to move and what to leave

Vince · brief · written August 18, 2026 · **for the redesign, not for now**

## 1. What is mirrored

Eight rules are hand-ported across Python, TypeScript and Kotlin, each declaring
itself a mirror in a comment and none of them checked by anything.

| Rule | Python | TypeScript | Kotlin |
|---|---|---|---|
| `bucket_for` | `lists/reads.py` | `agenda.ts` | `AgendaFormatting.kt` |
| `WEEK_HORIZON_DAYS` | `lists/agenda.py` | `agenda.ts` | `AgendaFormatting.kt` |
| `next_weekday`, `snooze_presets` | `lists/agenda.py` | `agenda.ts` | — |
| `AGE_WORTH_MENTIONING`, `ageLabel` | — | `agenda.ts` | `DailyFormatting.kt` |
| `dueLabel` | — | `agenda.ts` | `AgendaScreen.kt` |
| `standingLabel` | — | `DayRoute.tsx` | `DailyFormatting.kt` |

## 2. The divergence is demonstrated, not theoretical

Raise `WEEK_HORIZON_DAYS` to 14 in Python and TypeScript, leave Kotlin at 7, and
run everything:

```
python      594 tests  OK
typescript   34 passed
kotlin      311 tests, 0 failures, 0 errors
```

Fully green, with the digest and the web calling a task due in ten days *this
week* while the phone calls it *later*. The reason is that the Python and
TypeScript horizon tests each compute the expected edge from **their own**
constant, so neither can ever disagree with itself; Kotlin pins real dates, but
only its own.

**And one copy has already diverged, in production.** Same date, same task:

```
web  (Intl, en-US)         "Sat, Aug 15"
phone("EEE d MMM", any)    "Sat 15 Aug"
```

## 3. The finding that changes the shape of the answer

**The server already owns `bucket_for`.** Four live call sites — `daily/reads.py`,
`agenda.py`'s grouping, and three in `send_due_digest`. `BucketKey` is already in
the API contract. `AgendaOut` already ships `buckets` and `today`.

What it does not ship is *which bucket each item is in*. Both clients receive a
flat `items` list and re-derive an answer the server has already computed.
`AgendaModels.kt` says so outright, and gives as its reason only that the
server's `buckets` labels were out of scope for Android slice 2.

That is not an architecture. It is a payload gap.

**Two objections that do not survive checking.** Freshness: clients bucket
against the server's `today` from the payload, not their own clock
(`AgendaWorkspace.tsx:155`, and Kotlin's `bucketFor` takes it as a parameter) —
so moving the computation changes nothing about staleness. Offline: the agenda is
online-only on the phone; the offline queue is capture-only.

The one genuine cost is optimistic re-bucketing after a local edit — and
`changeDueDate` already awaits the server today, so nothing optimistic is lost.

## 4. The split to design toward

The current mirror conflates three different kinds of rule. Naming them is most
of the work.

**Domain rules — one authority, on the server.** `bucket_for`,
`WEEK_HORIZON_DAYS`. What counts as "this week" is a fact about the product, not
a rendering choice. These are exactly the rules whose divergence §2
demonstrates, and they are the ones that can be *deleted* from two languages
rather than guarded in three.

**Shared vocabulary — one wording, rendered per platform.** "Tomorrow", "3 days
overdue", `standingLabel`. Server-sent strings would unify them at the cost of
localisation and platform idiom. Worth deciding deliberately; the answer is not
obvious and this brief does not pick one.

**Presentation — should differ, on purpose.** Date formatting. A phone *should*
use platform conventions. The problem is not that `Intl` and `"EEE d MMM"`
differ; it is that nobody chose it, so nobody can tell an intended difference
from a drift.

## 5. What moving `bucket_for` would actually take

One field. `bucket: BucketKey` on `TaskOut`, populated from the `bucket_for` that
already runs. Then `bucketFor` and `WEEK_HORIZON_DAYS` delete from `agenda.ts`
and `AgendaFormatting.kt`, and their tests with them.

Order, so nothing is green for the wrong reason at any point:

1. Add the field, serve it, regenerate the contract. Clients ignore it.
2. Switch the SPA to read it; delete `bucketFor` from `agenda.ts`.
3. Switch Android; delete `bucketFor` from `AgendaFormatting.kt`.
4. Delete `WEEK_HORIZON_DAYS` from both clients, and the rows for it from the
   contract test in §6.

Steps 2 and 3 are independent and each is revertible on its own.

`next_weekday` and `snooze_presets` are input affordances rather than readings —
they answer "what dates may I pick", which the client needs before it has asked
the server anything. They stay client-side, and stay mirrored, which is why §6
outlives §5.

## 6. What the contract test does and does not do

`lists/tests/test_mirrored_business_rules.py` reads all three languages and fails
when a mirrored *constant* disagrees. It closes §2's demonstrated hole today,
costs nothing, and is worth having whatever this brief's conclusions turn into.

**It does not catch behavioural drift** — three implementations can hold the same
constant and disagree about a boundary. The thorough answer to that is a shared
fixture table of input-to-expected cases read by all three suites, which is a
larger build and is only worth it if the mirror keeps growing. §4's first
category shrinking to zero would be worth more than any test of it.

## 7. Refusals this brief does not overturn

`architecture-trajectory.md` §7 defers **a local-first sync programme before a
client needs one**, on the grounds that the programme waits for a second client.
Nothing here proposes one. Serving a computed field is the opposite move: it puts
*less* logic on the clients, not more.

Nothing in §7 refuses server-computed presentation fields, and this brief is not
an amendment to it.
