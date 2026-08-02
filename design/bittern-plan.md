# Bittern — delivery plan

**Status: M1 implemented and passing locally; release verification and the
remaining stages are next.** Bittern is staged work: make the deployed web
application trustworthy enough to be a dependable capture backend, ship the
Android capture client, then close the remaining web-session and state gaps.
It is not a grab bag of every attractive Postgres or public-readiness idea.

This document is the implementation plan for the active Bittern entry in
[`roadmap.md`](roadmap.md). Completed Albatross decisions and deploy history
are in [`roadmap-history.md`](roadmap-history.md).

## Stage plan

### Stage 0 — establish production truth

| Slice | Why it belongs | Dependency |
| --- | --- | --- |
| B0 — production bundle truth | Android needs a known-good, observable production backend; web navigation cannot be planned or verified while production may serve old JavaScript. | None; do first. |
| B0.1 — capture API smoke check | Confirm token creation, authenticated capture, and Inbox visibility against the actual production deployment. | B0's deployed-artifact identity. |

**Exit condition:** the running image and static bundle are identified, the SPA
navigation is visible after a hard refresh, and a newly created capture reaches
the owner's Inbox through the token-authenticated API.

**Evidence before repair.** Production is several commits behind `main`, and
two of those commits are code: the Agenda's direct Inbox/Ideas fallback links
and M1's idempotency migration. A deploy is therefore already owed — and a
deploy is also the repair step for B0's stale-artifact hypothesis. Do the
read-only half of B0 against the *currently running* container before pushing
anything new, or the redeploy destroys the only evidence that distinguishes a
stale bundle from a current bundle that fails at runtime. This ordering
constraint expires the moment production is updated.

### Stage 1 — Android Capture MVP

| Slice | Why it belongs | Dependency |
| --- | --- | --- |
| M1 — idempotent mobile capture contract | A retry must never create a duplicate thought after a lost response. | Stage 0 production API check. |
| M2 — native capture client | The core requested product: open, type, submit, and return to life. | M1 contract. |
| M3 — durable offline delivery | Capture must work when the thought arrives before the network does. | M1 and M2. |
| M4 — device/pilot verification | Confirms the real capture loop, token lifecycle, and background retry work outside an emulator. | M2 and M3. |
| M5 — share to capture | Lets text and links move from another Android app into an editable Clarice capture draft. | M4's dependable capture flow. |

**Exit condition:** an Android user can authenticate with a personal access
token, capture online or offline, safely retry without duplicates, and see the
result in the web Inbox.

**M1–M4 are done as of August 2, 2026.** Every clause of that exit condition
has been observed on a physical device against production, in a deliberate
pilot rather than opportunistically — see M4 for the evidence and for the
two criteria consciously not met. Only M5 remains, and it is optional for a
prototype.

### Mobile repository and sequencing decision

Keep native clients in this repository: create `android/` at the repository
root when real Android work begins, and reserve `ios/` as its future sibling.
The Django API, web application, mobile clients, release checks, and product
plans are one product and one delivery narrative today; splitting repositories
would add coordination cost without a present benefit. Revisit only if
separate teams or release processes earn that cost.

M1 is deliberately shared backend work, not Android scaffolding. It can be
implemented and fully tested without Gradle, Android Studio, or a device, and
both eventual native clients use the same contract. The native Android project
starts at M2 on a development machine with Android Studio and real dependency
resolution available; do not add an unbuildable placeholder project here.

Stage 0/B0.1 remains the deployment gate: M1 may be prepared before that
production check, but no mobile client should rely on it until the production
capture service and migration have been verified.

### Stage 2 — web usability completion

| Slice | Why it belongs | Dependency |
| --- | --- | --- |
| B1 — recurring-subtask response | Fixes the known task UI inconsistency with a bounded API/client contract. | Stage 0's trustworthy deploy path. |
| B2 — SPA logout | Every authenticated SPA needs an accessible, CSRF-safe logout path. | Stage 0. |
| B2.1 — safe entry and failure states | `/app/` should not be blank; an expired session or missing task should provide a recovery path, not a generic error. | B2's session behavior. |
| B2.2 — browser smoke coverage | Critical journeys need testing in a built browser application, not just component tests. | B1 and B2. |

### Stage 3 — production feedback loop

| Slice | Why it belongs | Dependency |
| --- | --- | --- |
| B3 — branded email and contact | Password resets and support must represent Clarice, not its developer's personal inbox. | Choice of email provider and verified domain sender. |
| B4 — error monitoring | Gives the next production issue evidence rather than guesswork. | A production DSN and release/environment configuration. |
| C2 — information-architecture observation | Decide from actual navigation friction, not a screenshot of a broken nav. | Stage 2 observed in use. |

### Does not ship in Bittern

| Candidate | Decision | Trigger for reconsideration |
| --- | --- | --- |
| C2 information architecture redesign | Observe after the navigation is actually visible. | At least three specific, repeatable navigation failures remain after B0/B2. |
| Ranked full-text search | Existing substring search already serves Inbox and Ideas. | Real reference-library usage makes simple filtering insufficient. |
| ~~Per-user time zones~~ | **Trigger fired August 1, 2026 — now built.** Both halves at once: a second active user in Indonesia, and the digest delivering at 03:00 Eastern. | n/a. See [`per-user-time-zones-plan.md`](per-user-time-zones-plan.md). |
| Audit/general undo and time blocking | Separate product-model work. | A focused product brief, not availability of Postgres alone. |
| Account export/deletion | Export is ready to scope; irreversible deletion needs an explicit retention decision. | Decide immediate deletion versus a grace period. |

### Non-goals

- No list sharing, real-time sync, or conflict resolution.
- No broad React rewrite of Capture or Ideas.
- No new recurring-task rules or task-model migration; M1's small capture
  idempotency migration is the sole planned schema change.
- No navigation redesign before the current navigation is proven to render.
- No Android triage, Idea management, task editing, push notifications, or
  account/token administration. The Android app captures; the web app reviews.
- No mobile-web work. Bittern does not make the browser application usable on
  a phone, which means the sentence above is load-bearing in a way worth
  naming: review happens on the web, and until the mobile web experience in
  the roadmap's Later section is addressed, that in practice means a desktop
  browser. Stage 0's mobile-breakpoint check is a defect check, not the start
  of that work.

