# Clarice — journey stories for the two-year product

Vince · the target these stories describe is the two-year product, not the next
release. Written August 12, 2026; **score re-checked August 16, 2026.**
**Two verdicts corrected August 18** — S13's cited the absence of ranking that
now exists, and S17's had scored an export that was silently dropping data. The
table itself is unchanged: both still land where they did, for different
reasons. This was not a re-score, and the other seventeen were not re-read.
**S1 re-checked the same day**, after three of its four requires shipped: it
stays impossible on the fourth, and its verdict now says which one rather than
describing a flow that no longer exists.

## The score

**3 work · 6 bend · 10 impossible** — from 2 · 2 · 15 on August 12, and the
difference is almost entirely the merger and Heron rather than work aimed at
these stories.

| | journeys |
|---|---|
| **Works** | S4 durable capture · S6 the honest weekly review · S17 leaving with your data |
| **Bends** | S2 the phone morning · S5 closing the day · S13 finding what you wrote · S14 a note that knows when · S16 the past arriving · S18 bringing your history |
| **Impossible** | S1 signing up · S3 planning against capacity · S7 acting on the review · S8 the quarter · S9 the week · S10 a project's why · S11 a decision returning · S12 a project explaining itself · S15 reading producing work · S19 paying |

**This score lives here and nowhere else.** Other documents link to it; they do
not quote it.

**Every verdict below cites a `file:line`.** A citation that does not resolve is
how this document became misleading while every sentence in it still read as
evidence.

## What this is for

[`commercial-blueprint.md`](commercial-blueprint.md) audits what Clarice is.
This describes what it is *for*, as behaviour, so the architecture question —
reshape in place or rebuild — can be priced against a specific destination
instead of a feeling.

Each story is written against the **target** product and then run against the
**current** one:

- **Works** — a real user could do this today.
- **Bends** — possible, but the product fights them.
- **Impossible** — no path exists at any cost short of new code.

The *impossible* pile is the argument, and the "requires" lines added together
are the target model. Stories are journeys rather than atomic feature cards
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

Design personas, not descriptions of the real people using Clarice.

- **Vince** — the builder. Two years of history, the deepest archive, uses every
  surface, plans at quarter scale.
- **Priya** — invited by Vince, not technical, mostly on a phone, cares about
  routines and the daily page, will never read documentation.
- **Sam** — a stranger. Arrives from a link, has used Todoist for six years,
  curious and impatient. Will give the product about four minutes.

---

## Loop 1 — Do

### S1. Sam's first four minutes

> Sam follows a link, reads what Clarice is, makes an account, and is doing
> something real before he decides whether to stay.

**Done means:** he reaches a usable workspace without waiting for a human, the
first screen offers one obvious thing to do rather than six concepts, and within
four minutes he has captured a thought and planned a day.

**Verdict: still impossible, and now for one reason instead of four.**
Re-checked August 18, 2026, after three of its four requires shipped.

**Closed:** the landing page is no longer a login form; `/app/day` teaches a
brand-new account instead of showing it three empty states it cannot act on;
and signup verifies an address — `accounts/tokens.py` signs a single-use link,
`emails.send_activation_email` is the message this module never had, and the
two waits are told apart at the login form rather than blurred into one.

**Open, and load-bearing:** `is_active` is still approval and approval is still
a person. Vince's call, August 18, and a defensible one while the site is
invitation-only and `roadmap.md` still lists a privacy policy as unwritten — but
this story's done-means says *without waiting for a human*, so it cannot be
scored on anything else. `email_confirmed_at` now carries confirmation so the
two facts are separable, which is what makes closing this later a change of
policy rather than of design.

**What the shipped half is worth**, since "impossible" now hides it: he learns
the form worked, learns what he is waiting for, and can recover a lost
confirmation email himself. Before, he signed up and was told nothing at all.

