# Clarice — Roadmap

Vince · active planning document · refreshed August 16, 2026

## Purpose

The forward-looking plan: what is active, what is next, what is deliberately
deferred, and what is still open. It is not the implementation spec for an
item; write a focused file in `design/` once work is ready to start.

What shipped — every release from Albatross through Heron, with its deployment
records and lessons — is in [`roadmap-history.md`](roadmap-history.md). The
standards used to deliver it are in [`principles.md`](principles.md). The
ordering behind releases, the charter every new model must satisfy, and the
directions this project has refused are in
[`architecture-trajectory.md`](architecture-trajectory.md). This file is the
authority on what is active and deferred; that one explains why.

The knowledge core's code lives in this repository; its **planning documents do
not**. `C:\dev\Clarice_secondmind` survives as documents only, and
`docs/design-concept.md` there remains the knowledge core's design authority.

## Where things stand — August 16, 2026

**There is no active release.** Heron was the last, verified in production
August 15. What it leaves is a baseline rather than a backlog:

- **One capture surface.** `/mind/`, writing a `Node`, and that is where the
  knowledge core lives permanently. `/capture/`, `Capture` and `Idea` are gone;
  `/capture/` came free and was deliberately not taken.
- **One of everything.** One API at `/api/v1/`, one token table with scopes,
  one login. `/api/v1/capture` is the application's, served by
  `mind/api_v1.py`; both the phone and the Day page post to it.
- **Two cores, one tree, one database.** The knowledge core is `src/mind/`;
  the task core is **Superlists**. The merger's direction ran one way and still
  does: Clarice was worked into Second Mind rather than the reverse.
- **No maintenance freeze on the task core.** A priority replaces it, see
  `CLAUDE.md`. Knowledge core and commercial substrate are where work goes.
- **`commercial-blueprint.md` Part 1 is closed** — all ten defects, August 15.
  There is no open production defect list.
- `django_migrations` keeps eight inert rows for the deleted `capture` app,
  **deliberately not deleted**: hand-editing production's bookkeeping to tidy
  something nothing reads is the worse trade.

Long-horizon knowledge work that used to sit in this file — idea resurfacing,
the mind-map, search over retained material — is **superseded, not deferred**.
It is planned in the Second Mind documents and built in `src/mind/`; do not
re-add it here.

## Open now

- ~~**`/api/v1/login` is unthrottled.**~~ Fixed August 18, 2026 (`9eb9eea`),
  with `/accounts/password/reset/` alongside it — an exact-match `limit_req`
  block each, proved by running nginx against the rendered template rather than
  by reading it. **Not live until the next deploy**, because an nginx template
  changes nothing until the playbook runs. What replaces it is a test:
  `clarice/tests/test_unauthenticated_endpoints_are_throttled.py` reads the
  template and the API together, so the *next* `auth=None` endpoint cannot ship
  unthrottled the way this one did.
- ~~**No mail leaves production at all.**~~ Closed August 18, 2026 (`jackdaw`).
  DigitalOcean blocks outbound 25, 465 and 587 on every Droplet, which is why
  three Sentry reports read as a flaky relay and were a total outage. Sending
  moved to Resend's HTTPS API. The proof kept deliberately: SMTP is **still**
  blocked from that host and mail goes anyway, so the fix is not coincident with
  anything DigitalOcean did.
- **Terms of service and a privacy policy.** Writing, not code.
- **Removing user data from Sentry and Resend when an account goes.** An
  account-level action in each, outside this application. Deletion and export
  inside Clarice shipped August 16.
- **Three genuinely open decisions in `commercial-blueprint.md` Part 9** — is
  this a business, which wedge, and mobile native versus responsive web. Two of
  its five are stale rather than open: #3 is answered but its reasoning predates
  the merger, and #5 was largely done by the August 15 documentation pass.
- **Whether the Android client keeps growing.** Slices 1 and 2 shipped (Today
  read-only, then Agenda with read and act); later slices are undecided. Part 9
  recommends freezing native for responsive web, on the evidence that
  `android-full-client-plan.md`'s core assumption — mostly an Android build-out,
  not a backend rebuild — was falsified twice, and that iOS is absent entirely.
  Nothing is scheduled. That plan's stub points here for this question.
- **Floating cadence is unbuilt.** ~~One defect to fix on the way in rather
  than port~~ — `_advance_due_date` spawning a successor already overdue —
  was fixed August 15, 2026 (`70bc6c8`), *after* the merger it was supposed to
  be fixed by, which is the argument for closing a defect where it lives rather
  than attaching it to a migration. What remains open is the mode: it is
  anchored-only, because Clarice has one cadence field and cannot say which
  mode a commitment is, while `design-concept.md` calls the distinction
  load-bearing. Deliberate, and recorded at the function.