## Order of work

```text
B0: establish production artifact and capture-API truth
        │
        ├── stale/mispackaged bundle → repair build/deploy → verify
        └── current bundle           → capture actual runtime failure → fix as B0
        │
        └── Stage 1: Android Capture MVP
                │
                ├── M1: idempotent writes
                ├── M2: native capture flow
                ├── M3: offline queue and retry
                └── M4: real-device pilot
                        │
                        └── Stage 2: web usability completion
                                ├── B1: spawned subtasks
                                ├── B2: logout and session recovery
                                └── B2.2: end-to-end smoke coverage
                                        │
                                        └── Stage 3: monitoring and IA decision
```

Stage 0 is a hard gate because it verifies the service the phone will call.
Within Stage 1, M2 can begin once M1's contract is settled, while M3 works
alongside the basic online flow. B4 must not block Android or web usability if
the monitoring account or DSN is not yet available.

## B0 — establish production bundle truth

**Status: closed August 1, 2026.** The artifact was never at fault — the
served bundle contained the navigation and the served CSS was byte-identical
to a local build. The cause was a source defect: `AppLayout` sealed the nav
inside a `<details>` that nothing opened, above a breakpoint where the CSS
hides its `<summary>`. Patched, deployed at 11:56 EDT, and confirmed in an
authenticated browser at both widths. Full evidence, including the
measurement that settled it and the false trail that delayed it, is in
[`roadmap-history.md`](roadmap-history.md). The checklist below is retained
because it is what produced the answer.

### Problem statement

`frontend/src/app/main.tsx` mounts `AppLayout`, which mounts `SideNav`, and
`app_shell.html` loads `frontend/app-shell.js`. The live Albatross screenshot
shows no side navigation even after a hard refresh. Source alone therefore is
not evidence of what production serves.

The two likely classes of cause are:

1. the running image contains an older frontend build or serves an unexpected
   static bundle; or
2. the current bundle loads but fails at runtime or is suppressed by layout
   CSS.

Treat these as different failures. Do not change navigation markup until this
check says which one occurred.

### Investigation checklist

Steps 1–4 are read-only and must be completed before any redeploy; step 5 is
the first step permitted to change what production serves. The host is the
single entry in `infra/production-inventory.ini`; there is no staging
environment to rehearse against, which is the other reason to gather evidence
before touching it.

1. Record the deployed commit/image identity and the response headers for
   `/app/agenda` and its referenced `app-shell.js` asset.
2. Inspect the running container's static files and verify that the served
   `app-shell.js` contains the distinctive Inbox/Ideas navigation strings.
3. Compare that artifact with a local production build from the deployed
   commit, including the HTML `<script>` path emitted by `app_shell.html`.
4. Open `/app/agenda` in an authenticated browser session and record browser
   console errors, failed network requests, and computed layout for the nav.
5. If the artifact is stale, rebuild without Docker cache, redeploy, then
   repeat the browser check. If it is current, fix the identified runtime or
   CSS defect in a focused B0 patch and repeat the check.

### Acceptance criteria

- The source commit, built image, served shell, and served JavaScript are
  positively identified in the release notes.
- An authenticated hard refresh of `/app/agenda` displays Agenda, Inbox,
  Ideas, Archive, Lists, Preferences, Settings, and their current counts.
- The same is checked at the mobile disclosure breakpoint; navigating closes
  the disclosure and leaves the selected destination visible.
- The root cause and verification evidence are added to
  `roadmap-history.md` when B0 closes.

### Guardrail for future deploys

Add one release smoke check — manual or automated — that loads `/app/agenda`
after deploy and asserts the navigation landmark and Inbox link are present.
The goal is to test the served artifact, not merely run the frontend build
again in CI.

## B0.1 — verify the production capture service

**Status: closed August 1, 2026. All five steps verified against
production.** A capture typed on a Samsung SM-F966U reached production and
appeared in the web Inbox:

```text
id 1  2026-08-01T22:01:48Z  145c6689-be80-4f2a-be25-d0892ec42eee  Vrbeall01
total captures: 1        with an idempotency key: 1
```

The stored key is what makes this conclusive. Browser captures never send
an `Idempotency-Key`, so a persisted UUID means the write went through M1's
path with a bearer token — the token decrypted out of the Keystore, the
header sent, `create_capture_idempotent` storing it, the migration holding
it, and exactly one row at the end.

**Revocation is verified, also on the phone, once M2's Settings screen made
it checkable without curl.** The token was deleted on the web and the
device was then observed doing three separate things right:

- Settings named no account and said "Clarice did not accept that token" —
  a refusal, distinct from an outage.
- A capture attempt was rejected on the separate `/api/v1/capture` path,
  `403` reaching `Disposition.NEEDS_RECONNECT`.
- **The typed text stayed in the field.** This is the one that matters. A
  revoked token must never cost somebody the thought they were capturing,
  and until M3 that field is the only queue there is.

Reconnecting with a freshly minted token restored capture, which also
exercised the replace-a-token path.

**The keyed replay passed**, by `curl`, since the app correctly refuses to
reuse a key. One thought sent twice under
`ee2d9bb3-de1e-443b-8d9d-d072481a512d`:

```text
attempt 1: HTTP 201  {"id": 2, "created_at": "2026-08-01T22:58:01.796437+00:00"}
attempt 2: HTTP 200  {"id": 2, "created_at": "2026-08-01T22:58:01.796437+00:00"}
```

Same id, same timestamp to the microsecond — the second request stored
nothing and returned the first write. Confirmed at the database rather than
inferred from the responses: two captures total, exactly one of them the
probe, holding the key that was sent.

M1's duplicate protection is now exercised against the production service it
protects, not only by the Django suite and CI's Postgres.

One lesson from the probe itself, which is why it is written down. The
script that ran it extracted ids with `"id":[0-9]*` while the API renders
`"id": 2`, so both ids came out empty, compared equal-to-each-other-as-empty
against the wrong branch, and it announced **FAIL — duplicate protection is
not working in production** over a completely healthy service. The evidence
in the same output said otherwise. A verification tool that can cry wolf is
worse than no tool, because the next person believes it: assert on values
you have proven you can parse.

Original steps, for whoever finishes it:

1. Create the token through the existing account page and save it only in the
   test client.
