# Clarice — Roadmap

Vince · active planning document · refreshed August 13, 2026

## Purpose

This is the forward-looking plan: what is active now, what is next, and
what has deliberately been deferred. It is not the implementation spec for
an item; write a focused file in `design/` once work is ready to start.

Every completed release — Albatross, Bittern, Crane, Dunlin — plus Release F
and the six unlettered lines of work that shipped alongside it, with their
deployment records and lessons, live in
[`roadmap-history.md`](roadmap-history.md). Keeping that record separate
makes this document useful when deciding what to work on next.

**Second Mind is a separate project and this file does not govern it** — see
the section immediately below. Knowledge-side work is no longer planned here.

The cross-cutting engineering and product standards used to deliver roadmap
work live in [`principles.md`](principles.md).

The multi-release ordering behind Crane and the releases after it, the design
constraints every new model has to satisfy, and the architectural directions
this project has explicitly refused live in
[`architecture-trajectory.md`](architecture-trajectory.md). This file stays the
authority on what is active and what is deferred; that one explains the order
and the reasoning, and does not schedule anything on its own.

## Second Mind is a separate project, and Clarice is downstream of it

**Decided August 13, 2026.** Second Mind lives in its own repository
(`C:\dev\Clarice_secondmind`) with its own design documents, its own
constitution, and its own test suite — 435 tests green as of that date. It is
**not** a module inside Clarice, not a bounded context hosted by it, and not
subject to this file, [`principles.md`](principles.md), or
[`architecture-trajectory.md`](architecture-trajectory.md). Its own
`docs/design-concept.md` is the authority for everything in it.

**The direction runs one way: Clarice is worked into Second Mind, not the
reverse.** The end state is one application with two cores — Second Mind for
knowledge, and Clarice's task system absorbed as a core named **Superlists**.
Second Mind's `docs/two-cores.md` is the authority on that merger, including
what does and does not survive it. Two consequences worth knowing here:

- **Clarice's knowledge half does not survive.** `capture.Capture` exists to
  hold untriaged text pending assignment; the node model does that without
  the debt. `capture.Idea` exists to hold retained material; that is what the
  graph is for — the conclusion `product-stories.md` already reached
  independently. This is also how the commercial audit's open question
  ("second brain: invest or retire?") resolves: `Idea` is retired because
  something better replaces it.
- **Clarice's commitment half does survive**, and is the reason the merger is
  worth doing: `Item`, `RecurringCommitment`, `ChecklistStep`, `Routine` and
  `RoutineOccurrence`, `DailyFocus`, `WeeklyReview`, `Project`, Area. The
  weekly review's honest denominators are the single strongest thing built
  here and are carried across intact.

**One defect to fix on the way in rather than port.** `_advance_due_date`
computes a recurring task's next occurrence from the previous *due date*, so a
monthly commitment due July 4 and completed August 10 spawns its successor due
August 4 — overdue at the instant it is created. Second Mind's design
specifies anchored and floating recurrence as distinct modes; this is the
floating case, and it should be fixed in the move.

**Nothing in this roadmap is cancelled by that decision.** Clarice keeps
running, keeps its users, and keeps being the working tool until the merger
actually happens; no merger work is scheduled here. What changes is that
long-horizon knowledge-side work in this file — Reference/Idea search, the
mind-map view, idea resurfacing, the second-brain direction in
[`daily-operating-system-vision.md`](daily-operating-system-vision.md) — is
now **superseded rather than deferred**, because it is being built properly
somewhere else.

`design/second-mind-core.md`, written earlier the same day, is deleted. It
proposed the opposite arrangement — Second Mind as a second core *inside*
Clarice, with actionability delegating to `Item` — and was wrong about the
direction. It is recorded here rather than kept, because a wrong charter left
in place is worse than an absent one.

## Current product baseline

Four releases are live. **Albatross** established the API-backed SPA and
Postgres foundation, then shipped task notes, subtasks, recurrence, Capture
triage and Ideas, password recovery, personal access tokens, CI, backups and
production hardening. **Bittern** added the Android capture client, per-user
time zones, and the session and failure-state gaps the web application still
had. **Crane** made the day the product: the Daily Page is the home surface,
practice is its own domain rather than a kind of task, repeating commitments
have an identity across their occurrences, and a weekly review reads the
record back against denominators that mean something. **Dunlin** settled the
commitment vocabulary: a subtask is a Checklist Step with its own life cycle,
a List is an Area that never completes, a Project is work that does, and
every model is owned at birth. The full record of each is in the history
file.

