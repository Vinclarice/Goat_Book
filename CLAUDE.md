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

Those three are the full check. Keep the Django app list matched to
`.github/workflows/ci.yml` — it once omitted `capture`, so following the
README ran every suite except the one covering the capture API.

Never `npx tsc`; the build's `tsc --noEmit` is the type check.

## Changing an API schema

A Ninja schema change does not reach the SPA until the contract is
regenerated, and the build type-checks against it:

```powershell
.\.venv\Scripts\python.exe src\manage.py dump_openapi_schema
pnpm --dir frontend generate:api
```

## Deploying

`ansible-playbook -i infra/production-inventory.ini infra/deploy-playbook.yaml -K`

That inventory has one host and it is production. There is no staging
environment to rehearse against, so read-only diagnosis comes before any
redeploy that would overwrite the evidence.