2. Send a short unique capture through `POST /api/v1/capture` with a bearer
   token.
3. Confirm `201`, a capture id, and a timestamp.
4. Confirm the item appears once — and only once — in that user's web Inbox.
5. Revoke the test token and confirm further requests are rejected.

Record the endpoint host, TLS behavior, request/response shape, and revocation
result in the release verification. A mobile app should never be the first
thing to discover that a deployed capture endpoint is unreachable.

## Stage 1 — Android Capture MVP

### Product promise

Capture is the mobile app's whole job: open it, write or paste a thought,
submit it, and immediately return to what you were doing. The thought may be
triaged later on the web. The app should feel faster than opening the browser
and should remain dependable under poor connectivity.

### M1 — idempotent capture writes

**Current state:** the additive server implementation and migration are
committed, and the capture suite passes both locally (98 tests, SQLite) and on
the Postgres-backed CI path, where migration `0003_capture_idempotency_key` is
applied by the test runner against Postgres 18. The M1 commit message's caveat
that it had never been run is resolved. Two items remain before M2 may depend
on it: apply the migration in production, and complete B0.1's production smoke
check. Both sit on the far side of the Stage 0 gate.

The current endpoint creates a capture for every successful POST. If Android
sends a request, loses the response, and retries, it cannot know whether the
first request was stored. Retrying risks duplicate ideas — the precise failure
a capture tool must avoid.

Add an optional `Idempotency-Key` request header to `POST /api/v1/capture`.
Android generates one UUID per locally created capture and sends the same key
for every retry. Persist the key with the capture, scoped to its owner, with a
database uniqueness constraint. A repeated owner/key returns the original
capture representation rather than creating a second record; requests without
the header retain their current behavior.

The endpoint must be transaction-safe, so two simultaneous retries cannot
create two captures. Malformed keys return `400`; the server must not invent a
key because the client owns retry identity.

**Server tests:** first keyed request creates one row; a repeated key returns
the original row; concurrent retries result in one row; different owners may
reuse a key; malformed keys fail; omitted keys still work; revoked or inactive
tokens cannot access another user's capture.

#### Mobile handoff contract

M2 receives a small, stable contract rather than needing to infer server
behavior from implementation:

| Situation | Client request / response | Client action |
| --- | --- | --- |
| New or queued capture | `POST /api/v1/capture`, bearer token, text payload, and the capture's locally generated UUID in `Idempotency-Key` | Treat `201` plus `{id, created_at}` as delivered. |
| Lost response or retry | Send the exact same UUID again | Treat `200` with the same response shape as delivered; never create a new UUID for a retry. |
| Invalid key or invalid capture | `400` | Keep the text, show a fixable error, and do not retry blindly. |
| Revoked, expired, or invalid token | `401` or `403` | Keep the queued text and require reconnection; never discard it. |

The Android engineer records the production base URL and TLS verification from
B0.1 in the client configuration; no endpoint, token, or server secret is
hard-coded into the app. The same table is the future iOS handoff.

### M2 — native app and token lifecycle

**Status: started August 1, 2026 — buildable skeleton in `android/`.** The
project assembles a real debug APK and runs unit tests from the command
line, which is the bar this plan set before any mobile code entered the
repository. `applicationId` is `com.vinclarice.capture`; versions are pinned
in `gradle/libs.versions.toml` from live Maven metadata rather than a
template, and the wrapper distribution is checksum-pinned to the release it
was generated from.

The first slice is M1's client half: `dispositionFor(status)` encodes the
handoff table as a pure function, so M3's retry logic branches on it instead
of re-deciding it. Eight tests. Unknown statuses map to retry rather than
rejection on purpose — a wasted background attempt costs little, discarding
a thought the person typed is the one failure this app exists to prevent.

Two things worth knowing before touching the build. **AGP 9 builds Kotlin
itself**, and applying `org.jetbrains.kotlin.android` alongside it fails
outright, which nearly every guide still tells you to do. And neither
`JAVA_HOME` nor `ANDROID_HOME` is set on this machine, so command-line
builds need both pointed at Android Studio's bundled JDK and SDK — see
`CLAUDE.md`.

Since then: the HTTPS client (tested against MockWebServer), the connection
logic behind a `TokenStore` seam, and a Keystore-backed implementation of
that seam.

**`androidx.security:security-crypto` is not used, and must not be added.**
It is deprecated; its 1.1.0 "stable" release shipped with every API already
marked deprecated and no further releases planned, which reads exactly like
the opposite of a deprecation. Google's replacement guidance is direct
Android Keystore use with no dependency, which is what
`KeystoreTokenStore` does.

Two details there are load-bearing rather than incidental:
`setUserAuthenticationRequired(false)`, because a key requiring user
authentication is permanently invalidated when the lock screen is removed
or biometrics are re-enrolled — after which every capture would throw; and
the backup exclusion, which exists for correctness rather than secrecy,
since a restore would otherwise hand a new device ciphertext with no key.

**Connect is verified on a physical device, August 1, 2026.** A Samsung
SM-F966U running Android 16 installed the debug build, connected to
production with a real personal access token, and stayed connected across a
force-stop — which is what proves the decrypt path, not just the write. The
seven Keystore instrumentation tests then ran on that device: 7 passed, 0
failed, including that the token is not written to disk in the clear, that
a corrupted value reads as no token rather than throwing, and that it does
not poison the next connection. Those last two are the failure modes the
deprecated library was abandoned over.

That happened earlier than planned. M4 still owns the capture loop, the
offline transitions and the revoked-token path; what is settled early is
the credential half.

One thing this exposed, and it is the reason B0.1 exists: the first attempt
failed with "Clarice did not accept that token" because the bearer-auth
`/api/v1/me` endpoint the client depends on was still only on `main`. The
token was always valid. A phone was the first thing to discover a
production contract gap — precisely the situation this plan says never to
allow. Check the deployed OpenAPI schema before pointing a client at an
endpoint, not after.

**Capture is verified on a physical device, August 1, 2026.** Text typed on
the phone reached production and appeared in the web Inbox, carrying the
idempotency key that proves it travelled M1's path rather than a browser's.

One defect found by running the real thing, worth keeping because no test
would have caught it: the instrumentation suite shared the app's own
preference file, so running it deleted a live token off the phone and sent
its owner back to Connect. The alias was parameterised; the file name was
not. Isolating one half of a store's identity is isolating neither. Fixed,
with a test that asserts the app's file is untouched.

