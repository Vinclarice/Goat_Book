# Code review — August 16, 2026

**A record, not a plan.** It describes one review at one commit and is explicitly
about the past, which by [`README.md`](README.md)'s own rule is the kind of
document that cannot go stale. It is not a new planning document —
`commercial-blueprint.md` Part 8 refuses those, and rightly.

Reviewed at `305d1e7` (`main`, clean tree). Risk-based rather than uniform:
effort followed consequence, and the fan-out was by risk theme cutting across the
whole tree rather than by directory, so the security pass read Django, Android,
frontend and infra together.

**This review does not copy its findings into
[`commercial-blueprint.md`](commercial-blueprint.md) Part 1**, which is the sole
authority for production defects. Promoting any of these to that list is a
separate decision and a separate commit.

---

## What was actually run

Every count below is from a real run today, by me, on this commit.

| Suite | Result |
|---|---|
| Django task core | **920 tests — OK** (109.3s) |
| Knowledge core (`pytest`) | **617 passed, 25 skipped, 1 xfailed** (114.7s) |
| Frontend (`vitest run`) | **284 passed**, 20 files (9.1s) |
| Android (`testDebugUnitTest`) | **309 tests, 0 failures**, 22 classes — read from the XML, not Gradle's summary |
| Browser (`functional_tests`) | **32 tests — OK** (1 skipped), against a fresh bundle |

**2,162 tests, all green.** `tsc --noEmit` clean. The counts match `928f303`'s
claim of "920 Django, 617 pytest, 32 browser" exactly.

**Every defect below is live against a fully green suite.** That is the single
most useful thing this review says about the tests: they are real — the mutation
probes prove it — and they do not cover these paths.

### How findings were checked

Nine parallel read-only reviewers, then adversarial verification, then mutation
probes in a throwaway git worktree. Three levels of evidence appear below and are
labelled per finding:

- **Confirmed** — I verified it myself, directly, beyond the reporting agent.
- **Executed** — proved by running code (a live request sweep, a JVM run, a
  parser invocation), not by reading.
- **Read** — from reading only. Treat as strong but unproven.

### What refutation changed

Eleven findings went through adversarial verification. **Six came back confirmed
unchanged; five were corrected**, and the corrections are recorded here rather than
quietly absorbed, because they are the evidence the control actually ran.

| Finding | Correction |
|---|---|
| **D8** | Reframed. I claimed Area deletion "silently rewrites past reviews." The UI *does* warn, the code *does* document the trade, and completed weeks' stamped headlines are immune. "Silently" removed |
| **D14** | **My claim was wrong.** `retirement_gate` decides domain *absorption*, not an embeddings purchase, and inflated misses push it the opposite way. Rewritten with the accurate mechanism |
| **D13** | Blast radius reduced — the nav self-corrects on window refocus, not "all session". Also: the correct pattern exists in four files, not two |
| **D15** | Sub-claim corrected — stale fixtures are not why nothing failed; nothing tests that block at all |
| **D6 / D16** | Sharpened in *both* directions: D6's crash is more bounded but its outcome worse; D16's mechanism is stronger (no attack needed) but its severity lower |

**One refutation was itself wrong, and I caught it by running the code.** A
verifier reported D17's first example as fabricated — but it had tested
`'Walked to the shops and back'`, dropping the `"Feeling good today."` prefix that
produces the match. Running the parser on the original string returns
`due 2026-08-16, matched 'today'`. All four examples stand, and a fifth found by
that same verifier is stronger than any of them. Recorded because it is the honest
shape of this method: verification catches real errors and introduces its own, and
neither agent's word is evidence — the run is.

**The register worked.** Nothing below re-proposes anything from
`architecture-trajectory.md` §7, Part 8, or Part 4's *Avoid* list. More usefully,
the review **corrected the register three times** — see §4.

---

## 1. Actual defects, ranked

### D1 — CRITICAL. Unsaved edits are silently destroyed by a background refetch, in three routes
**Confirmed.** `TaskDetailRoute.tsx:80-94`, `AreaRoute.tsx:38`, `ProjectRoute.tsx:49-50`.

Each seeds form state from *inside* the `queryFn`, so the setters re-run on every
refetch rather than once on mount. `main.tsx:15-17` sets only `retry: false`,
leaving `refetchOnWindowFocus` at its default `true`. Alt-tab away from a
half-written task note and back: every character is replaced by the server's
value. No message, no undo.

This violates the product's core promise — *"Never lose a person's thought, draft,
or queued action to a refresh…"* — and the project has **already fixed this exact
bug twice**. `PreferencesRoute.tsx:41-52` and `DayRoute.tsx:721-731` both use a
`seeded` ref, and the comment at the former names the consequence precisely:

> the save that followed then sent the restored value and reported "Saved.",
> which is worse than failing, because it looks like it worked.

Guarded in 2 of 5 stateful routes. The 3 unguarded ones are exactly the 3 with no
refetch test.

### D1b — HIGH. Two more ways the SPA loses written work
**Both confirmed.** Same class as D1, same principle broken.

**`AddRoutine` clears and closes before the request resolves.**
`DayRoute.tsx:604-617` calls `onCreate(...)` — wired to `mutate`, not
`mutateAsync`, with no per-call `onSuccess`/`onError` and no promise returned —
then unconditionally clears its fields and runs `setOpen(false)`. The mutation's
own `onSuccess` only patches the day cache; it cannot restore a child that has
already unmounted. On failure the user sees "Couldn't keep that routine." beside a
collapsed, empty form. `CaptureBox` twelve lines up does it correctly, and says so:
*"the box empties on success and never on the way there."* The existing test mocks
only a 200.

**Expired-session 401s are handled on reads and not on writes.**
All nine `RouteFailure` call sites guard a `useQuery` error; `statusOf` is called
in exactly those nine places and no mutation anywhere calls it. It could not help
if one did — every Ninja mutation throws a plain `Error` with the parsed body, so
the status is discarded at the throw site; only queryFns construct `RequestFailed`.
So a user whose session expired mid-write gets "Couldn't save this day." with no
status, no login link, and no hint that signing in would fix it.

