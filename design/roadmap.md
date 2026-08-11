# Clarice — Roadmap

Vince · active planning document · refreshed August 10, 2026

## Purpose

This is the forward-looking plan: what is active now, what is next, and
what has deliberately been deferred. It is not the implementation spec for
an item; write a focused file in `design/` once work is ready to start.

The completed Albatross, Bittern and Crane work, deployment notes, and
lessons learned live in
[`roadmap-history.md`](roadmap-history.md). Keeping that record separate
makes this document useful when deciding what to work on next.

The cross-cutting engineering and product standards used to deliver roadmap
work live in [`principles.md`](principles.md).

The multi-release ordering behind Crane and the releases after it, the design
constraints every new model has to satisfy, and the architectural directions
this project has explicitly refused live in
[`architecture-trajectory.md`](architecture-trajectory.md). This file stays the
authority on what is active and what is deferred; that one explains the order
and the reasoning, and does not schedule anything on its own.

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

C2's recorded interface failure is fully closed as of Dunlin — see that
section. What replaced it, five findings in
[`ui-second-pass-plan.md`](ui-second-pass-plan.md) (F1 through F5), is now
closed too. F1 shipped inside Dunlin itself; F2, F2a, F3 and F5 shipped
August 6, 2026, following the observational sitting recorded there on
August 3 that confirmed F2 and F3 rather than inferring them. Nothing named
in that brief is still open.

## Bittern — shipped August 2, 2026

**Deployed and tagged.** Three deploys carried it: 11:56 EDT on August 1
(`fed210b`), 21:51 EDT the same evening, and 00:35 EDT on August 2
(`359a7e3`), which was the one that finally carried B2.1 and B2.2. What was
built and what it taught are in [`roadmap-history.md`](roadmap-history.md);
the executable detail, including the acceptance criteria consciously not
met, stays in [`bittern-plan.md`](bittern-plan.md).

**Verified in production:** the deployed bundle carries `RequestFailed`, the
class B2.1 introduced — checked with a marker the change actually added,
after a weaker one nearly confirmed a deploy that had not happened. No
unapplied migrations. Sentry active with `DEBUG` false. B1's spawned
occurrence rendering with its children and no refresh. Android capture
reaching the Inbox exactly once, across every network condition. Per-user
time zones discriminating between accounts at 07:00 WITA.

**Closed with work outstanding**, deliberately rather than by omission: five
after-deploy checks were never run and three infrastructure confirmations
are still owed. All of them are carried into Crane and listed there.

C2 outlived the release rather than shipping in it, and is an observation
task rather than work:

**C2. Reassess information architecture after B0.**

The original complaint — “I can’t tell where things are” — may disappear
once the navigation is actually rendered. Observe the real remaining friction
before writing a redesign spec.

**C2 has its evidence now, from B1's own verification on August 2, 2026.**
Setting up one recurring parent with three children took three attempts, and
each failure was the interface rather than the person:

- A task's **Repeat** (a select, parent-only) sits directly above each
  subtask's **Repeats** (a checkbox, child-only). Near-identical words, one
  screen, opposite meanings — and setting the first to None silently hides
  every instance of the second, so the control you were reaching for
  disappears as a side effect of the mistake.
- A subtask row carries two checkboxes with no visual distinction: the
  leading one completes the task, a later one governs recurrence. Having
  used the first, it reads as though the row is done with.
- Neither failure produced an error. Both looked like success.

The verdict from that session was blunt and is recorded as given: the web UI
needs a complete overhaul, not adjustment. The Tailwind/shadcn work replaced
how it looks; what is wrong now is what it *says* and what it lets you
confuse. That is a design cycle of its own and should not be smuggled into
Crane as incidental cleanup.

**Answered by Dunlin, August 3, 2026.** Both defects above are gone — the
first dissolved by the model change without the interface being redesigned at
all, the second by making the two controls different kinds of control. The
evidence is left exactly as it was recorded rather than rewritten, because
what it observed is the reason the release took the shape it did. The verdict
itself was only half right: the model was the larger problem, and fixing it
removed a defect no amount of interface work would have.

### Track D — Postgres-enabled features

Future candidates. Each needs its own product trigger or focused brief
before joining an active release.

