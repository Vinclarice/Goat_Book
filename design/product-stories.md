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

**Re-scored against v2's increments 1–8, August 20, 2026.** Eight increments of
`planning-assistant-v2-plan.md` shipped in one stretch, and this is the second
consecutive body of work aimed at this document rather than passing near it.
**Only one verdict moved** — and the more useful finding is how many did not,
and how narrowly. Six stories were re-read (S3, S7, S9, S10, S12, S16); three
of them are now one clause short of *works*, and their entries say which clause.

**The three-loop model was corrected August 20, 2026, and this was not a
re-score.** The second brain is not the memory of the Decide loop; it is the
substrate the loops run on — see §The three loops, which owns the correction and
what it was hiding. Recorded up here because **this file's model is quoted by
other documents and a wrong model travels further than a wrong verdict.** The
nineteen verdicts were not re-read against it, and none is claimed to have moved.

**Re-scored against v3's *Usable* release, August 20, 2026 — and four moved.**
The first verdicts to move on work aimed at *bends* rather than at the
impossible pile, which is what `principles.md` changed this morning to allow.
S2 went first; S3, S7 and S9 followed with the review block. Four stories were
re-read; the other fifteen were not.

**Three of the four cost almost nothing, and that is the finding.** S3 was "an
argument's difference" and was; S9 was "a read nobody has written" and was; S7
"needed no new decision, only the same treatment" and did. `kestrel` and v2 had
already paid for their substrates, which is why a day's work moved four
verdicts after two releases moved one.

## The score

**8 work · 5 bend · 6 impossible** — from 7 · 6 · 6, 4 · 9 · 6 and 3 · 10 · 6
earlier on August 20, 3 · 9 · 7 on August 19, 3 · 6 · 10 on August 16, and 2 · 2 · 15 on
August 12.

**The impossible pile is now six, and it is the honest shape of what is left:**
signing up needs a policy decision, not code; the quarter and the project
retrospective are unbuilt reads; and `Decision`, `Source` and billing are three
models nobody has started. Nothing in it is waiting on a form any more.

| | journeys |
|---|---|
| **Works** | S2 the phone morning · S3 planning against capacity · S4 durable capture · S5 closing the day · S6 the honest weekly review · S7 acting on the review · S9 the week · S17 leaving with your data |
| **Bends** | S10 a project's why · S13 finding what you wrote · S14 a note that knows when · S16 the past arriving · S18 bringing your history |
| **Impossible** | S1 signing up · S8 the quarter · S11 a decision returning · S12 a project explaining itself · S15 reading producing work · S19 paying |

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

~~The second brain is not a fourth loop. It is the **memory of the third one**.~~
**Corrected August 20, 2026 — Vince's call, and it was wrong in a way that hid
work.**

**The second brain is not a loop at all. It is the substrate, and the three
loops above are tempos of reading and writing it.** Do writes fast and reads
today; Adjust reads a week and writes what was concluded; Decide reads long and
writes direction.

**What the old line hid.** Subordinating memory to the least-built loop made a
set of stuck things look like data problems when they are intake problems.
Memory has two intake pipes — `capture` and the journal — and the task core,
which records most of what actually happens, is not one of them:
`mind.EventType` carries 23 values and every one of them is about a note. So the
corpus is thin because nothing writes to it except deliberate capture, not
because one person uses it, and every gate waiting on corpus volume was waiting
on the wrong thing.

[`clarice-v3-plan.md`](clarice-v3-plan.md) and
[`temporal-substrate-plan.md`](temporal-substrate-plan.md) are both built on the
corrected model, and both recorded this correction as *owed* rather than making
it, because this file owns it.

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

## Re-scored after `nightjar`, August 22, 2026 — and nothing moved

**Thirty-one commits, five migrations, and the score is unchanged: 8 · 5 · 6.**
Recorded at the top because it is the least comfortable thing this file says
and burying it would be the same failure it exists to prevent.

**Every remaining require is a specific noun, and the substrate is underneath
all of them rather than any of them.** Checked one at a time:

| Story | Its require | Did `nightjar` touch it? |
|---|---|---|
| S13 | reach across **sources and reviews** | No. Reviews are still outside the index and `Source` does not exist |
| S14 | **typed links** from a node into the day and project objects | No. `around()` joins on *time*, `since()` on *provenance* — a note still does not carry its day |
| S15 | **`Source`** | No |
| S16 | S13, S14, S15 and S11 underneath it | No, by consequence |
| S1 | **approval that is not a person** | No |
| S8, S11, S12 | longer horizons, `Decision`, project retrospective | Not attempted |

