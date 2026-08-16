# Working on Clarice

Read [`design/principles.md`](design/principles.md) first. It is the
authoritative statement of how work is designed, implemented and verified
here, and it is not optional reading before making a change. Do not restate
or fork it — if a principle is wrong or missing, edit that file.

The two that most often get skipped under time pressure:

- **Write the failing test first**, and watch it fail for the reason you
  expect. A new test that passes on its first run is a signal: either the
  behaviour already existed, or the test is asserting the implementation
  back at itself. Regression guards are the honest exception — say so.
- **Say what was actually run.** "Verified by reading" is acceptable.
  "Tests pass" when they were never executed is not.

[`design/roadmap.md`](design/roadmap.md) is the plan; active specs live
alongside it in `design/`. **[`design/README.md`](design/README.md) indexes every
document there and owns the table of which fact lives where** — start there
rather than guessing whether a plan is current.

**If a document needs a fact it does not own, link to the owner rather than
restating it.** A restated fact is a fact that will be wrong later; this file
carried a copy of the production defect list for four days and twice described
finished work as open.

## Closing a piece of work

Two steps:

1. **Move the narrative to `roadmap-history.md`, and reduce the plan to a stub** —
   four lines saying what it was, when it shipped, and where the narrative went.
   Keep only the resulting baseline or remaining consequence in `roadmap.md`.
2. **Close the roadmap item** — strike it, date it, name what replaced it.

There is no status line to update and no index to re-check: a stub *is* its
status. Stubs rather than deletions, because 251 code comments cite these plans
by name and section — the file has to resolve, its 300 lines do not.

## The shape of the application

One application, two cores, one login, one database, one deployment: the
**Superlists** task core, and the knowledge core at `src/mind/` mounted at
`/mind/`. The merger shipped and deployed on August 14, 2026.

`C:\dev\Clarice_secondmind` still exists and is **documents only**: its `docs/`
remain the design authority for what the merger did not settle — what each core
owns, salience, the joint weekly report, the visual map. Its code, its venv and
its Postgres on 5434 are history; do not develop there.

**There is one of everything.** One capture surface — `/mind/`, writing a `Node`;
`/capture/` and its `Capture` and `Idea` models are deleted. One capture endpoint
— `/api/v1/capture`, served by `mind/api_v1.py`, which both the phone and the
SPA's Day page post to. One API at `/api/v1/`, one token table
(`accounts.PersonalAccessToken`, which has scopes), one login; the knowledge
core's own `NinjaAPI` at `/mind/api/v1/` and its `mind.ApiToken` were deleted on
August 15 having never been called by anything. **A knowledge-core endpoint
belongs on `/api/v1/` as a router in `mind/api_v1.py`, beside the capture one; do
not start a second API.**

**`/capture/` was freed and deliberately not taken.** Nine routes sit under
`/mind/` and only one is capture, so the prefix would have named the smallest
thing in the room, against a live PWA shortcut and every bookmark a move breaks.
It survives in one line of `clarice/urls.py` and everything under it is relative
— settled rather than welded.

**`android/` is a client of one backend.** The code for a split exists —
`Backends.isSplit`, a second token slot, a second Connect screen — but it
switches on `-PsecondMindBaseUrl`, which defaults to `""` and has never been
passed to a shipped build. Every request the phone makes goes to
`https://vinclarice.com/`. `docs/android-two-backends.md` in the Second Mind
repository describes the design, not the deployment; a plan to delete
`/api/v1/capture` on the strength of it would have drained the encrypted offline
queue into 404s.

Generalise it: **a seam that is not switched on is not a seam.** Three turned up
in two days — `/healthz` with nothing polling it, detectors built and never
invoked, and this. Check the build configuration, not the branch.

## Where work goes — the task core is not frozen, it is not the priority

The freeze was lifted on August 15, 2026. What replaces it is a priority, which
is a different thing and is not a licence: the task core is a competent todo
application, and the graph is the thing that makes this worth building. **The
scoreboard is `product-stories.md` and it is not restated here.**

**So, concretely.** Production defects, security and data-loss fixes need no
argument, in either core. Task-core *feature* work needs a reason beyond *while
I'm here* — and when you notice something there mid-task, **surface it and ask
rather than either fixing it silently or refusing.** That is the one thing the
freeze was actually buying: everything is one tree now, so the accidental edit is
available in a way it was not when there were two repositories.

**New models, in either core, are governed by `architecture-trajectory.md` §4**
and not by anything here. Its test is the strict one — *a concept earns its own
model when it has a different life cycle, not when it has a different name*.
`Item` is not restricted: it is the destination for every accepted commitment,
and it gained `owner` on August 14 precisely so a thought from the knowledge core
could become a task without a filing question.

