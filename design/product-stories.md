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

**S3 re-scored August 19, 2026, and it did not move.** Still *impossible*, so
the table below is again unchanged — nothing has been built, and the definition
of that verdict is *no path exists at any cost short of new code*. What changed
is its `Requires` line, which shrank from a model field, a capacity concept and a
signal to **a read and a signal, with no new field at all**; and its appetite
warning, which is withdrawn. Recorded here because "re-scored" and "re-ranked"
are different claims and only the first happened. The other eighteen were not
re-read.

**Re-scored against `kestrel`, August 19, 2026 — and this one moved the table.**
The planning assistant shipped that afternoon, hours after the S3 note above was
written, and it is **the first body of work aimed at this document's own gaps**:
five of its six increments land on stories in the impossible pile. Six were
re-read against the code (S3, S7, S9, S10, S12, S16) and three of them moved.
Two more were checked and left alone with a line saying why (S11, S15). The
other eleven were not re-read.

**One verdict is now held up by an absence rather than by a gap**, which is new
and is the most useful thing this pass found: **S9 has a model, a service, a read
and an API payload, and no way for a person to write one.** See its entry.

## The score

**3 work · 9 bend · 7 impossible** — from 3 · 6 · 10 on August 16, and from
2 · 2 · 15 on August 12. **Unlike every previous move, this one was aimed**: the
merger and Heron shifted the second-brain stories as a side effect, where
`kestrel` was built at the planning and project stories on purpose.

| | journeys |
|---|---|
| **Works** | S4 durable capture · S6 the honest weekly review · S17 leaving with your data |
| **Bends** | S2 the phone morning · S3 planning against capacity · S5 closing the day · S7 acting on the review · S10 a project's why · S13 finding what you wrote · S14 a note that knows when · S16 the past arriving · S18 bringing your history |
| **Impossible** | S1 signing up · S8 the quarter · S9 the week · S11 a decision returning · S12 a project explaining itself · S15 reading producing work · S19 paying |

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

**Done means:** the day says so while he is still planning, when what he has
pinned exceeds what his days actually hold — and the weekly review can separate
*over-committed* from *under-delivered*. **Rewritten August 18, 2026 to describe
the outcome rather than one mechanism**; it previously specified effort estimates
and a declared free-time budget, which is an implementation and not a journey.

**Verdict: bends**, moved from *impossible* by `kestrel` on August 19, 2026 —
**the same day the paragraph above said nothing had been built.** Both halves of
the `Requires` line were built within hours of it being written, which is worth
leaving visible rather than tidying into one entry.

The throughput read is `typical_week_for` (`review/reads.py:739`): the **median**
of what was finished across up to eight weeks that had a plan in them, computed
from `DailyFocus` exactly as the line below anticipated, returning `None` below
two planned weeks because *"no evidence yet"* and *"you have room"* call for
opposite responses. The planning-time signal is `draft_week`'s `over_committed`
(`review/reads.py:835`), and `ReviewRoute.tsx` states it without grading it — a
test asserts the scolding phrasing is *absent*, not merely that the neutral one
is present.

**What still fights him is grain and place.** The signal is a week's, on the
review, about the week ahead; his story pins five things to a **Tuesday** and
wants the day to answer while he is still choosing. `DayRoute` has no capacity
signal at all, so the day he is planning into stays silent, and he learns it by
opening a different surface and reading about a different unit. It reaches him
on Monday rather than at Friday's review, which is the thing the story actually
asked for — so this bends rather than blocks.

**Requires:** the same read at day grain, on the day surface. Still **no new
field**: `review/reads.py:103` computes planned against completed for a week and
a day is that computation finer, which is what made the week version cheap.

**The appetite test this story carried is withdrawn.** It read *"the sharpest
test of appetite in the whole set — if estimates would go unentered, this story
dies and takes the capacity model with it."* That was true of the mechanism and
not of the journey. **D2, August 19, 2026** chose capacity derived from history
over capacity entered by hand, so there are no estimates to go unentered and
nothing here rests on anybody's willingness to maintain them. Dated August 19
because the decision landed just after midnight; the reasoning is in
[`roadmap-history.md`](roadmap-history.md) — that plan became a stub when it
shipped, and this pointer followed it there. The
cost of being wrong about this fell with it: a throughput read that nobody finds
useful is a read to delete, where an abandoned estimate field is a column and a
migration.

