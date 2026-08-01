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
alongside it in `design/`.

## Environment

The virtualenv is at the repository root and is the only one — worktrees
need their own `pnpm install`. Run Python through it directly rather than
activating:

```powershell
.\.venv\Scripts\python.exe src\manage.py test accounts lists capture
pnpm --dir frontend test
pnpm --dir frontend build
```

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

**The container is recreated and migrated before the nginx and certbot
tasks.** New assets therefore start being served while the run still has
work to do — a rotated bundle hash proves the container step succeeded, not
that the deploy finished. Wait for the play recap.
