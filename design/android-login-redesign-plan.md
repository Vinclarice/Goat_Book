# The phone connects itself — the login redesign — focused spec

**Vince, September 7, 2026:** *"So I actually want to redesign the security
login for the app… what I want is to avoid having this issue where there is a
need to send a token to the phone."*

That sentence is the whole requirement and it is stricter than it sounds.
**Nothing secret is hand-carried between devices** — not a pasted token, and
not a fallback that quietly reintroduces one. The phone earns its own
credential over its own connection.

This supersedes [`android-login-plan.md`](android-login-plan.md), which shipped
August 6, 2026 and is the thing being redesigned rather than a stale document.

---

## The diagnosis

**Three different failures arrive as the same four words.** All three were met
this week, in one session, on one phone.

| What actually happened | What the phone said |
|---|---|
| Token lacks `day:read` and `agenda:read` | *Reconnect in Settings* |
| Account has a second factor, login refused | *Clarice answered 403* |
| Token past its 90 days | *Reconnect in Settings* — not yet met, but it will be |

**The cause is one thing, and it is not sloppiness.** `GET /api/v1/me` returns
`username` and `email`. That is the entire self-knowledge a connected phone
has. It cannot say what its token may do, when it dies, or which of the three
just happened — so every one of them collapses into the same sentence, and the
sentence names a cure rather than a cause.

**A distinction that got lost, and is the hinge of this whole plan.**
`TokenAuth` returns an undifferentiated 401 for unknown, expired and
wrong-scope, and that is *correct*: a stolen, narrowly-scoped token must not be
handed an oracle telling it which scope to go steal next. But that argument is
about **an attacker holding an unknown token.** A client that has just
presented a **valid** token, asking what that token can do, has already passed
the gate — it is not an oracle, it is a credential describing itself to its
holder. The phone inherited a blindness that was designed for somebody else.

**And the second failure is worse than it looks**, because the cure the message
named was unreachable. An account with a second factor was refused at
`/api/v1/login` and sent to the web to mint a token by hand — which is the act
this redesign exists to delete.

---

## What is being redesigned — two halves, deliberately independent

They ship in either order and neither blocks the other. **Half A is much
smaller and fixes a live defect; it goes first.**

- **A. The token explains itself.** `/me` returns scopes and expiry. Failures
  become legible and the 90-day cliff stops being a surprise.
- **B. The phone is paired, not credentialled.** No password, no code, and no
  token typed into a phone at all.

---

## Half A — the token explains itself

`MeOut` grows two fields:

```
scopes: list[str]
expires_at: datetime | None      # null means never, as it does in the model
```

**Additive and optional-by-construction**, which is `principles.md`'s
*evolve data and APIs without stranding clients*: an older build ignores two
fields it does not read, so this can deploy before any phone wants it.

**What it buys, concretely.** The phone stops guessing. When `/day` answers
401 it already knows whether `day:read` was in the set, so it can say *this
connection cannot read your day* and offer the one action that fixes it —
instead of *Reconnect in Settings*, which is what it said while Settings
reported everything fine. And it can warn at, say, seven days out rather than
dying at ninety with no notice.

**Not an oracle**, per the hinge above: `/me` already requires
`identity:read`, so the answer is only ever given to a holder who has passed
the gate, about the credential they are already holding. Worth a comment at
the endpoint, because it reads like a contradiction of `TokenAuth`'s docstring
and is not one.

**This half alone would have prevented the unexplained 401** that cost a day
and is written up in [`android-overhaul-plan.md`](android-overhaul-plan.md)
increment 5.

---

## Half B — the phone is paired

### The flow

1. **Phone**: *Connect this phone* → `POST /api/v1/pair/start`,
   unauthenticated. Returns a short `user_code`, a long secret `device_code`
   the phone keeps and never shows, and a poll interval.
2. **Phone** displays the `user_code` and where to type it.
3. **Laptop**, in a browser already logged in *and* past the second factor:
   `/pair/`, type the code, read what is being granted, approve.
