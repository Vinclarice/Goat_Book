# Clarice — Roadmap History

Vince · completed work and decision record · archived from `roadmap.md` on
August 1, 2026

## Why this file exists

This preserves the reasoning, deployment record, and lessons behind completed
work without making the active roadmap hard to scan. The active plan is
[`roadmap.md`](roadmap.md).

## Production defects — Part 1, opened August 12 and closed August 15, 2026

Ten defects found by the commercial audit. All closed. `commercial-blueprint.md`
Part 1 carried them in full until August 16; it is four lines now, because a
defect list with nothing on it is a document outliving its work.

| # | Defect | Closed by |
|---|---|---|
| 1 | CI had failed 17 consecutive runs | `fd4a8d7` — and it needed three fixes, not one: the `mind` suite was not in CI at all, `postgres:18` carries no pgvector, and the browser job could no longer use SQLite |
| 2 | Token-authenticated writes recorded the wrong day | `6da41c8`, at `_resolve_scoped_token` — the seam both token paths share, rather than at the six endpoints that each forgot |
| 3, 4 | Two dropped Tailwind styles | `2986ed6` — **already shipped on August 12**; the list said otherwise for two days |
| 5 | A white screen on any render exception | `0428efb` |
| 6 | Tags dropped on one of two promotion routes | Declined August 14; moot August 15 when Heron deleted both routes |
| 7 | The Android capture queue had no lock | A process-wide lock on the companion object — not `@Synchronized`, which would have passed a shared-queue test and protected nothing |
| 8 | The queue was included in Android backups | Excluded in *both* `backup_rules.xml` and `backup_rules_legacy.xml` |
| 9 | Nothing would tell you the site was down at 3am | `/healthz` (`fd896c6`), `restart_policy: unless-stopped` (`b2e16b2`), and UptimeRobot polling it from August 15 |
| 10 | Sentry could ship private note text | `bbfc38d` — `include_local_variables` defaults to `True` and is independent of `send_default_pii=False` |

**Three lessons cost a session each and outlive the defects.**

**A signal that is always red carries no information.** CI failed seventeen times
and stopped being read; the same shape appeared twice more that week — certbot
failing on a deleted staging certificate, and a defect list nobody trusted.

**A fix does not repair what the defect already wrote.** Defect 2 filed real
`RoutineOccurrence` rows against the wrong date for as long as it existed.
Nothing ever recorded which auth path created a row, so a repair would have to
guess at a durable record — which `principles.md` refuses. Left alone
deliberately, and recorded so it is a decision rather than an oversight.

**The list twice described finished work as open**, which cost more than the
defects did — a session of re-investigation on the Android pair, and two days on
the Tailwind pair. If a list like this exists again, check the code before
believing it.

## Account deletion and data export — August 16, 2026

The first piece of the commercial substrate, and the one that did not wait on
`commercial-blueprint.md` Part 9's unanswered first question — *is Clarice a
business, a product with users, or a personal tool* — because the answer is the
same either way. The blueprint calls the pair a legal blocker rather than a
feature gap: Sentry and Resend already process other people's data.

**Deletion was not unbuilt, it was impossible.** `ActivityEvent` is append-only
by database trigger, firing `BEFORE UPDATE OR DELETE`, and `ActivityEvent.owner`
was `on_delete=CASCADE` — so `User.delete()` issued a `DELETE` against the log
and raised. The model had reasoned exactly this through for its *node*
reference, whose comment says "CASCADE, SET_NULL and SET_DEFAULT are each a
*mutation* of the log, which the append-only trigger refuses", and made that one
non-constraining. The owner reference never got the same treatment, because
nothing had ever deleted an account.

**The line taken: append-only means history cannot be rewritten within a live
account.** It was never a promise to outlive the account's own erasure — and it
could not be, because the log is not content-free. `purge_node` keeps events on
the stated grounds that a purge payload "retains no content", which is true of
nodes; concept events carry the labels somebody typed, which on real material
include other people's names, and every event carries the username as `actor`.

The exemption is narrow on purpose: `DELETE` only, naming **one owner id**,
read from a **transaction-local** setting. A boolean would have passed the
"erases my log" test and failed the "does not touch anybody else's" one, which
is why both exist. `SET LOCAL` matters because connections are reused across
requests.

**A thirty-day grace period, and `is_active` deliberately untouched.** That flag
already means "pending admin approval", and one flag for two unrelated states is
indistinguishable everywhere it is read. The account stays fully usable while
leaving, which is also what keeps *cancel* reachable without inventing a
signed-link email flow for a window that is the person's own to close.

**Two things were found by reading rather than by asserting.** A fixture claimed
to cover every owned model and missed four — caught by the "another account is
untouched" test failing, since a neighbour with no rows cannot have them
preserved; there is now a test that the fixture populates what it claims. And an
export for an account with no areas produced a `tasks.md` containing the word
"Tasks" and nothing else, which a reader cannot tell from a broken export at the
exact moment they most need to trust the file.

**And four more came from Vince reading the copy rather than the code**, which
is the review the tests could not do — every one of them passed against wording
that was not good enough.

* **It never said "permanent".** The copy read *erased after 30 days*, which
  implies irreversibility rather than stating it. For the one control on the
  site that destroys data, implying is not enough. It now says permanently
  deleted and cannot be recovered, in the section, in the banner and in the
  email, and tests assert those words.
* **There was no acknowledgement.** Password re-entry was the only friction, and
  it guards the wrong mistake: it stops a passer-by at an unlocked screen and
  does nothing about somebody who has simply misread what the button does. Two
  gates now, and the tests say which mistake each one guards.
* **Nothing was emailed.** The thirty-day window only protects somebody who
  finds out inside it, and a banner cannot guarantee that. Three messages now —
  scheduled, cancelled, and a receipt sent immediately before the rows go, which
  reads the address *before* the delete because a receipt that depends on the
  record whose destruction it confirms is one that never sends.
* **The banner was built to be global and wasn't.** `deletion_purge_at` was put
  on the nav payload specifically so it could render on every route, and then it
  was only wired into Preferences — the data was right and the component was in
  the wrong place. `DeletionBanner` now lives in `AppLayout` and carries the
  stop button itself, because "go and find the page where you did it" is harder
  than starting it was.

**One nav entry went with it.** "Settings" sat beside "Preferences" and linked to
`/accounts/settings/`, which is a two-line view that redirects to the
`/preferences` route: two names for one screen, the second taking a round trip
through the server to arrive at the first. Vince read it as two pages worth
merging; it was one page with two doors. The URL stays — it is bookmarkable and
`change_password` redirects to it — and the duplicate door is gone.

Verified by 911 Django, 616 pytest, 277 frontend and 32 browser tests, including
a browser test that downloads the archive and opens it. The secrets exclusion was
checked by emptying it and confirming the password and token hash then appear —
the test would have caught its removal, which is not the same as the test having
been watched fail.

## Heron — the crossover, August 15, 2026

