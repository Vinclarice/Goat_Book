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
alongside it in `design/`. **[`design/README.md`](design/README.md) indexes all
thirty-one documents** — which are standing authorities, which are records of
shipped work, and which fact each one owns. Start there rather than guessing
whether a plan is current.

## Closing a piece of work

Thirty design documents drifted out of agreement by August 2026: four plans
still called themselves forward-looking months after shipping, two files gave
the same release letter to different work, and 257 lines of shipped narrative
piled up under a heading instructing the reader to move it elsewhere. **A prose
rule did not prevent this — it had been in `roadmap.md` since August 1 and was
simply not followed.** So it is a checklist, here, where it gets read:

1. **Update the plan document's status line** — shipped, when, and what was
   verified. First six lines of the file.
2. **Move the narrative to `roadmap-history.md`.** Keep only the resulting
   baseline or the remaining consequence in `roadmap.md`.
3. **Close the roadmap item** — strike it, date it, name what replaced it.
4. **Check `design/README.md`** still tells the truth.

Step 2 is the one that gets skipped, and it is the one that compounds. If a
document needs a fact it does not own, link to the owner rather than restating
it; a restated fact is a fact that will be wrong later.

**The merger is done. Second Mind's code lives here now.** All five steps of its
`two-cores.md` shipped on August 14, 2026 and deployed the same day: the
knowledge core is `src/mind/`, mounted at `/mind/`, behind this project's login,
in this project's database. One application, two cores — knowledge, and the
**Superlists** task core.

`C:\dev\Clarice_secondmind` still exists and is now **documents only**. Its
`docs/` remain the design authority for everything the merger did not settle —
what each core owns, salience, the joint weekly report, the visual map — and
`two-cores.md` records what each step cost. Its code, its venv and its Postgres
on 5434 are history; do not develop there. This paragraph said the opposite for
a day after the merger, which is exactly the drift the checklist above exists to
prevent.

**The crossover is over.** There is one capture surface, `/mind/`, writing a
`Node`; `/capture/` and its `Capture` and `Idea` models are deleted (Heron 4b),
and **`/mind/` is where the knowledge core lives** — step 5, Vince's call,
August 15, 2026.

It is no longer temporary, and that is a decision rather than an omission.
`/capture/` was freed and deliberately not taken: nine routes sit under `/mind/`
and only one is capture, so `/capture/` would have named the smallest thing in
the room, against a live PWA shortcut and every bookmark that a move breaks. The
prefix still appears in exactly one line of `clarice/urls.py` and everything
under it is still relative, so this stays cheap to revisit — it is settled, not
welded.

**There is one capture *endpoint*, as of Heron 4a on August 15, 2026.**
`/api/v1/capture` is the application's, served by `mind/api_v1.py`, and it
writes a `Node`. Both the phone and the SPA's Day page post to it.

**There is one of everything now.** One API at `/api/v1/`, one token table
(`accounts.PersonalAccessToken`, which has scopes), one login. The knowledge
core's own `NinjaAPI` at `/mind/api/v1/` and its `mind.ApiToken` were deleted on
August 15 having never been called by anything — no shipped Android build was
ever split, and the `/mind/` pages carry no JavaScript at all. A knowledge-core
endpoint belongs on `/api/v1/` as a router in `mind/api_v1.py`, beside the
capture one; do not start a second API.

## Where work goes — the task core is not frozen, it is not the priority

**The freeze is lifted — Vince's call, August 15, 2026.** What replaces it is a
priority, which is a different thing and is not a licence.

The freeze had been rewritten twice to survive. It read "until the merger", and
the merger ended; then "until the crossover ends", on the ground that `Capture`
and `Idea` were retiring so work on either was thrown away, and Heron deleted
both. Each rewrite found a narrower justification for a conclusion already held,
which is the shape of motivated reasoning, and a third rewrite would have been
cargo. On its own terms there was nothing left: the surviving clause, *no new
models on the task core, because a model added now is a model migrated twice*,
named a migration that has happened — and `architecture-trajectory.md` §4 gates
new models in **either** core anyway, more strictly.

**The reason that does not expire.** The task core is a competent todo
application. The graph is the thing that makes this worth building, and
`product-stories.md` has nineteen journeys with two working, most of them not
the task core's. Alongside it sits the commercial substrate — account deletion
and data export are untouched and `commercial-blueprint.md` calls them legal
blockers. That is where work goes.

**So, concretely.** Production defects, security and data-loss fixes need no
argument, in either core. Task-core *feature* work needs a reason beyond *while
I'm here* — and when you notice something there mid-task, **surface it and ask
rather than either fixing it silently or refusing.** That is the one thing the
freeze was actually buying, and it is worth keeping on its own: everything is
one tree now, so the accidental edit is available in a way it was not when there
were two repositories, and nothing structural prevents it.

The live production defect list is `design/commercial-blueprint.md` Part 1.

**All ten are closed, as of August 15, 2026.** The last one was never code:

- ~~**External uptime monitoring.**~~ **Closed August 15, 2026 — UptimeRobot is
  polling `/healthz`.** Not a commit and never was: a watchdog running on the
  machine it watches is not a watchdog, so this was always an account somebody
  creates. Defect 9 is fully fixed — the site can say it is healthy and
  something is now asking.

  **SSL expiry alerting is not included, and will not be chased.** UptimeRobot
  gates it behind a paid plan. Certbot renews automatically and the playbook
  exercises it, so the residual risk is a silent renewal failure — worth knowing
  about, not worth a subscription at three users. Recorded so nobody
  re-investigates and reaches the same paywall.