**Worse than I first stated:** drafts live in `useState` with zero persistence (the
SPA's only `localStorage` use is the theme), and `spa_shell` is `@login_required`
— so the natural response, refreshing, is a **Django redirect to login, and the
draft is gone before React runs.** Noted for whoever fixes it: the legacy `api.ts`
path already carries the status on `ApiError.status`, and no consumer reads it. The
two halves of the SPA lose the status at different points — Ninja mutations at the
throw, legacy mutations at the render.

### D2 — HIGH. One nullable column, four broken surfaces
**Confirmed; the review 500 and the Android crash were both Executed.**

`Item.list` was widened to nullable on August 14 (`0857835`, "Let an unfiled task
be read, not only written"). That commit touched ten files across `frontend/` and
`src/lists/`, fixed the agenda serializer, widened the task-core schema, and left
a comment at each explaining the trap. It did not touch `src/review/` or
`android/`. Every one of these is reachable in **one tap from `/mind/`** via
`confirm_actionable` — the merger's own payoff path.

| Surface | Effect |
|---|---|
| `review/api_v1.py:47` — `area_id: int` | `/api/v1/review` **500s permanently** for any week containing a completed unfiled task |
| `send_due_digest.py:48` — `item.list.title` | Digest crashes; **every user alphabetically after them is starved**, hourly, forever |
| `AgendaApi.kt:192` — `getInt("area_id")` | Android **Agenda tab blank**, with a misleading "wrong server address" message |
| `DailyApi.kt:259` — `getInt("area_id")` | Android **Today tab blank**, same message |

Executed proof of the review 500 — a live `/api/v1/` GET sweep against a real
Postgres test database:

```
baseline / unfiled ACTIVE:            all 200
unfiled COMPLETED:                    /api/v1/review 500, all else 200
unfiled COMPLETED + pinned:           /api/v1/review 500
unfiled ARCHIVED (completed_at set):  /api/v1/review 500
```

`pydantic_core.ValidationError: response.completed.0.area_id  Input should be a
valid integer [input_value=None]`. `reads.completed_in_week` filters on
`completed_at` alone, so archiving does not clear it — only filing by hand does.

Executed proof of the Android crash, run against the exact jar the unit tests use:
`getInt(area_id) THREW org.json.JSONException: JSONObject["area_id"] is not a int`.
The catch is at payload level, so **one bad row discards the entire response**.

**The tell:** both Kotlin lines read `getInt("area_id")` directly above
`optIntOrNull("project_id")`. The nullable idiom was known and applied one line
away.

**The near-miss:** `lists/tests/test_a_task_without_an_area_is_readable.py:85`
constructs *precisely* the state that 500s the review — `archive_item(complete_item(self.unfiled))`
— then asserts only `/api/v1/archive`. One more line would have caught this on the
day it shipped.

*Scope note, deliberately: this does **not** strand the capture queue.
`ClariceApi.capture` never parses the response body and unknown statuses are
treated as RETRY_LATER. Damage is confined to the two read tabs.*

### D3 — HIGH. Sentry ships raw request bodies despite `send_default_pii=False`
**Confirmed against installed sentry-sdk 2.66.1.**

`clarice/monitoring.py:39-66` passes no `max_request_body_size` and no
`before_send`. In `_wsgi_common.py:91-118`, `should_send_default_pii()` gates
**cookies only**; the body is gated solely by size (default `"medium"` = 10 KB),
and `request_info["data"] = data` is unconditional.

So a 500 on `POST /api/v1/capture`, `POST /mind/` or `POST /api/v1/day` sends the
captured thought, the day's intentions, or the note text to a third party.

The sharp part is that the file already documents this exact class of failure one
field over, for `include_local_variables` (defect 10):

> Passed explicitly rather than trusted to stay False, because the default belongs
> to a dependency: silence here is a decision made by whoever last released the SDK.

The neighbouring default was left unset.

### D4 — HIGH. `/api/v1/login` has no rate limit at any layer
**Confirmed.**

The endpoint that trades a password for a **90-day, all-scopes bearer token** is
`auth=None` and unthrottled. nginx's only `limit_req` rules cover
`^/(accounts/login|accounts/signup)/`, `= /contact/` and `= /`;
`/api/v1/login` matches only the catch-all `location /` at
`nginx-clarice.conf.j2:119`.

- **DoS.** `AXES_LOCKOUT_PARAMETERS = ["username"]`, so rotating the username
  never trips a lockout, and Django runs a full PBKDF2 hash even for a
  non-existent user (deliberately, to defeat timing attacks). The Dockerfile runs
  **one worker, four threads, one core, no swap** — a number its comment says
  "was learned the hard way."
- **Unbounded password spraying** — 5 guesses per username, unlimited usernames,
  unlimited rate.

**The codebase asserts the opposite twice.** The nginx template's header: *"First
line of defense against brute-forcing login/signup: throttle by client IP before
the request even reaches Django. django-axes … is the second line."*
`settings.py:263`: *"nginx's rate limiting … is what handles the by-IP case."*
Neither is true for this route. `architecture-trajectory.md` §6 records
closing exactly this hole for `/` on August 3; the API login shipped three days
later without a matching rule.

*This is not a re-proposal of §6's deferred "broad API rate limiting." That
deferral's own trigger — "when `/api/v1/` serves anyone not already trusted" — is
already met for this one route, because it is unauthenticated by design.*

Same shape, lower severity: `POST /accounts/password/reset/` is also unmatched by
every location block and sends mail synchronously.

### D5 — HIGH. `open_question` uses `dormant_thread`'s exclusion filter
**Confirmed. Independently reported by two agents.**

`open_question.py:37` imports `_previously_proposed_ids` from `.dormant_thread`.
Python binds a function's globals to its **defining** module, so the filter at
`dormant_thread.py:143` (`detector=DETECTOR`) queries `"dormant_thread"`.
`open_question.py:41` defines its own `DETECTOR` that nothing consults.
`semantic_echo` and `shared_referent` each define their own copy — `open_question`
is the sole exception.

Two consequences in opposite directions:
1. A **dismissed** open-question proposal is re-derived every night forever, and
   crowds a genuinely new finding out of the top three.
2. Any pair `dormant_thread` already proposed is **permanently invisible** to
   `open_question`, so the directional "answers" finding — "the whole content of
   the finding" per the module docstring — is unreachable for that pair.

`dormant_thread.py:131-137` documents precisely why the guard is needed. The one
detector that imports it is the one that does not get it.

### D6 — HIGH. One rejected recipient means the digest is *never* delivered to anyone sorting after them
**Confirmed empirically** by a verifier that wrote and ran two throwaway tests.

`send_due_digest.py:131-178`. No try/except in the loop at `:131`; `send_mail` at
`:164` without `fail_silently`; the `last_digest_date` stamp at `:172` is *after*
the send.

Test 1 — two users, alice's send raises `SMTPRecipientsRefused`:
```
sends that succeeded: []      alice.last_digest_date: None
                              bob.last_digest_date: None
```

Test 2 — a full simulated day of 24 hourly cron runs, both users in
`America/New_York`, real `--send-hour 7 --until-hour 12` gate:
```
07:00–11:00 local -> CRASH   delivered so far: []
12:00–23:00 local -> ok      delivered so far: []
bob.last_digest_date: 2026-08-17
```

**The verifier corrected this in both directions.** The crash is *bounded*, not
indefinite — past `until_hour` the failing user's branch skips the send and falls
through to the stamp, so the command stops raising after their local noon. But the
*outcome* is worse than first stated: for anyone in the same or an earlier time
zone as the failing recipient — **which is this product's actual case at three
users** — the digest is not delayed, it is **never delivered**, and
`last_digest_date` is stamped anyway by the write-off path. The day is recorded as
decided. It recurs daily and **leaves no trace in the data.**

The file already guards the *other* one-user-blocks-everyone failure
(`resolve_time_zone(...) or ZoneInfo(...)`, tested at line 289). The class was
recognised; the likelier instance was missed.

### D7 — HIGH. Note text in URL query strings, on disk and in Sentry
**Confirmed**, with the two halves separated — they are not equally broad.

`mind/views.py:69-84` reads `title`/`text`/`url` from `request.GET`, and
`manifest.json` declares `"share_target"` with `"method": "GET"` — so **Android's
share sheet puts the shared passage into the URL by design.** `:414-421` reads
`request.GET.get("q")` and `search.html:5` is `<form method="get">`.

- **The nginx half is unconditional.** No `access_log` directive anywhere in the
  template, and the playbook never templates `nginx.conf`, so the distro default
  applies with the built-in `combined` format, whose `"$request"` is the verbatim
  request line. **Every** search and every share is written to a plaintext disk
  log on every request, and stays through log rotation. *One inference, stated
  plainly: nginx was not run to observe this — it is documented default behaviour
  plus a template that unambiguously declares none.*
- **The Sentry half is on-error only.** `wsgi.py:364`'s `should_send_default_pii()`
  guards only the IP block; `:370` sets `query_string` unconditionally. The
  verifier also checked the escape hatch the original finding missed — the default
  `EventScrubber` only touches `headers`, `cookies` and `data`, never
  `query_string`. But `monitoring.py` sets no `traces_sample_rate`, so there are no
  transaction events: the query reaches Sentry only when an event is captured
  during that request. Real, and the same path as D3 — but "on error", not "on
  every request."

### D8 — MEDIUM. Deleting an Area hard-deletes completed and archived tasks, with no count
**Partially confirmed — the verifier corrected my framing, and the correction
stands.** I originally wrote that this "silently rewrites past reviews." That is
overstated in two ways and I have removed it.

The mechanism is real: `Item.list` is `CASCADE` with no status filter, and
`delete_area` → `services.delete_list:733` has no guard, no count and no archive
step — where `delete_archived_item:726` raises unless the task is already archived.
`completed_in_week` (`reads.py:50-67`) queries live with no snapshot, so
hard-deleted tasks vanish from a past week's completed list retroactively.

But:
1. **It is not silent at the UI.** `AreaRoute.tsx:226-232` puts deletion behind an
   AlertDialog reading *"**{title}** and all of its tasks will be permanently
   removed. This cannot be undone."* What is not disclosed is the *count* and the
   effect on past reviews.
2. **It is not silent in the code.** `reads.py:110-115` documents this exact
   consequence by name — a pin whose task was deleted counts as unfinished because
   the FK is SET_NULL, *"which is why §8 has completing a review stamp the figure
   it reported."* A reasoned trade, not a missed case.
3. **The mitigation partly works.** `recent_weeks:545-550` prefers
   `recorded_planned_met`/`_total` for any week whose review was completed, so **a
   completed week's trend headline does not move.**

The defensible statement, which is what this finding now claims: *deleting an Area
hard-deletes completed and archived tasks with no count and no archive step, and
`completed_in_week` — which has no stamp — loses them from past weeks
retroactively.* What still moves: a review page's met/unfinished lists for any
week, every figure for a week never reviewed, and `completed_in_week`.

### D9 — MEDIUM. Routine progress is an unlocked read-modify-write
`routines/services.py:131` — `max(0, progress + amount)` then save. No
`select_for_update`, no `F()`. A double-tapped "+1" loses an increment; if that
causes the target to be missed, `habits_met` is wrong and **cannot be
reconstructed, because the log is the count.** Contrast `lists/services.py`, where
every mutation opens with `select_for_update`.

### D10 — MEDIUM. `request_deletion` commits, then emails outside a transaction
**Confirmed — every link, empirically, including the critical one.**

`accounts/services.py:27-47` has no `@transaction.atomic`; the absence is
conspicuous, since `purge_account` twenty lines below has one. Verified at runtime
rather than by grep: `ATOMIC_REQUESTS is False`, `EMAIL_TIMEOUT is None`, and
`confirm_deletion_scheduled` uses `EmailMessage(...).send()` with the default
`fail_silently=False`.

The critical link, tested by patching the email to raise:
`deletion_requested_at` was **persisted** after the exception, and a second call
five minutes later hit the early return with the email mock's `call_count` at
**0**. The warning is permanently suppressed on retry.

**The order of the claim matters:** the idempotency guard is not the bug — a
doubled click is correctly not a second decision. The bug is that the guard's
precondition, *that the email went out when the timestamp was written*, is not
enforced by a transaction.

### D11 — MEDIUM. Two more unguarded loops with the same shape as D6
- `purge_deleted_accounts.py:48-58` — one bad address rolls back that erasure
  (deliberate) **and** blocks every remaining account, nightly.
- `run_mind_maintenance.py:79-95` — `run_detectors` catches only `Unavailable`;
  anything else aborts the loop, and owners after the failure get no maintenance
  and no marker.

### D12 — MEDIUM. Export drops all tag associations and three models
**Reported independently by three agents.** `accounts/export.py:60-76` — `_rows`
iterates `_meta.concrete_fields`, which by definition excludes M2M. So `Item.tags`
and `RecurringCommitment.tags` export as bare tag *names* with nothing recording
which tag was on which task. `HypothesisMember` (the span citations that are a
hypothesis's entire evidence), `Attachment` and `SentenceEmbedding` are never
queried.

The stakes: the export is the only thing standing before irreversible erasure. A
user who exports, then deletes, loses those associations permanently. The module
docstring claims "every row of every owned model across both cores."

### D13 — MEDIUM. Side-nav counts go stale on every task write
**Mechanism confirmed empirically; blast radius corrected downward.**

A verifier mounted `TaskWorkspace` with a seeded `["nav"]` entry, clicked "Mark
complete", and observed exactly one fetch (`/api/items/1/`) with `isInvalidated`
false and `dataUpdatedAt` unchanged before and after. `NavOut` really does serve
`areas[].open_count`, `overdue_count`, `projects[].open_task_count` and
`archived_count` — all of which that write moves — and `SideNav` really is mounted
once in `AppLayout`, outside the `<Outlet/>`.

**My original "stay wrong all session" was too strong.** `main.tsx` leaves
`refetchOnWindowFocus` at its default `true` with `staleTime: 0`, so the nav
self-corrects on the first window refocus, and a second throwaway test confirmed
the queryFn re-runs on `focusManager.setFocused(false)` then `(true)`.

Accurate statement: counts and the Archive badge go stale the moment a task is
completed, archived, deleted or created from `TaskWorkspace`, `ArchiveManager` or
`TaskDetailRoute`, and **stay stale for as long as the user keeps working in the
tab without leaving it.** Also corrected: the right pattern is present in *four*
files, not only the project ones — `ReviewRoute.tsx:719-720` invalidates `["nav"]`
on a day-focus write.

### D14 — MEDIUM. Search is a silent recency truncation, and the misses it manufactures corrupt two instruments
**Partially confirmed — and the second half of my original claim was wrong. It is
corrected here rather than quietly dropped.**

**(a) Confirmed, and slightly worse than first stated.** `SearchRank` appears
nowhere in `src/`. `live_nodes` is `.order_by("-captured_at")` and
`mind/views.py:414-431` applies `.distinct()[:30]` — a pure recency truncation of
an unranked filter. `search.html` has **no pagination, no result count and no
"showing 30 of N"**, so the truncation is invisible, and the "I know I wrote this
and can't find it" button sits directly beneath it. Separately,
`Q(revisions__search_body=query)` matches *any* revision, so a term deleted in a
later revision still returns the node while `current_body` renders text without it.

**(b) I misattributed the consequence.** I wrote that `RetrievalMiss` feeds
`instrumentation.retirement_gate`, "the instrument that decides whether to add
torch to the image." Verified directly: `retirement_gate`'s docstring is *"The
three conditions for absorbing Clarice's domains"* and it mentions neither
embeddings nor torch. It is the gate on **absorbing the task core's domains**, and
the direction is inverted — inflated misses make its "retrieval misses fall"
condition *fail*, holding the gate shut rather than arguing for spending.

**The true version, which is still worth acting on.** `RetrievalMiss`'s own model
docstring and `record_retrieval_miss` both call it *"the strongest evidence
available about whether semantic retrieval is needed"*, and Second Mind's
Second Mind's `design-concept.md` makes accumulated miss queries a scoring input to the
~2,000-node shadow evaluation that decides whether to swap in an embedding index —
design-doc only, not implemented in code. So a silent truncation manufactures
misses that corrupt two different instruments, in opposite directions: the shadow
evaluation that would argue *for* embeddings, and `retirement_gate`'s absorption
condition, which it holds shut.

### D15 — MEDIUM. Dead `/capture/` links in the Agenda sidebar
**Confirmed**, with one sub-claim corrected.

`AgendaWorkspace.tsx:989,995` hardcode `href="/capture/"` and
`href="/capture/ideas/"` under a "Capture" heading. `clarice/urls.py` has no
`capture/` entry and no catch-all — both are plain Django 404s, outside the SPA
shell, with no way back but the browser button. `SideNav.tsx:77-93` documents
removing the same two links; the Agenda's duplicate was missed, and the comment
above the dead block still describes "the inbox" and "the Ideas shelf" as live.

**Correction:** I attributed the silence to stale test fixtures. Wrong — the links
are hardcoded strings, so fixtures are irrelevant; **nothing failed because no test
asserts on this block at all.** The stale fixtures are real but separate and
smaller: `inbox_count`/`inbox_url`/`ideas_url` still appear in
`AppLayout.test.tsx:45-48` and `ProjectRoute.test.tsx:44-47`, fields `NavOut` no
longer serves.

### D16 — LOW-MEDIUM. The contact form's hourly cap does not hold — and no attack is needed
**Confirmed, then deliberately downgraded.** The verifier both strengthened the
mechanism and argued the severity down; both corrections are taken.

Verified at runtime, not by grep:
```
CACHES: {'default': {'BACKEND': '…locmem.LocMemCache'}}
CONTACT_MAX_PER_HOUR: 5
```
LocMemCache is a per-process dict; `Dockerfile:80-83` runs `--workers 1
--max-requests 500 --max-requests-jitter 50`, so a recycled worker starts at zero.

**Stronger than first stated:** whitenoise serves static files in production
(`WhiteNoiseMiddleware`, `CompressedManifestStaticFilesStorage`) and nginx has
**no `location /static/`** — so every CSS, JS and font request is proxied to
gunicorn and counts toward `--max-requests`. The counter is burned by ordinary
browsing. **No attack is required to defeat the cap; one is only required to
defeat it on demand.**

**But the severity is lower than "medium."** This is a support-inbox spam cap, not
an authorization control, and the honeypot plus nginx's `10r/m burst=5` on
`= /contact/` still bound throughput to roughly five messages per worker lifetime.
The honest framing is *correctness of a stated guarantee*: the nginx template's
comment claims the view "caps how many messages actually leave per hour," and that
claim is what is false.

### D17 — MEDIUM. The commitment parser proposes a task from ordinary past-tense prose
**Confirmed — I ran the parser myself, on the exact strings.** `today = 2026-08-16`:

| Input | Proposed |
|---|---|
| "Feeling good today. Walked to the shops and back." | due 2026-08-16, matched `today` |
| "Met Bob on Tuesday for coffee, he looked well." | due 2026-08-18, matched `Tuesday` |
| "Rereading the Sunday papers, nothing much in them." | due 2026-08-16, matched `Sunday` |
| "I drink coffee daily and it is probably too much." | due today, **recurrence `daily`** |
| "Spoke to mum on the 3rd of June." | **due 2027-06-03** — ten months out |

`_propose_any_commitment` (`services.py:306-333`) writes an unconfirmed ACTIONABLE
facet whenever `find_commitment` returns non-None, and `services.capture` calls it
on **every** capture. `importers/runner.py:236` goes through the same path, so a
200-document journal backfill proposes a commitment for every entry naming a
weekday, "today", or a cadence word. Combined with D18's unordered three-slot
queue, those slots fill permanently with the oldest of them.

**Precision, because the wording matters:** it is not that there is *no* gate — the
parser carries two deliberate false-positive gates, `_UNHOLDABLE`
(`commitments.py:63-68`, drops cadences `Item.Recurrence` cannot hold) and
`_ORDINAL`'s positional lookahead (verified: "the 4th time I tried this it worked"
→ `None`). What is absent is any gate on the **proposal**: no length floor, no
tense test, no confidence threshold. Contrast `MIN_MENTIONS_TO_ASK` /
`MIN_SPAN_TO_ASK`, whose comment says extraction over-generates on purpose and
*the gate is what stops it becoming an inbox*.

The negative-case test set is four strings, none of them past-tense prose
containing a weekday, "today" or a cadence word — so "untested against past-tense
prose" holds.

**Whether to gate this is a product call, not a bug report.** But today it is
ungated at the proposal, unmeasured, and untested against the input that trips it.

### Lower-severity defects
- **D18.** `views.py:116-125` — the commitment queue is an unordered queryset
  sliced to 3, so past three proposals the one you just made is not shown.
- **D19.** `accept_commitment` retires an already-*confirmed* facet (reported by
  three agents) — live task, node dropped to "quiet knowledge",
  `commitments_without_tasks` still reads 0.
- **D20.** `semantic_echo.available()` is not owner-scoped — `/numbers/` reports
  "ready" for every account once any one account has vectors.
- **D21.** One unembedded node disables `semantic_echo` for an entire run
  (`run_detectors.py:76-106`, run-scoped `unavailable` set, never cleared).
- **D22.** `requirements-embeddings.txt` does not exist, and four places name it —
  two as the remedy in a user-facing `CommandError`.
- **D23.** Gravity gate counts mentions on archived nodes while the evidence list
  beside it excludes them → "mentioned 3 times" above an empty list.
- **D24.** The docx importer appends a *successful* body-date override to
  `skipped`, so imported records are reported as "passed over".
- **D25.** `extract_concepts --dry-run` seeds from the *gated* candidate queue
  while the real run seeds from all non-retired — the dry run answers a different
  question than the one it exists to answer.
- **D26.** The two bearer paths parse the `Authorization` header differently
  (`startswith("Bearer ")` vs ninja's case-insensitive split), so `bearer` lowercase
  works on half the API. Both fail closed; no current client hits it.
- **D27.** `/api/v1/openapi.json` and `/api/v1/docs` are served anonymously
  (**Executed**: 200 while `/api/v1/me` 401s in the same run). Free reconnaissance
  for D4 — and `health.py`'s docstring argues at length against exactly this.
- **D28.** `capture_idempotent` check-then-insert race → 500 rather than 200 on a
  concurrent replay. No thought lost; wrong status and a Sentry alert.
- **D29.** Accessibility: `Switch` with no accessible name
  (`PreferencesRoute.tsx:262`); no focus management or skip link on route change;
  reorder is drag-only with no keyboard or touch path; the Archive delete dialog
  is hand-rolled `aria-modal` with **no focus trap** while Radix `AlertDialog` is
  used correctly elsewhere; inline errors and confirmations are outside live
  regions in the five newer routes.
- **D30.** Tag pills in `TaskWorkspace.tsx:53-64` use a hardcoded copy of the
  palette as *foreground* text → **1.19:1–1.70:1** contrast in light theme.
  `tailwind.css:150-156` says those tokens were designed as dots and to "revisit
  if that changes." It changed.

---

## 2. Missing tests around credible failure modes

Backed by experiment where marked. **11 mutations, 8 caught, 3 survived.**

### The three surviving mutations

**M1. `unique_active_arealess_item` — removed entirely, 1,537 tests across both
runners stayed green.** The biggest gap found. Its own comment names what it
prevents: *"A phone retrying a share would have written the note twice."*

Its sibling has a dedicated `UniqueActiveItemConstraintTest` going straight at the
database, and that class's docstring explains exactly why this matters:
`_duplicate_exists` *"short-circuits before the database is reached on most paths,
so a service-level test would still pass against a broken or missing constraint."*
That is precisely what happened. A missing backstop, not a live duplicate-write
bug — but the backstop is unverified.

**M2. `capture_idempotent`'s `created` gate — removed, suite stayed green.** The
rule has a test written specifically for it, `test_a_replay_does_not_deepen_the_evidence`,
whose docstring says a queue retrying six times would manufacture a recurrence. It
passes with the gate gone, because `record_typed_tags` does its own idempotency
check one layer down. Correct today either way; the gate itself is unproven.

**M3. `test_it_does_not_reach_another_persons_log` has a false docstring.** It
claims *"A boolean exemption would pass the test above and fail this one."* It does
not — it passed under exactly that mutation. The owner-scoping is genuinely
protected, just not by the test claiming to protect it.

### Gaps found by reading

- **The nullable-Area class** — no test passes `list=None` through the digest or
  the review, and the Android tests all hard-code `"area_id": 3`. Four one-line
  tests would have caught D2 entirely.
- **The refetch-clobber class** — guarded in 2 of 5 stateful routes;
  `grep refetch` across the SPA's tests hits only `DayRoute.test` and
  `PreferencesRoute.test`. The 3 unguarded routes are the 3 with no test.
- **`send_due_digest` has no failing-send test** — 26 tests, and grep for
  `SMTPException|side_effect|fail_silently|raise|except` returns nothing.
- **`open_question` is the only detector with no "a dismissed proposal is not
  offered again" test.** That test exists in `test_dormant_thread.py:312`,
  `test_shared_referent.py:303` and `test_semantic_echo.py:294`. Its re-run test
  asserts only a row count, which the fingerprint constraint guarantees anyway, so
  it cannot fail on D5.
- **The 25 skipped pytest tests skip in CI too.** `test_semantic_echo.py:45` and
  `test_detector_ensemble.py:27` gate on `embeddings.encoder_available()`;
  `sentence-transformers` is in neither `requirements.txt` nor
  `requirements-dev.txt`, and CI installs only the latter. **The semantic-echo
  detector — including the measured true/false pair corpus that exists precisely
  to control false positives — runs in no automated environment.** The skipif is
  defensible; it proves the app works *without* the dependency. It does not make
  the present path tested.
- **Four ID-taking surfaces have no direct isolation test** — checklist-step
  reorder, promote and DELETE, and `routines/{id}/resume`. All verified correctly
  scoped today; this is about the guard, not a live hole.
- **The two Android backup-rule files must stay byte-identical and nothing checks
  it.** `backup_rules_legacy.xml:6-12` says so itself: *"It drifted once … the only
  defence is remembering that this one exists."* The pattern for a fix already
  exists in this codebase — `test_frontend_style_contract.py` reads `frontend/src`
  from a Django `SimpleTestCase`.
- **No cross-language conformance test** for the three-language mirror (see §3).
- **TRUNCATE is uncovered** in the append-only guarantee. `save()` and raw `UPDATE`
  are both refused (verified); `TRUNCATE mind_activityevent CASCADE` succeeds
  silently, because Postgres row-level triggers do not fire on TRUNCATE. No
  application path issues one, but `manage.py flush` does.

---

## 3. Architectural debt with a present cost

Only debt whose cost is nameable **today**. Debt with a merely future cost is
omitted deliberately.

**A1. The three-language mirror is wider than recorded, and its guard is weaker
than it looks.** Not only `bucket_for`/`WEEK_HORIZON_DAYS` — `next_weekday`,
`snooze_presets`, `AGE_WORTH_MENTIONING`, `ageLabel`, `dueLabel` and
`standingLabel` are all hand-ported across Python, TypeScript and Kotlin, each
declaring itself a mirror in a comment.

All three `bucket_for` implementations **currently agree**, boundary by boundary.
But the Python and TypeScript horizon tests each compute their expected edge *from
their own constant*, so raising `WEEK_HORIZON_DAYS` and mirroring it into
TypeScript leaves both green while Android stays on 7. `AgendaFormattingTest.kt:34`
is the only test pinning a real date — and it pins Android's. Result: digest and
SPA on 14, phone on 7, CI fully green.

**One copy has already diverged visibly:** `agenda.ts:203-208` formats a far-future
due date with `Intl.DateTimeFormat` (locale-ordered), `DailyFormatting.kt` with a
fixed `"EEE d MMM"` — the same task reads "Sat, Aug 10" on the web and
"Sat 10 Aug" on the phone.

**A2. One serializer, two contracts.** `serialize_item` feeds both a
Ninja-validated surface and seven unvalidated hand-rolled endpoints. Add a field
and it appears on `POST /api/v1/areas/{id}/items/` while Ninja **silently strips
it** from `/api/v1/agenda` — verified: `TaskOut.model_validate({...,'bucket':'today'})`
returns 16 keys, pydantic drops the extra without complaint. So a freshly created
task renders the field and it vanishes on reload. `schema.ts` covers only the Ninja
half. No conformance test exists.

**This is the direction register C gets backwards.** A field added to `TaskOut` is
*loud* (Ninja 500s all five routes); a field added to `serialize_item` alone is
silent.

**A3. No enforced module boundaries.** `daily/api_v1.py:20` imports schema classes
from `lists.api_v1` and `routines.api_v1`, so `class DayActionItemOut(TaskOut)`
means a field added for the Agenda changes the Day contract for all three clients
immediately. Prose comments are the only enforcement.

**A4. The Android split-backend machinery cannot be switched on, and three
present-tense docstrings say it already is.** `build.gradle.kts:54` defaults
`secondMindBaseUrl` to `""`, CI runs `assembleDebug` bare, and `BackendsTest.kt:80-86`
records that the assertion on it was deliberately removed. So `isSplit` is false in
every build: `workspaceConnector` is always null, the second `ConnectScreen` branch
is unreachable, `SettingsViewModel`'s workspace section is dead.

**The cost is realised, not hypothetical.** `CLAUDE.md` records that Heron step 4
planned to delete `/api/v1/capture` on the strength of `Backends.kt:28-30` — which
would have drained the encrypted offline queue into 404s. The comments are still
there, set to mislead the next reader the same way. *Counter-argument on record:
`Backends`/`BackendsTest` are cheap and self-contained; the removable cost is
concentrated in the three false docstrings and the unreachable UI.*

**A5. No rollback path.** `docker build -t clarice .` overwrites one mutable tag.
Undoing a bad deploy means a full local rebuild from an old checkout; if it
migrated, the only undo is a cluster restore with 7-day retention. The playbook
**already registers `deployed_commit`** at `:179-183` for `DJANGO_RELEASE`, so the
identifier a SHA tag needs is already in hand.

**A6. Nothing reads cron's output.** Three cron tasks, no `MAILTO`, no MTA
installed. The commands are *designed* for a reader —
`purge_deleted_accounts.py:11-14`: *"A command that prints nothing when there is
nothing to do is indistinguishable from a command that did not run"* — and print
to a discarded stream. A command that stops being *scheduled* produces no signal
at all.

**A7. The backup freshness check is scheduled nowhere.** Confirmed live: two hits
in the whole repo, the script and one prose mention. Not among the playbook's three
cron tasks; CI has no `schedule:`. Already named in blueprint Part 5 — confirming
it, not discovering it.

**A8. The restore drill is stale.** Last exercised August 1 against 53 migrations
and 18 tables. There are now 74 migrations, plus the `vector` extension, the
append-only triggers and the erasure exemption — none of which existed then. The
drill compares row counts and `django_migrations` only, **so a restore that came
back without the append-only triggers would pass it.**

**A9. Unbounded work on request threads.** The GDPR export materialises the whole
account in memory with two queries per node, synchronously, on a single worker with
458 MB and no swap; `/numbers/` does two unbounded corpus scans. Both grow with the
corpus rather than with users, and `ActivityEvent` is append-only and never pruned.

---

## 4. Intentional constraints that should remain untouched

Carried forward so the *next* reviewer inherits them. Nothing in this review
proposes any of these.

**Refused designs** — `architecture-trajectory.md` §7 (task core only): a universal
Node/Block model in the task core; a headless Django backend; renaming `lists` or
`Item`; local-first sync before a second client; row-level security or connection
pooling at three users; deleting the provisioning scripts before Terraform; starting
over. Blueprint Part 4 *Avoid*: repositories and unit-of-work; hexagonal; **domain
events, an event bus, or Django signals**; event sourcing; feature folders; Pact; a
feature-flag service; the outbox pattern. Part 8: a rewrite; PKM features before
search; AI before Phase 3; **another long planning document**.

**Deliberate, not defects:**
- The `ActivityEvent` erasure exemption. Verified again here: exactly one caller,
  no route to set the GUC externally, and **the mutation probe confirms
  `test_erasure.py` really does fail if you widen it** — `CLAUDE.md`'s claim is
  true.
- SSL expiry alerting is refused, not missing.
- `/capture/` was freed and deliberately not taken as a URL prefix.
- Shipped plans reduced to stubs, so 251 code comments still resolve.
- The eight inert `django_migrations` rows for the deleted `capture` app.
- `run_mind_maintenance` deliberately not calling `embed_nodes`.
- The erasure receipt email inside the purge transaction — *"that is the failure
  worth having."* (The collateral in D11 is a separate issue.)

**Verified sound — the review's strongest negative results:**
- **No unscoped ID-taking surface anywhere**, across both cores. Defence in depth
  is real: `pin_task`, `_own_routine`, `_require_same_owner`, `propose_hypothesis`
  and `capture` all re-check at the service layer beneath the view filter. The
  mutation probes caught 4/4 ownership mutations, and one failed `403 != 404`
  rather than `200 != 404` — proving both layers exist and that the test knows
  which one fired.
- **CSRF is correct throughout.** `@csrf_exempt` appears exactly once in `src/`.
- **Scopes cannot be forgotten** — `TokenAuth.__init__(self, scope)` is positional,
  so no scope-blind default is constructible; `item_detail`'s PATCH guard is a
  whitelist, so new fields fail closed by construction.
- **The append-only trigger covers UPDATE as well as DELETE** (verified by
  mutation, both directions).
- **Recurrence is correct** — Jan 31 + 1 month = Feb 28, + 2 months = Mar 31, no
  drift; all arithmetic on `date`, so DST cannot shift a due date.
- **Time zones are correct** — both token paths activate the owner's zone; the
  digest reads the clock once and passes the date down.
- **Denominators cannot move for a completed week.**
- **All 74 migrations** use `apps.get_model`; destructive steps count rows first
  and declare irreversibility honestly.
- **The 30-day purge IS scheduled** — 04:40 daily in the playbook.
- **Zero optimistic mutations in the SPA** — every write awaits the server, so
  that entire class of rollback bug is absent *by construction*.
- **The generated OpenAPI contract has zero drift** — regenerated and diffed.
- **The Android capture queue is genuinely safe:** no secrets, no logging, no
  crash SDK, and the lock and backup exclusions are both in place (see §5).

---

## 5. Documentation-only drift

> **Actioned the same day.** Every item in this section was fixed by the
> documentation reduction of August 16, 2026, which cut the corpus from 6,433 to
> 5,190 lines. This section is kept as the record of what was found, not as a list
> of what is open — read it in the past tense. The one exception is
> `src/clarice/settings.py:304`, which is code and was deliberately left alone.

No code change implied. Listed because `design/`'s whole thesis is one fact, one
home — and these are the places that failed it.

**The most important one: `roadmap.md` contradicts itself.** `:219-225` says the
two Android capture-queue defects are "still unfixed"; `:545` in the same file says
Part 1 is closed, all ten. **The code says fixed** — `CaptureQueue.kt:154` declares
a process-wide `LOCK` used by every operation, and both backup-rule files exclude
the queue store. This cost this review time at the planning stage, which is exactly
the cost `CLAUDE.md` predicts.

**`architecture-trajectory.md` §4 — the model gate `CLAUDE.md` names for *both*
cores — opens on two false premises.** `:248-250` says the `routines` app does not
exist; it has models, reads, services, api_v1, periods and tests. `:356-358` says
`RoutineOccurrence` has no owner FK; `routines/models.py:119` declares one, and its
docstring records closing the very gap §4 still describes as open. A gate's
usefulness is its credibility.

**Three documents give a stale reason for a still-correct rule.** `CLAUDE.md`'s
Environment section, `architecture-trajectory.md` §3 and `settings.py:304` all said
the suite must run on Postgres because `Item.Meta`'s `unique_active_item` is
`nulls_distinct=False`. `lists/0027` **removed** that flag from both constraints,
deliberately. The conclusion still holds — via `mind.Mention.mention_unique`, now
the only live `nulls_distinct=False`, and the `vector` extension — but every
document names the wrong reason. *Found independently by three agents.*

**Register corrections — things the standing documents assert that are no longer
true:**
- `schema.ts` "covers reads only" — it carries **25 write operations** (16 post,
  6 patch, 3 delete).
- The hand-written frontend type set "has already drifted" — it has not;
  `types.ts` `Task`, `TaskOut` and `serialize_item` are the same 16 fields today.
- The "two disagreeing breakpoints" (760/768) — **760/761 agree**, and no `768`
  appears anywhere in the SPA. Half this item does not exist; the original citation
  is needed to close it properly.
- Blueprint `:400-406`'s scale premise — "`Item` has no `owner` column" — is false
  since August 14, and `product-stories.md` cites that measurement as
  load-bearing.
- The headless-backend refusal's evidence: thirteen templates extend `base.html`,
  not sixteen, and three named templates are deleted. **The conclusion holds and is
  not challenged** — but checkable evidence that does not check out invites the
  next reviewer to re-litigate it.

**Comments asserting invariants the code does not hold:**
- `clarice/api.py:35-40` labels `daily` and `routines` "Session-only". Both accept
  bearer tokens; Android calls them.
- `landing_surface` is claimed to have one decision site in two separate comments;
  it has two, with **opposite fallbacks** — add a third surface and a fresh login
  and a bare `/app/` visit land on different screens.
- `accounts/auth.py:137-139` points at "that module's own docstring" for why
  `lists/api.py` stays off Ninja. `lists/api.py:1` is `import json`. This is the
  rationale for an Adopt item, so the reason not to migrate is unrecoverable.
- `mind/api_v1.py:3-4` describes `mind/api.py` in the present tense — deleted
  August 15. **Three agents reported this independently.** It is the first file
  anyone opens when adding a knowledge-core endpoint, and it tells them a second
  live API exists.
- `mind/api_v1.py:111-113` — "There is no third case here." A PAT-using script and
  the Android **share sheet** both record `MOBILE`; `NodeSource.API` and
  `NodeSource.SHARE` are written by nothing. The same class of wrong-label bug the
  August 16 fix was written for.
- `accounts/api_v1.py:56-58` claims parity with the web login form, which *does*
  distinguish pending approval.
- `capture_idempotent`'s docstring says "Both HTTP surfaces need that answer"; it
  has one caller, and `mind/views.py` writes them out separately.
- Six further stale claims in `commercial-blueprint.md`, six more in `roadmap.md`
  (including account export and deletion still listed as the remaining
  public-readiness item, which the same file says shipped at `:553`), and three in
  `principles.md` / `product-stories.md` / `README.md`.

**Orphan:** `src/mind/templates/mind/login.html` — a second, pre-merger sign-in
page. No view renders it, no URL routes to it, but `render(request,
"mind/login.html")` resolves. `mind/urls.py:3-6` says "a second login page would be
two ways to sign in to one application"; it is sitting in the template directory.

---

## 6. Refactor candidates

Filtered hard. Nothing from §7 or the *Avoid* list. Each needs a present cost or a
named bug class prevented.

### Part 4's Adopt list — all six still open, status-checked today

| Item | Status | Present cost |
|---|---|---|
| **Serve the date policy in the payload** | Not done — `TaskOut` has 16 fields, no `bucket`; no `week_horizon_days`/`snooze_presets` in any payload | **Yes** — A1 is the symptom; this is the fix, and it deletes two of three implementations |
| **`.importlinter` in CI** | Not done — no config, zero CI references | **Yes** — A3 is the violation it catches. ~30 lines |
| **`contract.py` per context** | Not done | Pairs with the linter; shipping the linter alone gives it nothing clean to point at |
| **Migrate `lists/api.py` onto Ninja** | Not done — 0 routers, 3 `token_or_session_required` | **Yes, newly nameable** — A2. One serializer, two contracts, divergence invisible because validation drops rather than errors |
| **A written five-context map** | Not found — **and now awkward**: `README.md`'s August 16 rewrite and Part 8 both refuse new long planning documents. Cheapest home is a section in `architecture-trajectory.md`, not a new file | Weak |
| **`Item.status` transition table** | Not done — 23 guard sites, 11 of them the same `if status == ARCHIVED: return` preamble | **No.** No present cost could be named beyond the count, so by this review's own bar it stays recommended-but-unranked |

### New candidates, ordered by cost removed against risk of the change

1. **A conformance test across the three-language mirror** — cheapest fix for the
   largest silent-divergence risk, and strictly smaller than the Adopt item above.
   Pin one real date in each language against the same fixture. The pattern exists:
   `test_frontend_style_contract.py` already reads `frontend/src` from a Django
   `SimpleTestCase`.
2. **A parity test for the two Android backup-rule files.** Byte-comparison, a few
   lines. The files themselves say the only current defence is remembering.
3. **Give `open_question` its own `_previously_proposed_ids`** — the other two
   detectors already have one; this is deleting an import and copying six lines,
   and it fixes D5.
4. **Extract the unguarded-loop pattern.** Four commands (`send_due_digest`,
   `purge_deleted_accounts`, `run_mind_maintenance`, and `run_detectors`'s
   per-node loop) share one bug: a per-item failure aborts the batch. One
   `for_each_owner(..., on_error=...)` helper with a test would close D6, D11 and
   part of D21.
5. **Derive `ChecklistStep.owner` from its task**, as `Item` already derives from
   its Area. No reachable divergence today; the named class prevented is in
   `Item.owner`'s own comment — *"a task whose two owners disagreed would show up
   in one person's queries and another person's Area at the same time."*
6. **SHA-tag the deploy image.** A5; the commit is already computed at
   `deploy-playbook.yaml:179-183`.

---

## What this review did not cover

- **No fixes.** Report only; nothing in `src/`, `frontend/`, `android/` or `infra/`
  was modified. The only mutations were in a throwaway worktree, all reverted.
- **Read, not run, in most places.** Where a claim was executed it says so. The
  browser was not driven; contrast figures are computed from the WCAG formula, not
  measured in a renderer.
- **Not read at all:** most of the 9,679-line pytest suite as *source*, the six
  `design/*.html` mockups, `mind/extraction.py` and parts of `mind/importers/`,
  XSS/template escaping, the CSP contents, and the live production host (every
  infra claim rests on the playbook's contents, not on the running machine).
- **The 25 skipped tests were not un-skipped.** Installing `sentence-transformers`
  and running them would be a genuinely useful follow-up, and would test the
  detector this review can only say is untested.
- **Eleven of thirty defects went through adversarial refutation**, chosen as the
  high-severity ones I had not already confirmed myself. The rest carry their
  evidence label and nothing more. A finding marked *Read* is not a finding that
  survived a challenge.