**Settings shipped August 1, 2026, completing M2's three screens.** It shows
the account the stored token belongs to, and offers Disconnect.

Two decisions there are worth stating, because both were tempting to get
wrong:

The account name is **asked of the server on every open, never remembered**.
Caching it at connect time would leave Settings cheerfully naming an account
for a token that was revoked an hour ago — and revocation is precisely what
somebody opens that screen to check. So `Connector.whoAmI()` re-validates the
stored token, and its three answers stay distinct all the way to the text on
screen: a named account, "Clarice did not accept that token", or "could not
reach Clarice". Collapsing the last two would tell a person on a train that
their credentials are broken.

A refused token is **reported but not discarded**. Disconnecting is an action
someone takes, not one that befalls them because a request came back badly;
silently clearing it would eject them to Connect before they had read why.

The pending-queue display the screens list asks for is deferred to M3, since
there is no queue to report until then. Showing "nothing waiting" while the
Capture field is the only thing holding an unsent thought would be true and
misleading at once. For the same reason the `CaptureViewModel` is held above
the navigation branch: a trip to Settings must not drop the field — and the
thought in it — out of composition.

M2 closes with 75 JVM tests and 8 instrumentation tests.

#### Sequencing note

Stage 2's B1 and B2 shipped before M2 began, which reverses the documented
order. The reason was environment, not preference: Android Studio was not
installed while that work was done. Recorded here so the order looks
deliberate rather than forgotten.

Create a standalone Kotlin Android project using Jetpack Compose. Its first
release has three screens only:

1. **Connect:** explain how to create a labelled access token on the web,
   paste it, validate it with an authenticated request, and save it.
2. **Capture:** one prominent multiline field and one submit action. Focus the
   keyboard automatically; success clears the field and confirms briefly.
3. **Settings:** show connected account identity and pending-queue state, and
   offer an explicit Disconnect action.

Store tokens in Android Keystore-backed encrypted storage. Never log tokens,
put them in analytics or crash reports, or display them after saving. Use HTTPS
and the normal `Authorization: Bearer` header. A `401`/`403` marks the queue
as needing reconnection; it never discards captured text. Replacing a token
must retain pending captures.

### M3 — durable offline delivery

**Status: complete, August 1, 2026.** Five slices, 127 JVM tests and 16
instrumentation tests, and one end-to-end run on a Samsung SM-F966U: three
captures typed in airplane mode, the app force-stopped and reopened with the
queue intact, and the queue draining itself when the network returned. Every
capture reached the web Inbox exactly once.

The slices, and the decision in each worth remembering:

1. **The queue and its ceiling** (`CaptureQueue`). Attempts are counted and
   stop at five. A stalled item keeps its text *and its key*, so a manual
   retry weeks later is still the same write. A `400` is charged no attempt
   at all — the ceiling bounds pointless repetition, and a refused text will
   not be repeated.
2. **Encryption** (`EncryptedQueueStorage`). Its own Keystore alias and its
   own preference file, because disconnecting deletes the token's key and a
   shared one would destroy every unsent thought at the moment somebody was
   told their token had stopped working. The cipher was extracted from
   `KeystoreTokenStore` rather than copied — two implementations of GCM is
   two places to get it wrong silently.
3. **Capture writes to the queue before the network.** This reverses three
   M2 behaviours, each only safe once the queue existed: offline says "Saved
   — will send when online" and is not an error; a capture typed with no
   token is queued rather than refused; and a revoked token spends no
   attempt. A server rejection is the one path that returns the text to the
   field, because only a person can make a `400` acceptable and they cannot
   edit what they cannot see.
4. **Background delivery** (`QueueDrainer` + WorkManager 2.11.2). Every
   decision is about when to stop: a failure about the *connection* ends the
   run, a failure about one *capture* does not. `ExistingWorkPolicy.KEEP`,
   not `REPLACE` — replacing restarts the backoff on every capture, so
   somebody typing steadily through an outage would push their own queue's
   next attempt further away with each thought.
5. **Settings shows the queue.** Waiting and needs-attention are drawn
   differently rather than collapsed into a count of problems, and a stalled
   item shows its own text, since "a capture" is not enough to decide
   anything about.

**One defect found only by running it.** Background delivery worked on the
first real try — and "3 waiting to send" stayed on screen over the emptied
queue until the screen was left and re-entered. The count was a snapshot
taken when Capture entered composition, and a screen cannot see a background
drain. To its owner, a number sitting over an empty queue is
indistinguishable from three captures having gone missing, which is the
precise fear this whole milestone exists to remove. No unit test would have
caught it: every assertion about the count was correct, and the gap was
between the queue changing and anything telling the screen. Fixed by
observing WorkManager's unique-work flow.

**Deliberately not built:** there is no way to discard a rejected capture, so
one will sit in Settings indefinitely once its text has been fixed and
resent. Judged acceptable while the app is a prototype; adding a delete
button to the one screen guarding against data loss deserves its own
decision.

The original specification follows.

An accepted local capture must survive app close, restart, and a network drop.
Store its text, idempotency UUID, local creation time, and delivery state in
encrypted app storage. Use WorkManager for persisted network-constrained
retries.

The foreground submit tries delivery immediately. If it cannot complete, it
leaves the item in the durable queue and says **Saved — will send when online**
without preventing another capture.

- Generate the UUID before the first request and preserve it across retries.
- Remove a queued item only after a successful, parsed server response.
- Preserve the payload/key after a timeout or offline failure.
- Keep queued text on an invalid/revoked token and offer reconnect.
- Retain text on validation `400` and show a fixable error; do not retry it
  indefinitely.

#### Retry has to have an end

M2's `dispositionFor` maps every status it does not recognise — and every
`5xx` and `429` — to retry rather than rejection, deliberately: a few
backed-off attempts against something permanently broken cost little, while
discarding a thought someone typed is the one failure this app exists to
prevent. The cost of that choice lands here. A capture that keeps failing
for an unrecognised reason — a misconfigured base URL answering `404`, a
proxy stuck at `502` — would otherwise retry forever, burning battery on a
queue that will never drain, and saying nothing about it.

So the queue needs a ceiling, not just backoff:

- Count attempts per item and stop after a bounded number.
- A stopped item is **not** discarded and **not** silently dropped. It keeps
  its text and its idempotency UUID, so a later manual retry is still the
  same write rather than a second one.
- Surface it. Settings already shows pending-queue state; a stalled item has
  to be visibly distinct from one merely waiting for a network, and offer an
  explicit retry.
- Reaching the ceiling is a display change, never a data loss. "Never
  discard" outranks "never churn".

This is the same instinct as the `400` rule above, generalised: the client
stops repeating a request that is not going to start working, and tells the
person, rather than deciding on their behalf that the thought is gone.

**Android tests:** online submission sends one authenticated request; a timeout
retry uses the same key; process restart retains the queue; invalid token keeps
the text; offline submission remains responsive and visibly queued; an item
that exhausts its attempts stops retrying, keeps its text and UUID, and shows
as needing attention; and a manual retry of that item reuses the original key
rather than minting a new one.

### M4 — real-device pilot and release criteria

**Status: pilot run August 2, 2026 on a Samsung SM-F966U (Android 16)
against production. Every release criterion met except two, both recorded
below.** Fifteen captures across every network condition the plan names,
delivered to the production Inbox as fifteen rows with fifteen distinct
idempotency keys — nothing lost, nothing duplicated, nothing out of order.

```text
10  00:04:30  M4 wifi one          Wi-Fi, online
11  00:04:36  M4 rapid 1           three in quick succession,
12  00:04:40  M4 rapid 2           each its own request
13  00:04:46  M4 rapid 3
14  00:05:06  M4 cellular one      Wi-Fi off, mobile data
15  00:05:29  M4 cellular 2
16  00:15:07  M4 transition 1      radio switched mid-request
17  00:15:52.101  M4 crosslink 1   queued in airplane mode,
18  00:15:52.150  M4 crosslink 2   drained over Wi-Fi
```

The crosslink pair is the most informative line in that table: the queue was
built with no network at all and delivered over a transport it had never
seen, 49ms apart and in the order they were typed. Earlier the same evening,
two airplane-mode batches (ids 4–6 and 7–9) survived a force-stop and
drained themselves unattended, and a revoked token was recovered from
without losing the text in the field.

**Storage, verified with `run-as` rather than asserted.** The app's data
directory holds exactly two files it wrote: the token and the queue, both
ciphertext.

```text
shared_prefs/clarice_capture_secret.xml       JkKAHmU3cR3u3U1B:5Htos...
shared_prefs/clarice_capture_queue_store.xml  003WkL7j0vPjZ25L:tnWnN...
databases/                                    empty
```

WorkManager keeps its own scheduling database under `no_backup/`, which is
app storage that is neither of those two things — so the criterion is met in
substance rather than literally. It was searched for capture text and
contains none, which is what the criterion is actually protecting: the
worker takes no input data, so nothing anybody typed is stored outside the
encrypted queue.

**Two criteria not met on the device, deliberately:**

- **No emulator run.** The plan asks for a physical device *and* an
  emulator. A second API level would add something, but every radio
  behaviour in this list is more honestly tested on real hardware, and the
  instrumentation suite already runs on the device. Judged not worth the
  setup for a prototype.
- **Forced retry was not exercised through the app's own path.** Reaching
  the stall ceiling needs five failures, and since the worker only runs when
  a network is present, forcing it means a build pointed at a deliberately
  broken URL plus roughly eight minutes of backoff. The behaviour is covered
  by unit tests — that a manual retry reuses the original key rather than
  minting a new one, at both the queue and the Settings layer — and the
  server half was proven directly against production in B0.1, where the same
  key sent twice returned `200` and left one row. What has not been observed
  is those two halves meeting on a phone.

Verify on at least one physical device as well as an emulator: Wi-Fi,
cellular, airplane-mode transitions, app process death, and a revoked token.
Make several quick captures, then confirm the web Inbox contains each exactly
once and in created-at order.

Android is releasable only when fresh-token connection works against
production, online/offline captures survive those flows, forced retries create
no duplicates, token revocation is recoverable without data loss, and the app
stores only the encrypted credential and explicitly visible pending queue.

### M5 — share to capture

After the basic Android capture loop is reliable, register Clarice as an
Android share target for plain text and URLs. A share opens an editable capture
draft; it never silently posts another app's content. Submitting the draft uses
the same idempotent, offline-capable queue as typed capture.

The first version stores shared URLs as capture text rather than inventing a
source-link model prematurely. Whether a reference needs structured URLs,
titles, previews, attachments, or provenance belongs to the later second-brain
domain design. Test text sharing, URL sharing, cancellation, offline sharing,
and confirmation that the content reaches Inbox exactly once.

## B1 — return and render spawned recurring subtasks

**Status: done August 1, 2026, not yet deployed.** Implemented as specified
below: `spawned_subtasks` is a sibling array on the task-status response,
the recurrence rules are untouched, and both workspaces insert parent and
children as one update. Eight API tests plus one workspace test each; the
existing service tests stand unchanged as the regression guard that B1
altered serialization and not the lifecycle.

### Behavior to preserve

When a repeating parent is completed, the service creates the next parent and
clones only non-archived children with `always_recurs=True`. The old parent
and its current children are archived correctly. That lifecycle is already
tested and must not change.

The gap is only in the mutation response: it serializes `spawned`, but not
the spawned task's freshly created children. `TaskWorkspace` and
`AgendaWorkspace` can therefore insert the parent into local state but cannot
show its children until their next query.

### Contract decision

Extend only the legacy task-status response used by the workspaces:

```json
{
  "data": { "...": "completed-or-archived parent" },
  "spawned": { "...": "next recurring parent" },
  "spawned_subtasks": [
    { "...": "fresh active child" }
  ],
  "cascaded": ["...children moved by this action"]
}
```

Use a sibling `spawned_subtasks` array instead of adding children to every
`Task` serialization. The normal list, agenda, and detail read contracts stay
small and stable; only the one mutation that creates children carries them.
An empty array is valid when no child recurs.

### Implementation outline

1. In `lists.api.item_detail`, after reloading the spawned task, query its
   non-archived children with the same relation fields used by task detail
   and serialize them into `spawned_subtasks`.
2. Extend the `ApiResponse` and `TaskStatusUpdate` TypeScript shapes in
   `frontend/src/api.ts` so the field is always exposed as an array.