**What the cheaper route does not buy**, recorded so the next reader does not
assume this story got easier than it did: throughput is count-based, so nine
small things read the same as nine large ones. Distinguishing them still wants
the effort field this no longer requires. **Now shipped and still true** — a
median of counts is what `typical_week_for` returns, and it cannot tell a week
of five errands from a week of five features.

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

> **⚠ The premise came back, and the code answered the question this box was
> holding open.** It read: *this journey's premise no longer exists* — captures,
> the Inbox and triage were deleted on August 15 — *and the ageing pile has to be
> renamed before the story can be scored.* `kestrel` increment 5 named it without
> being asked to. `loose_ends` (`review/reads.py:588`) gives the review a pile
> that ages again: **unanswered questions** carrying `asked_on`, **commitments
> read out of her own writing and never accepted or dismissed** carrying
> `proposed_on`, and overdue work. *"Four things have been waiting eleven days"*
> is once more a true sentence about this product, with a different noun in it.
> The box stays as a record of the question, since the answer arriving from a
> plan that never mentioned this story is the interesting part.

**Verdict: bends**, moved from *impossible*. The pile exists, the review shows
it with its dates, and she can deal with it — the section links her to `/mind/`
to do it (`ReviewRoute.tsx:888`, *"Decide them in Second Mind"*). The journey
completes across two surfaces.

**What still fights her is the second surface.** *"Without leaving the review,
and the numbers update in place"* is unbuilt **and deliberately so**: the section
is extractive, and the comment above it gives the reason — nothing there
proposes, so nothing there needs a confirm gate. That is the read-only rule
protecting exactly what makes S6 the product's moat, and it is a refusal rather
than an omission. The review is not inert either way: `ReviewRoute.tsx:710` pins
a task to today and `:689` completes or reopens the review itself — both through
the owning service rather than a review-shaped write path, which is the shape any
answer to the question below should copy. **Those two citations were `:147` and
`:896` before this pass and had drifted onto unrelated lines**, which is the rule
at the top of this file catching itself.

**Requires:** deciding whether deciding-in-place is worth opening that rule —
the one genuine product question left here, now that what the pile *is* has been
settled by shipping it. The resolution already found for tasks — write through
the owning core's services, leave the review's own reads untouched — is the one
to repeat if the answer is yes.

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

**Verdict: impossible, and for a reason worth reading carefully — everything
this story needs exists except a way in.** The old verdict said *planning exists
only at day scale*, and that is no longer true. `kestrel` built S9 as increment
6's prerequisite:

- `WeeklyIntention` (`review/models.py:94`), its own model rather than a field
  on `WeeklyReview`, so that setting an intention cannot invent a review row and
  destroy the one thing a review's *existence* is evidence of.
- `services.set_intention` (`review/services.py:118`), which takes any day and
  normalises, so Wednesday can rewrite what Sunday decided without a second row.
- `reads.intention_for` (`review/reads.py:697`), returning `None` rather than
  creating.
- `week_intention` on the Day payload (`daily/api_v1.py:284`), with tests at
  `review/tests/test_weekly_intentions.py:154` asserting a Wednesday carries it.

**And nothing can write one.** `set_intention` has no caller outside its own
tests: there is no endpoint for it on the review router, `ReviewIn`
(`review/api_v1.py:491`) accepts `reflections` and `plan` only, and no template
posts one. **So "on Sunday she decides what the week is about" cannot happen at
all**, from any client, at any cost short of new code — which is this document's
definition of *impossible*, met by a feature that is otherwise finished.

**The second half is missing in the same shape.** `week_intention` appears in
`frontend/src/api/schema.ts:1420` and **in no component** — the Day page never
renders it. So *"on Wednesday the day knows"* is true of the payload and false of
the page, and the commit that built it (`8b02c1b`, *"so a Wednesday can know"*)
asserted it through the Day API rather than the Day page, which is where the gap
slipped through. The draft on the review displays the intention
(`ReviewRoute.tsx:947`), so the only text a person can ever see there is text no
person could have put there.

**Requires:** a write path and a render — **no model, no service and no read.**
This is the cheapest remaining item in the impossible pile by a wide margin, and
it is the difference between a shipped feature and a reachable one.