- **Three navigations, three identities, and a login form for a home page.**
  "Review" names two unrelated things, "Today" resolves to two different
  destinations depending on which nav was clicked, and `/mind/` is a one-way
  door — both other navs link in and its own has no link out. Alongside that,
  **no `mind/` template calls `theme_resolution_script`** (zero of eight), so
  the theme toggle silently does not apply to a third of the application, and
  `--font-sans` names Inter while nothing loads it. And `/` is still
  `LandingLoginView`, which is [`product-stories.md`](product-stories.md)'s S1
  verdict in one line: *a landing page that is not a login form.* Designed
  August 18, 2026 in
  [`navigation-and-identity-plan.md`](navigation-and-identity-plan.md), which
  owns the sequence and carries its design in two comps rather than in prose.
  **Step 1 is done** — the ledger palette in both themes, the three typefaces
  self-hosted, and a 44px touch target that grows the hit area rather than the
  button; **steps 2 to 6 are open.** The three direction decisions it rests on — full re-theme,
  the A+B wedge for the signed-out page's positioning, one app bar over three
  reconciled navs — are Vince's, taken the same day; **Part 9 #1, whether this
  is a business, stays open and still gates Phases 3–5.** Its step 1 is also
  where **Mobile web experience** below gets its largest item cheaply: that
  entry has been waiting on `Button`'s height because changing it "restyles
  every page in the application", and a re-theme restyles every page anyway.

## Carried in from B / C / D — not schedulable work

Fourteen items came out of Bittern; eleven closed through Crane and Dunlin.
`crane-plan.md` §2 stays the authority on the full checklist. These three
remain, and none of them is a task:

- ~~**A real production 500 reaching Sentry.**~~ **Closed August 18, 2026.**
  Three incidents in three days answered it: an SMTP timeout in
  `send_due_digest` (Aug 16, the excepthook path), the nullable-Area
  `AttributeError` in the same command (Aug 18), and an SMTP timeout in the
  `contact` **view** (Aug 18) — the last of which is the web 500 this item was
  waiting on, arriving through the WSGI integration rather than the excepthook.
  Breadcrumbs on all three, and a query breadcrumb reading `[Filtered]`, which
  is the `EventScrubber` working on live data. B4's monitoring is proven end to
  end; what the incidents cost is in
  [`roadmap-history.md`](roadmap-history.md).
- **No Android emulator run.** This SDK install has no AVD and no way to build
  one without a multi-gigabyte download better done through Android Studio.
  Low priority: everything M4 wanted a device for is answered twice over on
  real hardware.
- **Release signing.** `app/build.gradle.kts` is wired for it; the keystore is
  deliberately left for Vince to generate by hand, because a non-rotatable
  credential is the wrong thing for an agent to generate and momentarily hold.
  The command is in
  [`android-release-signing-plan.md`](android-release-signing-plan.md).

## Track D — Postgres-enabled features

Candidates. Each needs its own product trigger or focused brief before it
becomes work.

- **Full-text search over Clarice's own material.** `Item.text`, `Item.notes`
  and `DailyEntry`'s three fields, ranked. There is no full-text search
  anywhere in the product — zero hits for `SearchVector`, `GinIndex` or
  `pg_trgm` — a daily journal entry is not searchable by any means, and no date
  picker exists to reach one by hand.

  **Trigger: fired.** The old entry (Reference/Idea search) asked for "enough
  retained material that finding something again is a felt problem" —
  anticipated, never observed, and unreachable, because nobody accumulates in a
  store they cannot search. Daily entries are already written, already numerous
  and already unfindable, so the problem exists today. This entry replaced the
  Idea half on August 13, 2026 and needs no discovery pass first.

- **Audit log and general undo.** Structured change records making more than
  task completion safely reversible. **No trigger.**
- **Time blocking.** Model calendar ranges and prevent a user's blocks from
  overlapping at the database layer. **No trigger.**

This section has asked every candidate for a trigger since August 2, 2026,
which is how a future candidate quietly becomes a plan. Two of the three above
have gone two weeks without one. **A candidate with no trigger is a candidate
nobody wants yet**; the honest options are to find the trigger or drop it, not
to let it accrue significance by sitting in a list.

## Later — visible, not scheduled

### Sharing

Shared lists with real-time updates, and conflict handling for concurrent
edits. These belong together. **Do not start either until list sharing itself
is a deliberate product decision.**

