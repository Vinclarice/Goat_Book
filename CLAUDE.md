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

## Keeping a plan current — strike the increment in the commit that ships it

**Not afterwards, and not in a tidying pass.** An increment that shipped and is
still unstruck is how three plans came to read *not started* over shipped work
for six days in August, and how `roadmap-history.md` — the file that is supposed
to be unable to go stale — came to be missing four releases at once, including
the Second Mind merger.

**This is the tagging lesson again, and it is worth naming as such.** Tagging
drifted for exactly one reason: it was written down as a convention and nowhere
as a step. Documents drift for the same reason. The fix is the same: put it in
the commit, where there is already a trigger.

So, concretely, in the same commit as the code:

- **Strike the increment or decision in its plan**, with the date. If the answer
  turned out different from the plan's guess, say so there — `D3` and `D5` were
  both answered by *building* them and only the code knew for six days.
- **Never write a tally into a header.** `design/README.md` owns this rule: a
  header may state a decision, never a count. The strikes are the status.
- **If the work answered a decision, answer it where the reasoning already is.**
  `WeeklyOutcome`'s docstring carries D3's answer rule by rule against §4; the
  plan links to that rather than restating it.

## Closing a piece of work

Three steps:

1. **Move the narrative to `roadmap-history.md`, and reduce the plan to a stub** —
   four lines saying what it was, when it shipped, and where the narrative went.
2. **Evict the roadmap item — do not just strike it.** It becomes **one line**
   in *Open now*'s `### Closed` roll-up: what it was, when it closed, its
   codename, and nothing else. The narrative is already in `roadmap-history.md`;
   a struck paragraph here is a second copy of it.
3. **Promote any surviving consequence to its own live entry.** If the closed
   work leaves something open — a deferred increment, a defect, an unmet
   condition — it becomes a *separate* entry in its own right, not a paragraph
   inside a struck one.

**Step 3 is the one that is actually load-bearing, and step 2 exists to force
it.** A consequence buried inside a struck entry is invisible: that is precisely
how the moorhen copy defect sat unstruck for seven days over a fix that had
already shipped, and how *"removing user data from Sentry and Resend"* and
*"three genuinely open decisions in Part 9"* sat in this file as live work for
two and six days after both had closed.

**Measured, August 28, 2026**: *Open now* was 578 lines conveying twelve live
items, because ten closed ones had been struck-and-kept and had grown to 220
lines between them — all ten already narrated in `roadmap-history.md`. Evicting
them and promoting four buried consequences took the section to 403 lines and
raised the live count to fourteen, two of which nobody knew were live.

There is no status line to update and no index to re-check: a stub *is* its
status. Stubs rather than deletions, because code comments across `src/`,
`frontend/`, `android/` and `infra/` cite these plans by name and section — the
file has to resolve, its 300 lines do not. **How many is not written down here,
because it only ever goes up and a number that only goes up is a number that is
always slightly wrong.** To recount:

```bash
git grep -lE "[a-z0-9-]+-plan\.md|architecture-trajectory\.md|product-stories\.md|principles\.md|commercial-blueprint\.md|modules\.md" -- src frontend/src android infra | wc -l
```

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

**`/capture/` was freed and deliberately not taken.** Capture is **one surface
among many** under `/mind/` — notes, concepts, people, decisions, sources,
review, search, ask, dump and the rest — so the prefix would have named the
smallest thing in the room, against a live PWA shortcut and every bookmark a
move breaks. ~~Nine routes sit under `/mind/`~~ — **that said nine until August
28, 2026, when `mind/urls.py` carried thirty-three `path()` entries.** The
argument only got stronger as the count drifted, which is why it is now stated
as a shape rather than a number.
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
`design/commercial-blueprint.md` Part 1 and **is not copied here.**

