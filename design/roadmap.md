# Clarice — Roadmap

Vince · active planning document · refreshed August 1, 2026

## Purpose

This is the forward-looking plan: what is active now, what is next, and
what has deliberately been deferred. It is not the implementation spec for
an item; write a focused file in `design/` once work is ready to start.

The completed Albatross work, deployment notes, and lessons learned live in
[`roadmap-history.md`](roadmap-history.md). Keeping that record separate
makes this document useful when deciding what to work on next.

## Current product baseline

Albatross is live. It established the API-backed SPA and Postgres foundation,
then shipped task notes, subtasks, recurrence, Capture triage and Ideas,
password recovery, personal access tokens, CI, backups, and production
hardening. The full record is in the history file.

One known task-UI gap remains: when a recurring task completes, the server
creates the next occurrence and its recurring subtasks in one transaction,
but the response does not include the new children. The next parent appears
childless until refresh. This is a response-shape decision, not an emergency
patch; scope it before changing the task mutation contract.

## Bittern — next release

**Status: scoping.** Bittern has four small, independent tracks. Do not turn
them into one open-ended queue, and do not promote an item from Later without
a concrete reason.

The executable scope, sequencing, acceptance criteria, and deferred-item
gates live in [`bittern-plan.md`](bittern-plan.md). That plan intentionally
turns Bittern into a small reliability-and-navigation release rather than
committing every candidate below at once.

### Track C — Navigation and UI

**C0. Diagnose the missing production side navigation.**

The source renders `AppLayout` and `SideNav`, but neither appears in the
Albatross production screenshot, even after a hard refresh. First confirm
which frontend bundle the running container serves. If it is stale, force a
clean rebuild and redeploy; verify the served bundle contains the Inbox and
Ideas links. Do this before evaluating any navigation redesign.

**C1. Add logout to the SPA.**

The only current logout flow lives in a legacy Django template. Add an
equivalent POST-backed control to the SPA navigation or preferences surface.
This is worthwhile whether or not C0 turns out to be a stale bundle.

**C2. Reassess information architecture after C0.**

The original complaint — “I can’t tell where things are” — may disappear
once the navigation is actually rendered. Observe the real remaining friction
before writing a redesign spec.

### Track D — Postgres-enabled features

None of these ship in Bittern. They remain future candidates and need their
own product trigger or focused brief before joining an active release.

- **Reference/Idea search.** Start with ranked full-text and typo-tolerant
  search for Ideas, especially the `reference` archive. The Inbox is a queue
  to clear, not a library to search.
- **Per-user time zones.** Make “due today” and the daily digest local to
  each user rather than tied to one application time zone.
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
check. Its delivery plan — including secure token storage, offline delivery,
and idempotent capture writes — is in [`bittern-plan.md`](bittern-plan.md).

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
