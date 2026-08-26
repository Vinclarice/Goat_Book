# Security, resilience and reliability — what is unnamed, and what has ripened

Vince · plan · written August 19, 2026 · **not started**

## What this is

A pass over the security, resilience and reliability surface, sorted into three
piles rather than presented as a checklist. The posture is strong and most of
what a generic review would raise here is already decided — and decided better
than the generic answer. So the useful work is:

1. **What nobody has named.** Absent controls, not deferred ones.
2. **What was named, and whose trigger has since fired.**
3. **What is correctly settled**, recorded so it is not re-proposed. This
   project has watched an unrecorded refusal come back three times in one week.

Deferral decisions and their triggers are owned by
[`architecture-trajectory.md`](architecture-trajectory.md) §6 and §7; what is
open is owned by [`roadmap.md`](roadmap.md); the restore procedure is owned by
[`MIGRATION.md`](../MIGRATION.md). This plan links to them rather than
restating them, and **is not claimed by `roadmap.md`** until work starts.

## The posture as found

Stated first because the items below are corrections to something good, and a
plan that opens with gaps misrepresents what it is amending. Verified by
reading the source, not inferred from the documents:

- A content security policy with a per-request nonce, the one deliberate inline
  script named specifically rather than `'unsafe-inline'` on `script-src`.
- Sentry scrubbed on four independent axes — `send_default_pii`,
  `include_local_variables`, `max_request_body_size`, and a `before_send` hook
  for the query string that no option covers — each carrying the reasoning for
  why the option above it does *not* cover the next.
- `mind.ActivityEvent` append-only by database trigger, with exactly one
  exemption, one caller, and a test that fails on purpose if it is widened.
- `clarice/tests/test_api_auth_surface.py` pinning which operations accept a
  bearer token, so widening what a 90-day Keystore token reaches takes a
  deliberate edit.
- Health checks that fail closed, say almost nothing, and cannot 500 while
  reporting health. Two of them, deliberately separate, so a late cron job does
  not report the website as down.
- `check-backup-freshness.sh` scheduled in its own workflow, off the droplet,
  because the credential belongs somewhere a host compromise does not reach.
  **Scheduled is not the same as running, and this list said it was.** Its
  first firing — 09:47 UTC on August 19, the morning after it was added —
  failed in ten seconds: `DIGITALOCEAN_ACCESS_TOKEN is not set on this
  repository`. The guard did precisely its job, refusing loudly with the fix in
  the message rather than reporting a missing cluster, and the notification
  went out. **So the backup check has never successfully run**, and backups are
  unverified by any means since the August 1 drill — which raises 2.1 from
  important to the only thing that would tell you anything. One repository
  secret closes it, and it is Vince's to create.

## Who this is defended against

Added August 19 after the question *"what about security against hackers?"* —
which reorders the piles below, because the reliability lens and the adversary
lens do not rank the same items.

Ranked by likelihood times consequence, not by severity score:

1. **Someone who *has* the admin password** — phishing, reuse against a
   breached site, an infostealer on the laptop. The admin reads every user's
   data. See 1.5: this is the highest-consequence path and the least defended.
2. **Opportunistic scanning.** Ambient and constant, and **the blocking side is
   answered more thoroughly than a first read suggests.** Two default-server
   blocks mean a scan by IP address never reaches a request line: port 80
   returns `444`, closing the connection with no response, and port 443 sets
   `ssl_reject_handshake`, refusing the handshake without presenting a
   certificate. `ALLOWED_HOSTS` kills a wrong `Host` a second time. Since most
   opportunistic traffic is addressed to an address rather than a name, most of
   it dies before Django exists to it. The residual is 1.4, and — far more
   interesting — 1.7.
3. **A dependency advisory nobody hears about** (1.1). Under this lens it
   outranks most of pile 2 — an auth bypass in a framework, unheard, is exactly
   how this goes wrong quietly.