~~The commercial substrate's next pieces are terms, a privacy policy, and the
three open decisions in that file's Part 9.~~ **All five of those landed and
this line went stale — corrected August 23, 2026.** `/terms/` and `/privacy/`
are live and linked from both signup forms, and Part 9 closed on August 20. The
line cost something before it was noticed: it was quoted as a reason in a
recommendation about opening public signup, and the reason was false. **Which is
this file's own warning, a second time** — see the paragraph above about the
defect list. Do not restate what
[`design/commercial-blueprint.md`](design/commercial-blueprint.md) owns.

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

**`pnpm test` can print `411 passed` and exit 1.** Vitest reports *unhandled
errors* — an exception thrown during a render that no assertion caught — in a
separate block from the test tally, and fails the run on them while the tally
still reads green. CI checks the exit code; a human reading the summary line
does not. **Read `$?`, not the last line**, and that goes for every runner here:

```powershell
pnpm --dir frontend test -- --run; echo "EXIT = $LASTEXITCODE"
```

It cost a deploy on August 23, 2026: three commits went out with CI red, each
reported as green from a local run whose summary said `411 passed`. The failure
was a React component throwing inside a test whose mock returned the wrong
shape, which is a passing test *and* a broken render at the same time.

**The same three runs were red on the browser job too, and reading only the
summary hid that as well** — the conclusion drawn at the time was that CI had
stopped running that job, when in fact it had caught a real regression within
the hour. `gh run view <id>` per job, before believing anything about CI.

**And the regression it caught is its own trap: anchoring a text insertion on a
`def` line steals any decorator above it.** A new function inserted before
`def complete_project` landed *between* that def and its `@transaction.atomic`,
so the new function acquired it and the old one lost it. Both read correctly in
isolation and the diff showed an addition rather than a move. **Anchor above the
decorator, or below the previous function's last line.**

**Two Python runners, and both are real.** The task core runs on
`manage.py test`; the knowledge core arrived with 500-odd pytest-style tests and
stays on `pytest`, because converting them would be a large mechanical rewrite
of the thing in that app most worth leaving alone. **Running one and reporting
"tests pass" leaves most of a second application unrun** — `src/mind/` has grown
well past what it arrived with, and the two suites are now the same order of
magnitude as each other.

**The current number is deliberately not written here**, because it moves every
week and the recipe below produces it in one command. What arrived is a
historical fact and stays; what is there now is a question, not a claim.

**And `pytest` here prints no summary line under redirection** — progress to
`[100%]`, then nothing. No *"N passed"*, no timing, no verdict. **This is the
mirror of the `pnpm test` trap above and it is worse**: there the summary lies
and the exit code is honest; here there is no summary at all, so a run that died
quietly looks exactly like a run that passed. Do not count dots — the output
carries prose from the tests themselves, and counting characters in it reported
78 skips where there were 6.

Read `$?`, and when a real count is wanted, ask for one:

```powershell
.\.venv\Scripts\python.exe -m pytest --junitxml="$env:TEMP\mind.xml"
```

**The path has to be a Windows path.** `--junitxml=/tmp/...` exits 0 and writes
the file nowhere Git Bash can find it, which reads as pytest having failed to
produce it. Two runs were spent on that.

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

**Two checkouts no longer destroy each other's test database — the name carries
the checkout.** Django names it after the real one, so every run everywhere used
to be `test_clarice`; `clarice.deployment.test_database_name` now appends a
digest of the checkout path, and owns the reasoning. This checkout is
`test_clarice_e1a4712a`, a worktree is something else, and both can run at once.
Verified rather than assumed: two suites in parallel both pass, and forced onto
one name by hand the second dies on `Key (datname)=... already exists`.

**What the derived name does not cover is two runs inside one checkout** —
`manage.py test` and `pytest` together, which share a `BASE_DIR` and therefore a
name. That is what the override is for, and it still wins:

```powershell
$env:DJANGO_TEST_DB_SUFFIX = "b"   # test_clarice_b, created and torn down alone
```