**Tagged `heron` on `04e7c71`.** All five steps built, deployed and verified in
production in one day: 1–4a at 1200, then 4b and 5 together at 2030 — held to
one deploy on Vince's call, so that the crossover was never half-live. This is
the narrative, so that `roadmap.md` can carry the baseline rather than the story;
the plan is [`one-capture-surface-plan.md`](one-capture-surface-plan.md).

**Steps 1 and 2** wired a typed tag to a confirmed concept and carried a node's
concepts onto the task made from it. Almost no new machinery — `ConceptCandidate`
already had `label`, `confirmed_at` and `reason`, and `propose_mention` with an
explicit origin already self-confirmed. The trade it settled was real, though:
the Inbox modelled tags as first-class rows and the knowledge core deliberately
models none. The reconciliation is that **the gravity gate exists to filter the
system's guesses.** Three mentions across a day is what an *extracted* candidate
pays because extraction over-generates on purpose. A person typing a tag is not
a guess and owes that gate nothing.

**Step 3** moved 34 captures and 2 ideas into the graph carrying their original
timestamps, 22 of them archived on the way in as discards. The corpus is the
binding constraint on the whole knowledge core, so this was not cleanup that
preserved data — it was the step that gave the detectors something to work on.

### 4a, and the check that came back the other way round

Step 4 said to *check first that nothing on the phone still uses the task-core
capture scope*, on the belief that `Backends.kt` already routed capture to the
knowledge core. **It does not, and never has on any shipped build.**
`secondMindBaseUrl` defaults to `""`, so `isSplit` is false and `capture` is
literally the same object as `workspace`. Every thought typed on the phone posts
to the task core's `/api/v1/capture`. Deleting it, as step 4 planned to, would
have drained the encrypted offline queue into 404s.

The plan had also miscounted the surfaces. It said two; there were three — the
SPA Day page's quick-capture box posts to the same endpoint on session auth.

So the step became: keep the URL, the bearer token and the `capture:write`
scope, change what they write. `/api/v1/capture` writes a `Node` now, through
`services.capture_idempotent`, shared with `/mind/api/v1/capture` so the two
cannot drift. The router moved from `capture/api_v1.py` to `mind/api_v1.py`,
leaving the `capture` app with nothing on the API — which is what turns 4b from
a migration into a deletion. No APK rebuild, nobody logged in twice, and one
`/api/v1/` for one application.

`mind/urls.py` had already written down the answer: the two definitions of
`/api/v1/capture` were "the dual-write question arriving early, and it is
answered when facets land — one capture endpoint that writes a node and
optionally a task."

**A fix that had shipped to the wrong endpoint.** Android sends `captured_at`
from both call sites — `CaptureViewModel.deliver` and `QueueDrainer.drain` — so
a thought that waited hours in the queue arrives with the time it was written.
The live endpoint's schema was `text` and `tags` only, so Ninja dropped the
field in silence. It had been found and fixed once, on the August 14 device
pass, on `/mind/api/v1/capture` — which nothing calls. The defect stayed live on
the real path for a day, and the 22 device-test captures now in the graph carry
delivery times rather than writing times as a result.

**The lesson, and it is the third time in two days.** `/healthz` existed and
nothing polled it. The detectors were built, tested and green and were never
invoked. Here a two-backend seam was written, documented, unit-tested and never
switched on, and a fix for a real defect landed on the half nobody used. Code
that exists is not code that runs, and a test that walks the wrong endpoint
proves the wrong thing — `test_journeys.py` was doing exactly that, posting to
`/mind/api/v1/capture` with a `mind.ApiToken`, and now walks the real route with
the real credential.

Deployed at noon on August 15 as `DEPLOYED-2026-08-15/1200` (`99d48a2`), which
`LIVE` now points at. Verified by 974 Django tests, 686 pytest, 271 frontend, 30
browser and a clean build, then in production: the live OpenAPI schema carries
`captured_at` and returns `{public_id, captured_at}`, and an offline capture was
walked from the phone through the queue to `/mind/`.

**A last capture had reached the Inbox after the migration and before the
deploy** — "Barry tv show", August 15 — which is exactly the gap the re-run of
`migrate_inbox` exists to close. The graph stands at 41 nodes, 19 of them visible
to the detectors.

**Both of that command's counts describe the input rather than the action**, and
it is worth saying because somebody read them to decide whether to proceed. The
dry run lists everything in `Capture` rather than what it would write, so one new
capture reads as thirty-five; and "22 discarded capture(s) archived" counts the
discarded captures it walked past, not the nodes it archived. Neither is wrong
about the world, and neither answers the question being asked of it. The command
retired with `Capture` in 4b rather than being fixed.

### 4b — the deletion, and three things it did not cause

`/capture/`'s pages, forms, services, admin and tests are gone, with `Capture`,
`Idea` and `migrate_inbox`. Inbox and Ideas left both navs — the SPA's `SideNav`
and the Django `base.html` — and `inbox_count`, `inbox_url` and `ideas_url` left
the `/nav` payload. **`inbox_count` was the only number in that nav measuring a
backlog**, and nothing replaces it; a test now asserts that no nav key ends in
`_count` except `archived_count`, because a bare entry invites somebody to add
one and the attention policy exists to refuse exactly that.

`capture` stays in `INSTALLED_APPS`. Django needs it there for the delete
migration to run; removing the app in the same change would leave two tables in
production that no migration could reach. That is a follow-up, after the deploy.

Three things broke, and none of them were about capture:

- **`base.html` reversed `capture_inbox` and `ideas`.** Every Django-rendered
  page 500'd. The suite caught it in the first run.
- **The generated migration would not reverse.** `idea_owner_status_idx` covers
  `owner`, and unapplying `DeleteModel` runs before unapplying `RemoveField` —
  so a rewind rebuilt the table and then tried to index a column it had not
  re-added. Nothing in production would ever have reached it; the
  migration-rewind tests did. Fixed with a `RemoveIndex` first, on the grounds
  that a migration nobody can back out of is worst at the moment they want to.
- **Four migration-rewind tests only rolled their own app forward** in teardown.
  Harmless for as long as every table had a live model, because the inter-test
  flush truncates by model — and fatal the instant a table had none, surfacing
  as `cannot truncate a table referenced in a foreign key constraint` in a test
  about checklist steps. They now roll the whole graph forward, which is what
  their own comment already claimed and what `accounts` had always done.

The pattern in all three: **deleting a model is a schema change, and the things
it breaks are the things that quietly depended on the schema being wider than
they needed.** None was found by reading the diff.

872 Django, 672 pytest, 270 frontend, 30 browser, clean build.

Deployed with step 5 at 2030 as `DEPLOYED-2026-08-15/2030`. The pre-flight ran
first, against production while the models still existed, because `0008` has no
reverse and after it there is nothing left to check against: every `Capture` and
`Idea` row accounted for by a `Node` with an `inbox:` import key. Confirmed after
with `showmigrations capture` — `[X] 0008_delete_idea_capture` — because the
migration runs in its own container before the app is recreated and could in
principle fail without the play visibly failing.