**Everything since Dunlin shipped without a release letter**, between August 6
and 12, 2026, and it is a substantial part of the current baseline rather than
a tail of small fixes: Project became a standalone workspace holding Areas; the
Bootstrap→Tailwind arc finished across the task list, Agenda and Archive, with
`site.css` retired outright; the Android client gained read *and* write on the
Daily Page and the Agenda behind a new scoped-token tier; local development
moved onto Postgres; and Release F shipped the second-mind discovery pass and
its first slice. All of it is deployed. The record is in
[`roadmap-history.md`](roadmap-history.md).

C2's recorded interface failure is fully closed as of Dunlin — the evidence and
its resolution are in the history file. What replaced it, five findings in
[`ui-second-pass-plan.md`](ui-second-pass-plan.md) (F1 through F5), is now
closed too. F1 shipped inside Dunlin itself; F2, F2a, F3 and F5 shipped
August 6, 2026, following the observational sitting recorded there on
August 3 that confirmed F2 and F3 rather than inferring them. Nothing named
in that brief is still open.

## B / C / D legacy — what those releases left open

Bittern, Crane and Dunlin all shipped and are verified in production.
Their deploy records, what each changed and taught, the production
verification markers, C2's interface evidence and the capture-tags decision
are in [`roadmap-history.md`](roadmap-history.md). The executable detail
stays in [`bittern-plan.md`](bittern-plan.md),
[`crane-plan.md`](crane-plan.md) and
[`release-d-plan.md`](release-d-plan.md), each of which now carries a status
header saying it is a record rather than a plan.

**This section is only what those releases left open**, collapsed here on
August 13, 2026 from three release sections that had become a second copy of
the history file.

### Three carried-in items, none of them schedulable work

Fourteen items came out of Bittern; eleven closed through Crane and Dunlin.
`crane-plan.md` §2 stays the authority on the full checklist.

- **A real production 500 reaching Sentry**, rather than only the controlled
  probe. Needs an actual incident, not a task — the same reasoning that
  rejected a permanent `/sentry-debug/`-style route as a verification method.
- **No Android emulator run.** This SDK install has no AVD and no way to build
  one without a multi-gigabyte download better done through Android Studio's
  own AVD Manager. Judged low-priority: everything M4 wanted a device for is
  answered twice over on real hardware — the SM-F966U pilot against
  production, and two SM-S928U1 sessions.
- **Release signing.** `app/build.gradle.kts` is wired for it; the keystore
  itself is deliberately left for Vince to generate by hand — a non-rotatable
  credential is the wrong thing for an agent to generate and momentarily hold.
  The exact command is in
  [`android-release-signing-plan.md`](android-release-signing-plan.md).

### Track D — Postgres-enabled features

Candidates. Each needs its own product trigger or focused brief before it
becomes work. Per-user time zones left this list on August 1, 2026 when both
halves of its stated trigger fired at once — a second active user in
Indonesia, and a real scheduling error caused by the global zone.

- **Full-text search over Clarice's own material.** `Item.text`, `Item.notes`
  and `DailyEntry`'s three fields, ranked. **This replaced Reference/Idea
  search on August 13, 2026**, when the Idea half left for Second Mind and did
  not come back. The commercial audit found no full-text search anywhere in
  the product — zero hits for `SearchVector`, `GinIndex` or `pg_trgm` — that a
  daily journal entry is not searchable by any means at all, and that no date
  picker exists to reach one by hand. That is a real gap in the half Clarice
  keeps, and unlike its predecessor it needs no discovery pass first.

  **Trigger: it has one now, which the old entry never did.** The old trigger
  was "enough retained material that finding something again is a felt
  problem" — anticipated, never observed, and unreachable because nobody
  accumulates in a store they cannot search. Daily entries are already
  written, already numerous and already unfindable, so the felt problem
  exists today. Note `idea_owner_status_idx` was added specifically for the
  search that left, and is now dead weight.

- **Audit log and general undo.** Use structured change records to make more
  than task completion safely reversible. **No trigger.**
- **Time blocking.** Model calendar ranges and prevent a user's blocks from
  overlapping at the database layer. **No trigger.**