Two mechanism notes, recorded August 2, 2026 so they are not rediscovered from
scratch; both proposed rather than evaluated, neither a commitment. **Real-time
without Redis:** Postgres `LISTEN`/`NOTIFY` driving Server-Sent Events would
suit one small deployment better than adding a broker. **Granularity:** viewer
/ editor / co-owner is the obvious first split, and naming it early decides
whether permission is a column or a table. That sits close to row-level
security, whose trigger in
[`architecture-trajectory.md`](architecture-trajectory.md) §6 is this same
sharing work.

### Remaining public-readiness work

- Self-service signup with email verification.
- Rate limiting for capture. `/api/v1/capture` falls through nginx's catch-all;
  signup and login are throttled at 5r/m and this is not.
- ~~Account export and deletion.~~ **Shipped August 16, 2026** — self-service,
  a thirty-day grace period rather than immediate purge, and an export of every
  owned row as JSON beside readable Markdown.
- ~~Privacy policy and terms of service.~~ Tracked under *Open now* above.

Password recovery, adversarial per-user isolation tests, transactional email
via Resend and edge rate limiting for signup are all done.

### Support for people who are signed in

B3 gave strangers a contact path and left users without one: the link is in the
Django shell's nav, and users live in the SPA. The person most likely to have
something worth reporting has the worst route to reporting it. Not merely a
missing link — asking someone with a session to retype their name and email
invites an address that isn't the one on their account, and per-IP rate
limiting is the wrong key once there is an identity to use. The argument for
adapting `/contact/` rather than forking it is in
[`bittern-plan.md`](bittern-plan.md).

**Its promoter has already fired and nobody noticed.** The stated condition was
B4, production error monitoring, so that a signed-in report could carry its own
context. B4 shipped. This is promotable, not deferred.

### Public updates page

An unauthenticated page announcing what has shipped, written for people rather
than the repository — closer to a short press release per release than to a
changelog. No account, no login wall.

**No broad roadmap preview.** The page does not publish tracks, Later items, or
what the next release might contain. The single exception is a specific named
feature already in development, and it needs a definition or it drifts back
into promising: a feature qualifies when it has a focused spec in `design/` and
work has actually begun. A candidate sitting in a Later list never qualifies.

Two things to settle. **Where the text comes from:** the annotated release tags
and `roadmap-history.md` are both written for the developer, so expect to write
the public version by hand and treat those as sources, not drafts. **Which
stack renders it:** unauthenticated, cacheable and wanting to be indexable, so
a Django-rendered page rather than an SPA route, in keeping with the settled
boundary that only the task UI is SPA-only.

**What would promote it:** somebody unauthenticated to read it — realistically
alongside self-service signup.

### Mobile web experience

Making the browser application genuinely usable on a phone, as opposed to
merely surviving a narrow window. This is not the Android client: everything
beyond capture and the two shipped Android slices happens in the browser, and
"the app captures, the web app reviews" assumes the web app is reachable from a
phone. It is not really.

**Measured, not guessed.** Both shells set
`<meta name="viewport" content="width=device-width, initial-scale=1">`. Beyond
that there are exactly two layout breakpoints — side navigation collapses at
760px, the workspace input row stacks at 768px. Those two numbers should agree
and do not. Everything else is desktop-first.

**Touch targets are the largest thing in this entry**, found with numbers
attached during Crane 1 slice 7's phone pass. At 375px the Daily Page itself is
sound — no horizontal overflow, everything works — but its buttons measure
32px and its "Edit your compass" link 20px, against the ~44px both platform
guidelines and WCAG 2.5.8 ask for; the Agenda, untouched by Crane, is worse at
19–31px. The height lives on the shared `Button` primitive, which is still
`h-8`: the 44px fixes made during the Tailwind arc were applied per call site,
not to the primitive. Changing it restyles every page in the application —
which is why `navigation-and-identity-plan.md` puts it in the step that
restyles every page anyway, rather than leaving it here waiting for a pass of
its own. The two disagreeing breakpoints are in that plan's blast radius too:
its step 3 rewrites the machinery that holds them.

**One responsive application, not a mobile site.** No `m.` host, no second
codebase, no divergent templates. One API, one SPA. Said once so it is not
reopened.

**The overlap with native should be decided, not discovered.** Native earns its
cost through launch speed, Keystore-backed token storage, WorkManager retries
and the Android share target. A capable installable web app can approximate the
share target and an offline queue, less reliably. If mobile web lands well, M5
and parts of M3 deserve a fresh look rather than being finished out of
momentum.

