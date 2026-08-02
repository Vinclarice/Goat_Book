# Clarice — Roadmap

Vince · active planning document · refreshed August 1, 2026

## Purpose

This is the forward-looking plan: what is active now, what is next, and
what has deliberately been deferred. It is not the implementation spec for
an item; write a focused file in `design/` once work is ready to start.

The completed Albatross work, deployment notes, and lessons learned live in
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

Albatross is live. It established the API-backed SPA and Postgres foundation,
then shipped task notes, subtasks, recurrence, Capture triage and Ideas,
password recovery, personal access tokens, CI, backups, and production
hardening. The full record is in the history file.

The last known task-UI gap is closed. Completing a recurring task used to
return the next occurrence without the children created alongside it, so the
new parent appeared childless until a refresh. The mutation now carries a
`spawned_subtasks` sibling array and both workspaces place parent and
children in one update — Bittern B1, August 1, 2026.

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
  [`daily-operating-system-vision.md`](daily-operating-system-vision.md).
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

## Crane — daily-page foundation

### Carried in from Bittern

Bittern closed with these unfinished rather than pretending otherwise. None
of them blocks Crane's design work, and none should be allowed to disappear
quietly either. Deliberate decision on August 2, 2026: close the release,
carry the remainder.

**Verifications never run.** Each was written into Bittern's after-deploy
checklist and left undone; the code is deployed and the behaviour is covered
by tests, but nobody has watched it in production.

- Logout at desktop and narrow widths, then confirm protected API calls
  fail afterwards. (B2)
- A hard-refreshed `/app/agenda` showing navigation content and counts. (B0)
- A deliberately broken route — `/app/task/999999` — saying what went wrong
  and offering a way out rather than rendering blank. (B2.1, the slice the
  final deploy carried)
- An Android capture after the redeploy, confirming the client still reaches
  production.
- B1's opt-out rule: a subtask with `always_recurs` false must *not* clone
  onto the next occurrence. Three attempts to set this up failed on the
  interface rather than the rule; the service tests cover it and the
  production check does not.

**Confirmations owed on tonight's infrastructure.** All three share the
failure mode this release kept meeting — they look like success until
somebody checks.

- A forwarded contact message arriving in the inbox rather than spam, now
  that DMARC enforces.
- DMARC aggregate reports beginning to arrive at `dmarc@vinclarice.com`.
- A real production 500 reaching Sentry, not only the controlled probe.

**The New York morning digest**, 07:00–12:00 EDT on August 2. The Makassar
account's digest fired at its own 07:00 while both `America/New_York`
accounts stayed on the previous day, which proves the job discriminates.
What has not been seen is the other side of the same day.

**Android gaps**, all recorded in [`bittern-plan.md`](bittern-plan.md):
no emulator run; the forced-retry path never exercised on a device; a
plain-text share and an offline share never tested on hardware; no release
signing, so the APK cannot be given to anybody else; and no way to discard a
rejected capture, deferred deliberately while the app is a prototype.

Two design cycles were also named — the parent–child domain redesign and the
web UI overhaul — and are described under Bittern's C2 and in
[Named for the next design cycle](#named-for-the-next-design-cycle). Neither
is Crane's foundation work and neither should be started as a side effect
of it.

### The foundation itself

**Direction only.** Clarice's central
job is not maintaining task lists. It is removing the clerical work from a
daily practice: capture without categorising, see the right commitments today,
carry unfinished work forward automatically, and leave a useful record of the
day.

Crane should establish that daily page as the product's home. It must keep
tasks, captures, reflections, and ideas as distinct records with clear sources
of truth — never duplicate a task into a day page merely to make it visible.
Weekly review and its trustworthy completion/routine trends are the first
planning feature after that foundation. Routines and habits will be a separate
domain from recurring tasks. Crane also preserves the old template's persistent
purpose/guiding-question block as a user-level Personal Compass, separate from
daily intentions, and adds a durable “pin this to today” focus layer above the
broader agenda. Routine and target domain design begins as Crane 0, before
Daily Page implementation; its implementation follows the foundation. A wider
brief was proposed on August 2, 2026, covering repetition generally rather than
routines alone, because a recurring task had no durable identity across its
occurrences — `_spawn_next_occurrence` wrote no link back to the item it
spawned from — so no trend, streak or completion rate could be assembled from a
recurring commitment's history the way it will be for a routine. That widening
was accepted the same day in narrowed form, and the accepted half **shipped
that day as Crane 0a**: a thin commitment record and the missing foreign key,
ahead of Crane 1 because the unlinkable history accrues fastest once the Daily
Page makes this a daily practice. Moving text and cadence onto a real template
waits for release D and the parent–child redesign it depends on. Both halves
are described in [`crane-plan.md`](crane-plan.md) §3; the code is on `main` and
awaiting a deploy. The product
direction, data boundaries, review metrics, second-brain questions, and
eventual AI guardrails are in
[`daily-operating-system-vision.md`](daily-operating-system-vision.md).

### Named for the next design cycle

Two pieces of work were identified on August 2, 2026, while verifying B1 in
production. Both are design cycles rather than tasks, and neither should be
started as a side effect of something else.

**Parent–child domain redesign.** The relationship between a task and its
subtasks is doing too many unrelated jobs, and its rules were arrived at one
at a time rather than designed. Completing a parent cascades to its children;
reopening it does not bring them back. Recurrence belongs only to parents,
`always_recurs` only to children, and a child's flag is invisible unless its
parent happens to repeat. Archiving cascades on one path and not another.
Each rule is defensible alone; together they are not a model anybody could
predict. Decide what a subtask *is* — a step, a dependent task, a checklist
item — before adjusting any more of its behaviour.

**Web UI overhaul, second pass.** The Tailwind v4 and shadcn work replaced
how the application looks. What remains wrong is what it says and what it
lets you confuse: near-identical labels for opposite concepts, controls that
vanish as a side effect of an unrelated setting, and rows carrying two
checkboxes that mean different things. See C2 above for the evidence. This
is a redesign of language and interaction, not of styling, and it wants its
own brief.

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
- **Sequencing against Crane.** Crane makes the Daily Page the home surface.
  A mobile pass done first would be redone for a surface that does not exist
  yet; done as part of Crane, the Daily Page is designed mobile-aware from its
  first day — which is what the vision document already implies when it calls
  the Daily Page the shared center of the website "and, later, the mobile
  experience." Fix concrete breakpoint defects as they are found; save the
  layout work for Crane.

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
What Crane does carry is narrower than this item: `crane-plan.md` slice 7 is a
phone-viewport pass over the assembled Daily Page, one new surface. Triaging
the Inbox, completing a task and reading an Idea from a phone, and reconciling
the 760px and 768px breakpoints, are all still here. Crane makes the new
surface mobile-aware; it does not close this entry.

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
`bittern`, then `crane`. Tag only after production is verified.

- `LIVE` is a moving tag for the code currently running.
- `DEPLOYED-<date>/<HHMM>` is a permanent deployment-event tag.
- The bird codename is a permanent annotated release tag describing what
  shipped and how it was verified.

## Keeping this current

Update this file when an item in the active release begins, changes scope,
ships, or is explicitly deferred — Crane is that release now that Bittern
has shipped. Move completed detail into `roadmap-history.md` and keep only
the resulting baseline or remaining consequence here. When an idea from
Later earns work, give it a one-line reason and a focused spec before it
joins an active track.
