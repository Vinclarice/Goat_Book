# The Android overhaul — the phone catches up with the list — focused spec

**The phone shows a task core that was replaced two days ago.** Vince,
September 6, 2026: *"I think I want the lists on the app foremost."*

**The direction was settled on August 31, 2026** and this plan is the trigger
rather than the decision. [`roadmap.md`](roadmap.md) records *a complete
overhaul of the Android app, in its own session* — deliberately as an intention
with no date, no scope and no plan document, because "an intention with no
trigger is not a schedule". This is the document it said did not exist yet.

**It overrides `commercial-blueprint.md` Part 9's freeze recommendation**, and
that is Vince's call, already taken and recorded. Part 9 argued for responsive
web over native on the evidence that
[`android-full-client-plan.md`](android-full-client-plan.md)'s core assumption —
*mostly an Android build-out, not a backend rebuild* — **was falsified twice**.
That evidence is real and this plan does not wave it away; it measures the
backend cost up front instead, in *What the server already owes and what it
does not*, precisely because the last two estimates of it were wrong.

---

## The diagnosis

`android/` is a faithful client of the **pre-Superlists-2.0** task core. Every
endpoint it calls still exists, so nothing is broken — it is showing the wrong
application, correctly.

**What the phone shows that the website no longer has:**

| On the phone | On the website |
|---|---|
| `intentions`, `gratitude`, `happenings` in `DayEntry`, with an editor and a *Save the day* button | **Removed from the Day page September 4, 2026**, at Vince's own request |
| An **Agenda** screen — `AgendaScreen.kt`, `/api/v1/agenda` | **Deleted, 1,795 lines**, September 4; `/agenda` redirects to `/day` |

**Two rows stood here on September 6 and both were wrong. Corrected the same
day, before either was acted on.**

- ~~`compassPurpose`, `compassQuestion` — not on the day page~~ — **they are.**
  `DayRoute.tsx` renders both, three references each. Deleting them from the
  phone on the strength of this table would have removed a working feature.
- ~~`areas`, `projects` — retired from navigation September 4~~ — **retired
  from the *rail*, not from the day.** `DayRoute.tsx` still passes both to
  `ActionItems` and reads `areas.length` for first-run detection.

**Checked rather than remembered**, which is the only reason they were caught:

```bash
grep -c "data.compass_purpose" frontend/src/app/routes/DayRoute.tsx   # 3
grep -n "data.areas\|data.projects" frontend/src/app/routes/DayRoute.tsx
```

**What the phone does not have at all**, every one of it Superlists 2.0's:

- **The line.** `DailyModels.kt` has no `list_closed_at`, so the phone cannot
  show a bounded list at all — which is the redesign's whole subject.
- **The readback and its leftovers**, and rule 7's three moves on each.
- **The pool**, which is what replaced the Agenda.
- **Appointments**, shipped September 4.
- **The day's log** — what happened today, line by line.

```bash
grep -n "val " android/app/src/main/java/com/vinclarice/capture/DailyModels.kt
```

**So "the lists on the app foremost" is not a feature request.** The phone has
no list in the sense the word now means. This is the same shape as
`feedback-a-request-can-be-a-defect`: the ask names a symptom, and the cause is
that a client went stale under a redesign nobody pointed at it.

---

## What the server already owes, and what it does not

**Measured rather than assumed**, because this is exactly the estimate Part 9
says was wrong twice.

**Already there, and already reaching a bearer token.** `GET /api/v1/day` is in
`test_api_auth_surface.py`'s `TOKEN_AUTHENTICATED`, and it **already returns**
`list_closed_at`, `closing` — the readback with its leftovers — `focus`,
`appointments` and `appointments_coming`. The phone is being sent the line, the
leftovers and the diary today and is throwing them away because
`DailyModels.kt` does not name the fields.

**Still owed, and each one is a deliberate widening** of what a token in an
Android keystore can reach — which `test_api_auth_surface.py` exists to make
somebody type on purpose:

| Wanted | Today |
|---|---|
| `GET /api/v1/pool` | Session-only. The pool is what replaced the Agenda, so a phone without it has no way to pick tomorrow's list |
| `POST /api/v1/day/{day}/leftovers/{task_id}` | Session-only. Rule 7's three moves are the evening's whole job |
| Writing an appointment | Session-only, and **reading one is already free** — it arrives inside the day payload |

**Three entries, not a rebuild.** That is a smaller number than the last two
estimates and it is stated as a measurement with the command beside it rather
than as a claim about how easy this will be:

```bash
sed -n '64,112p' src/clarice/tests/test_api_auth_surface.py
```

**The knowledge core is out of scope entirely.** Capture already works, has an
encrypted offline queue, and rule 4 of
[`app-overhaul-plan.md`](app-overhaul-plan.md) keeps it exactly as it is.

---

## Increments

1. ~~**Delete what is gone.** The Agenda screen, and the three prose fields,
   `areas`, `projects` and the compass from `DayEntry`.~~ **Shipped September
   6, 2026 — and it deleted less than it said it would**, because the table
   above was wrong twice. What went is the Agenda and the journal editor; the
   compass, `areas` and `projects` are all still live on the website and stay.

   `AgendaApi` could not simply be deleted: `DailyViewModel` borrows
   `setTaskStatus` and `rescheduleTask` from it on purpose — *one rule, one
   authoritative definition*. So it was **split** into `TaskApi`, and
   `AgendaTaskEntry` became `TaskEntry`. `createTask` did not survive: it takes
   an `areaId`, and its only caller was the deleted screen. How a task is made
   on a phone is **A1**.

   `tomorrow()` moved to `DailyFormatting` as the only one of
   `AgendaFormatting`'s five helpers with a caller left — **and its new comment
   carries a warning for increment 4.** It moves a *due date*, one item,
   deliberately, which is what the vision document leaves open where it forbids
   automatic carry-forward; the website's evening has its own *Tomorrow* on a
   leftover, which rule 7 says is **never a date move**. Two legitimate acts,
   one word, and they must not silently merge.

   **313 → 268 tests, and every one accounted for**: three test classes deleted
   whose subjects no longer exist, the agenda-read and `createTask` cases gone
   with their code, four draft cases and one `writeDayText` case gone with the
   editor, and `tomorrow`'s case moved rather than dropped. Nothing whose
   subject is still live lost its test.

   `/api/v1/agenda` and `PATCH /api/v1/day/{day}` both stay:
   `test_api_auth_surface.py` pins them, and a shipped APK is what keeps them
   pinned until a signed release replaces one. **A3 is untouched** — an editor
   left the phone; the columns' fate is still `superlists-2.0-plan.md`'s
   deferred question.

2. ~~**The day, as it now is.** `list_closed_at` into the model, the bounded
   list above the line, what joined below it, and appointments — all four from
   the payload the phone already fetches.~~ **Shipped September 6, 2026, and
   the claim held: not one line of server code changed.** Every field was
   already being sent to this client and thrown away.

   **The split is read, never computed.** `FocusOut.above_the_line` arrives
   already decided, and the schema's own reason for sending it — *the
   comparison is on timestamps in the owner's zone* — is stronger here than on
   the web, because a phone can be in any zone at all. A client that worked it
   out locally would quietly file this morning's choices below the line after a
   flight.

   `timeOfDay` **takes its zone as an argument** rather than reading
   `ZoneId.systemDefault()` inside, for the same reason one level down: it made
   the three tests assert a fact rather than whatever machine runs them, and it
   turned the device's zone from an assumption into a visible choice at the
   call site.

   **A null line is the ordinary morning**, not an error — rule 11 keeps
   `list_closed_at` null until something is executed, and the screen says *the
   list is still open* rather than drawing a line at nothing.

   **What is verified and what is not.** 276 tests, 0 failures, and
   `assembleDebug` builds — so the model, the parser and the formatter are
   tested, and the Compose changes are proven to *compile* and nothing more.
   This suite has no UI tests; how the line and the appointments actually look
   is unverified until increment 5 puts a build on the phone.

