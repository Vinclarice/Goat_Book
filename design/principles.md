# Clarice — design and delivery principles

Working standards already visible in the codebase or required by the product's
core promise, each kept with the example that makes it usable. The roadmap
decides **what** to build; these guide **how** it is designed, implemented,
reviewed and verified.

## Scope: delivery practice governs everything here; design authority splits

The split is not by repository — there is one, and `src/mind/` is in it. It is
by *what kind of rule*.

**How work is delivered: this file, everywhere in this tree.** `src/mind/` is
tested in this CI, deployed by this playbook and read by whoever reads the
rest, so exempting it would mean two standards for one repository, which is how
one of them quietly becomes optional.

**How the knowledge core is designed: Second Mind's own `docs/`**, still at
`C:\dev\Clarice_secondmind`, documents only now. `design-concept.md` remains
the authority on what each core owns, on salience and on the attention policy.

Several principles here would actively obstruct that design, and that is
expected rather than a problem to reconcile. The knowledge core rejects
[`architecture-trajectory.md`](architecture-trajectory.md) §4's charter test —
its node-plus-facet model is the opposite of "a concept earns its own model
when it has a different life cycle" — and it answers differently on typed
relations and on how absolute "automations propose" should be. Those
principles were derived inside the task domain and are correct there; they are
not general law, and `src/mind/` sitting in this tree does not make them so.

**One question settles it: is the rule about how you work, or about what you
build?** A test written after the fact is wrong in either core. A new model in
`src/mind/` answers to `design-concept.md`; one in `lists/` answers to §4. Do
not weaken this file to accommodate the knowledge core, and do not cite it
there as design authority.

## Core planning philosophy

Four mutually reinforcing practices — test-driven development, vertical slices,
lightweight domain-driven design, reversible decisions — constrain AI-assisted
implementation toward a coherent, testable increment of the product rather than
a collection of plausible-looking code.

### Deliver vertical slices

Plan the smallest end-to-end path that lets a person accomplish a real outcome:
interface, API, domain rule, stored data, and verification where each is
needed. Do not complete all frontend, backend or database work in isolation
when a thinner usable path can reveal a mistaken assumption sooner. Bittern
validated connect → capture → safe retry → the text arriving on the server
before share sheets, settings, or richer mobile features. A slice has an
observable acceptance condition, not just a list of technical tasks.

**A slice is not closed while nothing calls it.** Built and dark is a deferral
wearing a completion's clothes: the tests pass, the code reads as live, and the
behaviour has never once happened. This project keeps rediscovering it —
`/healthz` with nothing polling it, detectors built and never invoked,
`Backends.isSplit` switched by a flag no shipped build has ever passed,
`resolve_retrieval_miss` with no caller and no reader, `Attachment` with no
upload path, `THREAD_ARTICULATED` declared in the first migration and never
written. The August 21 inventory found ten more in `src/mind/` alone, and the
two worst were the two that read most convincingly as working. `revise` has no
door, so `Revision` is empty in production and search's *superseded* branch is
decoration. And `mark_reviewed` is the only writer of **node-scoped** review
events, so `review_state` returns zero for every node and the whole spaced
schedule has never run — while production holds two `reviewed` rows from the
live connection-review page, owner-scoped, feeding nothing. **A seam can look
alive because something adjacent to it is.** Counting rows was not enough;
reading which column they filled was.

So: **check for a caller, not for existence.** `CLAUDE.md` says the same thing
one layer out — *a seam that is not switched on is not a seam; check the build
configuration, not the branch* — and this is its code half. Something
deliberately built one step ahead is still fine, and the second factor is the
model: *enrolment before enforcement, deliberately inert*, said out loud in
`settings.py` with the increment that switches it on named. **The rule is that
the deferral has to be declared.** Undeclared, it gets a named trigger or a
deletion — and by *Prefer reversible, evolutionary decisions* below, a trigger
that cannot fire is a refusal, which is an honest answer here too. Deleting the
design note loses nothing: the note is the part that was load-bearing.

### Use domain-driven design, lightly

