# Clarice — journey stories for the two-year product

Vince · written August 12, 2026 · the target these stories describe is the
two-year product, not the next release

**The "current product" half of every verdict below is a snapshot of August 12
and has moved since.** Heron deleted `Capture` and `Idea` on August 15 and put
every thought in the knowledge core's graph, so verdicts reasoning about
`Idea`'s eight fields or the Inbox's triage flow are describing a product that
no longer exists — including §"Verdict: impossible" at the `Idea` search story,
and the line predicting that `Idea` "does not survive", which has now happened.
The **target** half is unaffected, which is the half this document is for.
Re-running the stories against the current product is worth doing once step 5
lands rather than piecemeal now.

## What this is for

[`commercial-blueprint.md`](commercial-blueprint.md) audits what Clarice is.
This describes what it is *for*, as behaviour, so the architecture question —
reshape in place or rebuild — can be priced against a specific destination
instead of a feeling.

Each story is written against the **target** product and then run against the
**current** one, with one of three verdicts:

- **Works** — a real user could do this today.
- **Bends** — possible, but the product fights them.
- **Impossible** — no path exists at any cost short of new code.

The *impossible* pile is the argument. The "requires" line under each story is
what it costs, and those lines added together are the target model.

Stories are journeys through the three loops rather than atomic feature cards,
because this product's failures live in the seams between features, and only a
journey crosses a seam.

## The three loops

| Loop | Tempo | The question it answers |
|---|---|---|
| **Do** | daily | What am I committing to today, and what actually happened? |
| **Adjust** | weekly | Did my intentions and my life match? |
| **Decide** | project / quarterly | What am I pursuing, why, and what did it teach me? |

The second brain is not a fourth loop. It is the **memory of the third one**.

## Personas

These are design personas, not descriptions of the real people using Clarice.

- **Vince** — the builder. Two years of history, the deepest archive, uses
  every surface, plans at quarter scale.
- **Priya** — invited by Vince, not technical, mostly on a phone, cares about
  routines and the daily page, will never read documentation.
- **Sam** — a stranger. Arrives from a link, has used Todoist for six years,
  curious and impatient. Will give the product about four minutes.

---

## Loop 1 — Do

### S1. Sam's first four minutes

> Sam follows a link, reads what Clarice is, makes an account, and is doing
> something real before he decides whether to stay.

```
Given a stranger with no account
When he signs up
Then he reaches a usable workspace without waiting for a human
And the first screen offers one obvious thing to do, not six concepts
And within four minutes he has captured a thought and planned a day
```

**Verdict: impossible.** `src/accounts/forms.py:77` creates the account
`is_active=False`; approval is a checkbox at `src/accounts/admin.py:25`; and
`src/accounts/emails.py` has three functions, none of which tells him he was
approved. Even past that gate, `LOGIN_REDIRECT_URL` lands him on `/app/day`,
which has no affordance that creates anything.

**Requires:** self-service signup with email verification, a first-run path, an
empty state that teaches, and a landing page that is not a login form.

### S2. Priya's morning, on a phone

> Priya wakes, reads what today asks of her, ticks off the thing she did before
> breakfast, and moves one task to tomorrow — all on her phone, in bed.

```
Given a day with pinned commitments and two routines
When she opens Clarice on a phone
Then she can complete a task from the day surface itself
And reschedule another without leaving it
And every control is large enough to hit with a thumb
```

**Verdict: bends.** Android does agenda read/write, but the Day page's action
items are read-only *by design* (`DayRoute.tsx:117`) — completing a task means
navigating away. On mobile web, `button.tsx` tops out at 36px and `DayRoute`
carries none of the per-call-site 44px overrides.

**Requires:** complete/add from the day surface; a 44px floor in the primitive;
a decided client strategy so "on a phone" has one answer.

### S3. Vince plans a Tuesday he can actually survive

> Vince pins five things to Tuesday. Four hours are already committed. He wants
> to know he is lying to himself on Monday, not at Friday's review.

```
Given tasks carrying effort estimates and a day with declared free time
When the pinned total exceeds what the day can hold
Then the day says so while he is still planning
And the weekly review can separate "over-committed" from "under-delivered"
```

**Verdict: impossible.** No effort field, no capacity concept.

**Requires:** `Item.effort`, a per-day capacity, and a planning-time signal.
This is the sharpest test of appetite in the whole set — if estimates would go
unentered, this story dies and takes the capacity model with it.

### S4. Priya captures a thought in a supermarket queue

> A thought arrives. She writes it down in four seconds and forgets it, trusting
> it will be waiting.

```
Given a phone with no signal
When she captures a thought and closes the app
Then the text survives force-stop, reboot and a dead network
And it arrives exactly once when signal returns
And it is waiting in her inbox, undecided
```

**Verdict: works.** The best-built thing in the product — durable before the
network is asked anything, stable idempotency key, owner-scoped uniqueness
constraint behind it.

**Requires:** nothing. Two caveats already logged in the blueprint: the queue
has no lock, and it is not excluded from device backup.

### S5. Vince closes the day

> At the end of the day Vince records what actually happened, while it is still
> true, and the record is worth reading in six months.