**What would promote it:** daily phone use producing observable triage
friction. One device pilot is not that. Crane made its own new surfaces
mobile-aware — the Daily Page and the weekly review were each measured at
375x812 against the built bundle, both clean — and did not close this entry.
The older surfaces, the two disagreeing breakpoints and the touch targets are
all still here. Watch real failures rather than redesigning from a hunch.

### Recorded candidates with no trigger yet

Three ideas salvaged August 2, 2026 from an abandoned review branch. They were
generated by an outside review of the codebase, not by using Clarice and
wanting them, and none has a trigger — recorded as ideas rather than promoted
to Track D, because writing something down is not deciding to build it.

- **A calendar feed.** An authenticated read-only ICS endpoint so due dates
  appear in Google, Apple or Outlook calendars. It points the opposite way from
  time blocking: that models calendar ranges *inside* Clarice, this publishes
  what exists to a calendar someone already reads. Cheaper, and possibly the
  only one of the two ever wanted.
- **Natural-language due dates.** "Next Friday", "tomorrow at 3pm" parsed on
  input. The server owns date meaning, so parsing belongs server-side with the
  client showing what was understood before it is committed — an automation
  that proposes rather than silently decides.
- **A command palette.** `Ctrl+K` over tasks, lists and nodes. Genuinely
  premature: it is a *retrieval* affordance, and full-text search above is the
  thing that earns retrieval work first. Revisit it with that, not before.

### Longer-term product direction

- Build out the Daily Page's weekly, monthly and quarterly review cadence from
  the direction set for Crane. Weekly exists — its honest denominators are the
  single strongest thing built here — and the wider horizons do not.
- ~~Idea resurfacing, a mind-map view, an append-only idea log, and AI as a
  confirm-before-write planning assistant.~~ **All moved to the knowledge core,
  August 13, 2026**, and built further there than these lines imagined. Its ML
  policy is stricter than the AI line was; v1 ships no generation at all.

### Only if Clarice becomes a business

Billing, support operations, deeper legal requirements and horizontal scaling
remain out of scope until the public-readiness bar is genuinely met.

## Settled boundaries

- Notes remain plain text; no Markdown renderer.
- Subtasks are one level deep only.
- Completing every subtask does not auto-complete its parent.
- Only top-level tasks recur.
- `/mind/` is where the knowledge core lives, permanently — settled August 15,
  2026, not left temporary. Cheap to revisit: the prefix appears in one line of
  `clarice/urls.py` and everything under it is relative.
- **SSL expiry alerting is refused, not missing.** UptimeRobot paywalls it,
  certbot renews automatically. Recorded so nobody re-investigates and reaches
  the same paywall.

## Release practice

Production releases use alphabetic bird codenames: `albatross`, `bittern`,
`crane`, `dunlin`, `fulmar`, `godwit`, `heron`. **Tag only after production is
verified.** The letter carries; the bird is chosen when the release ships. The
sequence skips E — Vince's call, August 3, 2026 — and the next release takes I.

- `LIVE` is a moving tag for the code currently running. It is the only tag
  ever overwritten, which is safe precisely because the position it leaves is
  kept by the `DEPLOYED-` tag that marked it.
- `DEPLOYED-<date>/<HHMM>` is a permanent deployment-event tag.
- The bird codename is a permanent annotated release tag describing what
  shipped and how it was verified.

**Letters are never reserved for a subject** — Vince's call, August 15, 2026,
after `architecture-trajectory.md` §5 speculatively attached commercial
readiness to "release G" and Godwit spent that letter on the merger. A letter
is the next position in a sequence, claimed by whatever ships next.

**A release is a coherent body of work with a finish line.** The letters lapsed
between August 6 and 12, when six of seven lines of work shipped outside the
release structure, and were deliberately restored on August 15 — the merger was
exactly the coherent body of work the letters had stopped naming. Fulmar and
Godwit were assigned belatedly to close the gap, and Fulmar's annotation admits
its verification was piecemeal.

**Tagging is a step in the deploy, not something remembered afterwards.** It
drifted badly through August because it was written down here as a convention
and nowhere as a step. The step is in `CLAUDE.md`.

## Keeping this current

Update this file when work begins, changes scope, ships, or is explicitly
deferred. When an idea from Later earns work, give it a one-line reason and a
focused spec before it joins an active track.

**Move completed detail into [`roadmap-history.md`](roadmap-history.md) and
keep only the resulting baseline or remaining consequence here.** That
instruction has been in this file since August 1 and has been ignored twice —
257 lines migrated out on August 13, and 272 more on August 16, by which point
the file was contradicting itself about work it recorded as both open and
closed. If a section here is describing the past at length, it is in the wrong
file.