Use the product's actual language and give each meaningful concept a clear
owner, life cycle and source of truth. Before adding a field or screen, ask
which existing concept it belongs to — `Item`, `RecurringCommitment`,
`Routine`, `RoutineOccurrence`, `DailyEntry`, `DailyFocus`, `WeeklyReview`, or
the knowledge core's `Node` and `Facet` — or whether it needs a new, explicitly
named one.

This is a clarity practice, not an instruction to introduce DDD frameworks or a
large class hierarchy. The goal is to stop one convenient model — especially a
task — from quietly absorbing unrelated planning and second-brain behavior.

### Prefer reversible, evolutionary decisions

Choose the smallest decision that tests the current product hypothesis while
preserving future options, and document its reconsideration trigger. Optional
API fields before a client rollout, additive migrations before a schema
removal, human-confirmed planning assistance before autonomous AI changes. Make
an irreversible choice only when real usage, data or a stated safety
requirement makes its cost worthwhile: commit deeply, but only on evidence.

**A trigger that cannot fire is a refusal, and should be recorded as one.**
Documenting a reconsideration trigger is what keeps a deferral honest, and it
stops working when the trigger is gated on evidence this project cannot
generate — several months of weekly reviews measured against one person, a
corpus a single user will not reach, a cohort that does not exist. Three
separate gates now say *may never fire* in their own text. When that is the
true state, write a refusal, which cannot go stale, rather than a deferral,
which will.

## Delivery practices

### Make behavior executable first

Use test-driven development for deterministic behavior: domain rules, API
contracts, permissions, calculations, migrations, regressions. Express the
desired user-visible behavior in a failing test, implement the smallest change
that makes it pass, then improve the code while the test protects it. For a
production bug, first capture the failure in a regression test whenever it can
be reproduced safely.

TDD is a discipline, not ceremony. Do not manufacture fragile unit tests for
purely visual exploration; use component, browser or manual rendered checks at
the appropriate boundary instead.

### When a test fails, diagnose before editing either side

A red test means the code and the expectation disagree. Decide which one is
wrong before changing either, because both happen and they need opposite
responses. Changing an assertion to reach green is legitimate only when the
contract genuinely changed — and then it is part of the story, named in the
commit alongside what else moved. Quietly relaxing an assertion to match new
behavior is how a suite stops being evidence of anything.

Two failures from the same afternoon show the difference. Making `time_zone`
required on the preferences payload broke four tests that posted without it:
the contract really had changed, so the expectations needed updating.
Separately, a digest test asserted that two users would both be mailed at one
instant — that test was simply wrong about the domain, because users twelve
hours apart are never inside their morning windows simultaneously. Reaching
for the same fix in both cases would have hidden the second.

This is the sharpest hazard in AI-assisted work: a test written after the
implementation fails for reasons that turn out to be the test's own, and the
temptation is to treat every red as a stale expectation.

### AI assists; the project owns the result

AI may draft code, tests, migrations, documentation and alternatives. It does
not replace a clear acceptance condition, review of the actual diff, or
verification in the real environment. Treat an AI's explanation as a lead to
check, not evidence that a change works.

1. State the intended behavior and boundaries before implementation.
2. Inspect the changed files for unintended scope, security and data effects.
3. Run the smallest relevant checks while iterating, then the full suite before
   calling the change done. A green focused run beside a red full run is the
   ordinary result of touching a shared contract — adding one required API
   field turned a passing ten-test file into four failures elsewhere. Crossing
   an API, migration, authentication, build or deployment boundary makes the
   broader run mandatory.
4. Record a material design decision **where the decision lives** — a comment
   at the site carrying the reason, and a document in `design/` only when it
   spans files or has to be argued rather than stated.

   **A document is a standing cost, and this one is measured.** `design/` holds
   around fifty files; code comments across the tree cite them in their
   hundreds; an index document exists whose whole job is arbitrating which
   document owns which fact; six commits went to correcting stale statuses; and
   one August afternoon reduced 11,002 lines to roughly 4,000 without breaking a
   citation. The premise this rule was written on — a later contributor
   inferring intent from generated code — is not true here, and
   [`README.md`](README.md) records that those comments already state in full
   the reasoning they cite a plan for. The documents are provenance, not
   content.

   ~~251 code comments~~ — **struck August 28, 2026**, in both places this
   paragraph said it. It had drifted to 257 files and 631 mentions, and it is a
   number that only ever goes up. [`README.md`](README.md) owns the recount
   command; this file states the cost, not its magnitude.