3. In `TaskWorkspace.changeStatus`, insert the spawned parent and its
   children into local list state as one update. The existing row-nesting
   helper should then attach each child under the new parent.
4. In `AgendaWorkspace`, insert both the spawned parent and the returned
   children into the open-task collection before it re-buckets by due date.
   The agenda is intentionally flat, so children appear as their own rows
   with their parent breadcrumb.
5. Keep `cascaded` separate: it describes existing rows moved by the action,
   not newly created rows.

### Tests

- API: completing a recurring parent with two eligible children returns the
  spawned task and those two active children in deterministic position order.
- API: a child marked `always_recurs=False` and an independently archived
  child are absent from `spawned_subtasks`.
- API: a recurring parent without children returns `spawned_subtasks: []`.
- Service regression: completing the parent still archives/carries children
  exactly as it did before; B1 changes serialization, not recurrence rules.
- List workspace: complete a recurring parent and assert the new parent and
  its expected children render without a reload.
- Agenda workspace: complete a recurring parent and assert both the new
  parent and each child are placed in their correct due-date bucket without
  a reload.

### Acceptance criteria

- No manual refresh is needed to see the next occurrence's recurring
  subtasks in either the list or agenda workspace.
- Opted-out and archived children never reappear.
- The response is backward-compatible for callers that ignore the new field.

## B2 — add logout to the SPA

**Status: done August 1, 2026, not yet deployed.** `POST /api/v1/me/logout`
returns 204 and the control sits in `SideNav`'s Account group, so it is
reachable from every SPA route including the mobile disclosure, which
renders the same markup. `spa_shell` gained `ensure_csrf_cookie`: the SPA
can only send `X-CSRFToken` if something handed it the cookie, and that had
been relying on the user passing through a Django-rendered form on the way
in.

One behaviour worth recording, found while testing. An anonymous POST with
no CSRF token returns **403, not 401** — Ninja's `SessionAuth` runs its CSRF
check before it looks for a session, which `accounts.auth` already
documents. Both cases are tested separately, since a test that sends
neither a session nor a token proves only the first thing it trips over.

### Problem statement

The Django `base.html` template has a valid POST logout form, but the SPA is
served by `app_shell.html` and renders neither that form nor a logout control.
Logged-in users can change their password or manage tokens from the SPA, yet
cannot end their session there.

### Contract decision

Add an authenticated, CSRF-protected `POST /api/v1/me/logout` endpoint to the
Ninja API. It should call Django's normal `logout(request)` and return
`204 No Content`.

This is preferable to copying a template form into React:

- the existing typed API client already sends `X-CSRFToken` on non-GET
  requests;
- it retains Django's session invalidation behavior; and
- the SPA gets a clean success/failure contract before redirecting.

Ensure the app shell sets a CSRF cookie for an authenticated session so this
endpoint does not depend on a user having visited a separate rendered form.

### UI and behavior

- Place **Log out** in the Account group of `SideNav`; it should be visible
  on both desktop and mobile navigation.
- Disable the control while its mutation is pending.
- On success, clear client query state and perform a full navigation to `/`.
  Do not try to continue rendering an authenticated SPA after its session has
  been invalidated.
- If the request fails, retain the session and show a compact, actionable
  error rather than silently redirecting.

### Tests

- Endpoint accepts an authenticated POST with a valid CSRF token, logs out,
  and makes a subsequent authenticated API request fail.
- Endpoint rejects anonymous or CSRF-invalid mutation attempts according to
  the existing API security behavior.
- SideNav renders the control and invokes the endpoint once.
- Successful logout navigates home; failed logout does not navigate away.

### Acceptance criteria

- A user can end the current session from every SPA route.
- Logout remains a POST-only, CSRF-protected operation.
- There is no remaining SPA-only route from which logout is unreachable.

## B2.1 — safe entry and failure states

`/app/` currently has no index route, so a direct visit can render an empty
shell. Add an index redirect to `/app/agenda` and a deliberate not-found
screen for unknown SPA paths.

Replace each route's undifferentiated “Something went wrong” state with shared
recovery behavior:

- `401`: return to login with the intended in-app destination preserved.
- `403`: explain that access is no longer permitted.
- `404`: explain that the task or list no longer exists and offer Agenda.
- network/`5xx`: offer a retry without losing any unsaved local draft.

Test direct `/app/` load, an expired session, deleted-list and archived-task
links, and an offline/retry state. The acceptance criterion is that every
route failure gives the person somewhere sensible to go next.

## B2.2 — end-to-end browser smoke coverage

Add a browser-level test runner against a built application. Component and
Django tests remain valuable, but they cannot prove the routing, static asset,
session-cookie, and browser-navigation boundaries together.

Cover these critical journeys:

1. Login → Agenda → create and complete a task.
2. Direct-load a list and task-detail URL.
3. Capture → triage to task or Idea.
4. Logout → protected route redirects to login.
5. Mobile navigation disclosure opens, navigates, and closes.

The production deploy smoke check in B0 remains separate: this suite verifies
a built app before release; B0 verifies the artifact actually served after it.

## B3 — branded email and contact

### Provider decision — Resend, August 1, 2026

**Sending is Resend; receiving stays IONOS.** The domain's MX records already
point at IONOS and always did, so `support@vinclarice.com` is an IONOS mailbox.
Resend only sends. That split is the whole arrangement, and it is worth stating
plainly because a transactional provider looks like it replaces your mail
host and does not.

Two consequences that changed what this section originally said:

- **The SPF merge below does not apply.** Resend puts the Return-Path on a
  `send.` subdomain, so its SPF TXT and bounce MX land on
  `send.vinclarice.com` and the existing root record —
  `v=spf1 include:_spf-us.ionos.com ~all` — is left alone. DKIM at
  `resend._domainkey.vinclarice.com` signs `d=vinclarice.com`, which is what
  aligns DMARC for a `From:` on the root domain. The merge advice stands only
  if root-domain sending is ever chosen instead.
- **Resend's SMTP username is the literal string `resend`**, not an address,
  with a sending API key as the password. Django's stock SMTP backend covers
  it, so no provider SDK enters the dependency list.

The original constraint is unchanged: do not send public mail through the
developer's personal Gmail account, and do not merely change its display
name: the visible sender must be a Clarice address on `vinclarice.com`.