**There is no open production defect list.** All ten from the August 12 audit
closed on August 15; what they were and what fixed them is in
`design/roadmap-history.md`. When there is a list again it lives in
`design/commercial-blueprint.md` Part 1 and **is not copied here.** The
commercial substrate's next pieces are terms, a privacy policy, and the three
open decisions in that file's Part 9.

**The rule that protected the merger has expired, recorded here so it is not
reapplied**: *nothing here grows to serve Second Mind — no new endpoint, no
shared table, no export hook.* One project now, one transaction, and
`confirm_actionable` writing a node, a facet and a task together is the merger's
payoff rather than a violation of it.

**`ActivityEvent` is append-only by database trigger, and there is exactly one
hole in it.** `mind/migrations/0015_erasure_exemption` permits `DELETE` when a
transaction-local setting names the owner being erased, which is what makes
account deletion possible at all — before it, `User.delete()` raised, because
`owner` is a cascade and a cascade is a mutation of the log. The only caller is
`accounts.services.purge_account`. Do not widen it into a general "allow
deletes"; `mind/tests/test_erasure.py` fails if you do, on purpose.

**SSL expiry alerting is refused, not missing.** UptimeRobot paywalls it, certbot
renews automatically and the playbook exercises it. Recorded here rather than in
a defect list so nobody re-investigates and reaches the same paywall.

## Environment

The virtualenv is at the repository root and is the only one — worktrees
need their own `pnpm install`. Run Python through it directly rather than
activating:

```powershell
docker compose up -d db   # once per session; starts local Postgres
.\.venv\Scripts\python.exe src\manage.py test accounts lists clarice daily routines review
.\.venv\Scripts\python.exe -m pytest          # the mind app; config in pytest.ini
pnpm --dir frontend test
pnpm --dir frontend build
```

**Two Python runners, and both are real.** The task core runs on
`manage.py test`; the knowledge core arrived with 500-odd pytest-style tests and
stays on `pytest`, because converting them would be a large mechanical rewrite
of the thing in that app most worth leaving alone. Running one and reporting
"tests pass" covers about half the application.