### Prefer small, verifiable changes

One change, one understandable purpose, a proportionate verification story.
Separate contract changes, migrations, UI work and deployment changes when that
makes rollback, review and diagnosis safer; do not split a coherent atomic fix
merely to make commits tiny.

This pulls against vertical slices, and the resolution is **slice the work,
split the commits.** A migration that can be applied ahead of the code using it
earns its own commit. A schema change and the client regenerated against it do
not, because separating them produces a commit that cannot build.

## The person using it

Every principle in the next section is about the correctness of the substrate,
and while there was a substrate to build that was the right emphasis — it is
now genuinely good, in several ways `commercial-blueprint.md` calls better than
commercial average. This section exists because **nothing in this file spoke
for the person at the keyboard**, and it showed: `product-stories.md` scores
ten journeys as *bends*, meaning the capability exists and the product fights
the person, and a bend has never had to compete for time with anything.

These are task-core design rules and answer to the same split as the rest of
this file; see §Scope.

### A bend is a defect

A journey the product fights is not a lesser thing than one that is broken.
`product-stories.md` sorts journeys into works, bends and impossible, and only
the third pile has ever read as work — which is how task priority, named
*essential to the thesis* on August 12, 2026, was still absent from
`lists/models.py` eight days later, and how `lists/api.py`'s PATCH still
accepts six fields with `list` not among them, so a misfiled task stays
misfiled. Neither was blocked. Neither was argued against. Neither competed.

A bend has a cause, the cause is nameable in one line, and naming it is most of
fixing it.

### The main surface can do the main thing

`daily-operating-system-vision.md` names the Daily Page **the main working
surface**. It cannot complete a task, and the reason recorded at
`DayRoute.tsx:120` is that a Complete button "would mean reimplementing the
agenda's mutation and undo beside it."

That cost is real and it is not a veto. *One rule, one authoritative
definition* below says exactly how to pay it — name the authority, explain the
synchronization boundary, protect it with tests. A principle that forbids the
home screen its own verb has stopped guiding a choice and started making one.

### Felt friction is evidence

For a product with one user, n=1 is not a sampling problem — it is the
population. Friction you have hit yourself is observed use, and no
instrumentation having recorded it does not make it imagined. The rule against
optimizing an imagined workflow is about workflows **nobody has performed**;
reaching a day twelve weeks back by clicking "the week before" twelve times is
not imagined.

## Application design

### A new model answers to the charter, and the charter is not here

**Before adding a model to either core, read
[`architecture-trajectory.md`](architecture-trajectory.md) §4** — eight rules, an
owner at birth, snapshots against renames, deletion behaviour, and the test that
decides the question at all: *a concept earns its own model when it has a
different life cycle, not when it has a different name.* The knowledge core's
equivalent authority is `design-concept.md` in the Second Mind documents.

**Linked and deliberately not moved here — August 26, 2026.** §4 belongs in this
file by subject; it stays where it is because **code across the tree cites it as
`architecture-trajectory.md` §4** — ~~around forty-five comments~~, seventy-seven
files at the August 28, 2026 recount, and the number is
[`architecture-trajectory.md`](architecture-trajectory.md) §8's to keep, not
this file's — and several models carry rule-by-rule compliance against those
numbers. Moving the text would leave every
one of them citing a section that is not there — and *the file resolving is not
the same as the section resolving*. What the move was for was discoverability,
and this paragraph buys that for nothing, which is the corpus's own rule about
linking to an owner rather than restating it.

### Inject the clock; do not freeze it