This section has asked every candidate for a trigger since August 2, 2026,
"which is how a future candidate quietly becomes a plan." Two of the three
above have gone eleven days without one. Recorded rather than let pass: **a
candidate with no trigger is a candidate nobody wants yet**, and the honest
options are to find the trigger or to drop it, not to leave it accruing
significance by sitting in a list.

### Track E — folded into Later

Both Bittern items shipped: branded email with a rate-limited contact path
(B3), and production error monitoring (B4).

The one remaining item — **account export and deletion** — is the same item
as the one under "Remaining public-readiness work" below, and is tracked
there rather than in two places. The commercial audit raises it from a
feature to a legal blocker, with Sentry and Resend already processing user
data, and it is a trust precondition for anything holding personal material.

### Track F — Android capture MVP: complete

M1–M5 shipped August 1–2, 2026: a native Kotlin client that authenticates
with a personal access token, captures online or offline, accepts shares from
other apps, and delivers a durable encrypted queue in the background without
ever creating a duplicate. The device pilot ran against production — fifteen
captures across Wi-Fi, cellular, a mid-request radio switch and airplane mode
arrived as fifteen rows with fifteen distinct keys.

Its create-only scope was later widened by the full-client work recorded in
`roadmap-history.md`. **That direction is now an open question rather than a
plan**: the commercial audit recommends freezing native and going responsive
web, since its core assumption was falsified twice and iOS is entirely absent
— and the merger reopens the client question anyway. Nothing is scheduled.

**Two defects in the shipped client**, found by the commercial audit and still
unfixed: `CaptureQueue` has no lock, so `CaptureViewModel.submit()` racing
`CaptureWorker.doWork()` can lose a capture permanently; and the queue is not
excluded from device backup, so it rides cloud transfer while its Keystore key
does not, and unsent thoughts vanish silently on phone upgrade. Both are in
`commercial-blueprint.md` Part 1. **These are the one failure the app exists to
prevent**, and they outrank every open question above.


## Later — visible, not scheduled

### Sharing

- Shared lists with real-time updates.
- Conflict handling for concurrent edits.

These belong together. Do not start either until list sharing itself is a
deliberate product decision.

Two mechanism notes, recorded on August 2, 2026 so they are not rediscovered
from scratch when that decision is finally made. Neither is a commitment to an
approach, and both were proposed rather than evaluated. **Real-time without
Redis:** Postgres `LISTEN`/`NOTIFY` driving Server-Sent Events, which would
suit one small deployment better than adding a broker. **Granularity:** if
sharing happens, viewer / editor / co-owner is the obvious first split, and
naming it early matters because it decides whether permission is a column or a
table. That question sits close to row-level security, whose own trigger in
[`architecture-trajectory.md`](architecture-trajectory.md) §6 is this same
sharing work.

### Remaining public-readiness work

- Self-service signup with email verification.
- Rate limiting for capture.
- Account export and deletion, after deciding immediate deletion versus a
  grace period before purge.
- Privacy policy and terms of service.

Password recovery and adversarial per-user isolation tests are already done.

Two items left this list on August 2, 2026, having shipped without being
struck from it. **Transactional email** is live: `EMAIL_HOST` defaults to
Resend and the provider decision is recorded in
[`bittern-plan.md`](bittern-plan.md), so personal Gmail SMTP is no longer in
the path. **Rate limiting for signup** is done at the edge —
`infra/templates/nginx-clarice.conf.j2` throttles `/accounts/signup/` at 5r/m
alongside login, and that is the only signup route. Capture is still
unthrottled and stays on the list. Separately, the uncovered authentication
surface is `/`, a full login view the login/signup rate-limit block does not
match; that is a defect rather than a release item and is tracked in
[`architecture-trajectory.md`](architecture-trajectory.md) §6.

### Support for people who are signed in

B3 gave strangers a contact path and left users without one: the link is in
the Django shell's nav, and users live in the SPA. The person most likely to
have something worth reporting has the worst route to reporting it.

Not merely a missing link — asking someone with a session to retype their
name and email invites an address that isn't the one on their account, and
per-IP rate limiting is the wrong key once there is an identity to use. The
reasoning, and the argument for adapting `/contact/` rather than forking it,
is in [`bittern-plan.md`](bittern-plan.md).