Use distinct, real addresses (mailboxes or forwarding aliases are fine):

| Purpose | Visible address | Who receives replies |
| --- | --- | --- |
| Password resets and account mail | `Clarice <accounts@vinclarice.com>` | `support@vinclarice.com` via Reply-To, if replies are invited. |
| User questions | `support@vinclarice.com` | Support inbox/forwarder; never a public personal address. |
| Internal signup, lockout, and error notices | Private admin recipient | The developer only; never in user-facing headers. |

### Outbound-email implementation

**Sender identity done, August 1, 2026; not yet sent through Resend.** The
credential and the identity are now separate settings, which they were not:
`DEFAULT_FROM_EMAIL` was defined as `EMAIL_HOST_USER`, so the address a
stranger saw on a password reset *was* the SMTP login.

Splitting them exposed a second defect the coupling had hidden. Both senders
were set inside the `smtp` branch, so dev and the whole test suite — which
take the `console` branch — never exercised a Clarice sender at all. They
fell through to Django's `webmaster@localhost`, which is why no existing test
noticed the Gmail address: in the only environment the tests ran in, it was
never there. The sender settings are now unconditional, so the three
environments agree.

`SERVER_EMAIL` is the one that would have failed silently in production.
`mail_admins()` sends From it, its Django default is `root@localhost`, and
Resend rejects an unverified sending domain outright — so the first real
lockout would have failed to report itself, with nothing to say why.

**Verified in production, August 1, 2026, 20:06 EDT.** A password reset
requested at `vinclarice.com` arrived at an external Gmail inbox one second
later and authenticated on all three checks:

```text
From:    Clarice <accounts@vinclarice.com>
Subject: Reset your Clarice password
SPF:     PASS with IP 54.240.9.156
DKIM:    PASS with domain vinclarice.com
DMARC:   PASS
```

The DKIM line is what makes this conclusive rather than merely encouraging.
`d=vinclarice.com` aligns directly with the visible `From:`, which is the
whole reason the key sits at `resend._domainkey` on the root domain instead
of on the `send.` subdomain. SPF passed from an SES address authorized via
`send.vinclarice.com`, under relaxed alignment — the IONOS root record was
never consulted, exactly as the provider decision above predicted. The
`amazonses.com` Message-ID is Resend's infrastructure showing through and
does not affect alignment.

**`SERVER_EMAIL` verified the same evening.** That reset used
`DEFAULT_FROM_EMAIL`; `notices@` is the sender whose failure is silent by
nature, since nobody notices an admin notice that didn't arrive. Rather
than wait for a real lockout to be the test, a `mail_admins()` probe was
run against the container — no junk account, no self-inflicted lockout:

```bash
ssh elspeth@vinclarice.com 'docker exec -i clarice python manage.py shell' <<'EOF'
from django.core.mail import mail_admins
mail_admins("Clarice notices probe", "Checking SERVER_EMAIL authenticates.")
EOF
```

It arrived from `Clarice notices <notices@vinclarice.com>` — and its
subject read `[Django] Clarice notices probe`, which is how the unset
`EMAIL_SUBJECT_PREFIX` was found. Reading a delivered message caught what
the whole test suite had no assertion for.

### The suppression list, and why "fixed" looked broken

`support@vinclarice.com` now receives, and the contact form is verified end
to end against production. Getting there cost an evening to a failure mode
worth naming, because nothing in this repository could have revealed it.

The order of operations was: test the address, watch it bounce because no
IONOS mailbox existed yet, create the mailbox, test again — and get
nothing. The address was valid by then. The mail still never arrived.

**A hard bounce puts the address on Resend's suppression list, and
suppressed sends still look like successes.** SMTP returns 200, Django
records a clean send, the visitor is told "Thanks — your message is on its
way," and the message is discarded inside the provider before it reaches
the receiving server at all. Nothing in Clarice can see this. The Resend
dashboard shows the accepted payload — correct `From`, `To`, `Reply-To`,
subject — which reads as proof of success and is nothing of the kind.

The part that actually misleads: **fixing the root cause does not clear the
suppression.** The entry outlives the condition that created it, so the
repair appears not to have worked, and the next hour goes into forwarders,
spam folders, and SPF alignment on a path that was already correct.

Three things to carry forward:

- **Create the mailbox before sending anything to it.** A bounce is not a
  free test; it has a lasting side effect at the provider.
- **"Accepted by the provider" is a weaker guarantee than it sounds** —
  which matters directly for the acknowledgement-email line below, since
  acceptance is not delivery.
- **This is the argument for B4 stated in miniature.** A silent delivery
  failure that no test, log, or user-visible state can expose is exactly
  what production monitoring is for. Bounce and complaint webhooks from
  Resend belong in that conversation, not in a separate one.

- Decouple SMTP/API credentials from the visible `DEFAULT_FROM_EMAIL` in
  Django settings and deployment configuration.
- Use provider/domain authentication records exactly as issued. Merge any SPF
  include with the existing SPF record rather than creating a second SPF TXT
  record; verify DKIM and DMARC before public use.
- Keep secrets in the deployment environment or protected server files, never
  in the repository or browser bundle.
- Update password reset, daily digest, admin notices, and future contact mail
  to use the appropriate sender/reply path.
- Add tests asserting password-reset mail has the branded From address, while
  internal notifications still target the private admin address.
- Send a real test to an external inbox and inspect the displayed sender plus
  SPF, DKIM, and DMARC results before enabling stranger signups.

### Deferred: tighten DMARC to `p=quarantine`

`_dmarc.vinclarice.com` is `v=DMARC1; p=none;`, which asks receivers to
report on failures and act on none of them. That is the correct setting
while Resend is new and unproven — a stricter policy applied before real
mail has been observed authenticating would send legitimate password resets
to spam, and the failure would be invisible from this end.

It is also a policy that does no work. Publishing DMARC at `p=none`
indefinitely is a common way to have domain authentication in name only.

**Trigger:** several real sends observed passing SPF, DKIM, and DMARC at an
external inbox — Gmail's "Show original" reports all three. Then move to
`p=quarantine`. Do not skip to `p=reject`; quarantine fails a mistake into a
spam folder where it can be found, and reject fails it into silence.

Verify against DNS rather than the Resend dashboard, which reports on the
records it asked for and not on what the zone actually serves.