```
Given a day with commitments met, missed and set aside
When he writes what happened
Then the record keeps what he chose that morning, not just what he finished
And something prompts him to close the day at all
```

**Verdict: bends.** `DailyEntry.happenings` exists and `DailyFocus` preserves
the morning's choice honestly — genuinely good. But nothing ever asks him to
write it: no evening surface, no prompt, no reminder.

**Requires:** a closing ritual with a time-aware nudge.

---

## Loop 2 — Adjust

### S6. Friday, and the numbers are honest

> Vince reads back the week. The finish rate divides by what he actually
> committed to, and deliberate decommitments do not read as failures.

```
Given a week of pins, completions, routines and decommitments
When he opens the review
Then the finish rate divides by planned commitments, not the backlog
And a set-aside pin is shown as a decision, not a miss
And a paused routine does not count against him
```

**Verdict: works, and it is the product's moat.** `DailyFocus` snapshots
`task_text` at selection, `released_at` distinguishes decommitment, and
`WeeklyReview` stamps the concluded figure. Competitors cannot report this
because they never stored the denominator.

**Requires:** nothing. Protect it from every future change.

### S7. Priya acts on what the review just told her

> The review says four captures have been waiting eleven days. She wants to deal
> with them now, not remember to later.

```
Given a review showing an ageing inbox
When she decides what those captures are
Then she triages them without leaving the review
And the numbers update in place
```

**Verdict: impossible.** `ReviewRoute.tsx:352` renders each item as inert
`<span>` text. The review already runs the query and then refuses to let anyone
act on it — and `src/review/` has a structural test asserting the router stays
read-only, so this is a designed boundary, not an oversight.

**Requires:** a decision about whether the review may mutate. The read-only rule
is *why* the numbers are trustworthy; breaking it casually would be a mistake.
The likely resolution is triage-in-place that writes through capture's own
services, leaving review itself still read-only.

### S8. Vince zooms out to a quarter

> Three months in, Vince wants to know whether the shape of his life matched
> what he said it would be.

```
Given twelve weeks of reviews and routine history
When he opens a quarter
Then the same honest denominators aggregate at that scale
And weeks with no data read as absent, not as zero
```

**Verdict: impossible.** `WeeklyReview` is the only review model;
`TREND_WEEKS = 5`.

**Requires:** longer-horizon reviews reusing the weekly model. The
null-not-zero discipline already exists in `review/reads.py` and must carry up.

### S9. Priya plans a week, not just a day

> On Sunday she decides what the week is about. On Wednesday the day knows.

```
Given a stated intention for the week
When she plans Wednesday
Then the day shows what the week was for
And the review can ask whether the week's days served the week's intention
```

**Verdict: impossible.** Planning exists only at day scale — which is a hole in
a product whose pitch is "design the future."

**Requires:** intentions above the day, snapshotted the same way `DailyFocus`
snapshots a commitment.

---

## Loop 3 — Decide

### S10. Vince starts a project and records why

> He commits to a piece of work and writes down what he is trying to achieve and
> what would tell him it went wrong.

```
Given a new project
When he states its purpose and what would make him abandon it
Then that reasoning lives with the project
And is still there when he is deciding whether to continue
```

**Verdict: impossible.** `Project` is `owner/title/due_date/is_completed/
completed_at/created_at` — there is no description field at all.

**Requires:** projects as workspaces with purpose, notes and an abandonment
condition.

### S11. A decision comes back

> Six weeks ago he chose one approach over another and wrote down what would
> make him revisit. Something happens that touches the reason.

```
Given a recorded decision with a reconsideration trigger
When the condition it named occurs
Then he can reach the decision from the work that provoked it
And see what he considered at the time, not only what he chose
And decisions past their trigger surface without being hunted for
```

**Verdict: impossible.** No concept exists.

**Requires:** `Decision` as a first-class record. Note this story is not
hypothetical — `architecture-trajectory.md` §7 and §8 are exactly this practice,
done in Markdown because the product cannot hold it.

### S12. The project ends and explains itself

> A project completes. Vince wants a retrospective he did not have to write from
> memory.

```
Given a completed project with eleven weeks of history
When he closes it
Then he sees what was planned versus met across its life
And what he deliberately set aside
And the notes and decisions made along the way
And he adds what he would do differently, kept for next time
```

**Verdict: impossible.** `src/review/` imports nothing from projects; completing
a project touches no tasks and produces no record.

**Requires:** project-scoped aggregation over existing data, plus the link
between projects and knowledge records. **This is the story that makes the two
cores one product** — it is impossible without both halves.

---

## The second brain

### S13. Sam looks for something he wrote

> Eleven weeks ago Sam wrote something about a supplier. He remembers three
> words of it.

```
Given three words that appeared somewhere
When he searches
Then results span tasks, notes, sources, captures, days and reviews
And are ranked, not merely filtered
And he can reach the day it was written and see what else was happening
```

**Verdict: impossible.** There is no full-text search anywhere — verified, zero
hits for `SearchVector`/`GinIndex`/`pg_trgm`. Ideas offer `text__icontains`;
three other boxes are `Array.includes()` over data already in the browser; daily
entries are not searchable by any means, and no date picker exists.