**What would promote it:** B4. A user's report and a monitoring event are two
halves of one incident, and the version of this worth building — where a
signed-in report carries its own context — cannot be designed before there is
error monitoring to design it against.

### Public updates page

An unauthenticated page announcing what has shipped, written for people rather
than for the repository — closer to a short press release per release than to
a changelog. No account, no login wall.

**No broad roadmap preview.** The page does not publish tracks, Later items,
or what the next release might contain. The single exception is a specific
named feature already in development, which may be announced as coming.
Everything else is described only once it exists.

That exception needs a definition or it drifts back into promising. The
existing practice supplies one: a focused spec is written in `design/` once
work is ready to start, so a feature qualifies when it has that spec and work
has actually begun — not when it is merely wanted. A candidate sitting in a
Later list or a deferred-item table never qualifies.

Two things still to settle:

- **Where the text comes from.** The material exists: each release gets an
  annotated bird tag describing what shipped and how it was verified, and
  `roadmap-history.md` records the same at length. Both are written for the
  developer, and announcement-style writing is a different job from either.
  Expect to write the public version by hand and treat the tag and history as
  its sources, not its draft.
- **Which stack renders it.** This is unauthenticated, cacheable, and wants to
  be indexable, so it is a Django-rendered page rather than an SPA route, in
  keeping with the settled boundary that only the task UI is SPA-only.

**What would promote it:** there is currently nobody unauthenticated to read
it. This earns work when strangers can actually arrive — realistically
alongside self-service signup, or whenever a public `/contact/` page from B3
means the site has a public face at all.

### Mobile web experience

Making the browser application genuinely usable on a phone, as opposed to
merely surviving a narrow window. This is not the Android app: Bittern's
native client captures and nothing else, so every other thing you might want
to do from a phone — triage the Inbox, complete a task, read an Idea — happens
in the browser. “The Android app captures; the web app reviews” quietly
assumes the web app is reachable from a phone, and today it is not really.

**Measured starting point, not a guess.** Both shells already set
`<meta name="viewport" content="width=device-width, initial-scale=1">`, so the
foundation is there. Beyond that there are exactly two layout breakpoints: the
side navigation collapses at 760px and the workspace input row stacks at
768px. Those two numbers should agree and do not. Everything else is
desktop-first. B0 already has to confirm the navigation works at its mobile
disclosure breakpoint, so the first real evidence arrives with Stage 0.

Considerations to settle before this becomes a spec:

- **One responsive application, not a mobile site.** No `m.` host, no second
  codebase, no divergent templates. There is one API and one SPA; say this
  once so it is not reopened later.
- **The overlap with the native client is real and should be decided, not
  discovered.** Native earns its cost through launch speed, Keystore-backed
  token storage, WorkManager retries, and the Android share target. A capable
  installable web app can approximate the share target and an offline queue,
  less reliably. If mobile web lands well, M5 and parts of M3 deserve a fresh
  look rather than being finished out of momentum.
- **Sequencing against Crane — settled by events.** The argument was that a
  mobile pass done first would be redone for a surface that did not exist
  yet, and that done inside Crane the new surfaces would be mobile-aware
  from their first day. That is what happened: the Daily Page and the weekly
  review were each measured at a phone width as they landed. What was
  deferred rather than done is everything Crane did not build — the older
  surfaces, and the two breakpoints that disagree.

**What would promote it:** M4's device pilot. The moment captures arrive from
a phone daily, triaging from that same phone will be attempted, and the
friction becomes specific and observable. Treat it the way C2 is treated —
watch real failures rather than redesigning from a hunch.

**A measured finding, from Crane 1 slice 7.** This entry asks for observed
failures rather than a redesign from a hunch, and slice 7's phone pass
produced one with numbers attached. At 375px the Daily Page itself is sound —
no horizontal overflow, no control past the right edge, and writing, saving
and capturing all work. What it exposed is application-wide and older than
Crane: **touch targets are well under the ~44px both platform guidelines and
WCAG 2.5.8 ask for.** The Daily Page's buttons measure 32px and its "Edit
your compass" link 20px; the Agenda, which nothing in Crane touched, is worse
at 19–31px.

That is not slice 7's to fix. The height lives on the shared `Button`
component, so changing it restyles every page in the application — which
`crane-plan.md` §5 fences off, and which is the web UI overhaul's second pass
rather than a side effect of a smoke test. Recorded here, with the
measurements, so it is a finding rather than a feeling when that work starts.