4. **A leaked Android bearer.** Ninety days in a Keystore, and **the blast
   radius is genuinely bounded**: the scope is `capture:write`, so it writes
   captures and cannot read tasks. That containment is load-bearing and should
   not be widened casually. Unthrottled, though — 2.3.
5. **XSS to session theft.** Near-zero surface today, and 1.2's report-only
   policy blocks nothing if that changes.

**What the adversary lens found already strong**, recorded so effort is not
spent here: no `FileField`, `ImageField` or `MEDIA_ROOT` anywhere — `Attachment`
is metadata and object-storage keys, so a whole class of attack is absent. No
`dangerouslySetInnerHTML` in the SPA, and the single `mark_safe`
(`frontend_tags.py:141`) interpolates a three-value allowlist and a generated
nonce. Container non-root at uid 1234, bound to `127.0.0.1:8000` only. Secrets
at `0600` under `umask 077`. The database credential is scoped to one database
on the cluster and was cut over in production July 31, not merely scripted.
`PersonalAccessToken.generate` defaults `scopes` to nothing, so a forgetful
call site produces a powerless token rather than an omnipotent one. Export and
deletion are `/me/`-scoped, so there is no identifier to tamper with.

**Isolation testing is broader than its dedicated file suggests** — 49 files in
`mind` construct a second user, 17 in `lists`. `review` is the only app with
none. That is defensible rather than a hole: a review is addressed by date with
the owner taken from the session, stated at `review/api_v1.py:402`. It is the
one place the argument is a comment rather than a test, and worth one test that
two users asking for the same date get their own.

**Not visible from this repository:** the playbook manages no `ufw`, no
firewall rules and no SSH configuration. That may be a DigitalOcean cloud
firewall set out of band, which is fine — but it is not in code, so it is
neither reviewable nor reproducible, and a rebuild would not restore it.
**Open question for Vince**, not an assertion of a gap.

## Pile 1 — nobody has named these

### ~~1.1 Nothing tells you when a pin becomes an advisory~~ — closed August 26, 2026

`.github/workflows/dependency-advisories.yml`, scheduled daily, failing into the
same mailbox `backup-freshness.yml` reaches. **Proved both directions before it
was trusted** — a seeded `django==3.2.0` gives 37 advisories and exit 1, a clean
`six==1.17.0` gives exit 0.

**It found something on the first look, which is this item's own prediction:**
27 advisories over 16 packages, including **Django 5.2.16 — PYSEC-2026-3717,
CVSS 6.9, fixed in 5.2.17**, the framework serving production. The instrument
shipped; **the bump has not, and is Vince's next call.**

**Two of the three sets, not three.** Android is a declared gap: `osv-scanner`
reads `gradle.lockfile` and this build has none, declaring dependencies in a
version catalog no scanner parses. The trigger to close it is recorded in the
workflow.

~~Original text follows.~~

`requirements.txt` pins every version exactly, which is right. `.github/`
contains `ci.yml` and `backup-freshness.yml` and nothing else: no Dependabot
configuration, no `pip-audit`, no `pnpm audit`, no advisory feed. Exact pinning
without an advisory mechanism means the pins age silently and the notification
path is somebody else telling you.

**This is the only genuinely absent control in this document.** Everything else
below is a decided thing that has drifted, or a deferred thing whose trigger
fired.

*Acceptance:* a scheduled job that fails on a known advisory in any of the
three dependency sets — Python, pnpm, Gradle — and reaches the same inbox
`backup-freshness.yml` already reaches. It is proved against a seeded
known-vulnerable pin before it is trusted, the same way the login throttle was
proved by running nginx rather than by reading the template.

### ~~1.2 The CSP's promotion condition has no observer~~ — closed August 26, 2026

Promoted to enforcing on evidence already held, which is the second of the two
ways out below. `functional_tests.ContentSecurityPolicyTest` loads both shells in
real Chromium every CI run; the browser suite passed against a freshly built
bundle. The *must not appear yet* assertion inverted in the same commit.

~~Original text follows.~~

