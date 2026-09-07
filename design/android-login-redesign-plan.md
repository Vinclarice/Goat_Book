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

1. **`/me` returns scopes and expiry**, and the phone reads them. Failures name
   their cause; expiry warns ahead. No model, no new endpoint, ships alone.
2. **`PairingRequest`** — model, migration, service, and the two API endpoints,
   with their nginx zones and their `UNAUTHENTICATED` entries.
3. **The approval page** at `/pair/`, session-authenticated and verified.
4. **The phone's pairing screen.** Token paste is demoted below it.
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

- **P1. Does `/api/v1/login` survive?** Pairing makes it unnecessary for the
  common case, but it is the only path when the laptop is not to hand.
  **Bearing on the uncommitted second-factor work**: that work is built, green,
  and makes the credential path usable for a second-factor account. If P1 keeps
  the path, it should land. If P1 removes it, it should not. **This is the
  decision that says whether that diff is finished or wasted**, and it should
  be taken before it is committed.
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