**The honest reading is not that the work was wasted.** These stories measure
end-to-end outcomes for a person, and `nightjar` built the layer beneath them:
a log that can answer *when*, reads that cross both cores, retrieval that knows
why it is being asked, and the surfaces that make any of it visible. S14's
require went from *a model short* to *one relationship short* in an earlier
release and stayed there — the relationship is still not built.

**The uncomfortable half is that a release claimed an acceptance it did not
meet.** v3's *Unify* says **"Acceptance: S13 and S14 reach works"** and lists
four things; one shipped. The temporal substrate was delivered and called
Unify, and nobody checked the other three bullets — typed node-to-day links,
`FacetKind.GOAL` wired to `Project.outcome`, and search's fifth increment.
*Recollection* is 2 of 5 by the same count. `roadmap.md` said both had
delivered until this re-score; it no longer does.

**What this file is for**, and it did its job: a scoreboard nobody re-reads is
a scoreboard that flatters. The gap between *thirty-one commits* and *nothing
moved* is exactly the reading a stale score would have hidden.

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

**Verdict: works**, moved from *bends* on August 20, 2026 — the first story to
move on work aimed at a bend rather than at the impossible pile.

**All three requires closed the same day, and one of them was not code.**

- **Complete and reschedule from the day surface.** `DayRoute.tsx` declined a
  Complete button because it "would mean reimplementing the agenda's mutation";
  right that a second mutation would be wrong, and wrong that the only
  alternative was doing without. Both clients now call the one authority —
  `updateTaskStatus`/`updateTaskDueDate` on the web, `AgendaApi.setTaskStatus`/
  `rescheduleTask` on Android. What was actually missing was an *address*, so
  `FocusOut` gained `url`.
- **The 44px floor.** This story's citation of `button.tsx:28` went stale on
  August 18: the primitive carries `touch-target` on its base, so no call site
  needs an override. The compass link, which `roadmap.md` names as the half
  that was left, now carries it too. **The action-item row's inline links
  deliberately do not**, and there is a comment at the code saying why — the
  chips sit 6px apart under a utility whose own note says controls closer than
  ~12px fight on touch. Android's controls are Material `TextButton`s and
  inherit Material's 48dp minimum interactive size; that is inherited rather
  than measured here.
- **A decided client strategy.** Vince's call, August 20: **on a phone means
  the Android app too.** It contradicts `commercial-blueprint.md` Part 9 #4's
  recommendation to freeze native — and the check that mattered came out the
  other way. Every endpoint this story needs is already token-reachable
  (`day:read`, `day:write`, `agenda:write`), and the Kotlin client already had
  `setTaskStatus`, `rescheduleTask` and `tomorrow`. **Nothing in the backend
  moved.** The falsified assumption — *mostly an Android build-out, not a
  backend rebuild* — held here.

**What is deliberately not in it:** adding a task from the day surface. The old
`Requires` line said "complete/add"; this story's own *done means* asks for
complete, reschedule and thumb-reachable, and those are what it was scored on.
Adding remains a `commercial-blueprint.md` Part 3 item.

### S3. Vince plans a Tuesday he can actually survive

> Vince pins five things to Tuesday. Four hours are already committed. He wants
> to know he is lying to himself on Monday, not at Friday's review.

**Done means:** the day says so while he is still planning, when what he has
pinned exceeds what his days actually hold — and the weekly review can separate
*over-committed* from *under-delivered*. **Rewritten August 18, 2026 to describe
the outcome rather than one mechanism**; it previously specified effort estimates
and a declared free-time budget, which is an implementation and not a journey.

**Verdict: works**, moved from *bends* on August 20, 2026, having moved from
*impossible* by `kestrel` the day before —
**the same day the paragraph above said nothing had been built.** Both halves of
the `Requires` line were built within hours of it being written, which is worth
leaving visible rather than tidying into one entry.

