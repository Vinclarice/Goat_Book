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

## Bittern — implementation complete, deploy owed

**Every slice is written, tested and on `main` as of August 2, 2026.** What
was built and what it taught are in [`roadmap-history.md`](roadmap-history.md);
the executable detail, including the acceptance criteria consciously not met,
stays in [`bittern-plan.md`](bittern-plan.md).

**Bittern has not shipped**, and three things stand between here and the
`bittern` tag. None of them is code:

1. **A deploy.** Production carries B3 and B4 — the 01:51 UTC deploy — but
   not B2.1 or B2.2, whose commits landed after it. Verified rather than
   assumed: `RequestFailed` and `Request failed with status`, both
   introduced by B2.1, are absent from the bundle the container is serving.
   (`Something went wrong.` is present and proves nothing; it predates B2.1
   by months. Pick a marker the change actually introduced.)
2. **The after-deploy checklist** already written into `bittern-plan.md`:
   the recurring-task round trip, logout at both widths, a hard-refreshed
   nav, Android capture online and offline, and B4's controlled event.
3. **The release tags.** `LIVE` still points at `fed210b`, and the 01:51
   deploy has no `DEPLOYED-` tag. The `bittern` codename tag comes last, and
   only after production is verified.

C2 outlived the release rather than shipping in it, and is an observation
task rather than work:

**C2. Reassess information architecture after B0.**

The original complaint — “I can’t tell where things are” — may disappear
once the navigation is actually rendered. Observe the real remaining friction
before writing a redesign spec.

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

**Direction only; begin after Bittern, not alongside it.** Clarice's central
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
broader agenda. Routine/target domain design begins as Crane 0, before Daily
Page implementation; its implementation follows the foundation. The product
direction, data boundaries, review metrics, second-brain questions, and
eventual AI guardrails are in
[`daily-operating-system-vision.md`](daily-operating-system-vision.md).

## Later — visible, not scheduled

### Sharing

- Shared lists with real-time updates.
- Conflict handling for concurrent edits.

These belong together. Do not start either until list sharing itself is a
deliberate product decision.

### Remaining public-readiness work

- Self-service signup with email verification.
- Rate limiting for signup and capture.
- Transactional email instead of personal Gmail SMTP.
- Account export and deletion, after deciding immediate deletion versus a
  grace period before purge.
- Privacy policy and terms of service.

Password recovery and adversarial per-user isolation tests are already done.

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