Per-user time zones left this list on August 1, 2026, when both halves of
its stated trigger fired at once: a second active user in Indonesia, and a
real scheduling error caused by the global zone. Shipped, and observed
discriminating between users in production at 07:00 WITA — see
[`per-user-time-zones-plan.md`](per-user-time-zones-plan.md).

- **Reference/Idea search.** Start with ranked full-text and typo-tolerant
  search for Ideas, especially the `reference` archive. The Inbox is a queue
  to clear, not a library to search.

  **What would promote it:** enough retained material that finding something
  again is a felt problem rather than an anticipated one. Stated August 2,
  2026 — this section asks each candidate for a trigger and none of the three
  below had one, which is how a future candidate quietly becomes a plan. Audit
  log and Time blocking still need theirs. The discovery pass on what an Idea,
  reference and relationship actually are should precede the search work
  either way — see the second-brain direction in
  [`daily-operating-system-vision.md`](daily-operating-system-vision.md), now
  underway as Release F's opening work — see
  [`second-mind-discovery-plan.md`](second-mind-discovery-plan.md).
- **Audit log and general undo.** Use structured change records to make more
  than task completion safely reversible.
- **Time blocking.** Model calendar ranges and prevent a user’s blocks from
  overlapping at the database layer.

### Track E — Public-readiness essentials

Both Bittern items shipped: branded email with a rate-limited contact path
(B3), and production error monitoring (B4). Account export/deletion remains
deferred until the immediate-versus-grace-period decision is made.

### Track F — Android capture MVP

**Complete — M1–M5 shipped August 1–2, 2026.** A native Kotlin client in
`android/` authenticates with a personal access token, captures online or
offline, accepts shares from other apps, and delivers a durable encrypted
queue in the background without ever creating a duplicate. The device pilot
ran against production on a Samsung SM-F966U: fifteen captures across Wi-Fi,
cellular, a mid-request radio switch and airplane mode arrived as fifteen
rows with fifteen distinct keys, and a link shared from the browser arrived
with its title intact. The detail, including the criteria consciously not
met, is in [`bittern-plan.md`](bittern-plan.md).

Its only purpose is getting a thought into the inbox quickly; triage remains
in the web app. The shared idempotent-write contract (M1) is verified against
production and will serve a future iOS client as a sibling under `ios/`.

## Crane — shipped August 2, 2026

**Deployed and tagged.** Two deploys carried it: 17:54 EDT (`c3c57fb`,
`DEPLOYED-2026-08-02/1754`), which took Crane 0a, 1 and 2 in one run of ten
migrations, and 20:05 EDT (`e0acf05`, `DEPLOYED-2026-08-02/2005`), which
took Crane 3's four. `crane` went on after production was verified rather
than alongside the deploy — the correction Bittern's record asks for. What
shipped and what it taught are in
[`roadmap-history.md`](roadmap-history.md); the executable detail, the
settled design decisions and every slice's acceptance condition stay in
[`crane-plan.md`](crane-plan.md).

**Verified in production**, with markers each change actually added: the
review routes answer 401 while a made-up route answers 404, the POST-only
`/review/{day}/complete` and `/routines/{id}/enough` answer 405 to a GET,
the served bundle carries "Recent weeks", "Save the review" and "Call it
enough", and `/app/review` renders on the real account. The earlier deploy
was verified the same way, and `lists/0023` linked both existing repeating
tasks there.

**What it changed for the product.** The Daily Page is the home surface,
with a preference to land on the Agenda instead. Practice is a domain of its
own — routines and their occurrences are peers of tasks, never a kind of
them. Repeating commitments have a durable identity across occurrences. And
the weekly review reads all of it back against denominators that mean
something: completed planned commitments over planned commitments, and met
periods over the periods a week actually asked for.

### Still carried in from Bittern

Nine of the fourteen items remained at this point, and
[`crane-plan.md`](crane-plan.md) §2 was, and stays, the authority on them.
Cleared here: four of the five production verifications and the New York
digest, on August 2, 2026, in the session that deployed Crane 0a, 1 and 2.
The rest closed later — see "Carried in from Bittern, through Crane and
Dunlin" under Dunlin below for the current baseline, so this snapshot is not
duplicated stale.

## Dunlin — shipped August 3, 2026

