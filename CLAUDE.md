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
thirty documents** — which are standing authorities, which are records of
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

**Second Mind is a separate project and none of this governs it.** It lives at
`C:\dev\Clarice_secondmind`, has its own design documents, its own venv, its
own Postgres (port 5434, not 5433) and runs `pytest` rather than
`manage.py test`. The direction is settled: Clarice is worked into Second Mind,
not the reverse, ending as one application with a knowledge core and a
**Superlists** task core. Knowledge-side work — Ideas, resurfacing, the
mind-map, search over retained material — belongs there now, and the roadmap's
opening section says what survives the merger and what does not.

## Clarice is in maintenance until the merger

Not frozen — maintained. It has real users and it keeps running. But it is no
longer where features are added, and the risk to guard against is not an
accidental edit (separate repositories handle that) but a **justified** one:
*while I'm here*, or *Second Mind needs Clarice to expose X*.

**Allowed.** Production defects, which the merger does not make redundant — a
system with red CI and no uptime monitoring stays broken whichever project it
becomes part of. The live list is `design/commercial-blueprint.md` Part 1.
Security fixes and data-loss fixes qualify without argument.

**Two remain, as of August 14, 2026:**

- **External uptime monitoring.** `/healthz` exists now and checks the database;
  nothing polls it. This one is deliberately not code — a watchdog running on
  the machine it watches is not a watchdog — so it is an account somebody
  creates, not a commit.
- **Migrate-before-recreate.** `deploy-playbook.yaml` runs the container at
  :259 and migrates at :308, so new code serves traffic against the old schema
  for the length of the migration.

Closed, and listed only so the next reader does not re-fix them: `/healthz`
(`fd896c6`), `restart_policy: unless-stopped` (`b2e16b2`),
`include_local_variables` (`bbfc38d`), and both Android queue defects — the
process-wide lock and the backup exclusion, in *both* `backup_rules.xml` and
`backup_rules_legacy.xml`. **This list said those were open after they had been
fixed**, and that stale line cost a session's worth of re-investigation. If you
close one, close it here in the same commit.

**Not allowed without a deliberate decision.** New features on `Item`,
`Capture` or `Idea`. New UI work. New models — a model added now is a model
migrated twice, and `Capture` and `Idea` do not survive the merger at all.

**And the rule that actually protects the merger: nothing here grows to serve
Second Mind.** No new endpoint, no shared table, no export hook. When Second
Mind wants this data it reads the existing API or a database dump, once, at
merge time. A bridge built now is code paid for twice and thrown away.

The one exception is `android/`, which is a client of both backends rather than
part of either core — see Second Mind's `docs/android-two-backends.md`.

## Environment

The virtualenv is at the repository root and is the only one — worktrees
need their own `pnpm install`. Run Python through it directly rather than
activating:

```powershell
docker compose up -d db   # once per session; starts local Postgres
.\.venv\Scripts\python.exe src\manage.py test accounts lists capture clarice daily routines review
pnpm --dir frontend test
pnpm --dir frontend build
```

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

Those three cover the web application; `android/` has its own check below,
and CI runs all four. Keep the Django app list matched to
`.github/workflows/ci.yml` — it once omitted `capture`, so following the
README ran every suite except the one covering the capture API.

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