**Note on scope, August 2, 2026.** The pilot has run, but the stated condition
is daily phone use producing observable triage friction, and one session is
not that — so this stays here rather than being promoted on a technicality.
What Crane carried is narrower than this item: a phone-viewport pass over
each new surface — the assembled Daily Page at slice 7, and the weekly review
at Crane 3 slice 10, both measured at 375x812 against the built bundle and
both clean. Triaging the Inbox, completing a task and reading an Idea from a
phone, and reconciling the 760px and 768px breakpoints, are all still here.
Crane made its own surfaces mobile-aware; it did not close this entry, and
the touch-target finding above is still the largest thing in it.

### Recorded candidates with no trigger yet

Three ideas salvaged on August 2, 2026 from an abandoned review branch, whose
draft was ninety commits stale and whose every other proposal had either
shipped or been re-planned with better reasoning. These three had never been
written down anywhere in `design/`, which is the only reason they are here.

**Provenance stated plainly, because it bears on how much weight they carry.**
They were generated by an outside review of the codebase, not by using
Clarice and wanting them. This section asks every candidate for a trigger and
none of these has one, so they are recorded as ideas rather than promoted to
Track D — writing something down is not the same as deciding to build it, and
the distinction is exactly what keeps a Later list from becoming a backlog.

- **A calendar feed.** An authenticated read-only ICS endpoint so due dates
  appear in Google, Apple or Outlook calendars. Note it points the opposite
  way from time blocking in Track D: that one models calendar ranges *inside*
  Clarice, this one publishes what already exists to a calendar someone
  already reads. Cheaper, and possibly the only one of the two ever wanted.
- **Natural-language due dates.** "Next Friday", "tomorrow at 3pm" parsed on
  input. Worth noting against a settled principle: the server owns date
  meaning, so parsing belongs server-side with the client showing what was
  understood before it is committed — an automation that proposes rather than
  silently decides.
- **A command palette.** `Ctrl+K` over tasks, lists and Ideas. Genuinely
  premature: it is a *retrieval* affordance, and Reference/Idea search above
  already records that retrieval earns work only when finding something again
  is a felt problem. Revisit it with that search, not before.

### Longer-term product direction

- Build the Daily Page and its weekly, monthly, and quarterly review cadence
  from the direction set out for Crane.
- ~~Let exploring ideas resurface and relate to one another, potentially
  through a mind-map-style view and an append-only idea log.~~ **Moved to
  Second Mind, August 13, 2026** — and built further there than this line
  imagined: resurfacing is a named detector registry with per-detector accept
  rates, the append-only log exists and is enforced by a database trigger, and
  the mind-map is specified as a map of *concepts* rather than nodes, for
  structural findings only.
- ~~Add AI only as a transparent, confirm-before-write planning assistant after
  the daily and review records have earned enough real use.~~ **Moved to Second
  Mind, August 13, 2026**, whose ML policy is stricter than this line and whose
  v1 ships no generation at all. The commercial audit's correction stands
  wherever it lands: a gate measured against one person may never fire.
- ~~**Turn the Android app into a fully functional client, not just
  capture.**~~ **Trigger fired August 10, 2026 (the same day this was first
  recorded)** — see below. Vince's stated direction, raised while reviewing
  whether 4.1–4.3 needed a Ninja API: they didn't, because Track F's Android
  client is deliberately create-only today ("triage remains in the web app,"
  per that section) and nothing yet asked it to be more. Browsing, tagging,
  editing and relating Ideas from the phone still needs capture's
  create-only API (`capture/api_v1.py`) to grow into a real read/write
  surface for Idea (and likely Item), the same gap 4.1 and 4.3's design
  notes already flagged — that piece is explicitly not part of slice 1,
  named as open in the new plan's §5.

### Only if Clarice becomes a business

Billing, support operations, deeper legal requirements, and horizontal
scaling remain out of scope until the public-readiness bar is genuinely met.

## Settled boundaries

- Notes remain plain text; no Markdown renderer.
- Subtasks are one level deep only.
- Completing every subtask does not auto-complete its parent.
- Only top-level tasks recur.

## Release practice

Production releases use alphabetic bird codenames: `albatross`, then
`bittern`, `crane`, `dunlin`. Tag only after production is verified. The
letter carries; the bird is chosen when the release ships.

