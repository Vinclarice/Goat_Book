# Clarice — design and delivery principles

This is the project's short set of working standards. It records practices
already visible in the codebase or required by the product's core promise; it
is not a wish list. A principle should make a design decision easier, improve
review, or prevent a previously expensive class of mistake. Otherwise it does
not belong here.

The roadmap decides **what** to build. These principles guide **how** it is
designed, implemented, reviewed, and verified.

## Core planning philosophy

Clarice plans and delivers work through four mutually reinforcing practices:
test-driven development, vertical slices, lightweight domain-driven design,
and reversible decisions. They constrain AI-assisted implementation toward a
coherent, testable increment of the product rather than a collection of
plausible-looking code.

### Deliver vertical slices

Plan the smallest end-to-end path that lets a person accomplish a real outcome:
interface, API, domain rule, stored data, and verification where each is
needed. Do not complete all frontend, backend, or database work in isolation
when a thinner usable path can reveal a mistaken assumption sooner.

For example, Bittern validates connect → capture → safe retry → Inbox before
share sheets, sophisticated settings, or richer mobile features. A vertical
slice has an observable acceptance condition, not just a list of technical
tasks.

### Use domain-driven design, lightly

Use the product's actual language and give each meaningful concept a clear
owner, life cycle, and source of truth. Before adding a field or screen, ask
whether it belongs to a Task, Capture, Idea, Routine, Routine Occurrence,
Daily Entry, Daily Focus, or a new explicitly named concept.

This is a clarity practice, not an instruction to introduce DDD frameworks,
ceremony, or a large class hierarchy. The goal is to prevent one convenient
model—especially a task—from quietly absorbing unrelated planning and
second-brain behavior.

### Prefer reversible, evolutionary decisions

Choose the smallest decision that tests the current product hypothesis while
preserving future options. Make an irreversible choice only when real usage,
data, or a stated safety requirement makes its cost worthwhile. Document the
choice and its reconsideration trigger.

Examples include optional API fields before a client rollout, additive
migrations before a schema removal, manual Idea links before a mind-map, and
human-confirmed planning assistance before autonomous AI changes. This does
not mean avoiding decisions; it means committing deeply only when evidence
justifies it.

## Delivery practices

### Make behavior executable first

Use test-driven development for deterministic behavior: domain rules, API
contracts, permissions, calculations, migrations, and regressions. Express
the desired user-visible behavior in a failing automated test, implement the
smallest change that makes it pass, then improve the code while the test keeps
the behavior protected.

TDD is a discipline, not ceremony. Do not manufacture fragile unit tests for
purely visual exploration; use component, browser, or manual rendered checks
at the appropriate boundary instead. For a production bug, first capture the
failure in a regression test whenever it can be reproduced safely.

### When a test fails, diagnose before editing either side

A red test means the code and the expectation disagree. Decide which one is
wrong before changing either, because both happen and they need opposite
responses.

Changing an assertion to reach green is legitimate only when the contract
genuinely changed — and then it is part of the story, named in the commit
alongside what else moved. Quietly relaxing an assertion to match new
behavior is how a suite stops being evidence of anything.

Two failures from the same afternoon show the difference. Making `time_zone`
required on the preferences payload broke four tests that posted without it:
the contract really had changed, so the expectations were what needed
updating. Separately, a digest test asserted that two users would both be
mailed at one instant — that test was simply wrong about the domain, because
users twelve hours apart are never inside their morning windows
simultaneously. Reaching for the same fix in both cases would have hidden the
second.

This is the sharpest hazard in AI-assisted work. A test written after the
implementation fails for reasons that turn out to be the test's own, and the
temptation is to treat every red as a stale expectation.

### AI assists; the project owns the result

AI may draft code, tests, migrations, documentation, and alternatives. It does
not replace a clear acceptance condition, review of the actual diff, or
verification in the real project environment. Treat explanations from an AI as
leads to check, not evidence that a change works.

For every AI-assisted change:

1. State the intended behavior and boundaries before implementation.
2. Inspect the changed files for unintended scope, security, and data effects.
3. Run the smallest relevant automated checks while iterating, then the full
   suite before calling the change done. A green focused run beside a red
   full run is the ordinary result of touching a shared contract, not a
   surprise — adding one required API field turned a passing ten-test file
   into four failures elsewhere. Crossing an API, migration, authentication,
   build, or deployment boundary makes the broader run mandatory.
4. Record material design decisions in `design/` so a later contributor does
   not have to infer intent from generated code.

### Prefer small, verifiable changes

One change should have one understandable purpose and a proportionate test or
verification story. Separate contract changes, migrations, UI work, and
deployment changes when doing so makes rollback, review, and diagnosis safer.
Do not split a coherent atomic fix merely to make commits tiny.