**Deployed and tagged.** Two deploys carried it: 00:27 EDT (`e76c200`,
`DEPLOYED-2026-08-03/0027`), which took slices 1 to 8 and all six migrations
in one run, and 02:03 EDT (`DEPLOYED-2026-08-03/0203`), which took the
interface brief, the carries-forward switch and the deploy fix below. `dunlin`
went on after production was verified. What shipped and what it taught are in
[`roadmap-history.md`](roadmap-history.md); the executable detail and every
slice's acceptance condition stay in
[`release-d-plan.md`](release-d-plan.md).

**Verified in production**, with markers each change actually added:
`/api/v1/projects` and `/api/v1/areas/1` answer 401 while a made-up route
answers 404, `/api/v1/lists/1` is gone at 404, `/lists/1/` redirects to
`/areas/1/`, the login page says "areas" and never "lists", and the served
bundle carries "No projects in this area yet." and "stay open if you complete
this" with none of the old vocabulary. `app-shell.js` on production is
byte-identical to the build the tests ran against. All six migrations show
applied; `0026` converted six subtasks; ownerless areas number zero.

**What it changed for the product.** Clarice says what each thing is. A
subtask is a Checklist Step with its own life cycle rather than a task
wearing a parent. A List is an Area — a bucket that never completes — and a
Project is work that does, with a task keeping its Area and optionally
joining a project. Every model is owned at birth, without exception.

**C2 is closed.** Its recorded failure was one person needing three attempts
to set up one recurring parent with three children, caused by two independent
defects. The Repeat/Repeats label collision dissolved *by construction* when
a Checklist Step lost its recurrence field — the interface was never
redesigned to fix it, which is the strongest evidence the thesis behind this
release was right. The two identical-looking checkboxes on a row are now a
checkbox and a switch.

### Carried forward from Dunlin

- **Two migration counts are lost.** `0026`'s promotions and `0028`'s
  deletions printed into nothing, because the migrate task discarded its own
  stdout. Fixed in `a6550e4` and exercised on the second deploy while the
  stakes were a no-op. `0028`'s number is unrecoverable; the rows are gone and
  its reverse is a stated no-op by design.
- **The interface work Dunlin opened, now observed rather than inferred**,
  in [`ui-second-pass-plan.md`](ui-second-pass-plan.md) §6. The sitting §6
  asked for happened August 3, 2026: one real project with three real tasks,
  created through the actual UI rather than fixtures, checked at a 375×812
  viewport. **F2 and F3 are both confirmed**, not merely read from source — a
  project really is invisible everywhere a task is actually worked, and
  Projects really have no place in navigation. The sitting also surfaced
  **F2a**: even the Area page's own task rows carry no project indicator next
  to the project count sitting right above them. Method noted honestly: this
  session's Browser pane would not composite frames, so the interaction was
  DOM-level (real controlled inputs, real change events) rather than literal
  taps — sufficient for the information-architecture question F2/F3 ask,
  silent on touch-target size. **What this does and does not settle:** the
  brief is equally clear that the navigation question — how a project should
  actually surface — should not be started by guessing. The sitting supplied
  evidence, not an answer; whether steps 2–4 begin now is Vince's call.

  **Steps 2–4 began and finished, August 6, 2026.** F2 landed on the Agenda,
  the Daily Page and the Archive; F2a fixed the Area page's own disconnect
  between its project heading and the rows under it; F3 gave projects a
  flat, top-level group in the side nav, the shape decided by asking Vince
  directly rather than reading the sitting's evidence as license to guess;
  F5 split the Area page's two differently-scoped deletes apart and made
  `Save name` disabled until there is something to save. `ui-second-pass-plan.md`
  §4 has nothing left open — see that file for the full acceptance detail on
  each step.
- ~~**The vocabulary half of Crane 0**, still deferred.~~ **Shipped August 3,
  2026**, after Dunlin — see
  [`recurring-commitment-vocabulary-plan.md`](recurring-commitment-vocabulary-plan.md).
  `RecurringCommitment` is a real template now: it holds what the next
  occurrence starts as, each occurrence keeps its own snapshot of what it
  actually ran under, editing writes through as "this and future", and
  cadence lives on the commitment rather than being repeated down a chain.
  Deployed across `DEPLOYED-2026-08-03/0253` and `/0313`.

  **`crane-plan.md` §3 contradicted itself and the brief records the
  correction:** it described the work as *moving* `text` onto the template,
  while its own acceptance example required the earlier occurrences to keep
  the old title. It is a template plus a snapshot, not a move — the same pair
  `Routine`/`RoutineOccurrence` already shipped.