`/capture/` and `/capture/ideas/` now answer 404 where they used to redirect to a
login, and the live `/nav` payload carries none of `inbox_count`, `inbox_url` or
`ideas_url`. Those are the two observable facts that say 4b actually landed.

### 5 — the URL that did not move

Step 5 was written as *move `/mind/` to the URL 4b frees*, and asking the
question directly reversed it. **`/mind/` is permanent — Vince's call.**

`/capture/` came free and was deliberately not taken. Nine routes live under
`/mind/` and only one of them is capture; the rest are review, concepts, search,
numbers, share, the manifest and two actions. `/capture/concepts/` reads as
nonsense, and scattering them across the root instead — all four paths were free
— would have put a second "review" beside the task core's weekly one and spread
a single core across four places, ending the property that made the step cheap.
Against a rename with no winner stood a live PWA home-screen shortcut and every
bookmark.

**"Temporary" was a reason to reconsider the name once the collision was gone,
not an obligation to move.** The change was therefore subtraction: the word came
out of `clarice/urls.py`, `mind/urls.py`, both navs and their tests, replaced by
the reason it is permanent. It is still one line and everything under it is
still relative, so it is settled rather than welded.

This also answered a question the plan had listed as beyond it — where the
knowledge core's other pages live. They stay together, under a different root
from the task core's `/app/`: two cores, two homes, one login, one nav reaching
both.

### The leftovers, cleared the same day

Two things Heron made retirable rather than retiring, both deleted immediately
after the release was tagged.

**`/mind/api/v1/` and `mind.ApiToken`.** The knowledge core arrived with its own
`NinjaAPI` — login, me, tokens, captures, search, review, summary — and its own
bearer token table with an `sm_` prefix and its own resolver. It existed so the
Android app could point at a separate Second Mind server by setting one build
property. **No shipped build ever set it, and the `/mind/` pages carry no
JavaScript at all**, so nothing had ever called it from either direction. The
application now has one API, one token table — `PersonalAccessToken`, which has
scopes, which this never did — and one login.

Dropping the table took the same pre-flight 4b took, for the same reason: a row
would have meant a device this silently disconnects, and after the migration
there is nothing left to ask. Production returned **0**.

**The `capture` app.** 4b left it installed holding nothing but migrations,
because Django needs an app installed for its migrations to run and `0008` is
what dropped the tables. With that applied in production the shell went too. No
other app's migrations depended on it, which was checked first because it would
have been the blocker. `django_migrations` keeps eight inert rows; Django
ignores rows for apps it does not know, and editing production's bookkeeping to
tidy something nothing reads is the worse trade.

**One test was rewritten rather than deleted, and it is the point of the whole
exercise.** `test_capture_time_zones.py` asserted that a token capture reads
"tomorrow" in the *owner's* zone — the twin of `commercial-blueprint.md` defect
2, found by asking whether the task core's bug had a counterpart here. It ran
through `/mind/api/v1/capture`. Deleting that endpoint would have removed the
only coverage of a behaviour that is still live, on the grounds that an unused
route went away; it now runs through `/api/v1/capture` on a
`PersonalAccessToken`, where `_resolve_scoped_token` makes the same
`activate_for` call. **The seam moved; the defect did not.**

One test was genuinely lost: `test_ownerless_list_removal`'s third case, that an
`Idea` survives losing the task it pointed at. It needed `Idea` in a historical
migration state, and there is no longer a historical state containing one. Not a
re-evaluated risk — a scenario that stopped existing.

### And the rule Heron finally killed

The task core had been in maintenance since the merger was planned. **The freeze
is lifted — Vince's call, the same day.**

It is worth recording *why* rather than just *that*, because the rule's history
is the useful part. It had been rewritten twice to survive: "until the merger",
then — when the merger ended — "until the crossover ends", on the narrower
ground that `Capture` and `Idea` were retiring so work on either was thrown
away. Heron deleted both. **Each rewrite found a narrower justification for a
conclusion already held**, which is the shape of motivated reasoning, and a
third would have been cargo. Its own text had said the restraint needed a live
reason or it was exactly that.

On its own terms nothing was left. The surviving clause — *no new models on the
task core, because a model added now is a model migrated twice* — named a
migration that had happened, and `architecture-trajectory.md` §4 already gated
new models in either core, more strictly.

**What replaced it is a priority, not a prohibition**, on a reason that does not
expire: the task core is a competent todo application, the graph is what makes
this worth building, and `product-stories.md` has nineteen journeys with two
working. Task-core feature work now needs a reason beyond *while I'm here*, and
the instruction is to surface it and ask rather than to fix silently or refuse —
which is the one thing the freeze was actually buying, and the thing that got
riskier when two repositories became one tree.

## After Dunlin — Release F and six unlettered lines of work, August 6–12, 2026

Archived from `roadmap.md` on August 13, 2026. Six of these seven shipped
outside the release structure entirely, which is the honest reason the letters
stopped carrying information — recorded here as a fact about how the work
actually went, not as a lapse to correct retrospectively.

### Release F — opened August 7, closed August 13

Opened with the second-mind discovery pass, **Vince's call, ahead of the pain
that would otherwise have forced it.** `architecture-trajectory.md` §5 named
two candidates — this and the staging environment — and neither had fired its
stated trigger; the discovery pass was chosen anyway and recorded as a
deliberate exception rather than a trigger pretended to have fired.

**Discovery done and the first slice shipped in full, August 10** — see
[`second-mind-discovery-plan.md`](second-mind-discovery-plan.md). Reading the
models against the charter found most of the
idea/reference/project/task/routine boundary already settled by releases that
were not about this at all: `Idea.status` already made idea/reference one
model, and Dunlin and Crane 0 had already settled task/project/area and
routine/task. The slice was `Idea.tags` reusing `lists.Tag`, tag carry-forward
through promotion, and a plain `related_ideas` link with no `kind` field. 856
backend tests green throughout.

Two of the brief's own assumptions did not survive contact with the code and
were corrected in the document rather than built around: `capture.Idea` has no
Ninja API at all — the `IdeaOut` the brief pictured belongs to an unrelated
`review` summary — and `Idea` has no detail page for chips to live on, so they
render inline on the shared list.

**Closed August 13, 2026, with its subject moved out of the project.** The
second mind became its own repository, which Clarice is absorbed into rather
than the reverse. The shipped slice stays deployed and working; it is simply
the last of that line, since `Idea` does not survive the merger. See
`roadmap.md`'s opening section.

### The project workspace redesign — August 10

Trigger: a real navigation dead end. Opening a project from the side nav only
ever routed to its parent Area, because `Project` had never had a page of its
own. [`project-workspace-plan.md`](project-workspace-plan.md) inverted the
containment — a Project became a standalone workspace holding one or more
Areas rather than living inside exactly one. Eight slices, each its own commit,
in order: model, expand migration, service and read layer, API layer, contract
migration, regenerated client, frontend rewrite, browser smoke pass. 858
backend, 231 frontend, 28 browser journeys.