4. **Phone** has been polling `POST /api/v1/pair/poll` with its `device_code`,
   and now gets a token carrying `ANDROID_DEFAULT_SCOPES`.

### Why this satisfies the requirement

**The only thing crossing between devices is the `user_code`, and it travels
phone → human → web.** It is short-lived, single-use, and grants nothing on
its own — it names a request awaiting approval. The **token** travels over the
phone's own TLS connection, to the device that asked for it, and is never
displayed to anybody.

That is the precise inversion of today: a token is currently minted on the
laptop and carried to the phone. Here a request is made on the phone and
carried, as a meaningless-until-approved code, to the laptop.

### Why the second factor comes free

The approving session is a browser session that has already passed the login
form and the second-factor gate. **No TOTP is ever typed on a phone**, and
`/api/v1/login`'s awkward 403 stops being on the critical path.

Approval must require a *verified* session where the account has a factor —
`request.user.is_verified()`, the same gate `/admin/` uses — or pairing would
become a way around the very door it is standing next to.

### The model, against `architecture-trajectory.md` §4

**Does it earn one?** §4's test is *a different life cycle, not a different
name*. A `PairingRequest` lives about ten minutes, is single-use, dies on
redemption, and — the decisive part — **exists before it has an owner**. A
`PersonalAccessToken` lives ninety days, is reusable, and is owned from its
first instant. Those are not the same life cycle. **It earns a model.**

Rule by rule, and **rule 1 is violated on purpose**:

- **1. Owned at birth — no, and this is the deviation.** A pairing request is
  created by an unauthenticated phone; there is no owner to record until step
  3. `owner` is null until approval and non-null forever after. **Stated here
  rather than discovered later**, because §4 is explicit that this is the rule
  whose absence makes every isolation test weaker than it looks. What contains
  it: the row holds no user data, it is unreadable without the `device_code`,
  and it is hard-deleted on redemption — so the window where an ownerless row
  exists is minutes long and contains nothing.
- **2. Public identifier** — the `device_code` is it. Nothing is created
  offline, so the rule is satisfied rather than waived.
- **3. Snapshot what meaning depends on** — the granted **scopes are copied
  onto the row at approval.** Otherwise a later edit to
  `ANDROID_DEFAULT_SCOPES` would retroactively change what an approved but
  unredeemed request hands out, which is exactly the class of bug rule 3
  exists for.
- **4. Read module and service module** — a service owns *start*, *approve*
  and *redeem*; reads stay separate. Not negotiable here, because all three
  transitions are invariant-bearing.
- **5. Reference, never copy** — the token is a `PersonalAccessToken`; this row
  does not duplicate it.
- **6. Deletion decision** — **hard, on redemption and on expiry**, with a
  sweep for the abandoned ones. No tombstone: nothing offline references a
  pairing request, so §4's second half does not apply. Said out loud because
  §4 says the second half is the one that gets forgotten.
- **7. Index the query the feature runs** — unique on the `device_code` hash,
  and an index on `expires_at` for the sweep.
- **8. Repeating things** — not repeating. N/A.

### The security properties, and where they are load-bearing

- **Both codes are stored hashed**, never raw, exactly as
  `PersonalAccessToken.token_hash` already is. A database readable by an
  attacker must not yield a pending pairing.
- **The `user_code` is short and therefore guessable, and that is the one
  genuinely new risk this plan introduces.** It needs all of: a large
  unambiguous alphabet (no `0`/`O`, no `1`/`I`), a ten-minute TTL, and a
  **failed-attempt limit that destroys the request** rather than merely
  slowing it. Guessing must burn the target, not just cost time.
- **The poll endpoint must not become an oracle** — unknown, expired and
  not-yet-approved get one indistinguishable *pending* answer, so polling
  cannot enumerate live codes.
- **The approval page shows what is being granted**, in the words the token
  form already uses, and the device label. An approval screen that does not
  say what it approves is a click-through.

### The constraint that will bite, found while reading the config