**The letter sequence skips E.** Decided August 3, 2026, by Vince: the
Android device-testing branch and capture tags — merged onto `main` the same
day — stay folded into Dunlin rather than being promoted to their own
release, so there is no Release E. The next release to actually start is
**Release F**; its bird is still chosen only when it ships, same as always.

- `LIVE` is a moving tag for the code currently running.
- `DEPLOYED-<date>/<HHMM>` is a permanent deployment-event tag.
- The bird codename is a permanent annotated release tag describing what
  shipped and how it was verified.

**The letters lapsed between August 6 and 12, and were deliberately restored on
August 15 — Vince's call.** Six of the seven lines of work in that window
shipped outside the release structure entirely (see `roadmap-history.md`), and
this section previously ended "do not invent one to restore the pattern." That
instruction is superseded, because what it was written about has changed: the
merger was a single coherent body of work with one finish line, which is the
thing the letters had stopped naming.

Two birds were assigned belatedly, on August 15:

- **Fulmar** (`2986ed6`) — the whole August 6–12 period, Release F's discovery
  pass plus the six unlettered lines that shipped beside it. **Its annotation
  states that verification was piecemeal**, because it was: only the task list
  and agenda redesigns had their own verified deploys, and everything after
  reached production inside a later one. The tag exists so the sequence is
  unbroken, not to claim a release that was verified as a whole.
- **Godwit** (`d0983a8`) — the Second Mind merger, all five steps, plus nine of
  the ten defects in `commercial-blueprint.md` Part 1. Verified in production on
  August 15.

**Godwit spends the letter G**, which `architecture-trajectory.md` §5 had
speculatively reserved for commercial readiness while asking "does release G
exist?". A letter is a position in a sequence, not a reservation — so that
question is now answered by renumbering rather than by decision, and commercial
readiness is H or later whenever it is taken up.

**Going forward the scheme holds again**: a release is a coherent body of work
with a finish line, tagged only after production verifies it, and the bird is
chosen when it ships.

## Where things stand — August 15, 2026

**The last release is Godwit**, tagged and verified in production on August 15:
the Second Mind merger end to end, and nine of the ten defects in
`commercial-blueprint.md` Part 1. Fulmar was assigned the same day to the
August 6–12 period behind it. See Release practice for both, and for why the
letters were restored after being written off.

**There is no active release.** What is in front of the project is the
**crossover**, and it is release-shaped in a way nothing since Dunlin has been —
one subject, one finish line:

- Two capture surfaces still exist. `/capture/` writes a `Capture`, `/mind/`
  writes a `Node`, and `/api/v1/capture` is defined by both cores under
  different prefixes. The `/mind/` prefix is temporary and lives in one line of
  `clarice/urls.py`.
- `Capture` and `Idea` are retired by it, which is the live reason the task core
  stays in maintenance — see `CLAUDE.md`.
- **One decision blocks the plan**: whether a single capture surface keeps
  first-class tags, or adopts the knowledge core's position that structure
  should emerge rather than be declared at entry. That is the only real trade
  in the consolidation and it is Vince's to make.

**Two things outstanding that are not code.** An external uptime monitor to poll
`/healthz` — the last open item in Part 1, and deliberately not in this
repository, because a watchdog on the machine it watches is not a watchdog. And
the deployment tags, which drifted: `LIVE` sat five days and thirty commits
behind production until August 15, and the August 14 deploy went untagged
entirely. The convention is only worth having if it is kept.

**What no longer applies.** The knowledge-side roadmap did not come back with
the code — Ideas, resurfacing, the mind-map and search over retained material
are the knowledge core's now, and it is in this repository. The productivity
roadmap is intact and unaffected: the Daily Page, routines, reviews, wider
horizons and mobile web all still stand on their own triggers.

## Keeping this current

Update this file when work begins, changes scope, ships, or is explicitly
deferred.

**Move completed detail into [`roadmap-history.md`](roadmap-history.md) and
keep only the resulting baseline or remaining consequence here.** That
instruction has been in this file since August 1 and was not followed —
257 lines of shipped-work narrative had accumulated below "Keeping this
current" by August 13, and were migrated then. This document is the
forward-looking plan; if a section is describing what already happened at
length, it is in the wrong file.

When an idea from Later earns work, give it a one-line reason and a focused
spec before it joins an active track.