3. ~~**The pool.** `GET /api/v1/pool` gains token auth, deliberately and in
   `TOKEN_AUTHENTICATED`, and the phone gets the surface that replaced the
   Agenda.~~ **Shipped September 6, 2026 — the first increment here that
   changed the server, and it changed one line.**

   **The endpoint named its own trigger and this was it.** `lists.api_v1.pool`
   had said *session only. The phone has no pool surface, and widening a bearer
   to reach one before there is anything to reach would be the un-switched-on
   seam this project keeps finding.* That condition ended when the phone got
   the surface, so the widening arrived **with** its reason rather than ahead
   of it — which is the difference the whole guard exists to make somebody
   demonstrate.

   **`agenda:read`, not a new scope.** The pool is what replaced the Agenda,
   `GET /agenda` already takes exactly that, and a token holding it can already
   read every open task through the other endpoint — so a second scope over the
   same material would be a distinction the person granting it could not act
   on.

   **Read only, and `POST /pool/{task_id}/still-wanted` is deliberately
   absent** from `TOKEN_AUTHENTICATED`, with a test asserting it stays refused.
   The screen *shows* rule 8's question, because knowing the pool is asking is
   worth something on its own; answering it is a different decision from
   reading the list.

   **Picking needed no widening at all.** `POST /day/{day}/focus` was already
   token-authenticated, so `PoolViewModel` borrows `DailyApi.pinFocus` rather
   than growing a pool verb — the same borrowing `DailyViewModel` does for the
   task verbs, and for the same reason: a second way to pin would be a second
   definition of what picking means.

   Two things are read and never computed here, both for the reason that keeps
   recurring on this client: `days_until` and `asks_to_be_kept`. A phone
   comparing `unpicked_for_days` against a threshold of its own would be D8's
   mirrored constant arriving by the back door, and one working out a date in
   its own zone would answer a question about the owner's day from wherever it
   is standing.

4. ~~**The evening.** The readback, the leftovers, and rule 7's three moves —
   which needs the second widening.~~ **Shipped September 6, 2026.**

   **The endpoint asked to be asked, and this was the asking.**
   `decide_about_a_leftover` had said *session only. The phone has no evening
   ritual, and letting go archives a task — widening a bearer that sits in a
   keystore for ninety days to do that should be asked for rather than arrive
   with a closing prompt.* It has one now.

   **All three moves, `let_go` included, and that was settled by evidence
   rather than judgement.** `TaskStatus` includes `"archived"` and
   `PATCH /api/v1/tasks/{task_id}` is already token-authenticated and already
   accepts `status` — so a bearer can archive a task today, through a door open
   since August. A carve-out here would have guarded a capability the same
   token already has, while reading as though it guarded something.

   **And it closed the collision increment 1 flagged, by finding it was a
   defect rather than an ambiguity.** The phone's row *Tomorrow* called
   `rescheduleTask` — a due-date move — while the evening's *Tomorrow* chooses
   a day. **The website had exactly this bug and fixed it on September 3**,
   where its own comment says the word "did two opposite things on one page".
   So this is not a rename: `deferTaskToTomorrow` now reaches `leftovers`, and
   there is one meaning of *Tomorrow* on both clients again.

   `tomorrow()` was deleted **one increment after being moved**, its only
   caller gone. Its warning was right and resolved by deletion rather than by
   care.

   The test that asserted the old behaviour was **rewritten with its subject
   rather than deleted**, because the rule it guards still exists — it just
   says the opposite thing now.

5. **A signed release, and the deletion it unblocks.** See below; this is the
   increment that has a manual step in it and it is Vince's.

---

