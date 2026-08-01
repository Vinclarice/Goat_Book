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

## Bittern — next release

**Status: scoping.** Bittern has four small, independent tracks. Do not turn
them into one open-ended queue, and do not promote an item from Later without
a concrete reason.

The executable scope, sequencing, acceptance criteria, and deferred-item
gates live in [`bittern-plan.md`](bittern-plan.md). That plan intentionally
turns Bittern into a small reliability-and-navigation release rather than
committing every candidate below at once.

### Track C — Navigation and UI

These carry their Bittern slice numbers, since `bittern-plan.md` is where they
are actually specified. They were originally written here as C0, C1, and C2.

**B0. Diagnose the missing production side navigation. — Done, August 1, 2026.**

The deployed bundle was never stale. `AppLayout` sealed the nav inside a
`<details>` that nothing ever opened, above a breakpoint where the CSS hides
its `<summary>`, so the disclosure collapsed to zero height and left an empty
210px gutter in browsers that skip rendering closed disclosure contents.
Patched, deployed, and confirmed in an authenticated browser at both widths.
Evidence in [`roadmap-history.md`](roadmap-history.md).

**B2. Add logout to the SPA.**

The only current logout flow lives in a legacy Django template. Add an
equivalent POST-backed control to the SPA navigation or preferences surface.
This is worthwhile whether or not B0 turns out to be a stale bundle.

**C2. Reassess information architecture after B0.**

The original complaint — “I can’t tell where things are” — may disappear
once the navigation is actually rendered. Observe the real remaining friction
before writing a redesign spec.

### Track D — Postgres-enabled features

None of these ship in Bittern. They remain future candidates and need their
own product trigger or focused brief before joining an active release.

Per-user time zones left this list on August 1, 2026, when both halves of
its stated trigger fired at once: a second active user in Indonesia, and a
real scheduling error caused by the global zone. It is built and awaiting
the same deploy as M1 — see
[`per-user-time-zones-plan.md`](per-user-time-zones-plan.md).

- **Reference/Idea search.** Start with ranked full-text and typo-tolerant
  search for Ideas, especially the `reference` archive. The Inbox is a queue
  to clear, not a library to search.
- **Audit log and general undo.** Use structured change records to make more
  than task completion safely reversible.
- **Time blocking.** Model calendar ranges and prevent a user’s blocks from
  overlapping at the database layer.

### Track E — Public-readiness essentials

Bittern includes only the two items below. Account export/deletion remains
deferred until the immediate-versus-grace-period decision is made.

- **Branded email and contact.** Move account mail to verified Clarice-owned
  addresses and add a rate-limited contact path that routes to a product
  support inbox. This starts once an email provider is chosen.
- **Error monitoring.** Add production exception reporting with a DSN-backed
  service such as Sentry. This is deliberately small and independent.

### Track F — Android capture MVP

Build a basic native Kotlin capture client that authenticates with a personal
access token and calls `POST /api/v1/capture`. Its only purpose is getting a
thought into the inbox quickly; triage remains in the web app.

This is a committed Bittern stage, immediately after the production-bundle
check. Its shared idempotent-write contract (M1) is implemented ahead of the
client and still needs environment/deployment verification; that single
contract will serve both Android and a future iOS client. When native work
begins, keep it in this monorepo under `android/`; an eventual `ios/` client
will be a sibling. Do not add a placeholder mobile project without the Android
Studio environment needed to build and test it. The delivery plan — including
secure token storage, offline delivery, and idempotent capture writes — is in
[`bittern-plan.md`](bittern-plan.md).

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

Update this file when a Bittern item begins, changes scope, ships, or is
explicitly deferred. Move completed detail into `roadmap-history.md` and
keep only the resulting baseline or remaining consequence here. When an idea
from Later earns work, give it a one-line reason and a focused spec before it
joins an active track.