This pulls against vertical slices, and the resolution is: **slice the work,
split the commits.** Plan and verify the thin end-to-end path — that is what
reveals a mistaken assumption early — then land it as whatever sequence of
commits makes review and rollback safest. A migration that can be applied
ahead of the code using it earns its own commit. A schema change and the
client regenerated against it do not, because separating them produces a
commit that cannot build.

## Application design

### Inject the clock; do not freeze it

Pass dates and times into domain logic rather than reading the current time
inside it. `bucket_for(due_date, today)` is testable without time-freezing
tools because its clock is explicit. At application boundaries, the server
interprets dates according to the product's time-zone policy; clients render
that interpretation.

An entry point must read the clock somewhere — a request, a management
command. Read it once, at that edge, and pass the resulting date down;
`send_due_digest` calls `timezone.now()` once and hands each recipient's
local date to the same injected-date functions the agenda uses.

That policy is now per user: each account carries a `time_zone`, and
day-boundary logic reads the zone activated for the request rather than a
global setting. `settings.TIME_ZONE` is the anonymous fallback, not the
definition of anyone's day.

### The server owns business meaning; clients render and submit intent

Clients display task, capture, and date decisions made by the server rather
than each inventing its own rules. They submit a person's intent through a
defined API. The server remains the authority for ownership, status changes,
recurrence, validation, and date semantics.

### Keep reads and writes distinct

Read-side code answers questions; write-side services enforce invariants and
make mutations. For example, agenda queries belong in `agenda.py`, while task
and capture changes belong in service functions. This is not a demand for a
separate CQRS system—only a clear home for rules and side effects.

### One rule, one authoritative definition

Give a rule one source of truth. If it must be mirrored across server and
client, name the authority, explain the synchronization boundary, and protect
it with tests. `WEEK_HORIZON_DAYS` is a model: a shared named definition is
better than independently repeated numbers.

### Model the domain before the view

Do not merge concepts merely because they can share a screen. A task
recurrence, routine, routine occurrence, daily focus, idea relationship, and
calendar block should share data only when their life cycles and rules are
actually the same. This keeps the Daily Page from becoming an overloaded task
form.

### Preserve durable records and meaningful history

Completed tasks, daily-focus selections, routine occurrences, and reviews
need enough historical context to explain later metrics. Do not silently
rewrite the past because a live task, routine, or template changes. A record
may reference current data, but the relevant event and its meaning must remain
recoverable.

## Reliability and safety

### Capture is durable before it is clever

Never lose a person's thought, draft, or queued action to a refresh, network
failure, expired token, or background job failure. The mobile capture queue
may delay delivery, but it must retain the text and its retry identity until a
meaningful outcome is known.

### Retry-sensitive writes are idempotent

When a client cannot know whether a request succeeded, the same retry must not
create a second result. Use a client-generated identity, an explicit API
contract, and a database constraint for the guarantee. Bittern M1's
owner-scoped `Idempotency-Key` capture contract is the reference example.

### Automations propose; people decide

Carry-forward, routine generation, review summaries, and eventual AI may
prepare or recommend work. They must not silently change a person's
commitments, ideas, or history. Make automated outcomes visible, reversible
where practical, and explicit about the evidence used.

### Failure is recoverable and visible

Keep user work, state what happened in plain language, and give a sensible
next action. A blank route, invisible email failure, silently discarded
capture, or generic error with no recovery path is not an acceptable steady
state.

### Ownership, isolation, and privacy default to safe

Every owner-scoped, ID-taking surface gets a direct isolation test; tests that
prove one user cannot read or mutate another user's record are a first-class
part of the feature. Send the minimum data needed to support, monitoring, and
future AI. Sharing is an explicit product capability, never an accidental
default.

### Evolve data and APIs without stranding clients

Prefer additive migrations and compatible API changes: optional request
fields, additive response fields, and staged rollouts. When data eventually
must be reshaped or removed, use an expand–migrate–contract sequence with a
documented compatibility window and recovery plan. Do not make a destructive
schema change just because the current client can be updated at the same time.

### Guards fail closed; comments preserve why

Authentication, authorization, ownership checks, and validation reject an
uncertain request rather than granting access. Comments should explain the
non-obvious reason, trade-off, or invariant—not narrate syntax that the code
already states.

## Evidence as the product grows

### Production truth beats local confidence

Tests establish intended behavior; browser smoke checks, deployment evidence,
and error monitoring establish what users receive. Treat the served build,
not local source, as the authority when diagnosing production behavior.

### Measure behavior before optimizing it

Define a metric and observe real use before adding ranking, redesigning
navigation, or automating planning. Completion trends need a durable definition
of a planned commitment; habit trends need routine-occurrence records. Avoid
optimizing an imagined workflow.

## Keeping this useful

Review this document when a new domain, client, or public-facing capability
introduces a recurring design decision. Add a principle only after it has a
concrete project example or prevents a named risk. Remove or rewrite a
principle that no longer guides real choices.