**A polling endpoint collides with the existing rate limits.**
`clarice_api_login` is `5r/m`, and a phone polling every five seconds is
`12r/m`. `test_api_auth_surface.py`'s `UNAUTHENTICATED` set requires every
entry to carry an nginx limit, and `test_unauthenticated_endpoints_are_throttled`
enforces it — so `pair/start` and `pair/poll` each need a deliberate zone, and
**the poll zone must be sized from the poll interval rather than copied from
the login one.** Copying it would produce a pairing flow that rate-limits
itself into failure, and it would look like a server bug.

Both endpoints are new entries in `UNAUTHENTICATED`, which is a list somebody
has to edit on purpose. **The approval step is not on the API at all** — it is
an ordinary session-authenticated Django view, like `/accounts/security/` — so
nothing is added to `TOKEN_AUTHENTICATED`.

---

## Increments

1. ~~**`/me` returns scopes and expiry**, and the phone reads them. Failures
   name their cause; expiry warns ahead. No model, no new endpoint, ships
   alone.~~ **Shipped September 7, 2026**, and the claim held: no model, no new
   endpoint.

   **One refactor was needed and it is worth knowing about.**
   `_resolve_scoped_token` returned the *owner*, so the endpoint that has to
   describe the credential had no way to see it. It now returns the token and
   both callers read `.owner`; `TokenAuth` puts it on `request.access_token`,
   absent on the session path — which is what lets `/me` tell a bearer from a
   cookie without asking how the caller authenticated.

   **Null, not the full list, for a session.** A session is not scoped and does
   not expire the way a token does. Returning every scope would read as *this
   credential holds everything* to a client that cannot tell the two apart.

   **The phone keeps `Identity` and gains `TokenCapabilities`** rather than
   growing the first. They answer different questions and only one arrives
   everywhere: `/login` reports an identity and no scopes, so folding the
   fields together would have forced that path to invent them. Absent
   capabilities are `null` — *not known*, never *holds nothing*, a distinction
   a screen reading the second from the first would use to tell somebody their
   working connection can do nothing.

   **The judgement is in `connectionWarning`, outside Compose on purpose.**
   This module has no UI tests, so anything decided inside a `@Composable` is
   checked by compiling and nothing more; the function is pure, takes its
   clock as an argument, and has ten tests. Settings draws what it returns.
   Silent on a healthy connection — a warning that shows when nothing is wrong
   is wallpaper within a week, so a ninety-day token says nothing for
   eighty-three of them.

   **Two things this increment proved rather than assumed.** The contract guard
   from `ca41c25` caught the schema change on the very next commit, one day
   after being written, and its message named the fix. And a focused green run
   sat beside a red full one: `test_me_token_auth` passed while
   `test_api_v1.py` asserted the same contract in another file, which is the
   exact case `principles.md` describes and the reason the whole app list is
   the gate rather than the touched app.

   **What is not done here**: the Day and Pool screens still say *Reconnect in
   Settings* rather than naming the missing scope themselves. Settings is where
   that sentence sends somebody and where the cure is, so it is the surface
   that earns the diagnosis first; plumbing capabilities into those two view
   models is worth doing when something else needs them.
2. ~~**`PairingRequest`** — model, migration, service, and the two API
   endpoints, with their nginx zones and their `UNAUTHENTICATED` entries.~~
   **Shipped September 7, 2026.**

   **Three guards fired on this increment and each one was right**, which is
   the part worth recording. `test_api_auth_surface` refused two new `auth=None`
   operations until they were listed on purpose; `test_unauthenticated_endpoints_are_throttled`
   refused them until the nginx template had real limits;
   `test_dark_services_declare_their_deferral` found `approve` and `sweep` had
   no callers within minutes of their being written. None of that was caught by
   remembering.

   **The poll rate is derived, and copying the login zone would have been the
   bug the plan predicted.** `clarice_pair_poll` is 30r/m against a phone that
   asks 12r/m for ten minutes; `clarice_api_login`'s 5r/m would have throttled
   every pairing into failure partway through, and presented as a broken
   server rather than as a limit.

   **Two corrections to this plan, made on contact:**

   - ~~a failed-attempt limit that destroys the request~~ — **written and then
     refused.** It defends nothing: the only caller who can attempt an approval
     has already authenticated as the owner, so an attempt limit rations a
     person against their own typing. The threat model that survives is in
     `test_pairing.py`'s docstring — a mistype landing on somebody else's live
     request, which is what the code space is sized against.
   - **A sweeper was written and deleted the same hour**, by the dark-services
     guard. Expired rows are already inert because every query filters on
     `expires_at`, so a cron would be more machinery than the rows it removes.
     Refused in `pairing.py` with what would change the answer.

   **`approve` is deliberately dark** and declared as such with increment 3 as
   its named trigger. Splitting the grant away from the model and the endpoints
   would have meant an approval path with no request to approve.

   `PairingRequest` also had to be named in the account export — a new
   owner-scoped model is, and `test_export` said so. Both hashes are in
   `SECRETS`, so what leaves is a label and two timestamps.