## The thing to know before installing anything

**A release APK is signed with a different key than the debug build on the
phone, so Android refuses to install over it.** Uninstalling first **clears the
encrypted capture queue**, which must be drained before the swap.
[`roadmap.md`](roadmap.md) records this so the overhaul does not rediscover it,
and it is repeated here because it is the one step in this plan that can lose
somebody's data.

**The keystore is Vince's to generate and not an agent's** —
[`android-release-signing-plan.md`](android-release-signing-plan.md) §2, and it
is a permanence argument rather than a policy one. Verified ready on August 31,
2026: `assembleRelease` still builds after AGP 9, the signing config activates
only when all four `local.properties` keys are present, and `keytool` and
`apksigner` are both on this machine.

**A signed release on the phone is also the trigger for a deletion the task
core is waiting on** — `lists/api.py`, `lists/api_urls.py`, the `/api/` mount,
`TaskOut.url`, `AreaRefOut.create_item_url` and four exempted payload keys, in
one commit. The ordering is already written down: the compatibility surface
retires **with** the overhaul rather than before it.

---

## What this refuses

- **iOS.** Part 9 names its absence as evidence against native, and that
  argument is unchanged; nothing here answers it.
- **Reopening the freeze question.** It was answered in direction on August 31
  and re-arguing it is not this plan's job.
- **The knowledge core on the phone.** Capture stays as it is; nothing else
  from `/mind/` arrives.
- **A second API.** Everything here is `/api/v1/`, and a widening is a line in
  `TOKEN_AUTHENTICATED` rather than a new surface.
- **Widening a token by default.** Each entry is argued at the point it is
  added. A bearer sits in a keystore and outlives a session by ninety days.

---

## Decisions

- **A1. Does the phone get the composer?** The day page's four destinations
  write through `POST /api/v1/capture`, which the phone **already reaches** —
  so this costs almost nothing and may be the highest-value thing here. Not
  decided because it is a question about how Vince captures on a phone.
- **A2. Does the phone write appointments, or only read them?** Reading is
  free today. Writing is a third widening, and a diary entry typed on a phone
  is a plausible thing to want.
- **A3. What happens to `DailyScreen`'s writing surface?** It can still `PATCH`
  the three prose fields the website stopped showing on September 4. Whether
  those columns have a future is
  [`superlists-2.0-plan.md`](superlists-2.0-plan.md)'s deferred question, and
  **this plan must not answer it by accident** — increment 1 removes the
  fields from the phone's *model*, which is not the same as deciding the
  column's fate.

---

## Acceptance

**Scored by using it**, the way Money and Superlists 2.0 are, and with the same
warning: the first verdict on Money read *works* and became *not yet* after one
real walkthrough by the person who built it.

- **The morning's list gets built on the phone at least once**, and the line
  behaves — what is added before the day starts joins the chosen set, and what
  is added after joins below it.
- **The phone and the website never disagree about one day.** Same endpoint,
  same rules; if they diverge, the phone has grown its own copy of a rule and
  that is the defect this plan exists to prevent recurring.
- **Nothing shows a concept the website has retired.** The measurable half, and
  the least interesting.

---

## Where the facts live

- [`roadmap.md`](roadmap.md) — the August 31 direction, the keystore
  dependency, and the ordering between them.
- [`android-full-client-plan.md`](android-full-client-plan.md) — the stub for
  slices 1 and 2, shipped August 11, 2026.
- [`android-release-signing-plan.md`](android-release-signing-plan.md) §2 — why
  the key is Vince's.
- [`superlists-2.0-plan.md`](superlists-2.0-plan.md) — the model the phone has
  to catch up with, and A3's deferred question.
- [`commercial-blueprint.md`](commercial-blueprint.md) Part 9 — the freeze
  recommendation this overrides, and the evidence it rests on.
- `src/clarice/tests/test_api_auth_surface.py` — what a token reaches. The
  authority, not this file.