**Requires:** ~~self-service signup with email verification~~, ~~a first-run
path~~, ~~an empty state that teaches~~, ~~a landing page that is not a login
form~~ — and the one that remains: **approval that is not a person**, or a
decision that this story is not the target after all.

### S2. Priya's morning, on a phone

> Priya wakes, reads what today asks of her, ticks off the thing she did before
> breakfast, and moves one task to tomorrow — all on her phone, in bed.

**Done means:** on a day of pinned commitments and routines she can complete a
task from the day surface itself, reschedule another without leaving it, and hit
every control with a thumb.

**Verdict: bends.** Android does agenda read/write, but the Day page's action
items are still read-only *by design* (`DayRoute.tsx:122` explains why a Complete
button was refused) — completing a task means navigating away. On mobile web
`button.tsx:28` still tops out at `h-9`, 36px, and `DayRoute` carries none of the
per-call-site 44px overrides.

**Requires:** complete/add from the day surface; a 44px floor in the primitive;
a decided client strategy so "on a phone" has one answer.

### S3. Vince plans a Tuesday he can actually survive

> Vince pins five things to Tuesday. Four hours are already committed. He wants
> to know he is lying to himself on Monday, not at Friday's review.

**Done means:** tasks carry effort estimates and the day declares its free time,
so when the pinned total exceeds what the day can hold the day says so while he
is still planning — and the weekly review can separate *over-committed* from
*under-delivered*.

**Verdict: impossible.** No effort field, no capacity concept.

**Requires:** `Item.effort`, a per-day capacity, and a planning-time signal.
This is the sharpest test of appetite in the whole set — if estimates would go
unentered, this story dies and takes the capacity model with it.

### S4. Priya captures a thought in a supermarket queue

> A thought arrives. She writes it down in four seconds and forgets it, trusting
> it will be waiting.

**Done means:** with no signal, the text survives force-stop, reboot and a dead
network, arrives exactly once when signal returns, and is waiting for her
undecided.

**Verdict: works.** The best-built thing in the product — durable before the
network is asked anything, stable idempotency key, owner-scoped uniqueness
constraint behind it. Both former caveats are closed: the queue gained a
process-wide lock and is excluded from device backup in *both* `backup_rules.xml`
and `backup_rules_legacy.xml`.

**Requires:** nothing.

Two corrections. The thought lands in the graph at `/mind/` as a `Node`, not in
"her inbox" — the Inbox was deleted on August 15, and `/api/v1/capture` kept its
URL, token and scope through that. And the node records where it came from, a
label hard-coded to `mobile` for every caller until August 16, so a thought typed
into the web Day page claimed to be from a phone; it was found by reading an
account export, the one place that label is shown to the person it is wrong about.

### S5. Vince closes the day

> At the end of the day Vince records what actually happened, while it is still
> true, and the record is worth reading in six months.

**Done means:** the record keeps what he chose that morning and not only what he
finished — and something prompts him to close the day at all.

**Verdict: bends.** `DailyEntry.happenings` exists and `DailyFocus` preserves
the morning's choice honestly — genuinely good. But nothing ever asks him to
write it: no evening surface, no prompt, no reminder.

**Requires:** a closing ritual with a time-aware nudge.

---

## Loop 2 — Adjust

### S6. Friday, and the numbers are honest

> Vince reads back the week. The finish rate divides by what he actually
> committed to, and deliberate decommitments do not read as failures.

**Done means:** across a week of pins, completions, routines and decommitments,
the finish rate divides by planned commitments rather than the backlog, a
set-aside pin reads as a decision rather than a miss, and a paused routine does
not count against him.

**Verdict: works, and it is the product's moat.** `DailyFocus` snapshots
`task_text` at selection, `released_at` distinguishes decommitment, and
`WeeklyReview` stamps the concluded figure. Competitors cannot report this
because they never stored the denominator.

**Requires:** nothing. Protect it from every future change.

### S7. Priya acts on what the review just told her