**`--parallel` is not a substitute** — it clones from the database named above
and collides in the same place.

**Know the shape of the failure anyway, because it does not look like
contention.** The second run finds the database present and asks whether to
delete it, which is `EOFError` with nothing on stdin; unluckier timing has the
first run's teardown drop the database the second is still using, and what comes
back is a wall of `setUpClass` errors reading like a broken migration. A real
one of those on August 19 reported `column mind_facet.producer does not exist`
while the migration creating it was present and `makemigrations --check` was
clean. **Before diagnosing a suite that fails everywhere at once, ask who else
is running one:**

```powershell
docker exec goat-book-db-1 psql -U clarice -d clarice -tAc "select datname, count(*) from pg_stat_activity where datname like 'test_%' group by datname"
```

**The other cost of two sessions in one tree: commits capture each other's
edits.** `git commit -- <path>` and `git commit -a` both take the *working
tree*, so an unstaged edit somebody else is midway through lands in your commit
under your message. That is how `821be3e`, whose subject is the second factor,
also carries the `DJANGO_TEST_DB_SUFFIX` block described above — written by
another session that had not committed it yet. Nothing broke and the history is
left alone, because rewriting somebody else's commit is worse than a misfiled
hunk. Two habits avoid it:

- **Name your paths explicitly** on every commit, and check `git status` first —
  a file you did not touch appearing as modified means somebody else is in it.
- **Land small changes quickly.** The window is the whole risk, and it is
  measured in minutes.

The stronger answer, when two sessions are genuinely going to overlap, is a
worktree rather than care.

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

**This suite flakes, rarely, and the failure names the wrong test.** Twice on
August 26, 2026 — once locally, once on CI. What it looks like:

```
django.db.utils.OperationalError: deadlock detected
CommandError: Database test_clarice_… couldn't be flushed
django.db.utils.IntegrityError: duplicate key value violates unique
    constraint "accounts_user_username_…"
```

**Two errors, neither in the test that caused them.** `StaticLiveServerTestCase`
serves each request on its own thread while `_fixture_teardown` truncates every
table from the main one. `TRUNCATE` takes `ACCESS EXCLUSIVE`; a request still
running holds `ACCESS SHARE`; reach for the tables in different orders and
Postgres kills one of them. The flush then fails, so the tables keep their rows
and the *next* test dies in `setUp` on a duplicate username. The test named in
the output is the victim, not the cause.

**Diagnose it as a flake only by evidence, never by re-running until green.**
CLAUDE.md already carries the cost of the opposite habit: three commits went out
with CI red because the browser job's failure was read as noise, and it had
caught a real regression. The evidence that says *flake* is (a) the deadlock and
flush messages above, and (b) the same commit passing on a re-run with nothing
changed — `gh run rerun <id> --failed`.

**What was tried and did not work**, so it is not tried again. Waiting for the
page before teardown looks like the fix and is not:

- `wait_for_load_state("networkidle")` reports the page's *current* state, so a
  page that went idle once after loading returns from it immediately, however
  many XHRs React has fired since. Measured: `/api/v1/day` outstanding before
  the call and still outstanding after it.
- Counting requests and waiting for the set to empty costs the full timeout,
  because at least one request per page never reports finished to Playwright —
  `failure=None`, `redirected_to=None`, no service worker involved. Ten seconds
  a test, for nothing.
- **And nothing is the right word.** `pg_stat_activity` at teardown says the
  live server's connections are `idle`, not `active` and not
  `idle in transaction` — the server has finished; the browser's bookkeeping is
  the artifact. Waiting on the browser cannot close a window that is already
  shut on the side that matters.

So the window is genuinely narrow and genuinely server-side, and no cheap
client-side wait addresses it. **If it becomes frequent enough to be worth
fixing**, the lever is the flush rather than the browser: make
`_fixture_teardown` retry once on `OperationalError`, or hold the live server's
threads open until they drain. Both are more machinery than two occurrences
justify.