`clarice/middleware.py` ships `Content-Security-Policy-Report-Only`, and both
it and `architecture-trajectory.md` §6 say enforcement follows "once real use
has stayed quiet." There is no `report-uri` and no `report-to` in
`CSP_DIRECTIVES`. Violations therefore land in the console of whoever has
devtools open, which is nobody, so the condition cannot be observed to have
been met and never will be.

**A report-only policy with no collector is a seam that is not switched on** —
the third instance of that pattern in a week, and the first where the thing not
switched on is an *observation* rather than a feature.

Two honest ways out, and the second is probably right:

- Add a collector. Real, and it is a new endpoint to build, rate-limit and then
  ignore.
- **Promote to enforcing on the evidence already held.**
  `ContentSecurityPolicyTest` loads both shells in real Chromium and asserts
  nothing was reported, and separately that the theme script actually ran —
  which is a stronger signal than a quiet console, because it is checked every
  CI run rather than whenever somebody happens to look.

*Acceptance:* one header name changes, the "must not appear yet" assertion in
`test_content_security_policy.py` inverts in the same commit, and the browser
suite passes against a freshly built bundle.

### 1.3 Nothing gates the deploy on the ref

The playbook records what it built — `git describe --always --dirty` feeds both
the image tag and `DJANGO_RELEASE` — which is good forensics and not a control.
Nothing refuses.

The consequence changed on August 19. `LIVE` is `dec80c4` on
`navigation-and-identity`; `main` does not contain the privacy policy or the
terms. Checking out `main` and running the playbook would take two **published
legal documents** off a live site, and the first trace would be a release tag
read afterwards.

*Acceptance:* a pre-flight task stating the branch, the describe string and
whether the tree is dirty, requiring confirmation when the tree is dirty or the
ref is not an ancestor of what is currently `LIVE`. It must be overridable —
this is a speed bump, not a lock, and the playbook builds from the working tree
on purpose.

### ~~1.4 `/admin/` has no rate limit~~ — closed August 26, 2026

`location ^~ /admin/`, 120r/m with `burst=60`, deliberately generous: the
residual is enumeration and volume, and a limit that made the admin unusable
would be the worse bug. Rode along with 2.3 exactly as this item asks.

~~Original text follows.~~

It falls through to nginx's catch-all. django-axes covers credential stuffing
by username, so the residual is thin: enumeration and blunt request volume.
Listed for completeness, and to ride along with 2.3 rather than as its own
piece of work.

### 1.5 There is no second factor on the account that can read everything

**The single highest-value item in this document under the adversary lens.**

`otp`, `two-factor`, `2fa`, `totp`, `mfa`, `webauthn` and `passkey` appear
nowhere in `src/`, in either requirements file, or in `design/`. A superuser
session reaches every user's tasks, journal entries and notes through
`/admin/`.

**django-axes does not cover this, and the distinction is the whole point.**
Five attempts an hour by username defends against *guessing*. Guessing is not
how passwords are lost — phishing, reuse against a breached site, and
infostealer malware are, and against all three axes does exactly nothing
because the attempt succeeds first time. Every other control in this
application is aimed at a stranger at the front door; this is the path that
arrives with a key.

Proportionate scope, in order:

- **The admin and staff accounts first.** They are the ones with reach beyond
  their own data, and there are very few of them.
- **Ordinary accounts second, and optional**, when there are enough users for
  it to matter. Forcing a second factor on an invitation-only site of three
  people buys little and costs a recovery path that has to be designed.

*Acceptance:* a superuser cannot reach `/admin/` with a password alone, proved
by a test that authenticates correctly and is still refused. Recovery codes
exist and are generated once — **which makes this the one item here that
creates a new way to lock yourself out**, so the drill for using a recovery
code is written down before it ships, not after.

**Specced August 19 in [`admin-mfa-plan.md`](admin-mfa-plan.md)**, which owns
the design and is not summarised here. One finding from it belongs in this
document's threat model rather than that one: **`POST /api/v1/login` trades a
password for a 90-day token and starts no session**, so every session-based
gate misses it. A second factor on the web form alone would not be one. The
scopes contain the damage — that token reaches the holder's own day, agenda and
captures, never `/admin/` — but the bypass is real and the spec closes it in
the same deploy as the enforcement.