One gap the plan missed — nowhere to create a *new* project once
`ProjectsPanel.tsx` was gone — surfaced only while writing the browser journey.

**Two follow-ups the same day, both from using the shipped feature rather than
from planning:** a `/projects` index page, and letting a Project create a
brand-new Area rather than only reassign one. The second forced a standing-rule
change — **an Area no longer needs a first task to exist.** The follow-up's own
browser journey caught a real bug neither plan anticipated: the sidebar going
stale after completing or deleting a project. 865 / 239 / 30.

### The Bootstrap → Tailwind arc — three components, August 10–11

**Task list** (`a12a310`, `DEPLOYED-2026-08-10/1928`). Trigger: `TaskWorkspace.tsx`
flagged as "simply a mess" mid-review of the Projects redesign. Carried the
migration plus additions approved against a reviewed mockup — due-date sort,
select-mode bulk complete/archive, removable tag pills, pill dedup. 254 / 867.
Pre-existing `ProjectJourneyTest` failures were ruled out by bisecting against
`main` before the work touched anything.

**Agenda** (`94a6c4f`, `DEPLOYED-2026-08-10/2100`). The last Bootstrap-era
component and the app's highest-traffic page. Two real functional gaps were
found by reading the code rather than guessing: no text search anywhere on the
page, and no staleness signal, because `age_in_days` lived on Daily's and the
review's own item types rather than the shared `Task` type. Shipped with the
migration, the touch-target fix, a unified area/tag filter row replacing three
separate surfaces, search, and the staleness label. Bulk actions and manual
reordering were deliberately left out as editing-shaped work belonging to the
Area page. 263 / 867. Live verification against the built bundle caught a
layout bug nothing else did — a search field collapsing to 30px for want of a
`flex-shrink:0` guard.

**Archive** (`1cf9147`, `85154a8`). The last component on `site.css`. Carried
the migration, the same touch-target fix, and switched the row date from
`created_at` to `archived_at`, confirmed against the model's own
`CheckConstraint` rather than assumed. Because it was the last dependent,
**`site.css` and `workspace.module.css` were retired from the app entirely**,
source file deleted rather than left unreferenced. 264 / 867.

**The finding worth keeping, because it was not confined to one page.** The
Archive delete dialog's buttons measured 32px against a ≥44px claim.
`Button`'s size variants top out at 36px, and no component test measures
rendered layout. Checking the other two found the identical gap in both
already-deployed redesigns: every `<Button size="sm">` composer and dialog
button in all three was 28–36px, despite each brief claiming ≥44px and each
live verification reporting it confirmed. Fixed in all three with an explicit
height override. **Three consecutive verifications reported a measurement none
of them had taken.**

### Android as a full client — slices 1 and 2, August 10–11

Trigger: a request for a "more comprehensive overhaul" after a design pass on
the app's previously nonexistent visual theme.
[`android-full-client-plan.md`](android-full-client-plan.md) checked the gap
first and got half of it wrong: `lists`, `daily`, `review` and `routines`
expose the same *routes* the SPA consumes but not the same *auth* — only
`/api/v1/me` and `/api/v1/capture` accepted the Bearer token Android carries.

**Slice 1 (Daily, read-only)** installed clean on both devices and then did not
load: the stored token authenticated Settings and got 401 from `/api/v1/day`.
Asked directly rather than patched around, the call was to design a scoped
token tier before opting more routers into `TokenAuth` — see
[`token-scopes-plan.md`](token-scopes-plan.md). 899 backend tests, deployed the
same day. Verified live: a fresh login minted a scoped token and Today rendered
production data end to end, while the older device's pre-existing token kept
working, confirming the migration's grandfathering.

**Slice 2 (Agenda, read *and* write)** turned out bigger than the read half.
Complete/reopen, reschedule and quick-add live on `lists/api.py`'s hand-rolled
pre-Ninja endpoints with no token concept, sitting behind Django's *real*
`CsrfViewMiddleware` that every Ninja route is structurally exempt from.
`token-scopes-plan.md` §7 traces the mechanism Ninja actually uses — blanket
Django exemption plus a manual, auth-class-scoped CSRF re-check — and ports it
by hand as a `token_or_session_required` decorator, with a field-level guard so
`agenda:write` can complete or reschedule a task but never delete one or touch
its text, tags, notes or recurrence. 918 backend, 260 Android.

**Slice 1 extended to writable** the same day: focus pin/unpin, the day's own
text, and all six routine actions, behind `day:write` and `routines:write`.
Every endpoint was already Ninja, so no CSRF porting was needed. 933 / 285.

Both verified live on the SM-S928U1 against production. **One operational
lesson: a scope-adding deploy needs a fresh login on each device**, because an
existing connection predates the new scopes. Also found and fixed: a long
action-item title left the "Pinned" badge a few pixels wide, wrapping it letter
by letter.

### The staging environment — designed August 11, deferred August 12

Next in line on the infrastructure track per `architecture-trajectory.md` §6.
Decided directly rather than guessed: a second DigitalOcean droplet, not a
second process on production's already memory-tight host, with its own database
on the existing Postgres cluster — see
[`staging-environment-plan.md`](staging-environment-plan.md).

**Designing it found a real gap before it could reach production.**
`settings.py`'s `DEBUG` had only two states and neither fit `"staging"` safely;
the decision was pulled into a tested `clarice/deployment.py::is_debug()`, the
same "a function with a test, not a branch in a config file" pattern
`monitoring.py` already used. 937 backend tests.

**Deferred the next day, before provisioning** — see that plan's §8. Nothing in
flight touched the deploy mechanism, and there was no real user data to protect
from an untested migration, so the recurring droplet cost had nothing to offset.
The decisions and the `is_debug()` fix stand; the droplet waits for one of those
two triggers to fire.

Alongside it, §6's other two "now" items closed: **local development moved onto
Postgres**, closing the gap where SQLite silently omitted a constraint
production enforces, and the droplet-swap item — done back on August 3 — was
found never to have been marked complete.

## What the active roadmap carried for B, C and D — archived August 13, 2026

Three things lived in `roadmap.md`'s release sections and nowhere else. The
fuller what-shipped and what-it-taught records for each release are in the
sections below; these are the pieces that would have been lost when those
sections were collapsed.

### Production verification markers, per release

The practice these record is worth more than the markers themselves: **verify
with a marker the change actually introduced, not one that merely looks
plausible.** Bittern nearly confirmed a deploy that had not happened by
checking for `Something went wrong.`, a string that predated the change.

**Bittern.** The deployed bundle carried `RequestFailed`, the class B2.1
introduced. No unapplied migrations. Sentry active with `DEBUG` false. B1's
spawned occurrence rendering with its children and no refresh. Android capture
reaching the Inbox exactly once across every network condition. Per-user time
zones discriminating between accounts at 07:00 WITA.