### Carried in from Bittern, through Crane and Dunlin — eleven of fourteen closed

`crane-plan.md` §2 stays the authority on the full checklist; this is the
baseline. Cleared since Dunlin shipped: **B1's opt-out rule**, confirmed
against production on August 6, 2026 rather than merely unblocked — setting
up a daily-recurring task with an opted-out Checklist Step was, as
predicted, unremarkable through the fixed interface. **The forwarded
contact message**, confirmed the same day landing in the inbox rather than
spam, DKIM-aligned through Resend rather than through the Google-signed
report that had only encouraged, not proven, it. Both join **DMARC
aggregate reports**, confirmed August 3.

Three items remain, and none of them are work still to schedule:

- **A real production 500 reaching Sentry**, rather than only the
  controlled probe. Needs an actual incident, not a task — the same
  reasoning that rejected a permanent `/sentry-debug/`-style route as a
  verification method.
- **No Android emulator run.** This SDK install has no AVD and no way to
  build one without a multi-gigabyte download better done through Android
  Studio's own AVD Manager. Judged low-priority: everything M4 asked a
  device for is now answered twice over on real hardware — the SM-F966U
  pilot against production, the SM-S928U1 session that closed three more
  gaps, and M3's encrypted-storage guarantees reconfirmed on the SM-S928U1
  again on August 6.
- **Release signing.** `app/build.gradle.kts` is wired for it; the keystore
  itself is deliberately left for Vince to generate by hand — a
  non-rotatable credential is the wrong thing for an agent to generate and
  momentarily hold. See
  [`android-release-signing-plan.md`](android-release-signing-plan.md) for
  the exact command.

**Verified live:** `DEPLOYED-2026-08-06/2248` carries all of the above;
`LIVE` matches `main` at `d7133fe` with nothing ahead on either side. The
same deploy also carries the rest of what the Android device-testing branch
merged in on August 3 — in-app login, the optional unlock gate, release
signing wired into the build, and capture tags — which had merged onto
`main` but sat undeployed when this file last said so.

### Capture tags — built alongside the Android device-testing session

**Decided August 3, 2026: stays folded into Dunlin, not promoted to its own
release.** Merged onto `main` the same day; deployed August 6, 2026 in
`DEPLOYED-2026-08-06/2248`. Optional tags
on a capture, typed on the Android compose screen and displayed as pills in
the web Inbox — see [`capture-tags-plan.md`](capture-tags-plan.md) for the
trigger and the slice. Reuses `lists.Tag` rather than a parallel model
(`_resolve_tags` became public `resolve_tags` so `capture.services` can call
it), an additive `Capture.tags` migration, and the Android queue carries
tags through offline capture the same way it already carries text. Triage
still does not gain a tags field, and a capture's tags do not yet carry
forward onto the task or idea it becomes — both named as deliberate
non-goals in the brief, not oversights.

The same decision covers the rest of what the Android device-testing branch
carried in — in-app login, the optional unlock gate, release signing wired
into the build, and the three Android gaps closed above. None of it earns
Release E; the next lettered release, whenever one actually starts, is
**Release F** — see "Release practice" below for why the letter jumps.

All of it is deployed now, along with the rest of Dunlin's carried-forward
work — see "Carried in from Bittern, through Crane and Dunlin" above.


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
- Let exploring ideas resurface and relate to one another, potentially through
  a mind-map-style view and an append-only idea log.
- Add AI only as a transparent, confirm-before-write planning assistant after
  the daily and review records have earned enough real use.
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

## Keeping this current

Update this file when an item in the active release begins, changes scope,
ships, or is explicitly deferred. **Release F is the active release**,
opened August 7, 2026 — see below. Dunlin shipped August 3 and nothing was
promoted to replace it until then; `ui-second-pass-plan.md`, the last piece
of work still folded into Dunlin, shipped its remaining steps August 6,
2026 (`DEPLOYED-2026-08-06/2248`) and has nothing left open. The
Bittern/Crane carried-forward checklist is down to three items, none of
them schedulable work — see "Carried in from Bittern, through Crane and
Dunlin" above.