**Requires:** ranked cross-content search. Nothing else in the knowledge core
matters until this exists — it is what makes retention worth anything.

### S14. A note knows when it was written

> Priya writes a note during a hard week. A year later it is still legible,
> because it remembers what was happening around it.

```
Given a note written on a particular day
When she reads it much later
Then it carries the day it belongs to, the project it was inside,
    and what she had committed to that week
And she reached it without having filed it anywhere by hand
```

**Verdict: impossible.** `Idea` has eight fields, no `updated_at`, no link to a
day, project or task.

**Requires:** `Note` with typed links into domain objects. **This is the
differentiator** — the graph accretes from what you were already doing instead
of being built by hand, which is the one thing Obsidian and Notion structurally
cannot do.

### S15. Reading produces work

> Sam reads an article. Two ideas and one task come out of it, and six months
> later he can still tell where they came from.

```
Given an external source
When he takes notes and one becomes a task
Then the task remembers the source it came from
And the source shows everything that grew out of it
```

**Verdict: impossible.** No `Source` concept; and provenance is one-way —
`promoted_task` uses `related_name="+"`, so from a task you cannot find its
origin.

**Requires:** `Source`, and backlinks. The backlink half is nearly free — four
`related_name` renames.

### S16. The past arrives when it is useful

> Vince starts a project on a topic he worked on eighteen months ago. Without
> asking, Clarice offers what he learned last time.

```
Given a new project tagged with a topic
When he opens it
Then notes, decisions and sources from previous work on that topic appear
And each says why it surfaced
And nothing is changed on his behalf
```

**Verdict: impossible**, and correctly deferred until there is material to
resurface.

**Requires:** S13 and S14 first. This is the story that makes a second brain
feel like one, and it is worthless before the corpus exists.

### S17. Priya leaves

> Priya decides to stop. She takes everything and closes the account.

```
Given two years of tasks, notes, days and reviews
When she asks for her data
Then she receives all of it in a readable format
And can delete the account herself
And is told plainly what happens to the copy
```

**Verdict: impossible.** No export, no deletion, no self-service deactivation.

**Requires:** export and deletion. A legal obligation before payment, and for a
second brain a trust precondition — a private archive with no exit is not one.

---

## Cross-cutting

### S18. Sam brings six years of Todoist with him

```
Given an export from another product
When he imports it
Then his projects, tasks, due dates and completion history arrive intact
And he is told what could not be carried across
```

**Verdict: impossible.** No import of any kind. This is the switching cost that
decides whether an experienced user ever becomes a real one.

### S19. Sam decides to pay

```
Given a trial that has shown him the weekly review at least twice
When he subscribes
Then his limits change without his data moving
And cancelling leaves him able to read and export
```

**Verdict: impossible.** No billing, plan, entitlement or trial concept.

---

## What the stories add up to

**19 stories: 2 work, 2 bend, 15 impossible.** The two that work — durable
capture and the honest weekly review — are the two the product should be sold
on, and neither needs changing.

The impossible pile resolves into a target model:

**Knowledge**
- `Note` — title, body (rich, versioned), `updated_at`, kind, tags *(S13, S14)*
- `Source` — external material with provenance *(S15)*
- `Decision` — choice, alternatives considered, reconsideration trigger *(S11)*
- `Link` — typed, polymorphic, spanning knowledge **and** domain objects
  *(S12, S14, S15, S16)*
- Search index across every text-bearing model *(S13)*
- `Idea` does not survive; it becomes `Note` plus `Source` plus `Decision`

**Productivity**
- `Item.owner` direct; `Item.list` nullable *(S1, S15 — a task must be able to
  exist without an Area)*
- `Item.effort` and per-day capacity *(S3)*
- Deferral distinct from `due_date`, so snooze stops erasing the commitment
- A someday state, so non-committed work stops masquerading as an Idea
- `Project` as a workspace: purpose, notes, abandonment condition,
  retrospective *(S10, S12)*
- Intentions above the day; reviews above the week *(S8, S9)*

**Substrate**
- Self-service signup, first-run, onboarding *(S1)*
- Export and deletion *(S17)*
- Import *(S18)*
- Plans and entitlements *(S19)*

**The load-bearing finding:** S1, S15 and the someday state each independently
require a task that can exist without an Area. The list-spine has to go for
product reasons, not only for the scaling reasons the blueprint gives. That is
now the most-supported single change in either document.

## What these stories do not settle

- **S3 (capacity)** rests entirely on whether estimates would actually be
  entered. Untested, and the model should not be built until it is.
- **S7** asks whether the review may ever mutate. The read-only rule is why its
  numbers are trustworthy; the answer is probably triage-in-place through
  capture's services, but it is a real decision.
- **S11 (`Decision`)** may be over-fitted to how this project documents itself
  rather than to how anyone else works. It is the story most in need of a second
  opinion.
- Nothing here is validated with a user who is not already invested. Fifteen
  impossible stories written by the person who would build them is a hypothesis,
  not evidence.