**Crane.** The review routes answered 401 while a made-up route answered 404;
the POST-only `/review/{day}/complete` and `/routines/{id}/enough` answered 405
to a GET; the served bundle carried "Recent weeks", "Save the review" and
"Call it enough"; `/app/review` rendered on the real account. `lists/0023`
linked both existing repeating tasks.

**Dunlin.** `/api/v1/projects` and `/api/v1/areas/1` answered 401 while a
made-up route answered 404; `/api/v1/lists/1` was gone at 404; `/lists/1/`
redirected to `/areas/1/`; the login page said "areas" and never "lists"; the
served bundle carried "No projects in this area yet." and "stay open if you
complete this" with none of the old vocabulary. `app-shell.js` on production
was byte-identical to the build the tests ran against. All six migrations
applied; `0026` converted six subtasks; ownerless areas numbered zero.

### C2 — the interface failure, and the reason it was not an interface problem

C2 was an observation task rather than work: *reassess information architecture
after B0*, on the theory that "I can't tell where things are" might dissolve
once the navigation actually rendered.

**Its evidence arrived from B1's own verification on August 2, 2026.** Setting
up one recurring parent with three children took three attempts, and each
failure was the interface rather than the person:

- A task's **Repeat** (a select, parent-only) sat directly above each subtask's
  **Repeats** (a checkbox, child-only). Near-identical words, one screen,
  opposite meanings — and setting the first to None silently hid every instance
  of the second, so the control being reached for disappeared as a side effect
  of the mistake.
- A subtask row carried two checkboxes with no visual distinction: the leading
  one completed the task, a later one governed recurrence. Having used the
  first, the row read as done with.
- Neither failure produced an error. Both looked like success.

The verdict from that session was recorded as given: the web UI needed a
complete overhaul, not adjustment.

**Closed by Dunlin, August 3, 2026 — and the verdict was only half right.**
Both defects are gone. The first dissolved *by construction* when a Checklist
Step lost its recurrence field: the interface was never redesigned to fix it,
which is the strongest evidence the thesis behind that release was right. The
second became a checkbox and a switch. **The model was the larger problem, and
fixing it removed a defect no amount of interface work would have.** The
evidence above is left as it was recorded rather than rewritten, because what
it observed is why the release took the shape it did.

### Capture tags — folded into Dunlin rather than promoted

**Decided August 3, 2026.** Merged onto `main` the same day, deployed August 6
in `DEPLOYED-2026-08-06/2248`. Optional tags on a capture, typed on the Android
compose screen and displayed as pills in the web Inbox — see
[`capture-tags-plan.md`](capture-tags-plan.md). It reuses `lists.Tag` rather
than a parallel model (`_resolve_tags` became public `resolve_tags` so
`capture.services` could call it), adds `Capture.tags` additively, and the
Android queue carries tags through offline capture the same way it already
carried text. Triage gained no tags field, and a capture's tags did not carry
forward onto the task or idea it became — both named as deliberate non-goals,
not oversights. The second of those was closed later by Release F's first
slice.

The same decision covered the rest of what the Android device-testing branch
carried in: in-app login, the optional unlock gate, and release signing wired
into the build. None of it earned a release of its own, **which is why the
letter sequence skips E.**

## Dunlin — shipped August 3, 2026

`dunlin` (`82fd591`) was tagged after production was verified. Two deploys
carried it: 00:27 EDT (`e76c200`, `DEPLOYED-2026-08-03/0027`), which took
slices 1 to 8 and all six migrations in one run, and 02:03 EDT
(`DEPLOYED-2026-08-03/0203`), which took the UI brief, the carries-forward
switch, and the playbook fix below.

The plan, the settled decisions and every slice's acceptance condition stay
in [`release-d-plan.md`](release-d-plan.md); the interface work it opened
rather than finished is in
[`ui-second-pass-plan.md`](ui-second-pass-plan.md). Both are kept rather than
archived.

It closed with work outstanding by decision rather than omission, listed at
the end of this entry.

### What shipped

- **Slices 1–4 — the parent–child redesign, end to end.** A subtask is a
  **Checklist Step**: its own model, no due date, no tags, cannot recur, dies
  with its parent, promotable into a real task. `lists/0025` added the table,
  `0026` converted every existing subtask — deleting the `Item` each came
  from, or auto-promoting it when it carried a due date, tags, notes or a
  recurrence the new model could not hold — and `0027` retired `Item.parent`,
  `always_recurs` and `archive_group` outright rather than leaving them dead.
- **Slice 5 — the Area vocabulary.** A `List` is an **Area** everywhere a
  person reads one: copy, `aria-label`s, JSON field and schema names, and URL
  paths. The `List` model and the `lists` app keep their names, per
  `architecture-trajectory.md` §7. The old `/lists/` paths redirect rather
  than 404. No migration.
- **Slice 6 — `List.owner` non-null.** `0028` deleted the anonymous-era
  ownerless areas, irreversibly; `0029` made the column required. Charter
  rule 1 — owned at birth — now holds for every model without an exception.
- **Slices 7–8 — `Project`.** Work that completes, inside an Area that never
  does. `Project.area` is required, `Item.project` additive and nullable, so
  a task keeps its Area and may *additionally* join a project. Projects are
  created and finished on the Area page; a task joins one from its own detail
  page.
- **Slice 9 — the interface brief**, plus the single fix in it that had
  evidence behind it: a checklist step's carries-forward control is a
  `Switch`, so the two questions on a step row are told apart by control type
  rather than by their labels alone.

**What it closed.** C2's recorded failure was one person needing three
attempts to set up one recurring parent with three children, caused by two
independent defects. Both are gone. The Repeat/Repeats label collision
dissolved *by construction* when a Checklist Step lost its recurrence field —
the interface was never redesigned to fix it. The two identical-looking
checkboxes on a row are now a checkbox and a switch.

### What it taught

- **A word in a plan document hid a defect for two slices.** `release-d-plan.md`
  §4 predicted the two-checkbox row would be mechanical "once `is_done` is
  the only boolean on the row." It was not — `carries_forward` stayed on the
  row as a second checkbox. Slice 3's own entry called it a "toggle", and
  because the plan then read as though the problem were solved, nobody
  checked. It was found by counting `type="checkbox"` occurrences in one
  `<li>`, which took a minute and should have happened two slices earlier.
  **Check a plan's predictions against the shipped interface before writing
  the next plan on top of them.**
- **A migration that prints its evidence is worthless if the deploy discards
  it.** `0026` and `0028` both printed counts precisely so that running them
  against production would be the evidence no local database could supply.
  The playbook ran migrations through `docker_container_exec`, which captures
  stdout into an Ansible result — unregistered and unprinted, so it went
  nowhere, and `docker logs` never had it either. `0026`'s figure was
  recoverable afterwards by counting rows; `0028`'s is gone permanently.
  Fixed the same night in `a6550e4`, and exercised on the second deploy while
  the stakes were a no-op.