3. ~~**The approval page** at `/pair/`, session-authenticated and verified.~~
   **Shipped September 7, 2026**, and `approve` came alive the same day its
   deferral was declared.

   **At the root rather than under `/accounts/`, and the short path is the
   feature.** This URL is read off a phone screen and typed into a laptop by
   hand — the one thing the whole flow asks of a person. Its sibling
   account-security pages are all arrived at by clicking, so none of them pays
   that cost.

   **The page's job is its wording, not its form.** By the time a code reaches
   the box, the only attack this flow has — *"type this code into your
   Clarice"* — has already succeeded or not. So the page names the phone, lists
   what it will be able to do in `TokenForm.SCOPE_CHOICES`'s own words, says it
   lasts ninety days, links to where to revoke it, and says outright not to
   type a code somebody sent you.

   **One vocabulary, not two.** The scope labels are read from the token form
   rather than restated, which is `principles.md`'s *one rule, one
   authoritative definition* — and reading the rendered page is what found the
   consequence: `day:write`'s label still describes *Intentions, Grateful for
   and Happenings*, which the Day page dropped on September 4. Amplified rather
   than introduced by this increment, and left alone because the fate of those
   columns is `superlists-2.0-plan.md`'s deferred A3. **Noted here so the next
   person to open that question knows a second surface now shows the old
   words.**

   **`has_a_second_factor` moved from `accounts/api_v1.py` to
   `accounts/mfa.py`** so both doors read one definition. Two doors disagreeing
   about what *has a second factor* means is one of them becoming a way around
   the other.

   **Verified in a real browser as well as in tests**, which was worth doing
   for exactly one reason: logged in as an account *with* a factor, `/pair/`
   redirected to *Confirm it's you*. The gate is the property that stops
   pairing being a way around the door it stands beside, and it was watched
   working rather than only asserted.

   **The tests were written first but their red was never watched**, so the
   security-critical one was checked by mutation instead: removing the
   `is_verified()` gate turns
   `test_an_account_with_a_second_factor_must_have_proved_it` red. Recorded
   because "written first" and "seen to fail" are different claims.
4. ~~**The phone's pairing screen.** Token paste is demoted below it.~~
   **Shipped September 7, 2026, and this is the increment that delivers the
   requirement.** Nothing secret is carried to the phone any more: it asks,
   shows a code somebody carries the *other* way, and the token arrives over
   its own connection.

   **Pairing is first on the Connect screen, not merely present.** Everything
   below it is a way of getting a credential onto the phone by carrying one;
   this is the way that is not, and the order is the recommendation.

   **The poll interval is read from the server, never chosen here.** A client
   with its own idea of it would be a second copy of a rate limit, and would
   throttle itself out of its own pairing — the same shape as D8's mirrored
   constant. The loop is bounded by the server's own `expires_at` for the same
   reason: a lifetime constant on the phone would be a second place deciding
   how long a pairing lives.

   **A network blip does not abandon a pairing.** The code on screen is still
   good and somebody may be walking to a laptop with it. What stops it running
   forever is the budget, not the first failure.

   **`startPairing` and `pollPairing` were added to `ClariceApi` without
   default implementations**, which forced all five test fakes to acknowledge
   them. That is this codebase's habit — `TOKEN_AUTHENTICATED`, `EXPORT_KEYS`,
   `ELSEWHERE` — and it means a second real client forgetting a transition is a
   compile error rather than a quiet failure.

   **Two things reading the code back caught that the tests did not.** The
   screen first built its address from the server's display *name*,
   rendering `clarice.com/pair` — a domain this project does not own, in large
   type, as an instruction. `pairingAddress` derives it from the base URL the
   app actually talks to, so a debug build pointed at staging says staging.
   And two tests observed the pairing state *after* `beginPairing` returned,
   by which point the code is correctly cleared; they now watch while it waits.

   **Not verified on a device.** This module has no UI tests, so the screen
   compiles and nothing more. The first real pairing is the acceptance.
