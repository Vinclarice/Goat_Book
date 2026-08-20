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

**Kept as a dated snapshot rather than rewritten**, because the baseline below
is still exactly right and only its first sentence went stale. Since August 16
the releases have been Ibis, Jackdaw, the navigation and identity work, signup
with the legal documents, and `kestrel` — the planning assistant, August 19,
which spent the letter K. ~~Left no active release again~~ — **release L
opened on August 19 and half of it is live**; the snapshot below is what a
baseline looked like before it, and *Open now* carries the current state, as it
is supposed to.

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

- **Release L is open, and its bird is not chosen.** *Tag only after production
  is verified* — so the letter is claimed, the name waits, and this entry is
  what the release is until it has one. **Half of it is already live.**

  **Deployed August 19, 2026** (`DEPLOYED-2026-08-19/2338`, image
  `a60df12fc9ad`, migrations applied and none pending). What went out:

  - **The planning assistant's second version, increments 1–8** — the entry
    below carries the detail.
  - **The second factor's machinery**, installed and *enforcing nothing*.
    Enrolment before enforcement is the ordering `admin-mfa-plan.md` insists
    on, so this half is deliberately inert until somebody has enrolled.
  - **Mail no longer waits on reverse DNS**, which cost a browser-suite journey
    twelve seconds and two wrong diagnoses before it was measured.
  - **Two test-infrastructure fixes**: a test database name derived from the
    checkout, and a CI check on recorded file modes.

  **What it still needs before it is a release** is Vince's to add — the point
  of leaving the bird unchosen is that a release is *a coherent body of work
  with a finish line*, and this one has not reached its. When it does: verify in
  production, then the annotated codename tag, then the narrative moves to
  [`roadmap-history.md`](roadmap-history.md) and this entry becomes its stub.

  **A deployment is not a release**, which is exactly what the two tag kinds
  are for. `DEPLOYED-2026-08-19/2338` permanently records that this code ran;
  the codename will record what the work *was*. Fulmar's annotation admits its
  verification was piecemeal precisely because those two got conflated once.

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
- ~~**The planning assistant.**~~ **Closed August 19, 2026**, shipped and
  verified in production as `kestrel` (`DEPLOYED-2026-08-19/1339`). All six
  increments: commitments read out of the journal, unresolved questions with
  the notes that came back to them, a project that can say what it is for and a
  brief that retrieves what bears on it, the weekly review's loose ends, and
  next week drafted against observed capacity. Every proposal cites the passage
  that caused it and nothing is created without a confirmation.

  **`v1 shipped no generation at all`**, which is `design-concept.md`'s ML
  policy holding rather than a corner cut — D1 deferred generated prose with two
  firing conditions written down rather than a someday.

  Two of `product-stories.md`'s target-model items moved as prerequisites rather
  than as features: **S9's weekly intention** exists, and **S3 no longer
  requires `Item.effort`** — capacity is derived from `DailyFocus` history, so
  there are no estimates to go unentered. ~~Neither story's verdict moved~~ —
  **re-scored against this release later the same day, and three verdicts did**;
  that file owns the score and is not quoted here.

  ~~**What the re-score found and this file has to carry: S9's write path does
  not exist.**~~ **Built August 20, 2026** as v2's increment 1 — see the entry
  below, which is where that work continued.

  The narrative, the four decisions and the three silent-nothings that build
  turned up are in [`roadmap-history.md`](roadmap-history.md); the v1 plan is a
  stub.

- **The planning assistant's second version is the active work.** Designed and
  being built to
  [`planning-assistant-v2-plan.md`](planning-assistant-v2-plan.md): the weekly
  planning *session*, on the review's forward half rather than a second
  surface. **Eight of its nine increments are complete and live** — deployed
  August 19, 2026 as the first half of release L, see the entry above — the
  weekly intention made reachable (which closed the item
  struck above), capacity at day grain where D2 always specified it, a project
  that can say what done looks like and be parked, a check-in that opens with
  what the system believes, outcomes chosen from evidence, blockers answered
  where they are read, the week laid out by day and stress-tested, and scenario
  planning.

  **Nothing in it generates anything**, which is the finding that shaped it:
  twelve of fourteen elements needed no prose at all, and the two that do are
  the sites D1 already ranked. Scenario planning — the part that feels most like
  an assistant — is `draft_week` with one argument.

  **Increment 9 may never ship, and that is the correct outcome rather than a
  failure**: ranking by confirmation history is gated on a sample floor a corpus
  of 41 nodes has not cleared. Three smaller pieces were deferred and named in
  `abcfc51`: confirming a recurring name in place, the planning-miss signal, and
  "schedule a decision" as a third disposition.

  **Two decisions dissolved on contact with the code** and are recorded there
  rather than here: D5, whether the review may decide things, which it already
  did through the owning core's services; and D6, where the ritual lives, which
  does not bind while only questions are acted on because a question carries no
  review window. D1, D2, D4 and D7 remain open; the score is
  [`product-stories.md`](product-stories.md)'s and is not quoted here.