Pass dates and times into domain logic rather than reading the current time
inside it. `bucket_for(due_date, today)` is testable without time-freezing
tools because its clock is explicit. An entry point must read the clock
somewhere — a request, a management command — so read it once, at that edge,
and pass the date down: `send_due_digest` calls `timezone.now()` once and hands
each recipient's local date to the same injected-date functions the agenda uses.

That policy is per user. Each account carries a `time_zone` and day-boundary
logic reads the zone activated for the request; `settings.TIME_ZONE` is the
anonymous fallback, not the definition of anyone's day.

**Passing the date down is not enough where there is no request.** Reads convert
their own timestamps — `timezone.localtime` and `localdate` read the *active*
zone, which the middleware sets and a management command does not have. So a
scheduled job must **activate the owner's zone**, not merely compute their date:
`clarice.scheduled_mail` composes inside `timezone.override`, and
`accounts.auth._resolve_scoped_token` does the same for token requests. Activate
where the owner first becomes known, rather than asking every read to remember —
six token endpoints each forgot to when the asking was a docstring.

**And whose clock is not always the reader's.** *Today* is a question about the
person looking; *which day was this written on* is a property of the record, and
must give the same answer to anybody, or to nobody at all in a nightly pass.
That second question is `clarice.clocks.day_for(owner, instant)`, which takes the
owner and the instant and nothing else. Both of the above were found the same
day, in code that had shipped and been scored as working.

**A fixture that picks a convenient hour has chosen the passing case.** Both
defects survived their tests for one reason: every fixture captured at UTC
midday, on the default zone, where all the clocks agree. Green over a clock
means nothing until a test runs in a zone that is not the setting, at an hour
where the dates disagree. Applies past clocks — wherever a test picks a value
freely, ask what the awkward value would have been.

### The server owns business meaning; clients render and submit intent

Clients display the task, capture and date decisions the server made rather
than inventing their own, and submit a person's intent through a defined API.
The server stays the authority for ownership, status changes, recurrence,
validation and date semantics.

### Keep reads and writes distinct

Read-side code answers questions; write-side services enforce invariants and
make mutations. Agenda queries belong in `agenda.py`, task and capture changes
in service functions. Not a demand for a separate CQRS system — only a clear
home for rules and side effects.

### One rule, one authoritative definition

Give a rule one source of truth. If a value must be mirrored — across server
and client, or as a fast flag beside the record that is really in charge — name
the authority, explain the synchronization boundary, and protect it with tests.
`WEEK_HORIZON_DAYS` is the model: a shared named definition beats independently
repeated numbers.

### Model the domain before the view

Do not merge concepts merely because they share a screen. A task recurrence,
routine, routine occurrence, daily focus, knowledge-core relation and calendar
block share data only when their life cycles and rules are actually the same.
This is what keeps the Daily Page from becoming an overloaded task form.

### Preserve durable records and meaningful history

Completed tasks, daily-focus selections, routine occurrences and reviews need
enough historical context to explain later metrics. Do not silently rewrite the
past because a live task, routine or template changed. A record may reference
current data, but the event and its meaning must stay recoverable.

## Reliability and safety

### Capture is durable before it is clever

Never lose a person's thought, draft or queued action to a refresh, network
failure, expired token or background job failure. The mobile capture queue may
delay delivery, but it must retain the text and its retry identity until a
meaningful outcome is known.

### Retry-sensitive writes are idempotent

When a client cannot know whether a request succeeded, the same retry must not
create a second result. Use a client-generated identity, an explicit API
contract, and a database constraint for the guarantee. Bittern M1's
owner-scoped `Idempotency-Key` capture contract is the reference example.

### Automations act reversibly; people decide what is durable

Carry-forward, routine generation, review summaries and AI may prepare,
recommend, and — where the act is **visible and undoable** — perform work
without asking first. Drafting a week, filing a note, proposing a due date: a
person who can see that it happened and undo it has not lost a decision, and
making them click yes first buys nothing but friction.