> The review says four captures have been waiting eleven days. She wants to deal
> with them now, not remember to later.

**Done means:** she decides what those captures are without leaving the review,
and the numbers update in place.

> **⚠ This journey's premise no longer exists, and rewriting it is a product
> decision rather than an edit.** Captures, the Inbox and triage were deleted on
> August 15; the crossover's whole claim is that a thought stops needing to be
> filed. The nearest live equivalent is *names worth confirming* — the review
> already surfaces concept candidates that have earned a question by recurring,
> and confirming one from the review is not possible. That is the same story with
> a different noun, if it is still the story worth telling. **Left as written,
> marked, and counted as impossible until Vince decides.**

**Verdict: impossible** — for the thing this story names, which no longer
exists. Not because the review is inert: `ReviewRoute.tsx:147` pins a task to
today and `:896` reopens or completes one, so it already mutates, through the
task core's own services.

**Requires:** deciding what the ageing pile is now. The read-only rule is *why*
the numbers are trustworthy, and the resolution already found for tasks —
writing through the owning core's services, leaving the review's own reads
untouched — is the one to repeat.

### S8. Vince zooms out to a quarter

> Three months in, Vince wants to know whether the shape of his life matched
> what he said it would be.

**Done means:** the same honest denominators aggregate across twelve weeks of
reviews and routine history, and weeks with no data read as absent rather than
zero.

**Verdict: impossible.** `WeeklyReview` is the only review model;
`TREND_WEEKS = 5`.

**Requires:** longer-horizon reviews reusing the weekly model. The
null-not-zero discipline already exists in `review/reads.py` and must carry up.

### S9. Priya plans a week, not just a day

> On Sunday she decides what the week is about. On Wednesday the day knows.

**Done means:** Wednesday shows what the week was for, and the review can ask
whether the week's days served the week's intention.

**Verdict: impossible.** Planning exists only at day scale — which is a hole in
a product whose pitch is "design the future."

**Requires:** intentions above the day, snapshotted the same way `DailyFocus`
snapshots a commitment.

---

## Loop 3 — Decide

### S10. Vince starts a project and records why

> He commits to a piece of work and writes down what he is trying to achieve and
> what would tell him it went wrong.

**Done means:** the purpose and the abandonment condition live with the project,
and are still there when he is deciding whether to continue.

**Verdict: impossible.** `Project` is `owner/title/due_date/is_completed/
completed_at/created_at` — there is no description field at all.

**Requires:** projects as workspaces with purpose, notes and an abandonment
condition.

### S11. A decision comes back

> Six weeks ago he chose one approach over another and wrote down what would
> make him revisit. Something happens that touches the reason.

**Done means:** he can reach the decision from the work that provoked it, see
what he considered at the time and not only what he chose, and find decisions
past their reconsideration trigger without hunting for them.

**Verdict: impossible.** No concept exists.

**Requires:** `Decision` as a first-class record. Note this story is not
hypothetical — `architecture-trajectory.md` §7 and §8 are exactly this practice,
done in Markdown because the product cannot hold it.

### S12. The project ends and explains itself

> A project completes. Vince wants a retrospective he did not have to write from
> memory.

**Done means:** closing a project with eleven weeks of history shows what was
planned versus met across its life, what he deliberately set aside, and the notes
and decisions made along the way — and he adds what he would do differently, kept
for next time.

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

**Done means:** results span tasks, notes, sources, days and reviews, are ranked
rather than merely filtered, and he can reach the day a result was written and
see what else was happening.

**Verdict: bends.** Full-text search exists: `src/mind/models.py` gives `Node` a
`search_original` `SearchVectorField` with a GIN index and revisions a
`search_body`, and `/mind/` has a search page over both.

**Ranking shipped August 18, 2026** (`jackdaw`, D14) and this verdict used to
cite its absence. `queries.search_ranked` scores on the better of the two
vectors, and the page says when it is showing 30 of N rather than truncating in
silence — which mattered because the "I know I wrote this" button sits directly
beneath the results, so a truncation was being recorded as a retrieval failure.