**Tests run on Postgres now, not SQLite.** `mind.Mention.mention_unique` is
`nulls_distinct=False`, "Postgres 15+ only" per its own comment, and SQLite omits
that class of constraint in silence — so a local run would pass while proving
less than it appeared to (`design/architecture-trajectory.md` §3). The `mind`
migrations also `CreateExtension("vector")`, which SQLite cannot do at all.
`clarice/settings.py`'s `DEBUG` branch defaults `DJANGO_DATABASE_URL` to the
`docker-compose.yml` database (`localhost:5433`, chosen to avoid clashing with
another project's Postgres on `5432`) when the env var isn't set. Nothing to
configure beyond starting the container; a stale `db.sqlite3` from before this
change is harmless and can be deleted.

The browser smoke suite is deliberately not in that list — it needs a built
bundle and a browser binary, which an ordinary edit-and-test loop should not
have to install. Run it when you have touched routing, the app shell, static
assets, session handling, or navigation:

```powershell
.\.venv\Scripts\python.exe -m playwright install chromium   # once
pnpm --dir frontend build                                   # it loads the real bundle
.\.venv\Scripts\python.exe src\manage.py test functional_tests
```

**Build first or you are testing the last build.** The tests serve
`src/lists/static/frontend/`, so without a rebuild they will happily pass
against stale JavaScript. `HEADED=1` runs them in a visible browser.

CI runs all of the above across five jobs — `django`, `mind`, `browser`,
`frontend`, `android`. **Keep the Django app list above matched to
`.github/workflows/ci.yml`.** It has been out of step twice, and both times the
effect was a suite nobody ran while the docs said otherwise. The failure mode is
an app added to one list and not the other.

**CI's Postgres is `pgvector/pgvector:pg17`, in every job that has one.** Django
builds the test database from *every* app's migrations whichever labels are under
test, so a stock image fails in `setup_databases` before a single test runs,
including on jobs that never touch the knowledge core.

Never `npx tsc`; the build's `tsc --noEmit` is the type check.

## Android

Neither `JAVA_HOME` nor `ANDROID_HOME` is set globally, and the `java` on
PATH is an unrelated Java 8 stub — so the build needs both pointed at
Android Studio's own JDK and SDK:

```powershell
$env:JAVA_HOME = "$env:ProgramFiles\Android\Android Studio\jbr"
$env:ANDROID_HOME = "$env:LOCALAPPDATA\Android\Sdk"
cd android; .\gradlew.bat :app:testDebugUnitTest
```

`:app:assembleDebug` builds the APK. Results land in
`app/build/test-results/`; the Gradle summary says BUILD SUCCESSFUL without
naming the test count, so read the XML rather than trusting the absence of
red.

**AGP 9 builds Kotlin itself.** Applying `org.jetbrains.kotlin.android`
alongside it fails the build outright — nearly every guide predates this.
The Compose compiler plugin is still applied separately.

## Changing an API schema

A Ninja schema change does not reach the SPA until the contract is
regenerated, and the build type-checks against it:

```powershell
.\.venv\Scripts\python.exe src\manage.py dump_openapi_schema
pnpm --dir frontend generate:api
```

## Deploying

Run from WSL, where ansible, Docker and the ssh key all live:

```bash
cd /mnt/c/Users/vince/goat-book
.venv-wsl/bin/ansible-playbook -i infra/production-inventory.ini infra/deploy-playbook.yaml -K
```

`-K` prompts for the become password, so this is the user's to run, not
yours. That inventory has one host and it is production. There is no
staging environment to rehearse against, so read-only diagnosis comes
before any redeploy that would overwrite the evidence.

**When Vince says "deploy it," he's asking for this command, not asking
you to run it.** Surface it in a fenced `bash` block and stop there — he
runs it himself and reports back once it's done.

**The deploy is not finished until it is tagged, and this is your job, not
his.** Three tags, each meaning a different thing:

- `LIVE` — a moving pointer at the code currently running. **The only tag
  that is ever overwritten** (`git tag -f` plus `git push --force origin
  LIVE`), which is safe precisely because the position it leaves is kept by
  the `DEPLOYED-` tag that marked it.
- `DEPLOYED-<YYYY-MM-DD>/<HHMM>` — a permanent record of one deployment
  event. Ask for the time if you do not have it; do not guess, and check
  the name is free, because these collide silently.
- The bird codename — a permanent annotated release tag, applied when a
  release is verified in production, describing what shipped and how.

Tagging drifted badly through August — `LIVE` sat five days and thirty commits
behind production, two deploys went untagged — because it was written down in
`roadmap.md` as a convention and nowhere as a step. It is a step: when he reports
a deploy done, verify what is live, then tag it in the same turn.

Note that the playbook builds the image **from the working tree**
(`delegate_to: 127.0.0.1`), not from a git ref — so what is deployed is
whatever branch is checked out, merged or not. Tag the commit that was
actually built, and confirm it with `git describe --always --dirty`.

**An apt task that looks hung is usually not.** The "Install docker" step
stalled for minutes on three separate deploys and was cancelled each time,
because `state: latest` plus an unconditional `update_cache` made apt
resolve upgrade candidates on every run — and it could have restarted the
Docker daemon mid-deploy, killing the running container. Fixed in `fed210b`
(`state: present`, `cache_valid_time`); the task now takes about twenty
seconds. Before ever suggesting a cancel, check rather than assume:

```bash
ps -eo pid,etime,cmd | grep AnsiballZ    # is the task actually working?
ls -l /var/lib/dpkg/lock-frontend /var/lib/apt/lists/lock
dpkg --audit                              # empty = consistent
```

Generalise it: `state: latest` on an infrastructure package means a routine
application deploy is willing to upgrade and restart the thing running the
application. Prefer `present` and make upgrades deliberate.

**A "Build container image locally" failure with a DNS timeout is WSL's
network stack, not the deploy.** That step's `docker build` failed against
`auth.docker.io` with `dial tcp: lookup auth.docker.io on
10.255.255.254:53: ... i/o timeout` — `10.255.255.254` is WSL2's internal DNS
relay (`/etc/resolv.conf`'s `nameserver` line) and it had gone unreachable:
`ping 8.8.8.8` worked while `getent hosts auth.docker.io` timed out, so
resolution specifically was broken, not connectivity. Fixed from a **Windows
PowerShell prompt, not WSL**:

```powershell
wsl --shutdown
```

This forces a full WSL network-stack restart and regenerates the DNS
relay; reopen WSL and Docker Desktop afterward and retry the build. Since
this step runs `delegate_to: 127.0.0.1` before anything touches the remote
host, a failure here never reaches production — there is nothing to undo
before retrying.

**The container is recreated and migrated before the nginx and certbot
tasks.** New assets therefore start being served while the run still has
work to do — a rotated bundle hash proves the container step succeeded, not
that the deploy finished. Wait for the play recap.