- **The nullable-to-required cost is asymmetric, and one slice's experience
  reversed the next slice's design.** Slice 6 spent an entire slice paying it
  on `List.owner`: an audit, a destructive migration, sixteen tests. Slice 7
  then had to choose for `Project.area`, and `release-d-plan.md` §3 had
  recommended nullable on reversibility grounds. That reasoning inverts once
  the direction is named — required→nullable is a bare `AlterField` with no
  data work. **The permissive default is the expensive one to undo.**
- **The local database was not evidence, exactly as the plan said.** Local
  development held three lists and zero ownerless rows; production held nine
  areas. Both migrations were written to handle the general case rather than
  the observed one, and that was the right call for reasons only visible
  afterwards.
- **A contract rename lands wider than the plan scopes it.** Slice 4 found
  `daily` and `review` each carrying their own hand-rolled `parent`
  breadcrumb rather than reusing `lists.serializers.serialize_item`; slice 5
  found the same split for `area_id`. `daily` reuses the shared serializer
  and got the rename for free; `review` hand-rolls its own and needed it
  applied separately. **The difference between the two is the whole argument
  for the shared serializer.**
- **A feature can be write-only if you only build the surfaces that create
  it.** Slice 8 shipped project assignment, and `project` reaches exactly
  three frontend files. Not the Agenda, which already renders an area pill
  and has room for a second; not the Daily Page, the review, or the Archive.
  Someone can put a task in a project and never see that fact again. Found
  while writing slice 9's brief, and it is the sharpest thing left open.

### Closed with work outstanding

- **Two migration counts are lost**, per the second lesson above.
- **`ui-second-pass-plan.md` steps 2 to 4 are blocked on evidence, not
  effort.** A project is invisible everywhere a task is worked, and Projects
  have no place in navigation — but both findings come from reading source,
  where C2's came from a person failing a real task. Production holds zero
  projects. One sitting with a real project on a real phone either confirms
  them or replaces them with something better.
- **The vocabulary half of Crane 0** is still deferred. It was blocked on
  knowing what a subtask is, which Dunlin answered, and was never given a
  slice.

## Crane — shipped August 2, 2026

`crane` (`e0acf05`) was deployed at 20:05 EDT and marked by
`DEPLOYED-2026-08-02/2005`. Two deploys carried it: 17:54 EDT, which took
Crane 0a, 1 and 2 in one run of ten migrations, and the last one, which took
Crane 3's four. The tag went on after production was verified rather than
alongside the deploy, which is the correction Bittern's own record asks for.

The plan, the settled design decisions and the slice-by-slice acceptance
conditions are in [`crane-plan.md`](crane-plan.md), which is kept rather
than archived; the product direction behind it is in
[`daily-operating-system-vision.md`](daily-operating-system-vision.md).

It closed with work outstanding by decision rather than omission: the
remainder of Bittern's carried-in checklist, most of which this deploy
finally unblocked. That list stays in `crane-plan.md` §2 and in the active
roadmap until it is cleared.

### What shipped

- **Crane 0 and 0a — the repetition domain.** A design brief settling
  routines, targets and occurrences, plus the one half built immediately:
  `RecurringCommitment` and `Item.commitment`, so a recurring task's
  occurrences form a series rather than a chain of rows whose only
  connection was a matching text string. Its backfill linked both repeating
  tasks in production. The vocabulary half — moving `text` and `recurrence`
  onto a real template — went to release D with the parent–child redesign it
  depends on.
- **Crane 1 — the Daily Page**, in seven slices: a written day, the agenda
  embedded rather than copied, capture, a durable Daily Focus whose
  `released_at` distinguishes a decommitment from an unfinished commitment,
  the Personal Compass, the home surface with a preference to opt back out,
  and a phone-viewport pass over the assembled page.
- **Crane 2 — routines and task age**, in five slices: `Routine` and
  `RoutineOccurrence` with lazily created periods and snapshotted targets,
  correction and skip as distinct statements, routines on the day, pausing
  that keeps what already happened, and how long a task has been waiting
  said without reproach.
- **Crane 3 — the weekly review**, in ten slices: what a week finished, what
  it planned and what came of it, its own words and what is still waiting, a
  dated review record that stamps the figure it concluded from, one explicit
  decision at a time with no bulk reschedule anywhere on the surface, how
  habits performed over the periods a week actually asked of them, a paused
  week that says it was paused, a satisfied-but-partial close that is not a
  skip, four weeks of context, and a phone pass.

### What it taught

- **A slice list hides a missing surface unless you look for one.** It had
  happened twice — the Daily Page reachable only by typing its URL until
  slice 6, routine creation with no surface at all until Crane 2 slice 3 —
  so Crane 3's list was read back for that specific failure before any code
  was written. It found three: the navigation entry, the way to reach the
  week *before* this one, and a control for the new partial close. Reading
  the list for a known failure mode is cheaper than a slice discovering it.
- **A test can be wrong about the world rather than about the code.** Four
  times in this release: an assertion that the week of July 27 was not the
  current one, made on a Sunday inside it; a British date order asserted
  against a locale-following formatter; an unanchored `/all/` matching "Call
  the bank"; and a straight apostrophe asserted against the typographic one
  the application renders. Each looked like a defect for as long as it took
  to read it. `principles.md` already says to diagnose before editing either
  side; the corollary is that the test is a suspect too.
- **The schema could not answer a question the plan asked.** Slice 9 needed
  "before the account existed" and `accounts.User` carries no creation
  timestamp at all — no `date_joined`, no `created_at` — which a test found
  by asserting against one that was not there. Adding the field would have
  meant defaulting three real accounts to today and marking their whole
  history prehistoric, so the line was drawn at the owner's first trace
  instead: earliest day written, task made, routine kept, thought captured.
  The better question, arrived at by being unable to ask the worse one.
- **A rule emerged that no single slice set out to make.** Released pins,
  skipped periods and periods closed as enough all leave a denominator —
  three decisions taken a slice apart that turned out to be one: *a
  deliberate decision leaves the denominator; only what merely elapsed stays
  in it.* It is written that way in the code rather than as three
  subtractions, so the next decision-shaped outcome inherits it.
- **A guard that has never been seen red is a claim, not a check.** Three
  passed on their first run this release — that nothing in the review
  mutates a task, that the pause backfill seeds what it should, and that the
  page does not scroll sideways at 375px. Each was made to fail on purpose
  before being left alone.
- **Running the tests does not migrate the development database.** The first
  browser check of the review record failed with `no such table` on a suite
  that had been green for an hour, because tests build their own database
  and `migrate` had never been run against the dev one. The page said
  "Couldn't reach Clarice" with a retry rather than rendering blank, which
  was B2.1's fix doing precisely what it was built for — an unplanned
  confirmation of an earlier release from a mistake in this one.

## Bittern — shipped August 2, 2026