### ~~1.6 HSTS is one hour~~ — closed August 26, 2026

A year, with `SECURE_HSTS_INCLUDE_SUBDOMAINS`. Preload deliberately absent and
**asserted absent**, so turning it on has to be argued — it stays D4. The habit
this item names is now held by a test rather than by memory.

~~Original text follows.~~

`settings.py` sets `SECURE_HSTS_SECONDS = 3600` under a comment saying to start
small and raise it "only once HTTPS is confirmed working end-to-end, per
Django's own warning." HTTPS has been confirmed end to end for weeks; certbot
renews automatically and the playbook exercises it.

At one hour the header is close to decorative: a person returning the next day
has no protection against a downgrade at all, which is the attack it exists
for.

**This is 1.2's pattern a second time** — a deliberately conservative starting
value, a stated promotion condition, the condition met, and nobody firing it.
Two instances is a habit, and the habit is worth naming more than either
instance: **a conservative default with a condition attached needs somebody
holding the condition, or it becomes permanent by inattention.**

*Acceptance:* a year, with `SECURE_HSTS_INCLUDE_SUBDOMAINS`. Preload is a
separate decision and a genuinely hard-to-reverse one — it belongs to D4 below
rather than riding along with this.

### 1.7 The rate limits fire into a file nobody reads

**Found August 19 while checking 1.4, and it is the larger half of that
item.** `limit_req_status 429` is configured across five zones. If somebody
were grinding the login form right now, nginx would answer with 429s written to
`/var/log/nginx/access.log` on the droplet, and nothing reads that file.

Sentry sees application *exceptions*. A 404 is not an exception and a 429 never
reaches Django at all, so **neither scanning nor throttling is visible from any
surface anybody looks at.** The limiter could have fired once or ten thousand
times since it shipped and there is no way to tell which.

**The same shape as 1.2 and 1.6 a third time**: a mechanism correctly in place,
with nobody holding the other end. Three instances now, in three different
parts of the system, which makes it the pattern this document is most useful
for having found. **The recurring defect is not any of the individual gaps — it
is shipping the mechanism and not the observation.**

**The constraint that makes this more than "add log aggregation."** The
`clarice_no_query` log format exists because `/mind/share/?text=` and
`/mind/search/?q=` put somebody's own words in the URL, and the distro default
was writing every one of them to a plaintext disk log on every request, not on
error. That was closed deliberately. **Anything that ships logs elsewhere must
inherit that discipline or it re-opens the hole somewhere newer and harder to
see** — a third party's log store is a worse place for a search query than the
droplet's own disk was.

*Acceptance:* status codes, paths and counts leave the box; **queries never
do**, held by a test over the shipped format the way
`test_unauthenticated_endpoints_are_throttled.py` holds the template. The
minimum honest version is a scheduled job that counts 4xx and 429 by path and
reports a total — enough to answer "is anything happening", which is currently
unanswerable. Alerting on a threshold is a second step and needs a baseline
this does not yet have.

### ~~1.8 `server_tokens` is unset~~ — closed August 26, 2026

`server_tokens off;` at the top level, so both server blocks inherit it — the
port-80 block only redirects but it answers strangers too.

~~Original text follows.~~

nginx therefore emits its version in the `Server` header and on its own error
pages, which is what a scanner fingerprints on to pick an exploit. One line,
and it rides along with 1.4.

**Moving `/admin/` off the default path is refused**, and recorded here so it
is not proposed again: it is obscurity rather than a control, its marginal
value against axes and 1.5 is near zero, and it disturbs the
`admin_password_reset` ordering that `clarice/urls.py` carries a load-bearing
comment about. The log noise it would save only matters once something reads
the logs, which is 1.7.

## Where to spend first