**Release F opens with the second-mind discovery pass — Vince's call,
August 7, 2026, ahead of the pain that would otherwise force it.**
`architecture-trajectory.md` §5 named two candidates: this one, and the
infrastructure track's staging environment, which §6 says gates most of
what follows it. Neither had fired its stated trigger; the discovery pass
was chosen anyway, recorded as a deliberate exception rather than a trigger
pretended to have fired. The staging environment stays next in line on the
infrastructure track, not dropped.

**Discovery done, first slice shipped in full, August 10, 2026:**
[`second-mind-discovery-plan.md`](second-mind-discovery-plan.md). Reading
the current models against `architecture-trajectory.md` §4's charter found
most of the idea/reference/project/task/routine boundary already settled by
releases that weren't about this at all — Idea's own `status` field already
makes idea/reference one model, and Dunlin and Crane 0 already settled
task/project/area and routine/task. What's genuinely still open is narrower:
whether an idea-to-idea relationship earns its own model (charter says no —
it's a plain link), and whether links/sources should be structured data
(no evidence yet either way, stays plain text).

The first slice — tags on `Idea` reusing `lists.Tag` the way `Capture`
already does (4.1), a capture's tags carrying forward onto the Idea or task
it becomes (4.2), and a plain manually-added `related_ideas` link with no
`kind` field (4.3) — is done: additive migrations, `capture` and `lists`
suites plus the full backend run (856 tests) green throughout. Two of the
brief's own assumptions didn't survive contact with the actual code and are
corrected in the plan doc rather than silently built around: `capture.Idea`
has no Ninja API at all (the `IdeaOut` the brief pictured belongs to an
unrelated `review`-app summary), so tags and related-idea links gained no
new API surface, only read/write paths through the existing Django views;
and Idea has no per-page detail view for chips to live on, so they render
inline on the shared Ideas list instead. Nothing from the brief is still
open — see its §7 for the full accounting.

**A second, separate line of work — not folded into Release F, shipped in
full August 10, 2026.** Trigger: Vince hit a real navigation dead end
trying to open a project from the side nav and finding it only ever
routed to the project's parent Area — Project had never had a page of its
own. [`project-workspace-plan.md`](project-workspace-plan.md) inverted
Project's containment: a Project is a standalone workspace that can hold
one or more Areas now, rather than living inside exactly one. Eight
slices, each its own commit — model, expand migration, service and read
layer, API layer, contract migration, regenerated client, frontend
rewrite, browser smoke pass — landed exactly in that order. 858 backend
tests, 231 frontend tests, 28 browser journeys, all green. One real gap
the plan itself missed (nowhere to create a *new* project once
`ProjectsPanel.tsx` was gone) surfaced only while writing the browser
journey and is recorded, fixed, in the plan's own §5.

**Two more follow-ups the same day, both from Vince using the shipped
feature rather than from planning ahead:** a `/projects` index page
(§"what this cycle does not decide" had flagged it deferrable; asked for
directly once the gap was actually felt), and letting a Project create a
brand-new Area rather than only reassign an existing one — the
predominant use case, per Vince, and the occasion for a standing-rule
change: an Area no longer needs a first task to exist. Both closed the
same day, recorded in the plan's own §6, which also names a real bug
(the sidebar going stale after completing or deleting a project) the
second follow-up's browser journey caught that neither plan anticipated.
865 backend tests, 239 frontend tests, 30 browser journeys, all green.

**A third, separate line of work — not folded into Release F, shipped and
deployed August 10, 2026** (`a12a310`, `DEPLOYED-2026-08-10/1928`, verified
live on the real Area page). Trigger: Vince flagged
`TaskWorkspace.tsx`'s Area task list as "simply a mess" mid-review of the
Projects redesign — the last Bootstrap-era screen (with `AgendaWorkspace`,
still deferred) not yet on Tailwind.
[`task-list-redesign-plan.md`](task-list-redesign-plan.md) carried the
Tailwind migration plus real additions approved against a reviewed mockup:
a due-date sort, select-mode bulk complete/archive, removable tag pills,
and due-date/recurrence pill dedup. 254 frontend tests, 867 backend tests,
and a browser smoke pass all green; see that plan's §5 for the full
accounting, including the pre-existing `ProjectJourneyTest` failures ruled
out by bisecting against `main` before this work touched anything.

**A fourth, separate line of work — not folded into Release F, shipped and
deployed August 10–11, 2026** (`94a6c4f`, `DEPLOYED-2026-08-10/2100`,
verified live on the real Agenda page). Direct follow-on to the
above: with `TaskWorkspace.tsx` migrated, `AgendaWorkspace.tsx` became the
last Bootstrap-era component, and it's the app's actual highest-traffic
page (the preferred landing surface). Asked how the page could be improved
beyond the visual pass, two real functional gaps surfaced by reading the
code rather than guessing — no text search anywhere on the page, and no
staleness signal, since `age_in_days` lives on Daily's and the weekly
review's own item types rather than the shared `Task` type Agenda's own
items are.
[`agenda-redesign-plan.md`](agenda-redesign-plan.md) carried the Tailwind
migration, the touch-target fix (measured 19–31px against the ~44px
guideline, the same finding Crane 1 slice 7 recorded for this exact page),
a unified area/tag filter row replacing three previously separate filter
surfaces, search, and the staleness label. Bulk actions and manual
reordering were considered and deliberately left out as editing-shaped work
that already belongs to the Area page. 263 frontend tests, 867 backend
tests, and a browser smoke pass all green; see that plan's §5 for the full
accounting, including a real layout bug (a search field collapsing to 30px
for lack of a `flex-shrink:0` guard) that only live verification against
the actual built bundle caught.

**A fifth, separate line of work — not folded into Release F, shipped
August 11, 2026 (uncommitted, awaiting review).** The last piece of the
Bootstrap→Tailwind arc: with `TaskWorkspace.tsx` and `AgendaWorkspace.tsx`
both migrated, `ArchiveManager.tsx` was the only component left on
`site.css`, and with no Tailwind-migrated wrapper above it either.
[`archive-redesign-plan.md`](archive-redesign-plan.md) carried the
migration, the same touch-target fix, and switched the row date from
`created_at` to `archived_at` (confirmed against the model's own
`CheckConstraint`, not assumed) — and, because this was the last dependent,
**retired `site.css` and `workspace.module.css` from the app entirely**,
deleting the stylesheet's source file rather than leaving it unreferenced.
264 frontend tests, 867 backend tests, and a browser smoke pass all green.

**Caught only by live verification, not by any test, and worth naming
because it wasn't confined to this page:** the delete dialog's buttons
measured 32px against the ≥44px claim — `Button`'s own size variants top
out at 36px, and no component test measures rendered layout. Checking
`TaskWorkspace.tsx` and `AgendaWorkspace.tsx` for the same pattern found
the identical gap in both already-deployed redesigns — every
`<Button size="sm">` composer/dialog button in all three components was
actually 28–36px despite each brief's own ≥44px claim and each live
verification reporting it confirmed. Fixed in all three with an explicit
height override once found; see `archive-redesign-plan.md`'s own §5 for
the full accounting.

**A sixth, separate line of work — not folded into Release F, started
August 10, 2026, slice 1 in progress.** Trigger: Vince asked for a "more
comprehensive overhaul" of the Android app after a frontend-design pass on
its (previously nonexistent) visual theme, wanting it to become a real
mirror of the website rather than stay capture-only — firing the direction
already recorded above the same day.
[`android-full-client-plan.md`](android-full-client-plan.md) checked the
actual gap first: most of the domain already has a token-authenticated
Ninja API (`lists`, `daily`, `review`, `routines` `api_v1.py`), the same one
the SPA consumes, so this is mostly an Android build-out rather than a
backend rebuild — except `capture.Idea`, which still has none. Slice 1,
Vince's own choice of surface and scope: the Daily Page, read-only — a new
`DailyApi`, a `DailyScreen`, and a lightweight tab switcher beside the
existing Capture screen, with pin/unpin, routine logging and day-editing
deliberately deferred to a later slice. See that plan's §3 for the exact
scope line and §5 for what's still undecided after this slice.

Move completed detail into `roadmap-history.md` and keep only the resulting
baseline or remaining consequence here. When an idea from Later earns work,
give it a one-line reason and a focused spec before it joins an active
track.