- ~~**Terms of service and a privacy policy.**~~ **Written and published
  August 19, 2026**, at `/privacy/` and `/terms/`, linked from a footer on
  every signed-out page and from the signup form. Owned by Vinclarice, LLC;
  hosting named as DigitalOcean's New York region. Every claim was checked
  against the source and a dozen tests hold the ones with a mechanical
  counterpart — the deletion window, the digest default, the four Sentry
  exclusions, the absence of analytics — so the code cannot drift away from a
  published promise silently. **The one claim no test can hold is the hosting
  region**, and the template says so at the paragraph.
  **Deliberately not lawyer-reviewed, and the trigger for changing that is
  named: broader beta testing.** Vince's call, August 19 — proportionate while
  the site is privately owned and invitation-only. What a professional read
  would want, and what is therefore still absent: the LLC's state of formation
  and business address, a governing-law clause, and a considered answer on the
  minimum age (16 is asserted).
- **Removing user data from Sentry and Resend when an account goes.** An
  account-level action in each, outside this application. Deletion and export
  inside Clarice shipped August 16.
- **Three genuinely open decisions in `commercial-blueprint.md` Part 9** — is
  this a business, which wedge, and mobile native versus responsive web. Two of
  its five are stale rather than open: #3 is answered but its reasoning predates
  the merger, and #5 was largely done by the August 15 documentation pass.
- **Unified search is active and usable, and undeployed.** Designed and built
  to [`search-plan.md`](search-plan.md). **Three of its five increments are
  done**, and the third is the one a person can use: `/mind/search/` now
  answers in three sections — notes, tasks and days — from one box.

  What landed August 20, 2026, all on `main` and **none of it deployed**:
  generated `tsvector` columns with a `GinIndex` on `Item` and `DailyEntry`
  and two migrations; `lists/search.py` and `daily.reads.search_entries`;
  `clarice/search.py`, holding the one definition of how typed text becomes a
  query, because sectioned results have a quiet dependency on every section
  having asked the same question; `GET /api/v1/search`, session-only; and the
  page. 42 new tests.

  **All four decisions are answered and the brief records them** — the endpoint
  went in `mind/api_v1.py` beside capture, and the surface is the page that
  already existed, which is what keeps search attached to the miss button.

  **D4 said no to the command palette and found the real gap instead: nothing
  in the task core linked to search at all.** Four navigation surfaces were
  checked and only the knowledge core's own sub-nav had it, so reaching search
  from the task core meant two hops through the other core's capture page — for
  a feature built partly to search tasks. One link in the shared app bar,
  in the utility group rather than the Cores nav, because search belongs to
  neither core. The palette entry below carries the trigger to watch.

  **D3 turned out to be the wrong question, and answering it caught a defect
  this work had just created.** It asked whether `RetrievalMiss.resolved_node`
  should widen to reach a task; it should not, because nothing has ever
  populated that field — **the fourth un-switched-on seam found in a
  fortnight.** What did need fixing is that the retirement gate's *"retrieval
  misses fall"* counted every miss, which was exact only while this page
  searched notes alone. A miss now records what each section returned and the
  gate counts the ones where the note index returned nothing. **Fixed before
  the deploy on purpose**: a miss cannot be re-interpreted afterwards, so every
  one recorded in the gap would have been permanently ambiguous.

  **Sectioned, never merged, and that is a refusal rather than a first
  version.** `SearchRank` compares documents within one set and means nothing
  across two, so one ordered list would present a number that does not exist as
  relevance. Validating a weighting would need the retrieval evidence that does
  not exist yet — which is what the miss button is for.

  Two things were decided at the keyboard and are recorded at the code rather
  than here: search returns every status, where the agenda hides finished work,
  because the older a task is the more likely it is both done and the one being
  looked for; and `Item` weights its text above its notes, which is safe within
  one model in a way ranking across two is not.
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
- ~~**Three navigations, three identities, and a login form for a home page.**~~
  **Closed August 18, 2026**, shipped in two deploys and verified in
  production. What replaced it: one server-rendered app bar on all three
  surfaces, a per-core sub-nav, the rail demoted to contents, the ledger
  palette and three self-hosted typefaces in both cores, and `/` as a landing
  page rather than the login form. The narrative and its six lessons are in
  [`roadmap-history.md`](roadmap-history.md); the plan is a stub.
  **The codename was deliberately held** to ship with the planning-assistant
  work, and was spent on `kestrel` on August 19. **What this did *not* close is S1**, which also wants self-service
  signup with email verification — still an admin checkbox, and
  `accounts/emails.py` still has no message telling the applicant it happened.
  [`product-stories.md`](product-stories.md) owns that score.

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