The throughput read is `typical_week_for` (`review/reads.py:802`): the **median**
of what was finished across up to eight weeks that had a plan in them, computed
from `DailyFocus` exactly as the line below anticipated, returning `None` below
two planned weeks because *"no evidence yet"* and *"you have room"* call for
opposite responses. The planning-time signal is `draft_week`'s `over_committed`
(`review/reads.py:974`), and `ReviewRoute.tsx` states it without grading it — a
test asserts the scolding phrasing is *absent*, not merely that the neutral one
is present.

~~**What still fights him is grain and place.**~~ **The grain half closed on
August 20, 2026**, in v2's increment 2. `daily/reads.py`'s `typical_day_for` is
the same computation at day scale — the median of what was finished across days
that had a plan, `None` below five of them — and `DayRoute.tsx:967` states it on
the day itself while he is pinning: *"5 pinned for today. You have finished 3 on
a typical day."* Absent on a day already lived, absent before anything is
pinned, absent below the evidence floor.

~~**One clause of the done-means is left, and it is the review's half**: *the
weekly review can separate over-committed from under-delivered*.~~ **Closed
August 20, 2026, and the story with it — verdict: works.** The review now
carries `typical` and `over_committed` on its own week, states them in the
same neutral wording the draft uses, and says nothing at all below the sample
floor. It was exactly the argument's difference this line predicted:
`typical_week_for` was already running on every review and pointed forwards at
the draft, and the fix was to point the same call backwards. The paragraph
below records what it was.
Finishing four of nine is reported as a rate (S6's, and honest), but nothing
holds that nine against what his weeks actually hold, so the two readings of the
same number stay indistinguishable — the exact confusion this story exists to
resolve. The figure needed is already computed: `typical_week_for` runs on every
review, pointed forwards at the draft rather than backwards at the week.

**Requires:** the comparison the draft already makes, applied to the week being
reviewed. No model, no field, no new read — an argument's difference.

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

**Verdict: works**, moved from *bends* on August 20, 2026, in v3's *The day*
release. The half this entry already called genuinely good is untouched;
what it named as missing — *"no evening surface, no prompt"* — now exists.

`reads.closing_for` asks in the evening, on today only, until the record is
written. It reports what the day held using `planned_in_week` for a one-day
window — the same borrowing `typical_day_for` does, because D2 says two
definitions of *what I got through* would drift — and it reports a released
pin **apart from** what is still open, since "I decided this wasn't for today"
and "I never got to it" are different facts.

**It cannot close a day retroactively**, deliberately: a prompt on a past day
asks somebody to reconstruct one, and this record is worth reading in six
months precisely because it was written while it was still true. A day nobody
answered closes unclosed, which is itself a fact.

**The hour is the server's**, in the owner's own zone, read once at the request
boundary — so the client has no time of its own to reason about and cannot
disagree about whose evening it is.

~~**One limit, flagged rather than buried.** The third absence this entry
listed was *"no reminder"*, and that is still true.~~ **Closed the same day.**
`send_closing_nudge` is an evening email carrying what the day held and a link
to it, asking the same read the page does so the two cannot disagree about what
the day held or whether it has already been written.

**Off by default, unlike the digest**, and that had a published consequence
rather than only a product one: `/privacy/` said in live text that *"the one
recurring message is the daily summary"*, which a second one makes false. The
page was amended in the same change, and two tests hold it — one pairing the
page's *off by default* against the model's default, and one asserting the old
sentence is **gone**, since a positive test would have passed with it still
sitting beside the new paragraph.

So all three of this entry's original absences are closed: the evening surface,
the prompt, and the reminder.

~~**Requires:** a closing ritual with a time-aware nudge.~~

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
> being asked to. `loose_ends` (`review/reads.py:598`) gives the review a pile
> that ages again: **unanswered questions** carrying `asked_on`, **commitments
> read out of her own writing and never accepted or dismissed** carrying
> `proposed_on`, and overdue work. *"Four things have been waiting eleven days"*
> is once more a true sentence about this product, with a different noun in it.
> The box stays as a record of the question, since the answer arriving from a
> plan that never mentioned this story is the interesting part.

**Verdict: works**, moved from *bends* on August 20, 2026. The pile exists, the review shows
it with its dates, and she can deal with it — the section links her to `/mind/`
to do it (`ReviewRoute.tsx:1070`, *"Decide them in Second Mind"*). The journey
completes across two surfaces.

~~**What still fights her is the second surface.**~~ **Half of that closed on
August 20, 2026**, in v2's increment 6, and the refusal it rested on turned out
to be narrower than it read. A question carries **no review window** — nothing
expires, nothing ripens — where a proposal is stamped when it is shown, so
answering one from another surface cannot disturb the machinery that interprets
silence. Two verbs now do it in place: `mind/api_v1.py:175` records *"I settled
this"* and `:190` records *"this was never a question"*, both through the
knowledge core's own services, so a question answered from the planner records
exactly what one answered from `/mind/review/` does.

~~**What is left is the rest of the pile.**~~ **Closed August 20, 2026 —
verdict: works.** Four session-only routes on the knowledge core's own router
(`mind/api_v1.py`) answer a proposed commitment (accept / not a commitment) and
a recurring name (confirm / not a thing), through that core's own services, so
the record is identical to the same decision made from `/mind/`. *"Decide them
in Second Mind"* is gone, and a test asserts its **absence** — a positive one
would have passed with the link still beside the new buttons. The numbers
update in place because each verb invalidates the week.

**The reason it was "only the same treatment" was checked rather than
assumed.** Increment 6 was safe because a question carries no review window;
`first_surfaced_at` turns out to belong to `ConnectionHypothesis` alone, so
neither `Facet` nor `ConceptCandidate` has one either, and D6 stays
undisturbed. What the old line said still stood: So she can deal with *some* of what the review
tells her without leaving it, which is a bend rather than a block — and the
remaining half needs no new decision, only the same treatment. The review is not inert either way: `ReviewRoute.tsx:888` pins
a task to today and `:867` completes or reopens the review itself — both through
the owning service rather than a review-shaped write path, which is the shape the
remaining rows should copy. **Both numbers have now drifted twice** — they were
`:147` and `:896` before the kestrel pass and `:710` and `:689` before this one,
moved each time by work in the file rather than by anything changing meaning.
That is the rule at the top of this document catching itself, twice, and the
argument for citing a function's own line rather than a call site inside a
component that grows.

**Requires:** the same treatment for the other two rows — an unaccepted
commitment and a recurring name — through the owning core's services, which is
the shape both the questions and the pinning already take. ~~Deciding whether
deciding-in-place is worth opening the read-only rule~~ is answered: it was
never that rule. The review still holds no write path of its own, and every verb
on it calls the core that owns the record.

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

**Verdict: works**, moved from *bends* later the same day it moved from
*impossible* — both on August 20, 2026. The previous
entry said everything this story needed existed **except a way in**, and named
the absence precisely: a model, a service, a read and a Day payload, with no
form and no endpoint. V2's increment 1 built the way in.

**Sunday can decide now.** `PUT /api/v1/weeks/{day}/intention`
(`review/api_v1.py:710`) is the write path that did not exist, and the review's
forward half carries the box that calls it. **And Wednesday knows**:
`DayRoute.tsx:922` renders the week's intention under the compass, which is the
half that reached `schema.ts` and no component for a fortnight.

~~**What it still bends on is the second clause**~~ **— closed August 20,
2026, verdict: works.** The week payload now carries the *reviewed* week's own
intention, and the review states it above the numbers rather than beside them,
because it is the thing they are meant to be measured against. A week nobody
named says nothing rather than showing an empty heading.

**The test worth having is the one that would have passed by accident**:
`draft.intention` has been in that payload since v2's increment 1, so reading
*an* intention proves nothing — two different sentences, and the assertion is
that the reviewed week gets its own.

**One judgement, flagged rather than buried.** The done-means says the review
*can ask*; what it now does is hold the days against the intention so a person
can. The entry's own statement of the gap — *"nothing looks back at a finished
week and holds its days against what it was for"* — is false now, which is why
this scores as *works*. A review that **poses** the question is the briefing in
`clarice-v3-plan.md`'s *first question* release, not this story. What the old
line said still stood: Every ingredient is
present — `DailyFocus` has the days, `WeeklyIntention` has the sentence, and
`review/reads.py` already computes planned against met — so this is a read
nobody has written rather than anything missing.

**Requires:** a retrospective that reads the intention beside the week's own
days. No model, no service, no field.

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
increment 4 anchors retrieval against — `brief_for` (`lists/projects.py:117`)
returns nothing for a project without one, on purpose, because an unanchored
query is a ranked-by-coincidence panel. Optional, and staying optional: requiring
it would put a writing task in front of somebody who only wants to group three
areas.

**What still fights him:** notes and the abandonment condition have no home, so
*"what would tell him it went wrong"* goes into the purpose text or nowhere. It
survives — plain text takes anything — but the abandonment condition is then
indistinguishable from the ambition, which is precisely the distinction the story
is about, and nothing can ever read one without the other.

**A fourth field arrived on August 20, 2026 and it is not one of the three.**
`Project.desired_outcome` (`lists/models.py:468`) says *what done looks like*,
where purpose says *why*; a project can also now be **paused**
(`lists/models.py:487`), which is the third state a workspace needed. Both are
real additions to the workspace and **neither is the abandonment condition**, so
this story's gap is exactly where it was. Recorded because a project page that
has grown two fields looks from a distance like a story that moved.

Whether the outcome *absorbs* the abandonment condition — what done looks like
against what going wrong looks like — is D4 in
[`planning-assistant-v2-plan.md`](planning-assistant-v2-plan.md), and is open.
If it does, this story's remaining requires is one field rather than two.

**Requires:** the remaining two of the three — notes, and an abandonment
condition that is its own field, unless D4 folds the second into the outcome.

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
from projects"* stopped being true at `review/reads.py:27`, and
`upcoming_constraints` (`review/reads.py:671`) reads project deadlines into the
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

**Re-read against v2 and unmoved, August 20, 2026.** The project workspace
gained a desired outcome and a paused state, and the weekly ritual gained
outcomes that carry a project and snapshot its title
(`review/models.py:267`) — so a project's *life* is better recorded than it was.
None of that is what this story asks for. `services.complete_project` still
sets two fields and writes no record, and nothing reads a project's history back
at the moment it ends.

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

~~What still bends is reach. It searches **notes only** — tasks, days and reviews
are outside it — and reaching the day a note was written still means clicking
back a week at a time.~~ **Both halves of that sentence are now stale, and the
verdict is unchanged anyway.** Corrected August 20, 2026 rather than left, since
this file's own rule is that a citation which no longer resolves is how it
became misleading while every sentence still read as evidence.

**Reach widened**, in `lapwing`: `/mind/search/` answers in three sections —
notes, tasks and days — from one box, and `GET /api/v1/search` serves the same
thing.

**Landing on a date is done**, in v3's *The day* release. `/app/calendar` is a
month of open tasks by due date and days that have words in them, both
neighbours on every response, and every square links to `/app/day/:date` —
which had no UI entry point at all until then. The Day page links to it, and a
test holds that link, because an unreachable route is the same gap wearing a
nicer name. Day search results already linked to their own date, so what this
adds is reaching a date **nobody searched for**.

**What still bends, and why the verdict does not move:** the done-means asks
for results spanning *sources and reviews* too. Reviews are simply outside the
index. **Sources do not exist** — there is nothing to attach an article to,
which is S15's whole entry and its own `Source` model. Search's fifth
increment, the nine fields deferred by name, is the rest of the reach.

**Requires:** ~~a way to land on a date~~ — and the one that remains: **reach
across sources and reviews**, which waits on S15 for the first noun. Ranking
has not been on this list since August 18.

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

**19 stories: 3 work, 10 bend, 6 impossible.**

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
  planning and projects still only bend.
- **After v2's first eight increments, no planning story is impossible.** S9 was
  the last one, and it moved when it got a form. What replaced that pile is
  narrower and more awkward to be pleased about: **three stories are now one
  clause short of *works***, and in each case the missing clause is a read
  nobody has written rather than a model nobody has built. S3 needs the draft's
  own comparison pointed backwards at the week being reviewed; S9 needs the
  intention held against that week's days; S7 needs two more rows treated the
  way its questions now are.
- **A one-clause gap is not a small gap, and this document should not pretend
  otherwise.** *Works* means a real person could do the whole journey today, and
  a journey that stops one step short stops. What the count does say is that the
  remaining work is reads over records that already exist — which is a different
  and cheaper kind of remaining than the one this document opened with.

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
  abandonment condition *(a desired outcome and a paused state shipped in v2 and
  are neither — S10, and D4 asks whether the outcome absorbs the condition)*,
  retrospective *(S12)*
- ~~Intentions above the day~~ — **shipped whole in v2's increment 1**, model,
  service, write path and render *(S9)*; reviews above the week *(S8)*

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