What still requires a person is anything **durable or destructive** — changing
a commitment, editing history, deleting, or anything that leaves no trace of
having been automatic. *Preserve durable records and meaningful history* is
unweakened by this and stays absolute. Automated outcomes remain visible and
explicit about the evidence used.

**Two guards, because "reversible" is the easiest thing here to claim falsely.**

- **Undo has to exist, not merely be conceivable.** Where there is no undo the
  act is not reversible and needs a confirmation, whatever it looks like in
  principle. This is the product trigger `roadmap.md`'s Track D has been asking
  *audit log and general undo* for since August 2, 2026 — it has now fired, and
  the scope of the automation is what sets the scope of the undo.
- **`daily-operating-system-vision.md`'s two rules are untouched.** No manual
  carry-forward and no duplicate task copies describe what the Daily Page *is*;
  they are not confirmation requirements that reversibility can satisfy.
  Automatically rescheduling everything left incomplete stays forbidden however
  cleanly it could be undone.

**Why the text changed and the practice mostly does not.** The previous form —
*automations propose; people decide* — shipped two versions of a planning
assistant with **no generation at all**, and that was a correct reading of it
rather than an over-cautious one. Read the change narrowly: it licenses acting
where the act is cheap to reverse, not deciding.

### Failure is recoverable and visible

Keep user work, state what happened in plain language, give a sensible next
action. A blank route, invisible email failure, silently discarded capture, or
generic error with no recovery path is not an acceptable steady state.

### Ownership, isolation, and privacy default to safe

Every owner-scoped, ID-taking surface gets a direct isolation test; proving one
user cannot read or mutate another's record is a first-class part of the
feature. Send the minimum data needed to support, monitoring and future AI.
Sharing is an explicit product capability, never an accidental default.

### Evolve data and APIs without stranding clients

Prefer additive migrations and compatible API changes: optional request fields,
additive response fields, staged rollouts. When data must eventually be
reshaped or removed, use an expand–migrate–contract sequence with a documented
compatibility window and recovery plan. Do not make a destructive schema change
just because the current client can be updated at the same time.

### Guards fail closed; comments preserve why

Authentication, authorization, ownership checks and validation reject an
uncertain request rather than granting access. Comments explain the non-obvious
reason, trade-off or invariant — they do not narrate syntax the code states.

## Evidence as the product grows

### Production truth beats local confidence

Tests establish intended behavior; browser smoke checks, deployment evidence
and error monitoring establish what users receive. Treat the served build, not
local source, as the authority when diagnosing production.

### Measure behavior before ranking or automating it

Define a metric and observe real use before adding **ranking or automation**.
An invented weighting is noise wearing a number, which is why the planning
assistant's confirmation-history ranking is gated on a sample floor rather than
shipped on a hunch. Completion trends need a durable definition of a planned
commitment; habit trends need routine-occurrence records.

**This is a rule about inventing rankings, not a licence to leave interface
friction alone.** It read as the second for a while, and with no analytics and
one user that made it unfalsifiable — no observation could ever qualify, so
every navigation and interface repair failed a test nothing could pass. See
*Felt friction is evidence*. Avoid optimizing an imagined workflow — one nobody
has performed; do not wait for a metric before fixing one you perform daily.

## Keeping this useful

Review this document when a new domain, client or public-facing capability
introduces a recurring design decision. Add a principle only after it has a
concrete project example or prevents a named risk. Remove or rewrite one that
no longer guides real choices.

**Revised August 20, 2026, and nothing was deleted.** The review asked whether
these principles had begun limiting the product rather than protecting it, and
the answer was that the file's problem was omission and three framings, not
bloat — the delivery practices, the isolation tests, the injected clock and the
durable-record guarantees are why this codebase is what it is, and they get
*more* valuable as the product grows, not less. What changed: **§The person
using it** was added, because nothing here argued for the person at the
keyboard and the score showed it; *measure behavior* was narrowed to ranking
and automation, having become unfalsifiable with one user and no analytics;
*automations propose* became *automations act reversibly*, having shipped two
planning assistants with no generation at all; and recording design decisions
moved to the site of the decision, the later contributor it was written for
being nobody.