**Run the whole app list before pushing, not a subset.** `accounts` and
`clarice` are where this codebase keeps its promises — the export guard, the
restore-drill coverage, the dark-service registry, the release record — and none
of them lives in the app you are editing. Two red builds on August 27, 2026 came
from running `lists daily review accounts` and pushing: the guards caught four
separate omissions, twice after they had been cited approvingly in the same
session. **Remembering is not the control; running them is.**

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

**Quoting a remote command through PowerShell eats your quotes.**
`ssh host 'grep -E "^(a|b)" /etc/f'` loses the single quotes before `ssh` sees
them, and the remote shell answers ``syntax error near unexpected token `(' ``.
Double quotes outside and single inside works — `ssh host "grep -rE 'a|b'
/etc/f"` — or choose a pattern with no shell metacharacters at all.

**And `sudo` over `ssh` needs a terminal.** `ssh host 'sudo ...'` answers *"a
terminal is required to read the password"*; `ssh -t` allocates one. Both cost a
command each on August 27, 2026, while answering D5.

**Ask a daemon for its effective configuration rather than reading its files.**
`/etc/ssh/sshd_config.d/60-cloudimg-settings.conf` said
`PasswordAuthentication no` and a root-only `50-cloud-init.conf` sat above it —
and `sshd` takes the **first** value it obtains, so the file nobody could read
would have won. `sudo sshd -T` reports what is actually in force. The general
shape: a config directory plus an include order is not something to resolve by
eye.

**Writing a file from Python here produces CRLF, and git will hide it.**
`pathlib.write_text` and `open(...,'w')` default to `newline=None`, which
translates `
` to `os.linesep` on Windows. `.gitattributes` normalises the blob
on commit, so `git status` stays clean and review sees nothing — while the
working copy is corrupt. For `.py` and `.ts` that is harmless; for anything a
shell parses it is fatal, and the documented restore drill runs from WSL against
*this* checkout. It cost `check-restore-integrity.sh` exactly that way: written,
run against a live database, then edited and silently broken.