What still bends is reach. It searches **notes only** — tasks, days and reviews
are outside it — and reaching the day a note was written still means clicking
back a week at a time.

**Requires:** reach across content, and a way to land on a date. Ranking is no
longer on this list.

### S14. A note knows when it was written

> Priya writes a note during a hard week. A year later it is still legible,
> because it remembers what was happening around it.

**Done means:** the note carries the day it belongs to, the project it was inside
and what she had committed to that week — and she reached it without having filed
it anywhere by hand.

**Verdict: bends.** `Node` carries `captured_at` separately from `created_at` —
the thought's own time, not the row's — plus `Revision` history, confirmed
concepts, and a `Facet` linking to the `Item` it became. So a note does know when
it was written, and what it turned into.

What it does not know is the **surrounding**: no link to the `DailyEntry` for
that day, or to the `Project` it was inside, so "what had she committed to that
week" is not answerable from the note.

**Requires:** typed links from a node into the day and project domain objects.
**This is still the differentiator** — the graph accreting from what you were
already doing rather than being built by hand — and it is now one relationship
short rather than a model short.

### S15. Reading produces work

> Sam reads an article. Two ideas and one task come out of it, and six months
> later he can still tell where they came from.

**Done means:** the task remembers the external source it came from, and the
source shows everything that grew out of it.

**Verdict: impossible.** There is nothing to attach an article to. `NodeSource`
(`mind/models.py:30`) is a capture-channel label — mobile, web — not external
material, and no model records a thing you read.

The backlink half is no longer missing: `Facet.task` (`mind/models.py:324`)
carries `related_name="mind_facets"`, so from a task you can already reach the
thought it came from. Only the source end is absent.

**Requires:** `Source`, and links from it to what grew out of it.

### S16. The past arrives when it is useful

> Vince starts a project on a topic he worked on eighteen months ago. Without
> asking, Clarice offers what he learned last time.

**Done means:** opening the project surfaces notes, decisions and sources from
previous work on that topic, each saying why it surfaced, and nothing is changed
on his behalf.

**Verdict: bends.** The mechanism exists and the trigger does not. `/mind/review/`
resurfaces material on a schedule, `mark_reviewed` records what was done with it,
and every proposal carries a `contribution_reason` — which is precisely this
story's *"each says why it surfaced"*, built without anybody aiming at this story.

What is missing is the entry point the story describes: opening a **project**
surfaces nothing. Resurfacing is time-driven, not context-driven. It is also
still limited by the corpus rather than the code — 41 nodes, 19 of them visible
to the detectors.

**Requires:** S13 and S14 first. This is the story that makes a second brain
feel like one, and it is worthless before the corpus exists.

### S17. Priya leaves

> Priya decides to stop. She takes everything and closes the account.

**Done means:** two years of tasks, notes, days and reviews come back in a
readable format, she can delete the account herself, and she is told plainly what
happens to the copy.

**Verdict: works** — and it was scored that way while the export silently
dropped every tag association and three whole models, fixed August 18, 2026
(D12). Recorded rather than quietly corrected: a verdict of "works" on a file
nobody had checked against the models it claimed to cover is the failure mode
this document's own citation rule exists to catch.

Preferences carries a download of everything the account owns
(JSON plus Markdown a person can actually read) and a self-service deletion with
a thirty-day grace period, an acknowledgement, a password re-entry and three
emails — `src/accounts/export.py`, `src/accounts/services.py:ACCOUNT_DELETION_GRACE`.
Proven by `src/functional_tests/test_leaving.py`, which downloads the archive in
a real browser and opens it.

**The obstacle was not effort.** `User.delete()` raised against the append-only
`ActivityEvent` trigger, so deletion was impossible rather than unbuilt, and
nobody had noticed because nobody had ever tried
(`mind/migrations/0015_erasure_exemption`).