Closed, and listed only so the next reader does not re-fix them: `/healthz`
(`fd896c6`), `restart_policy: unless-stopped` (`b2e16b2`),
`include_local_variables` (`bbfc38d`), migrate-before-recreate (`b779c0c`), CI
green across five jobs (`fd4a8d7`), token requests using the owner's time zone
(`6da41c8`), and both Android queue defects — the process-wide lock and the
backup exclusion, in *both* `backup_rules.xml` and `backup_rules_legacy.xml`.
**This list said those Android ones were open after they had been fixed**, and
that stale line cost a session's worth of re-investigation. If you close one,
close it here in the same commit.

Also closed: the white screen on any render exception (`0428efb`), and defects
3 and 4 — the two Tailwind styles — which turned out to have shipped on
August 12 in `2986ed6`. **That is the second time this list and the blueprint
have claimed finished work was open.** Check the code before believing either.

**Blueprint defect 6 is moot, not open — Vince declined it August 14, 2026 and
Heron 4b removed the code.** `promote_idea_to_task` carried an Idea's notes but
not its tags; `Idea` no longer exists, so neither does the function. Recorded
because the blueprint still lists it, and this list has twice claimed finished
work was open.

**New models, in either core, are governed by `architecture-trajectory.md` §4**
and not by anything here. Its test is the strict one — *a concept earns its own
model when it has a different life cycle, not when it has a different name* —
and it applies to the knowledge core too. This file used to carry a separate
task-core prohibition on the grounds that a model added then would be migrated
twice; that migration has happened, and one gate is better than two that can
disagree.

`Item` is no longer on that list. It is the destination for every accepted
commitment, and it gained `owner` on August 14 precisely so a thought from the
knowledge core could become a task without a filing question. Work on it is
work on the thing that survives.

**The rule that protected the merger has expired, and is recorded here so it is
not reapplied.** It read: *nothing here grows to serve Second Mind — no new
endpoint, no shared table, no export hook; when Second Mind wants this data it
reads the existing API or a dump, once, at merge time*. That was right while
there were two projects. There is one now, one database and one transaction, and
`confirm_actionable` writing a node, a facet and a task together is exactly the
"bridge" the rule forbade — which is the merger's whole payoff rather than a
violation of it.

**`android/` is a client of one backend, and this paragraph said otherwise until
August 15.** It read: *capture goes to the knowledge core, Today and Agenda to
the task core*. The code to do that exists — `Backends.isSplit`, a second token
slot, a second Connect screen — but it switches on `-PsecondMindBaseUrl`, which
defaults to `""` and has never been passed to a shipped build. Every request the
phone makes goes to `https://vinclarice.com/`. Heron step 4 planned to delete
`/api/v1/capture` on the strength of that sentence, which would have drained the
encrypted offline queue into 404s. `docs/android-two-backends.md` in the Second
Mind repository describes the design, not the deployment.

Generalise it: **a seam that is not switched on is not a seam.** Three of these
turned up in two days — `/healthz` with nothing polling it, detectors built and
never invoked, and this. Check the build configuration, not the branch.

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

**Tests run on Postgres now, not SQLite.** `Item.Meta`'s
`unique_active_item` is `nulls_distinct=False`, "Postgres 15+ only" per its
own comment — SQLite silently omitted that constraint, so a local run
passed while proving less than it appeared to
(`design/architecture-trajectory.md` §3). `clarice/settings.py`'s `DEBUG`
branch now defaults `DJANGO_DATABASE_URL` to the `docker-compose.yml`
database (`localhost:5433`, chosen to avoid clashing with another
project's Postgres on `5432`) when the env var isn't set. Nothing to
configure beyond starting the container; a stale `db.sqlite3` from before
this change is harmless and can be deleted.

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

Those cover the web application; `android/` has its own check below, and CI
runs all of them across five jobs — `django`, `mind`, `browser`, `frontend`,
`android`. **Keep the Django app list matched to `.github/workflows/ci.yml`.**
That list once omitted `capture`, so following the README ran every suite except
the one covering the capture API, and the `mind` suite was absent from CI
entirely for the first day of the merger while `requirements-dev.txt` claimed
otherwise. `capture` has since been deleted outright and came off both lists
together — which is the easy direction; the failure mode is an app added to one
and not the other.

**CI's Postgres is `pgvector/pgvector:pg17`, in every job that has one.** The
`mind` migrations run `CreateExtension("vector")`, and Django builds the test
database from *every* app's migrations whichever labels are under test — so a
stock image, or SQLite, fails in `setup_databases` before a single test runs,
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

This drifted badly through August: `LIVE` sat five days and thirty commits
behind production, and two deploys went untagged. It drifted because
tagging was written down in `roadmap.md` as a convention and nowhere as a
step. So: when he reports a deploy done, verify what is live, then tag it
in the same turn.

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
10.255.255.254:53: ... i/o timeout` on 2026-08-10 — nothing to do with the
commit being deployed or the playbook itself. `10.255.255.254` is WSL2's
internal DNS relay (`/etc/resolv.conf`'s `nameserver` line), and it had
gone unreachable: `ping 8.8.8.8` (a raw IP) worked fine while `ping
auth.docker.io` and `getent hosts auth.docker.io` both timed out,
confirming resolution specifically, not general connectivity, was broken.
Fixed from a **Windows PowerShell prompt, not WSL**:

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