`bittern` (`359a7e3`) was deployed at 00:35 EDT and marked by
`DEPLOYED-2026-08-02/0035`. Three deploys carried the release: 11:56 EDT on
August 1 (`fed210b`), 21:51 EDT that evening, and the last one, which was
the only one to carry B2.1 and B2.2 — their commits landed after the second
deploy, and an earlier claim that Bittern was already live rested on
`/contact/` returning 200, which proved B3 and nothing else.

It closed with work outstanding by decision rather than omission: five
after-deploy checks never run, three infrastructure confirmations owed, and
several Android gaps. All are carried into Crane and listed there. The
executable detail is in [`bittern-plan.md`](bittern-plan.md), which is kept
rather than archived.

### What shipped

- **A native Android capture client** (`android/`, M1–M5). Personal access
  token authentication, capture online or offline, a durable encrypted
  queue drained in the background, a share target, and idempotent writes
  that cannot duplicate a thought. 143 JVM tests and 16 instrumentation
  tests.
- **Per-user time zones.** Left the deferred list the day both halves of
  its trigger fired: a second active user in Indonesia, and a digest
  delivering at 03:00 Eastern.
- **Web session and state gaps closed** — B1's spawned recurring subtasks,
  B2's SPA logout, B2.1's failure states, B2.2's browser smoke coverage.
- **Branded email and a contact path** (B3), and **production error
  monitoring** (B4).
- **B0** — the missing side navigation, diagnosed and fixed; see its own
  section below.

### What it taught

- **A phone was the first thing to discover a production contract gap.**
  The Android client's first real connection failed because the bearer-auth
  `/api/v1/me` endpoint was still only on `main`. The token was always
  valid. Check the deployed OpenAPI schema before pointing a client at an
  endpoint, not after. B0.1 exists because of this.
- **Verification tooling can lie.** The script written to prove production's
  duplicate protection matched `"id":[0-9]*` against an API that renders
  `"id": 2`, extracted nothing from either response, compared the two
  nothings, and announced that production was broken — over evidence in its
  own output showing it working. Assert on values you have proven you can
  parse.
- **Rebuilding a state object silently drops fields.** Twice in one evening:
  a pending count left standing over an emptied queue, and a keyboard
  preference reverting on every capture. Neither would ever be reported as a
  bug; people would just quietly stop trusting the app.
- **Some defects only exist on hardware.** Background delivery worked on its
  first real attempt, and the count on screen did not update, because a
  screen cannot see a background drain. Every unit test asserting that count
  was correct.
- **A marker has to be something the change introduced.** Checking whether
  B2.1 was deployed, `Something went wrong.` was found in the served bundle
  and nearly taken as proof — it predates B2.1 by months. `RequestFailed`,
  which B2.1 actually added, was absent. The weaker check would have
  confirmed a deploy that never happened, and the same instinct produced a
  premature "Bittern is live" in these documents an hour earlier.
- **`state: latest` on an infrastructure package** means a routine deploy is
  willing to restart the thing running the application. The "Install docker"
  task looked hung on three separate deploys and was cancelled each time.
- **Isolating one half of a store's identity is isolating neither.** The
  instrumentation tests parameterised the Keystore alias but not the
  preference file, so running them deleted a live token off a real phone.

## Albatross — shipped July 31, 2026

`albatross` (`f5ddb85`) was deployed at 22:24 EDT and marked by
`DEPLOYED-2026-07-31/2224`. It carried seven migrations, taking the schema
from 53 to 60 without changing existing rows.

### Platform and production work

- Replaced the task UI with a React Router/TanStack Query SPA backed by a
  Django Ninja `/api/v1/` contract and generated TypeScript types.
- Moved production from bind-mounted SQLite to managed Postgres.
- Added GitHub Actions: Django tests run against Postgres and frontend tests
  and builds run on every push and pull request.
- Restricted the application to a dedicated Postgres database user, proved
  the backup/restore path, and restricted the database firewall to the
  application droplet.
- Added the daily-digest cron job, verified by dry run. Its first unattended
  cron fire is 07:00 on August 1, 2026; "runs as root from cron on a
  schedule" has a failure mode that "prints to stdout when I run it" does
  not, so this is not proven until that run is checked.
- Added self-service password reset and production-ready static asset
  handling through Docker, Gunicorn, WhiteNoise, nginx, and Ansible.

### Task and agenda work

- Added archive/restore state handling and snooze presets.
- Added notes as plain text on task detail.
- Added one-level subtasks with duplicate protection, ordering, ownership
  isolation, archive/restore, completion, recurrence, and undo behavior.
- Added `always_recurs` to decide which subtasks return with a recurring
  parent, plus the follow-up fix that prevents completed children from being
  orphaned when their recurring parent archives.
- Added persistent SPA navigation in source. Its absence in production was
  Bittern B0, diagnosed and patched on August 1, 2026 — see below. The
  deployed bundle was never the problem.
- Added direct Inbox and Ideas links to the Agenda workspace as a fallback
  entry point. They mitigate a missing side nav only once the current frontend
  bundle is deployed; they do not replace B0's production-bundle diagnosis.

### Capture and account work

- Added Capture: a zero-friction, owner-scoped inbox for untriaged thoughts.
- Added Capture triage into a task, an Idea, or a discarded record; added
  undo for that brief transition period.
- Added Ideas with exploring/reference states, notes, edit/delete, and
  promotion to a task.
- Added personal access tokens and `POST /api/v1/capture` for non-browser
  capture clients.
- Added account themes, daily-digest preferences, and password reset.

## Completed tracks

### Track A — infrastructure and public-readiness foundations

All A0–A6 work is complete:

| Item | Result |
| --- | --- |
| A0 | CI with a Postgres 18 service container, Django tests, frontend tests, and build verification. |
| A1 | Dedicated production database user, including ownership correction required for Django migrations. |
| A2 | Restore drill passed against a cloned managed database. |
| A3 | Adversarial per-user isolation suite, including id-based task/list and subtask cases. |
| A4 | Daily digest cron installed; first unattended run still to be checked. |
| A5 | Database firewall closed to the production droplet. |
| A6 | Self-service password reset, including live validation of lockout behavior. |

### Track B — Capture MVP

Capture shipped as a Django app before being expanded with token-authenticated
API capture, then its triage and Idea model. The two-week usage checkpoint was
dropped as a release gate: the triage model had enough direct product
conviction to ship. Real usage should still inform future scope.

### Track A Next — task model improvements

The original queue — archive/restore correction, snooze presets, task detail,
notes, subtasks, and persistent navigation — is complete. The recurring
subtask follow-up is also complete.

The one deliberately unscoped consequence — a spawned recurring task not
serializing its copied subtasks, so they appeared only after a refresh — was
closed as Bittern B1 on August 1, 2026.

## Bittern B0 — the missing side navigation, diagnosed August 1, 2026

### The artifact was never the problem

B0 existed to decide between two causes: a stale or mispackaged frontend
bundle, or a current bundle failing at runtime. Read-only evidence gathered
against the running albatross deployment, before any redeploy:

| Check | Result |
| --- | --- |
| Deployed asset | `frontend/app-shell.b94af7d63d1b.js`, 179,011 bytes |
| `Last-Modified` | 2026-08-01 02:23:16 GMT — the `DEPLOYED-2026-07-31/2224` deploy |
| Deployed `staticfiles.json` | Maps `frontend/app-shell.js` to that hash, so it is what `app_shell.html` referenced |
| Navigation strings in the served JS | Agenda, Inbox, Ideas, Archive, Preferences all present |
| `Log out` in the served JS | Absent, correctly — B2 was unbuilt, corroborating the artifact as albatross |
| Served `app.css` | Byte-identical to a local build, including the shell grid and the 760px rule |
| `AppLayout`/`SideNav`/`sidenav.module.css` at `f5ddb85` vs `main` | Unchanged |

The bundle was current and correct. The stale-artifact branch was closed on
evidence rather than assumption.

### The cause

`AppLayout` wrapped `SideNav` in a `<details>` that nothing ever opened,
while `sidenav.module.css` hid its `<summary>` unconditionally. Above the
breakpoint the nav was therefore sealed inside a closed disclosure with no
handle to open it — the source comment asserted "above it the nav is always
open," but no code implemented that.

A closed `<details>` has its contents skipped, so the element collapsed to
zero height. Measured on the live page:

```text
detailsBox: 210x0     <- the empty gutter the user could see
navBox:     210x306   <- a skipped subtree keeps its geometry
shellCols:  210px 1814px
```

Firefox does not paint skipped content, so the column was simply empty.
Chromium 148 still paints it, which is why the same page looked correct in
Edge and on a Chromium phone, and why the defect shipped.

### Why no test caught it

`SideNav.test.tsx` renders the component directly, never inside the
`<details>`, and jsdom has no paint model in any case. The condition is
invisible to unit tests by construction. `AppLayout.test.tsx` now asserts
the invariant that was violated — above the breakpoint the disclosure is
open, and stays open across navigation — but proving what a person actually
sees needs B2.2's browser-level coverage.

### The fix

The layout now holds the disclosure open above the breakpoint via
`matchMedia`, rather than depending on how an engine treats a closed one,
and only closes on navigation when narrow. Verified by measurement: with
the patch applied the disclosure's own box goes from `210x0` to `210x145`,
matching its content, so no engine has anything left to disagree about.

### Verified in production, August 1, 2026

Deployed at 11:56 EDT. The served bundle rotated from
`app-shell.b94af7d63d1b.js` to `app-shell.98590f71d7af.js`, byte-identical
to a local build of the same source, and contains the fix's own
`min-width: 761px` breakpoint. An authenticated visit confirmed what the
measurements predicted: the nav panel appears down the left above the
cutoff, and collapses into the ☰ menu below it. B0 is closed.

### A false trail worth keeping

The first reproduction reported the nav as "visible" in every browser,
which discarded the correct hypothesis for most of the investigation. The
instrument was wrong: it tested `getBoundingClientRect().width > 0 &&
height > 0`. **A layout box is not paint.** Content skipped by a closed
disclosure keeps its geometry, so the probe answered "visible" for
something invisible on screen, and the user's own report was trusted less
than a faulty measurement. The signal that finally settled it was a
container measuring `210x0` while its child measured `210x306` — a
contradiction that can only mean skipped content.

## Decisions and lessons retained from the work

### Product decisions

- Capture never forces categorization at entry time; triage decides whether a
  thought becomes a task, an Idea, or nothing worth keeping.
- An Idea is not a task without a due date. It has a distinct lifecycle and
  can later promote into a task, carrying its notes with it.
- The task UI is now SPA-only. Capture and account surfaces can remain
  Django-rendered where that is the better fit.
- The agenda is a date-based cross-list view; lists are navigation targets,
  not agenda filters in the persistent navigation.

### Deploy: the "Install docker" task that looked hung

Seen on at least two deploys before August 1, 2026, and again that day:
the playbook appears to stall on **Install docker** for minutes, long
enough that the natural response is to cancel the run — which is what
happened each time, leaving the deploy unfinished.

It was never hung. Read-only inspection of the droplet during the stall
showed the work genuinely in progress and nothing blocking it:

```text
142818   03:08  AnsiballZ_apt.py      <- the apt task, 3 minutes in
143131   02:03  apt-check --human-readable
load average: 2.49
```

The dpkg and apt lock files were unheld. The `unattended-upgrades` process
that normally deserves suspicion was only the `--wait-for-signal` shutdown
daemon, idle for twelve days, and that day's real unattended run had
finished cleanly hours earlier. The cause was the task's own configuration:
`state: latest` plus an unconditional `update_cache` made apt refresh every
index and resolve upgrade candidates for `docker.io` on a small busy
droplet, every single deploy.

Worse than slow, it was unsafe. `state: latest` meant an ordinary Clarice
deploy was willing to upgrade the Docker daemon, and upgrading Docker
restarts it — killing the running container partway through the deploy that
asked for it, at the one moment nobody would look for that as the cause.

Fixed in `fed210b` by using `state: present` with `cache_valid_time: 3600`,
so Docker is installed once and upgrading it becomes a deliberate act rather
than a side effect of shipping a Django change. The task now completes in
about twenty seconds.

If a deploy ever appears to stall on an apt task again, check before
cancelling: `ps -eo pid,etime,cmd | grep AnsiballZ`, the lock files under
`/var/lib/dpkg` and `/var/lib/apt/lists`, and `dpkg --audit`. Cancelling
mid-apt happened to leave the droplet consistent each time here — verified
by `dpkg --audit` and a check for half-configured packages before the rerun
— but that is luck rather than a property to rely on.

### Engineering lessons

- A deployment task is not proven until it has run against production.
- Test against the same database family and relevant version as production.
- Database grants are not ownership; Django migrations require ownership of
  existing tables.
- A clean hard refresh does not prove the deployed frontend image contains
  current source. Inspect the served bundle when UI source and production
  disagree.
- A layout box is not paint. `getBoundingClientRect` returns real geometry
  for content a browser has skipped rendering, so "has a box" is not
  evidence that anyone can see it. When a probe and a person disagree about
  what is on screen, suspect the probe.
- Markup must not depend on how an engine renders a closed `<details>`.
  Engines differ and are still converging; a layout that only works in the
  browser it was built in will look correct to whoever built it.
- Token and session authentication need deliberately different CSRF behavior.
- Every id-taking surface requires direct per-user isolation tests, not just
  trust in a general ownership convention.

## Release conventions

Releases use alphabetic bird names. A release receives three tags after it is
verified in production:

| Tag | Purpose |
| --- | --- |
| `LIVE` | Moving pointer to the exact code currently running. |
| `DEPLOYED-<date>/<HHMM>` | Permanent record of the deployment event. |
| Bird codename | Permanent annotated record of scope and verification. |

Do not reuse a letter: a follow-up production release receives the next bird
name, even if it immediately corrects the last one.