### Contact page MVP

Add a public `/contact/` page with name, reply email, and message. It sends a
single support message to `support@vinclarice.com`; it is not a ticketing
system, CRM, or chat feature.

- Validate inputs server-side and use the visitor's address only as Reply-To,
  never as the message's From address.
- Apply IP-based rate limiting and a low-friction spam control such as a hidden
  honeypot before making the form public.
- Return a generic success state that does not reveal internal delivery or
  inbox details. Do not promise a support response time until one is real.
- Send an optional acknowledgement only after the support message is accepted
  by the configured mail provider.
- Test valid submission, invalid input, rate limit, honeypot rejection, and
  that a visitor cannot inject email headers through form fields.

**Acceptance criteria:** a stranger can request a password reset or contact
Clarice without seeing a personal email address; support can reply from a
product address; and outbound mail passes domain-authentication checks.

### Deferred: support for people who are already signed in

B3 shipped its acceptance criteria and left an inversion behind. The contact
link lives in the Django shell's nav; users live in the SPA. So a stranger
has a support path and an actual user largely does not — and the person most
likely to have something worth reporting is the one hitting a real bug
mid-task, who has the worst route to reporting it.

The fix is not only a link in `SideNav`. The public form is subtly wrong for
someone with a session:

- **It asks for what the app already knows.** Name and email are clerical
  work it can skip, and an open email field invites an address that is not
  the one on the account — which makes a support thread ambiguous about who
  is writing.
- **The rate limit is keyed wrong.** Per-account is both more meaningful and
  harder to evade than per-IP once there is an identity to key on.
- **The honeypot is pointless** behind a session.

In the product's own terms this is *one* concept with two entry points, not
two concepts. So `/contact/` should adapt rather than fork: on an
authenticated request, drop the name and email fields, take the identity
from the account, and key the limit on the user. Same URL, same mail path,
one branch.

**Do not build the richer version first.** The tempting one has a signed-in
report carry its own context — current route, bundle hash, recent client
errors. That is genuinely more useful and it is **B4's territory**: a user
report and a monitoring event are two halves of one incident, and fixing the
report format before error monitoring exists means guessing at what support
will need. Design the two together or not at all.

**Caveat worth carrying:** signup still has no email verification, so an
account's address is admin-approved but unproven. Acceptable for support
correspondence; check it again before anything more sensitive routes through
that address.

**Cost:** touches the SPA, so it needs a frontend build to regenerate the
bundle — the only reason this is not a five-minute change.

## B4 — add production error monitoring

### Scope

Add a Django error-monitoring integration such as `sentry-sdk` with a
production-only DSN, environment, and release identifier. It must report
unhandled server errors without altering normal request behavior or exposing
secrets to the browser.

### External decision needed

Provision the monitoring project and DSN before implementation. The DSN may
be added to deployment secrets, but never committed to the repository. If it
is not available during Bittern, B4 simply slides to the next release; it
does not hold Android or web usability work.

### Acceptance criteria

- Development and tests do not send events.
- Production initializes the integration only when its DSN is configured.
- A controlled staging/production exception creates one event with the
  release/environment metadata needed to trace it back to a deploy.
- Documentation explains the required secret and how to verify the setup.

## Release gates and verification

### Before merge

- Django tests covering M1/B1/B2, including idempotency and ownership/security
  regressions.
- Android unit and instrumentation tests covering token storage, queue
  persistence, offline retry, and reconnect behavior.
- Frontend tests covering local-state insertion, logout, routing, and
  failure-recovery behavior.
- `pnpm --dir frontend build` to regenerate the production asset bundle.
- Review the generated API schema/types if a new Ninja endpoint changes the
  OpenAPI contract.

### Before deploy

- Apply and verify the M1 idempotency migration before releasing a client that
  depends on it; use the existing Postgres-backed CI path.
- Confirm the production configuration has the monitoring DSN only if B4 is
  included.
- Build the image from the intended commit; retain its identity for the B0
  artifact check.

### Outstanding after the August 1, 2026 deploy

Deployed 11:56 EDT. B0 is closed and verified. Tagging was deliberately held
until B0.1 passed, so the release tags describe a capture service that has
actually been exercised rather than one that merely deployed.

**1. Set `alethaclara` to `Asia/Makassar`. Done — and it has already fired.**
At 23:00 UTC on August 1, which is 07:00 WITA on August 2, their
`last_digest_date` advanced to `2026-08-02` while both `America/New_York`
accounts stayed on `2026-08-01`. One hourly job, three accounts, and only
the one whose local morning it was got picked up. That is the entire point
of the change, observed in production rather than in a test.

What this proves is *selection*, not delivery: the command stamps the date
whether or not the mail leaves, and cron's output goes to root's mail, which
read-only diagnosis cannot reach. Asking the recipient is the only remaining
proof.

**2. B0.1 — the capture smoke test. Closed, all five steps.** See the B0.1
section above for the evidence.

**3. Confirm the New York morning, August 2.** The 07:00–12:00 EDT window.
Both remaining accounts should receive their digest there, hours after the
Makassar one — the same job, two different mornings, which is the behaviour
the whole change exists for. This is the last piece of the time-zone work
still unobserved.

**4. Then tag. Done:** `DEPLOYED-2026-08-01/1156` and `LIVE`, both at
`fed210b` — the tip at deploy time; everything since is documentation. No
`bittern` tag: Stages 1–3 are still ahead.

### After deploy

- Complete a recurring task with recurring, opted-out, and already-archived
  children; confirm the agenda and list both update without refresh.
- Log out from desktop and mobile SPA navigation, then verify protected API
  calls no longer work.
- Hard-refresh `/app/agenda` and verify navigation content and counts.
- On a physical Android device, capture online, queue a capture offline, bring
  the device online, and confirm every capture appears exactly once in Inbox.
- If B4 ships, trigger its controlled verification event and confirm it is
  attributed to Bittern.
- Only then apply the `bittern` release tag and update `LIVE`.

## What happens after Bittern

Keep C2 as an observation task rather than a promised redesign. Capture
specific navigation failures after Stage 2, then decide whether there is a
coherent information-architecture change to make.

The next feature release should choose one substantial product direction —
likely account export or a time-zone decision — rather than combining search,
time blocking, audit history, and deletion into one scope.