Pass `newline="
"` when writing, and if a script starts failing with
``syntax error near unexpected token `$'{\r'``, the fix is
`rm <file> && git checkout -- <file>` — a plain checkout will not do it, because
git sees no difference to restore. `clarice/tests/test_executable_line_endings.py`
fails locally when this happens; CI cannot catch it, since a fresh Linux checkout
is always LF.

**The same shape a second time: a new `.sh` here is not executable, and
everything says it is.** `core.fileMode` is `false` on this checkout, so git has
no mode to record and writes `100644`; Git Bash's `ls` prints the file with a
`*` regardless, guessing from the extension; and `git status` has nothing to
report either way. So a shell script looks executable locally, in review, and in
every listing, while the blob says otherwise — and the failure appears only on a
Linux runner or in WSL, as `Permission denied` and exit 126.

It cost all four of `infra/*.sh`, wrong from the day each was written. The
backup-freshness workflow died on it the first night its token let it get that
far, and `MIGRATION.md`'s restore drill would have died identically at step 5,
mid-drill, with a paid scratch cluster running. Neither was noticed because
neither script had ever actually been run.

```bash
git ls-files -s infra/*.sh      # 100755 is right; 100644 is the bug
git update-index --chmod=+x <file>   # chmod alone does nothing, core.fileMode is false
```

**Unlike the CRLF case, CI can catch this**, because `git ls-files -s` reports
the recorded mode on any platform.
`clarice/tests/test_executable_file_modes.py` does, and it reads the index
rather than the filesystem on purpose: the playbook builds the image from WSL
over `/mnt/c`, which mounts `drvfs` with no `metadata` option and reports every
file `-rwxrwxrwx` whatever git recorded. Windows answers much the same, so
`os.access(..., X_OK)` is green on both machines this is worked on and means
nothing. **That is also why `./manage.py migrate` has worked in production for
months while `src/manage.py` was `100644`** — fixed when the test was written,
and the reason §6's CI-built images would have broken the first thing a deploy
does.

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
his.** Three tags, each meaning a different thing — **the first two always,
the third only when the deploy is a release:**

- `LIVE` — a moving pointer at the code currently running. **The only tag
  that is ever overwritten** (`git tag -f` plus `git push --force origin
  LIVE`), which is safe precisely because the position it leaves is kept by
  the `DEPLOYED-` tag that marked it.
- `DEPLOYED-<YYYY-MM-DD>/<HHMM>` — a permanent record of one deployment
  event. Ask for the time if you do not have it; do not guess, and check
  the name is free, because these collide silently.
  **Local time, and say the offset in the message** — every tag from
  `DEPLOYED-2026-08-23/1510` back does, and this line exists because it was
  the one thing the convention never wrote down: a time reported as *11:45pm*
  was a UTC reading of 19:45 local, tagged `/2345`, and renamed the same
  evening. Both are the same instant and only one is consistent with the
  others. **Annotated, not lightweight**, for the same reason the codename is:
  `git describe` ignores a lightweight tag, so the command this file tells you
  to confirm a build with cannot see it.
- The bird codename — a permanent annotated release tag describing what
  shipped and how it was verified. **Not every deploy gets one**, and this is
  the tag to leave off when unsure: the first two are the record and this one
  is a claim that a body of work finished. `roadmap.md`'s *Release practice*
  owns the test and is not restated here — the short version is that a release
  needs a subject you can say in a sentence *and* has to move something a
  document tracks, and that infrastructure is excluded outright by
  `architecture-trajectory.md` §6. **Well under half of all deploys have one**,
  and the tags themselves are the count — `git tag` answers it, so no number
  lives here. (~~Fourteen of thirty-six~~ said so until August 28, 2026, by
  which point it was fifteen of thirty-seven; it was wrong within one deploy of
  being written, in the file that tells you tagging is a step.)
  **When it is arguable, it is not a release.**

Tagging drifted badly through August — `LIVE` sat five days and thirty commits
behind production, two deploys went untagged — because it was written down in
`roadmap.md` as a convention and nowhere as a step. It is a step: when he reports
a deploy done, verify what is live, then tag it in the same turn.

**And if it earned a bird, write the entry in that same turn too.** The tag
message is already the narrative — `osprey`'s runs to thirty lines and is better
than anything reconstructed later would be — so this is a transcription into
`roadmap-history.md`, not fresh writing, and it takes a minute. **Twelve inches
was the whole gap**: four releases had a carefully written tag and no entry,
`godwit` and `ibis` for eleven days, and `osprey` appeared nowhere in `design/`
at all while having moved four of the nineteen journeys.
`clarice/tests/test_every_release_is_in_the_record.py` now fails when a codename
has no narrative, and that guard is why the count is four rather than five.

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

**Rolling back.** Since August 18 the image is tagged with the commit's
abbreviated SHA and the last four are kept on the server, so undoing a bad
deploy no longer means rebuilding from an old checkout:

```bash
ssh elspeth@vinclarice.com 'docker images clarice'          # what is still there
ssh elspeth@vinclarice.com 'docker stop clarice && docker rm clarice'
# then re-run the playbook from the good commit, which retags and recreates
```

**It rolls back code and not the database, and that is the whole caveat.** If
the bad deploy migrated, the old image meets the new schema — often worse than
the bug. A migration is undone by `MIGRATION.md`'s restore drill or not at all,
which is why the drill is the thing to keep exercised rather than this.

**The container is recreated and migrated before the nginx and certbot
tasks.** New assets therefore start being served while the run still has
work to do — a rotated bundle hash proves the container step succeeded, not
that the deploy finished. Wait for the play recap.