---

## Loop 3 — Decide

### S10. Vince starts a project and records why

> He commits to a piece of work and writes down what he is trying to achieve and
> what would tell him it went wrong.

**Done means:** the purpose and the abandonment condition live with the project,
and are still there when he is deciding whether to continue.

**Verdict: bends**, moved from *impossible* by `kestrel` increment 3. The old
verdict — *"there is no description field at all"* — is the citation this
re-score existed to catch: `Project.purpose` (`lists/models.py:450`) is end to
end, model to text area, and the comment above it names this story as the reason
and names its own two omissions.

**One of S10's three shipped, and it is the load-bearing one.** Purpose is what
increment 4 anchors retrieval against — `brief_for` (`lists/projects.py:105`)
returns nothing for a project without one, on purpose, because an unanchored
query is a ranked-by-coincidence panel. Optional, and staying optional: requiring
it would put a writing task in front of somebody who only wants to group three
areas.

**What still fights him:** notes and the abandonment condition have no home, so
*"what would tell him it went wrong"* goes into the purpose text or nowhere. It
survives — plain text takes anything — but the abandonment condition is then
indistinguishable from the ambition, which is precisely the distinction the story
is about, and nothing can ever read one without the other.

**Requires:** the remaining two of the three — notes, and an abandonment
condition that is its own field.

### S11. A decision comes back

> Six weeks ago he chose one approach over another and wrote down what would
> make him revisit. Something happens that touches the reason.

**Done means:** he can reach the decision from the work that provoked it, see
what he considered at the time and not only what he chose, and find decisions
past their reconsideration trigger without hunting for them.

**Verdict: impossible**, unchanged, and re-read against `kestrel` rather than
assumed. No concept exists.

**The "comes back" half now has a working precedent**, which is the only thing
that moved: `unresolved_questions_in_context` (`mind/queries.py:688`) reports how
long a question has been open **and which later notes returned to it**, each
carrying the terms that matched — a mechanism for *"something happens that
touches the reason"*, built for questions. A question is not a decision: it has
no alternatives-considered and no reconsideration trigger, which are two of this
story's three parts. But the retrieval that would serve those parts is no longer
hypothetical either.

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

**Verdict: impossible**, unchanged — **but both halves of the old citation are
now false, and half the `Requires` shipped.** *"`src/review/` imports nothing
from projects"* stopped being true at `review/reads.py:22`, and
`upcoming_constraints` (`review/reads.py:661`) reads project deadlines into the
review. Left in the impossible pile anyway, because what this story asks for is
none of that.

**What shipped is the live half, and this story wants the closing half.**
`brief_for` (`lists/projects.py:86`) is project-scoped aggregation joined to
knowledge records — the second `Requires` line, delivered — but it briefs a
project that is *running*: prior thinking, loose ends, dated commitments.
Nothing computes planned-versus-met across a project's life, and
`services.complete_project` (`lists/services.py:785`) still sets two fields and
writes no record, so the second clause of the old verdict stands exactly as
written. There is nowhere to put *what he would do differently* either.

**Requires:** what completing a project produces — a retrospective read over its
life, and somewhere to keep his own account of it. **This is still the story
that makes the two cores one product**, and it is now half-built rather than
unstarted: the link between projects and knowledge records exists and is in
daily use.

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

The backlink half is no longer missing: `Facet.task` (`mind/models.py:400`)
carries `related_name="mind_facets"`, so from a task you can already reach the
thought it came from. Only the source end is absent.

**Re-read against `kestrel` and left where it was.** Increment 2 turns writing
into tasks — a commitment read out of the journal, cited at the sentence that
proposed it — which looks adjacent and is not: the material is his *own*, and
this story starts with an article somebody else wrote. That is the whole of the
gap, and nothing in the planning assistant touched it.

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

**The entry point arrived.** This verdict used to end *"opening a project
surfaces nothing; resurfacing is time-driven, not context-driven"* — `kestrel`
increment 4 built exactly that missing thing. `ProjectBrief.tsx` puts *"What
bears on this?"* on the project page, `material_bearing_on`
(`mind/queries.py:580`) anchors retrieval on the project's purpose, and every
item carries the terms that selected it, which **is** this story's *"each saying
why it surfaced"*. Nothing is changed on his behalf — a brief assembles what is
already his, so it has no confirm gate and records nothing on being read.