**Five of these seven closed between August 23 and 26, 2026** — MFA as
`petrel`, then advisories, HSTS, the enforcing CSP and the nginx trio. What is
left is 2 (Vince's), 6 and 7, and the order below is kept unstruck because the
*reasoning* is what dates well; only the items do not.

**One of them got more urgent by being worked around.** 1.7 — the rate limits
firing into a file nobody reads — now has two more limits firing into it, since
2.3 and 1.4 added `/api/v1/capture` and `/admin/`. Four rate limits and no
reader is a worse ratio than two, and the item's own argument said it is worth
more once there is more to watch. There is more to watch.

The piles are a taxonomy, not an order. Under both lenses together:

1. ~~**1.5, MFA on the admin.**~~ **Shipped August 23, 2026 as `petrel`.** Highest consequence, least defended, and nothing
   else in this document changes that ratio.
2. **2.1, the restore drill.** Confirmed in scope, and it is the whole database
   recovery path.
3. ~~**1.1, dependency advisories.** Cheap, and the only absent control.~~ **Done August 26, 2026, and it found Django 5.2.16 carrying an advisory.**
4. ~~**1.6 and 1.2, HSTS and enforcing CSP.**~~ **Both done August 26, 2026.** Both are a line each, both have
   their promotion condition already met, and 1.2 is safest to do *now*
   precisely because the application currently has nothing for it to break.
5. ~~**2.3, 1.4 and 1.8**, the two rate limits and `server_tokens`, together —~~ **Done August 26, 2026, and they were one change exactly as this line said.**
   they are all one nginx template and should be one change.
6. **1.7, seeing that any of it fires.** Deliberately below the controls rather
   than above them: it is worth more once there is more to watch, and its
   minimum honest version answers "is anything happening at all", which nothing
   answers today.
7. **2.2**, processor erasure, gated on D1.

**One caveat on that order.** 1.7 is last on effort-per-unit-risk and would be
first if the question were *how would we find out*. Three of the eight items in
pile 1 are the same defect — a mechanism shipped without the observation that
tells you it is working — so the ordering above treats the instances and 1.7
treats the cause. If a fourth instance turns up, reorder rather than adding it
to the list.

## Pile 2 — named, and the trigger has fired

### 2.1 The restore drill is stale, and it is the rollback path

**The top item, and confirmed in scope — Vince, August 19, 2026.**

The August 1 pass compared row counts and `django_migrations` across 18 tables
at 53 migrations. There are 75 now, and the database has since gained the
`vector` extension, `ActivityEvent`'s append-only triggers, the depth-one
triggers and `mention_unique`'s `NULLS NOT DISTINCT`.
[`MIGRATION.md`](../MIGRATION.md) states the consequence itself: a restore
missing all of that passes the drill exactly as written and fails on the first
write.

**This matters more here than it would elsewhere, because rollback is
code-only.** `CLAUDE.md` calls that the whole caveat — a bad migration is
undone by this drill or not at all. The drill *is* the database recovery path,
and it has not been exercised since the schema doubled. Retention is
DigitalOcean's seven days, so the drill is also the only thing that establishes
what that week is actually worth.

Three corrections before it is run:

- **`MIGRATION.md`'s own next-run instruction is satisfied and superseded.** It
  says to add extension and trigger checks to step 4. Step 5 was added
  afterwards and does both *behaviourally* — attempting the forbidden `UPDATE`
  and requiring refusal, rather than asserting a row in `pg_trigger` that a
  disabled trigger would satisfy equally well. Delete the instruction rather
  than following it twice.
- **`check-restore-integrity.sh` checks the knowledge core and not the task
  core.** It covers the `vector` extension, three `mind` triggers,
  `mention_unique` and its `NULLS NOT DISTINCT`. It does not check
  `unique_active_item`, `unique_active_arealess_item`,
  `valid_item_status_timestamps`, `unique_open_checklist_step_text` or
  `valid_project_completion`. A restore that lost every task-core constraint
  prints *"All checked guarantees are intact."* That is `health.py`'s own
  objection turned back on this script: **a check narrower than the failures it
  watches for reports healthy through the ones it forgot.**
- **Step 4 is still a manual comparison**, and it is roughly thirty tables now
  rather than eighteen. Step 1 prints counts and step 4 says "compare"; a human
  diffing thirty pairs at the end of a paid cluster-hour is the weakest link in
  a procedure whose other steps are scripted.

*Acceptance:* the script gains the task-core constraints under the same
behaviour-over-presence discipline — a partial unique constraint proved by
attempting the duplicate insert and requiring refusal inside a rolled-back
transaction, not by a `pg_constraint` count. Step 4 becomes a script that diffs
step 1's output. Then the drill runs end to end against a scratch cluster, and
the result — pass or fail — replaces the August 1 record in `MIGRATION.md`
rather than sitting beside it, carrying the migration count and engine version
it was run at.

**Editing `check-restore-integrity.sh` needs care.** It is parsed by a shell,
and `CLAUDE.md` records that this exact file has already been silently broken
once by CRLF line endings that `git status` hid. Write it with LF explicitly
and confirm before trusting it.

### 2.2 Erasure at Sentry and Resend is now a published promise

Open in [`roadmap.md`](roadmap.md) as an account-level chore in two consoles.
As of August 19 there is a live document at `/privacy/` making claims about
deletion, held by tests wherever a claim has a mechanical counterpart. **The
two processors are the part with no counterpart**, and its priority changed the
day the policy shipped rather than because anything about the work changed.

*Acceptance:* named in `accounts.services.purge_account`'s documentation as the
steps a purge does not perform, with the argument for why they are manual, so
the gap is visible at the function rather than only in a roadmap. Whether it
becomes automated is D1 below.

### ~~2.3 `/api/v1/capture` is unthrottled~~ — closed August 26, 2026

`rate=30r/m`, `burst=60 nodelay`, `limit_req_status 429`. **The rate is argued
from `QueueDrainer.drain()`** rather than chosen round, as this item asks: the
drain is serial with no gap, so burst is what covers a backlog. **Proved by
running nginx** — 100 rapid requests, 61 passed, 39 refused 429.

**The first proof was wrong in the flattering direction** and is worth keeping:
the stub used `return 200`, which is a rewrite-phase directive and
short-circuits before `limit_req` runs at preaccess, so every request passed and
the limiter read as working *and* generous. A harness that never reaches the
thing it tests reports success.

~~Original text follows.~~

It falls through nginx's catch-all. Authenticated by token or session, so not a
stranger's endpoint — and the realistic failure is not an attacker. The bearer
lives ninety days in an Android Keystore and the offline queue on the other end
is *designed* to retry; a retry loop or a leaked token writes unbounded `Node`
rows against a droplet with one core and 458MB.

`architecture-trajectory.md` §6 defers broad API rate limiting until `/api/v1/`
serves someone untrusted, and adds that an individual route can meet the
trigger alone. **This one has**, by a different argument than that section
anticipated.

*Acceptance:* an exact-match `limit_req` block, its rate chosen against what
the Android queue actually does when it drains a backlog rather than against a
round number, and a case added to
`test_unauthenticated_endpoints_are_throttled.py` — or to an authenticated
sibling, if that test's premise does not stretch that far. Proved by running
nginx against the rendered template, the way `9eb9eea` was.

## Pile 3 — correctly settled, recorded so it is not re-proposed

Each was examined in this pass and left alone. The reason matters more than the
verdict:

- **axes locks by username alone.** Documented at the setting, with `axes.W006`
  silenced and its reasoning kept: nginx covers the by-IP case, and pairing
  them would let one attacker dodge lockout by rotating addresses. The residual
  — a stranger who knows a username can lock it for an hour — is bounded by
  `AXES_RESET_ON_SUCCESS` and by there being three users.
- **`style-src` keeps `'unsafe-inline'`.** Stated trade: React writes style
  *attributes*, which a nonce cannot cover, so removing it is a refactor
  against a far narrower class of attack than script injection.
- **SSL expiry alerting is refused.** UptimeRobot paywalls it, certbot renews
  automatically. Recorded in `CLAUDE.md` so nobody reaches the same paywall a
  second time.
- **Row-level security and connection pooling**, refused in
  `architecture-trajectory.md` §7 with triggers named — sharing or paying
  tenants, and an observed connection ceiling.
- **Staging**, designed and deferred. A spending decision, and it gates the
  async queue and Terraform items in §6 rather than anything here. **Nothing in
  this plan waits on it**, which is worth saying explicitly: the restore drill
  rehearses against a scratch cluster and needs no staging environment, so §6's
  ordering of long-retention backups *behind* staging looks inherited from the
  list's shape rather than from a real constraint.

## Not production, but it costs evidence

**Two sessions cannot run the test suites at the same time.** Both runners
build a database named `test_clarice` on `localhost:5433`, so a run in a
worktree and a run in the main checkout destroy each other's test database.
Observed August 19: a run died in `setup_databases` with
`column "owner_id" of relation "lists_list" already exists`, which reads as a
migration bug and is not one.

It belongs in a reliability plan because of what it costs. The failure is
indistinguishable from a real schema fault, and the temptation under it is to
believe the suite rather than re-run it. `principles.md` asks that a red test be
diagnosed before either side is edited; this manufactures reds that have no side
to diagnose.

*Acceptance:* the test database name carries something per-checkout, so two
runs coexist. Cheap, and it should not wait for anything above it.

## What this plan refuses

- **A generic hardening checklist.** Every item here either has no owner or has
  a trigger that fired. Items whose trigger has not fired stay in §6.
- **Re-litigating pile 3.** An entry there is closed until its stated trigger
  fires, and the trigger is the thing to argue with, not the verdict.
- **Treating the restore drill as done because a script exists.**
  ~~It has never been run against a restore.~~ **It was run on August 19, 2026
  — the first pass entitled to the word** — with an empty step-4 diff across 42
  tables and thirteen behavioural checks at step 5; the checks were audited and
  repaired on August 21 without provisioning a cluster. [`MIGRATION.md`](../MIGRATION.md)
  owns that record. The refusal still stands as written, because what it
  refuses is the *reasoning*: `architecture-trajectory.md` §6's line is that a
  backup nobody has restored is a belief rather than a control, and a drill
  certifies the schema it ran against rather than the one deployed today.
- **Automating the two processor deletions before D1 is answered.**

## Open decisions — Vince's, not this document's

1. **D1. Does erasure at Sentry and Resend become automated, or stay a
   documented manual step?** Automating means an API credential for each, held
   by the application, able to delete — which widens what a compromise of the
   droplet reaches, in order to remove a manual step taken a handful of times a
   year. The manual answer is defensible; it needs saying out loud rather than
   arriving by default.
2. **D2. Enforcing CSP, or a report collector first?** 1.2 recommends enforcing
   on the Chromium test's evidence. The collector is the more cautious path and
   costs an endpoint.
3. **D3. Does §6's ordering of long-retention backups behind staging stand?**
   Seven days is the real bound on undoing a bad migration, and the drill shows
   that rehearsal does not need staging.
4. **D4. HSTS preload — yes or no?** 1.6 raises the max-age and adds
   `includeSubDomains` without touching this, because preload is submission to
   a list baked into browser binaries and removal takes months. It commits
   every present and future subdomain of `vinclarice.com` to HTTPS forever, and
   the question is whether any of them will ever need not to be.
5. **D5. What is in front of port 22, and is it in code?** The playbook manages
   no firewall and no SSH configuration. If the answer is a DigitalOcean cloud
   firewall, that is a fine answer and should be written down, because a
   rebuild from this repository would not reproduce it.

## Relationship to other documents

- Deferrals, refusals and their triggers: `architecture-trajectory.md` §6, §7.
- What is open: `roadmap.md`. This plan is not claimed by it yet.
- The restore procedure and its record: `MIGRATION.md`.
- Delivery standards, including the failing-test-first rule these acceptance
  conditions assume: `principles.md`.