---

## Cross-cutting

### S18. Sam brings six years of Todoist with him

**Done means:** his projects, tasks, due dates and completion history arrive
intact from another product's export, and he is told what could not be carried
across.

**Verdict: bends.** `src/mind/importers/` reads Markdown files, `.docx` and
JSONL, and `import_material` is a runner that is idempotent on an import key and
reports what it skipped — the "read a foreign file, land it here without
duplicating on a re-run" machinery, which is the part that usually costs most.

None of it imports a **competitor**, and none of it reaches the task core: no
path turns a Todoist export into projects, tasks, due dates and completion
history. Still the switching cost that decides whether an experienced user
becomes a real one.

### S19. Sam decides to pay

**Done means:** after a trial that has shown him the weekly review at least
twice, subscribing changes his limits without his data moving, and cancelling
leaves him able to read and export.

**Verdict: impossible.** No billing, plan, entitlement or trial concept.

---

## What the stories add up to

**19 stories: 3 work, 6 bend, 10 impossible.**

**Almost none of the movement since August 12 was aimed at these stories**,
which is the most useful thing the re-score found. The merger and Heron were
about capture surfaces and models; they moved S13, S14, S16 and S18 off
"impossible" as a side effect. S17 is the only one closed deliberately.

- **The knowledge core is further along than its own planning said.** Four of the
  five second-brain journeys moved. The remaining gaps are narrower than "build a
  second brain" — ranking on a search that exists, two typed links on a model
  that exists, a context trigger on resurfacing that exists.
- **The task core's gaps did not move at all.** S3, S8, S9, S10, S11 and S12 are
  untouched since August 12, and they are the planning, quarterly and project
  stories. That is the honest shape of the product: capture and reflection work,
  planning and projects do not.

The three that work — durable capture, the honest weekly review, and leaving with
your data — are what the product should be sold on, and none needs changing.

The impossible pile resolves into a target model.

**Knowledge** — `Node`, `Revision`, `Facet` and the search index already cover
the note half. What is missing:

- `Source` — external material with provenance *(S15)*
- `Decision` — choice, alternatives considered, reconsideration trigger *(S11)*
- `Link` — typed, polymorphic, spanning knowledge **and** domain objects
  *(S12, S14, S15, S16)*
- Ranking, and a search index reaching every text-bearing model *(S13)*

**Productivity**

- `Item.effort` and per-day capacity *(S3)*
- Deferral distinct from `due_date`, so snooze stops erasing the commitment
- A someday state, so non-committed work stops masquerading as something else
- `Project` as a workspace: purpose, notes, abandonment condition,
  retrospective *(S10, S12)*
- Intentions above the day; reviews above the week *(S8, S9)*

**Substrate**

- Self-service signup, first-run, onboarding *(S1)*
- Import of a competitor's export *(S18)*
- Plans and entitlements *(S19)*

**The load-bearing finding, and it shipped.** S1, S15 and the someday state each
independently required a task that can exist without an Area, which made it the
most-supported single change in either planning document. `Item.list` became
nullable and `Item.owner` direct on August 14; `lists/models.py:123-156` cites
this document back as the reason. The list-spine went for these product reasons,
and the blueprint's separate scaling argument for the same change now rests on a
premise — `Item` having no `owner` column — that the change itself removed.

## What these stories do not settle

- **S3 (capacity)** rests entirely on whether estimates would actually be
  entered. Untested, and the model should not be built until it is.
- **S7** asks whether the review may ever mutate, and what the ageing pile is now
  that captures are gone. A real decision, not an oversight.
- **S11 (`Decision`)** may be over-fitted to how this project documents itself
  rather than to how anyone else works. It is the story most in need of a second
  opinion.
- Nothing here is validated with a user who is not already invested. Ten
  impossible stories written by the person who would build them is a hypothesis,
  not evidence.