**What still bends, and one of the two is a refusal.** It is *asked for, never
pushed* — `enabled` stays false until the button is pressed, because the
Attention Policy permits a queue only inside a ritual the person chose to open —
where the story's own sentence is *"without asking"*. **That tension is the
story's to resolve, not the code's**, and it is the same shape as S7's: the
product has a considered position and the journey was written before it. The
other gap is plain: the brief reaches **notes only**, because `Source` (S15) and
`Decision` (S11) do not exist, so *"notes, decisions and sources"* is one of
three. It is also still limited by the corpus rather than the code — 41 nodes,
19 of them visible to the detectors.

**Requires:** S15 and S11 for the other two nouns, S13 and S14 still underneath,
and a decision on whether *"without asking"* survives contact with the Attention
Policy. This is the story that makes a second brain feel like one, and it is
worthless before the corpus exists.

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

**19 stories: 3 work, 9 bend, 7 impossible.**

**The August 16 reading of this section was that almost none of the movement had
been aimed at these stories** — the merger and Heron were about capture surfaces
and models, and moved S13, S14, S16 and S18 off "impossible" as a side effect,
with S17 the only one closed deliberately. **`kestrel` is the counter-example and
the pattern it breaks is the important one.** It was planned against this
document, and it moved S3, S7 and S10 while narrowing S9, S12 and S16 — the
planning and project cluster this section named as immovable three days earlier.

- **The knowledge core is further along than its own planning said.** Four of the
  five second-brain journeys moved. The remaining gaps are narrower than "build a
  second brain" — ranking on a search that exists, two typed links on a model
  that exists, and a context trigger on resurfacing which now **exists too**, as
  a project brief somebody asks for.
- ~~**The task core's gaps did not move at all.**~~ **They moved on August 19**,
  and the sentence is struck rather than deleted because it was true for a week
  and its being wrong is the point. What remains true is the shape underneath it:
  the three journeys that *work* are still capture, reflection and leaving, and
  planning and projects still only bend. Nothing in the impossible pile is a
  planning story any more except **S9, which is impossible for want of a form**,
  and **S8, the quarter**, which nothing has touched since August 12.

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

- ~~`Item.effort` and per-day capacity~~ — **no longer a model change** *(S3)*,
  and **since built at week grain** as `typical_week_for`. Decided as D2 on
  August 19, 2026 and shipped the same day. It is struck rather than deleted
  because the target model is an argument, and an item leaving it by getting
  cheaper is the most useful thing that can happen to one
- Deferral distinct from `due_date`, so snooze stops erasing the commitment
- A someday state, so non-committed work stops masquerading as something else
- `Project` as a workspace: ~~purpose~~ *(shipped, `kestrel`)*, notes,
  abandonment condition, retrospective *(S10, S12)*
- ~~Intentions above the day~~ *(the model shipped; the form did not — S9)*;
  reviews above the week *(S8)*

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

- ~~**S3 (capacity)** rests entirely on whether estimates would actually be
  entered.~~ **Dissolved rather than answered, August 19, 2026.** D2 took
  capacity from `DailyFocus` history, so there are no estimates to go unentered
  and no appetite to test. What is untested now is whether a throughput figure
  somebody never asked for changes what they pin — a question about a read, which
  is a read to delete if the answer is no.
- **S7** asks whether the review may ever mutate. **Half of this settled itself:**
  what the ageing pile is now that captures are gone was answered by increment 5
  shipping one. The mutation question is untouched and still real.
- **S16 and S7 now share a shape worth naming.** Both journeys ask for something
  the Attention Policy declines to give — *"without asking"* and *"without
  leaving"* — and in both the mechanism is built and the delivery is a considered
  refusal. Either the stories are wrong about what a person wants, or the policy
  is too strict in a ritual the person opened deliberately. **That is one
  decision, not two**, and it is the largest unanswered product question in this
  document.
- **S11 (`Decision`)** may be over-fitted to how this project documents itself
  rather than to how anyone else works. It is the story most in need of a second
  opinion.
- Nothing here is validated with a user who is not already invested. Ten
  impossible stories written by the person who would build them is a hypothesis,
  not evidence.