- ~~**Full-text search over Clarice's own material.**~~ **Stopped being a
  candidate on August 20, 2026** — briefed as
  [`search-plan.md`](search-plan.md), started the same day, and now carried
  under *Open now* above, which is where active work lives. The trigger that
  fired and the argument for it are in the brief; this section's job was to
  hold the candidate until one of those existed, and it is done.

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

- ~~Self-service signup with email verification.~~ **Shipped and deployed
  August 19, 2026, and it does not close S1.** Confirming an address is
  self-service now — a single-use signed link, the applicant finally told
  something, a resend for when the mail is lost, and the two waits told apart
  at the login form. An account being approved now writes to the person too,
  which three surfaces had been promising for a day before anything sent it.
  What stays is approval, which is still a person: `is_active` is approval and
  `email_confirmed_at` is confirmation, kept separate so opening the doors is
  later a policy change rather than a redesign. **Deliberate** — the site is
  invitation-only, and the privacy policy that made this publishable is the
  item struck above. [`product-stories.md`](product-stories.md) owns the score;
  [`roadmap-history.md`](roadmap-history.md) has the narrative.
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
`<meta name="viewport" content="width=device-width, initial-scale=1">`.
~~Beyond that there are exactly two layout breakpoints — side navigation
collapses at 760px, the workspace input row stacks at 768px. Those two numbers
should agree and do not.~~ **Fixed August 18, 2026** by
`navigation-and-identity-plan.md` step 4: the rail's collapse is Tailwind's
`md` on both sides now, and `test_frontend_style_contract.py` fails if the CSS
and the JavaScript drift apart, which is what the comment asking the next
person to remember was standing in for. Everything else is still desktop-first.

**Touch targets are the largest thing in this entry**, found with numbers
attached during Crane 1 slice 7's phone pass. At 375px the Daily Page itself is
sound — no horizontal overflow, everything works — but its buttons measure
32px and its "Edit your compass" link 20px, against the ~44px both platform
guidelines and WCAG 2.5.8 ask for; the Agenda, untouched by Crane, is worse at
19–31px. ~~The height lives on the shared `Button` primitive, which is still `h-8`.~~
**Half-closed August 18, 2026.** The primitive now carries a `touch-target`
utility that grows the *hit area* to 44px under a coarse pointer while leaving
the drawn control where it is — raising the real height would have fixed phones
and wrecked the dense desktop layouts this is mostly used in. So every button
in the application clears the floor, and every new call site inherits it rather
than needing its own override.

**What remains is the links.** "Edit your compass" is still a 20px anchor, and
the utility is available to it — this was a fix to the primitive, not a sweep
of every control. The overlap tradeoff is recorded at the utility: two controls
closer than ~12px apart now overlap targets on touch and the later one wins.

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
- **A command palette.** `Ctrl+K` over tasks, lists and nodes. ~~Genuinely
  premature: it is a *retrieval* affordance, and full-text search above is the
  thing that earns retrieval work first. Revisit it with that, not before.~~
  **Revisited August 20, 2026 when search shipped, and still no** — the answer
  is `search-plan.md`'s D4 and the reasoning is there. In short: that condition
  was a *precondition*, and clearing it removes an objection without supplying
  demand. A candidate with no trigger is a candidate nobody wants yet, which is
  this section's whole standard.

  **The trigger to watch is friction in reaching or repeating a search**, now
  that one is a click away from both cores — and it **fires on felt friction**,
  which `principles.md` makes admissible evidence. That matters: nothing
  instruments how long it takes to open a search box, so a trigger requiring a
  measurement could not fire, and this entry would be a deferral pretending to
  be one. **`RetrievalMiss` cannot supply it** — it measures whether search
  succeeded, not how long it took to ask — so nobody should watch the miss
  count for this.

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
sequence skips E — Vince's call, August 3, 2026. Since then `ibis`, `jackdaw`
and `kestrel` have taken I, J and K, so **L is the current letter** — and it is
already claimed rather than next. See *Release L, open* under **Open now**;
what it is called is decided when it is finished, which is what "the bird is
chosen when the release ships" means.

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