5. **Decide what happens to the credential path** — see P1. Deliberately last,
   and deliberately a decision rather than a step.

---

## What this refuses

- **A QR code, for now.** It needs a `CAMERA` permission the manifest does not
  have, for a flow that already works with eight typed characters. Revisit if
  the typing is the part that annoys.
- **A sliding expiry that never ends.** The ninety-day bound is what makes a
  lost phone a bounded exposure; renewing it silently on use would delete that
  property to save a two-minute re-pair. See P2.
- **Pairing as a way around the second factor.** Approval requires a verified
  session. A pairing flow that accepted an unverified one would be a bypass
  wearing a redesign's clothes.
- **Deleting the offline queue's guarantees.** Nothing here touches
  `CaptureWorker`, the encrypted queue or the share target.

---

## Decisions

- ~~**P1. Does `/api/v1/login` survive?** Pairing makes it unnecessary for the
  common case, but it is the only path when the laptop is not to hand.~~
  **Answered September 7, 2026: it survives.** Vince: *"keep the login path."*

  **So pairing is the way in, and credentials are the way in when the laptop
  is not.** That makes them siblings rather than a path and its replacement,
  and it has one consequence worth stating now: **the credential path has to
  stay good, not merely present.** A fallback nobody maintains is the thing
  that fails on the day it is finally needed — which is precisely the phone
  whose owner is standing somewhere without the laptop.

  **It also settles the second-factor work**, which was built and green and
  waiting on this answer: it lands. Without it that fallback is unusable on
  exactly the accounts that have a second factor, which is the account this is
  being built for.

  **What it does not license** is treating pairing as optional. Half B is still
  the primary path, and the refusal below about the second factor still holds
  on both.
- **P2. What happens at ninety days?** Warn and re-pair, or extend on use. The
  refusal above leans to the first; the second is a real option if re-pairing
  turns out to be annoying in practice rather than in theory.
- **P3. Does the phone show which scopes it holds, or only act on them?**
  Half A makes the data available either way. Showing a list in Settings is
  cheap and may be noise.

---

## Acceptance

**Scored by using it**, with the same warning Money and Superlists 2.0 carry —
the first verdict on Money read *works* and became *not yet* after one real
walkthrough.

- **A phone gets connected with nothing copied from the laptop**, and nothing
  secret typed into the phone. That is the requirement, stated as a test.
- **A failure says which failure it is.** Scope, expiry and revocation are
  three sentences, not one.
- **Reconnecting is something done from the phone**, at the moment the phone
  is the thing complaining.

---

## Where the facts live

- [`architecture-trajectory.md`](architecture-trajectory.md) §4 — the charter
  `PairingRequest` is argued against above, including the rule it breaks.
- [`principles.md`](principles.md) — *evolve data and APIs without stranding
  clients* for Half A; *guards fail closed* for the poll endpoint.
- `src/clarice/tests/test_api_auth_surface.py` — what a token reaches and what
  needs no account at all. **The authority, not this file.**
- `infra/templates/nginx-clarice.conf.j2` — the rate-limit zones, and the one
  that must not be copied.
- [`android-overhaul-plan.md`](android-overhaul-plan.md) — the overhaul this
  sits inside, and increment 5's write-up of the 401 that Half A prevents.
- [`android-login-plan.md`](android-login-plan.md) — what is being replaced.
