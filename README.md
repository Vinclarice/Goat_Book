# Clarice

A private Django application with two cores, sharing one login, one database and
one deployment.

**The task core** — *Superlists* — is commitments: tasks, areas, projects,
recurring commitments, checklist steps, routines, the daily page and a weekly
review. Mostly a React SPA under `/app/`, with the Django forms still usable if
JavaScript is unavailable.

**The knowledge core** — *Second Mind* — is `src/mind/`, at `/mind/`. A thought
is captured as a `Node` and nothing is asked of it at the moment of writing: no
filing, no category, no due date. Structure emerges afterwards, from concepts
that recur and from connections the system proposes and a person confirms. It is
server-rendered, deliberately plain, and carries no JavaScript.

The two meet where a captured thought turns out to be a commitment: the parser
reads a date out of what was written, offers it, and a confirmed offer becomes a
task in the other core. `/api/v1/capture` is the one capture endpoint — the
Android client and the daily page's quick-capture box both post to it, and it
writes a `Node`.

Second Mind's design authority is its own `docs/`, which still live at
`C:\dev\Clarice_secondmind`; its code does not.

## The agenda

The agenda is every open task across every area, grouped by how soon it's due
(overdue, today, this week, later, no due date). Areas and tags become filters
in the sidebar; the archive has its own page.

Both live in the SPA, at `/app/agenda` and `/app/archive`. `/dashboard/` and
`/archive/` are redirects into it: `/dashboard/` is `LOGIN_REDIRECT_URL`, and
which surface it lands on is the account's `landing_surface` preference -- the
Daily Page or the agenda -- so the login form, a bookmark and the Django
shell's own "Today" link all agree without any of them knowing the rule.

The bucketing rules live in one place, `src/lists/agenda.py`, and are mirrored by
`frontend/src/agenda.ts` so the API, the React agenda and the daily digest email
all agree on what "overdue" means. If you change the window in one, change it in
the other -- `WEEK_HORIZON_DAYS` exists in both.

**There is no longer a no-JavaScript agenda.** This section described one until
August 28, 2026 -- server-rendered in full, with completing, snoozing, quick-add
and filtering as plain form posts. `dashboard()` and `archive()` are now bare
redirects and the templates are gone; `AgendaWorkspace` is mounted by
`AgendaRoute` and fed by the API, not laid over server-rendered markup.

## Local Windows development

Install the Python requirements in the project virtual environment, then install
the frontend packages:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
cd frontend
pnpm install
```

`requirements-dev.txt` pulls in `requirements.txt` plus packages only
needed to run the test suite (not part of the production image).

For normal Django development using the last compiled frontend bundle:

```powershell
pnpm --dir frontend build
.\.venv\Scripts\python.exe src\manage.py migrate
.\.venv\Scripts\python.exe src\manage.py runserver
```

For React hot reload, run Vite in one terminal:

```powershell
pnpm --dir frontend dev
```

Then start Django in another terminal with the development-server address:

```powershell
$env:VITE_DEV_SERVER_URL = "http://127.0.0.1:5173"
.\.venv\Scripts\python.exe src\manage.py runserver
```

## Checks

**[`CLAUDE.md`](CLAUDE.md) owns the commands** — the two Python runners and why
both are real, the local Postgres container, the frontend suite, and the browser
smoke suite with its build-first warning. They used to be written out here as
well, and a second copy is how a list goes stale.

CI (`.github/workflows/ci.yml`) runs all of them on every push and pull request,
across five jobs: `django`, `mind`, `browser`, `frontend`, `android`. **Keep the
Django app list in `CLAUDE.md` matching CI's.** It once omitted `capture`, so
following the documented command ran every suite except the one covering the
capture API -- which is how an idempotency change was committed claiming tests
that had never run.

## Account approval

Signups are not self-activating: `/accounts/signup/` creates the account
with `is_active=False` and shows a "pending approval" message instead of
logging them in. Approve (or reject) accounts at `/admin/`, where you can
also manage lists directly. The signup and each account lockout (see
below) sends a notification email to `ADMINS` in settings.py.

Making yourself a superuser so you can reach `/admin/` in the first place, and
the local recovery path for a forgotten password:

```powershell
.\.venv\Scripts\python.exe src\manage.py createsuperuser
.\.venv\Scripts\python.exe src\manage.py changepassword USERNAME
```

## Daily reminder emails

`send_due_digest` emails each opted-in user a summary of what's overdue or due
today. Users with nothing due are skipped, so quiet days stay quiet, and the
preference lives on the account (`User.daily_digest`, toggled at
`/accounts/settings/`).

Each user gets it at 07:00 in *their* time zone (`User.time_zone`), which is
also what decides their overdue/due-today boundaries -- see "Time zones" below.

Preview it without sending anything:

```powershell
.\.venv\Scripts\python.exe src\manage.py send_due_digest --dry-run
```

On the server, run it hourly from cron:

```
0 * * * * docker exec clarice python manage.py send_due_digest
```

Hourly, not daily: one daily run can only be somebody's morning. The schedule
wakes the command and the command decides per recipient. `User.last_digest_date`
records the user's own local date of the last send, so the other twenty-three
runs are no-ops and a retry, restart, or DST repeat cannot send twice.

The morning is a window, 07:00 to 12:00 local, not just a start time. Past it
the day is written off: nothing is sent, but it is recorded as decided, so a
container that was down all morning does not deliver "Good morning, here is
your day" at 20:00 -- by then the summary is not late, it is wrong.

A run outside that window therefore does nothing, which makes a manual test
look broken. Open both ends to check it by hand:

```powershell
.\.venv\Scripts\python.exe src\manage.py send_due_digest --dry-run --send-hour 0 --until-hour 24
```

## Time zones

`settings.TIME_ZONE` is the fallback for anonymous requests, not the
definition of everyone's day. Each account carries its own `time_zone`, and
`accounts.middleware.TimeZoneMiddleware` activates it for the request, so
every day boundary -- agenda buckets, per-list overdue counts, snooze
presets, the completed-today range -- is computed against that user's date
without any of that code knowing a user exists.

**Token-authenticated requests are covered too.** Ninja resolves a bearer token
inside the view, by which point `TimeZoneMiddleware` has already run against an
anonymous request and deactivated. This was once left to each endpoint to handle;
five shipped and none did, so a routine logged at 07:30 in Makassar was filed
against the previous day -- a durable record silently wrong, with no error
anywhere. It is now fixed once, in `accounts.auth._resolve_scoped_token`, the
single point both token paths converge on. `TimeZoneMiddleware`'s `finally` is
what stops an activated zone outliving the request on a reused worker thread.

Rows written before the fix are still wrong and were deliberately left alone:
nothing recorded which auth path created a `RoutineOccurrence`, so a repair
would have to guess at a durable record.

## Brute-force protection

Login attempts are rate-limited by client IP in nginx
(`infra/templates/nginx-clarice.conf.j2`) and by account via
[django-axes](https://github.com/jazzband/django-axes), which locks an
account out for an hour after 5 failed attempts, independent of which IP
they come from. Both layers email `ADMINS` when they're triggered.

## Production environment variables

In addition to `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOST`, and
`DJANGO_DATABASE_URL` (a Postgres connection URL, e.g.
`postgresql://user:password@host:port/clarice?sslmode=require` -- see
`infra/provision-postgres.sh` and `MIGRATION.md`), production
(`DJANGO_ENVIRONMENT=production`) requires:

- `DJANGO_EMAIL_HOST_USER` / `DJANGO_EMAIL_HOST_PASSWORD` -- SMTP
  credentials. Outbound mail goes through [Resend](https://resend.com),
  whose username is the literal string `resend` and whose password is a
  sending API key.
- `DJANGO_ADMIN_EMAIL` (optional) -- where internal signup and lockout
  notices are sent; defaults to vincentjg01@gmail.com. This is a private
  routing address and never appears in mail sent to a user.

`infra/deploy-playbook.yaml` reads the API key from `~/.resend-api-key` on
the server rather than accepting it as a playbook variable -- see that file
for how to create it.

### What a recipient sees

The visible sender is deliberately separate from the credential above, so
that changing providers can't change Clarice's identity (and so that dev,
the test suite, and production agree on it). All three default to the
`vinclarice.com` sending domain and are overridable:

- `DJANGO_DEFAULT_FROM_EMAIL` -- password resets and the daily digest.
  Defaults to `Clarice <accounts@vinclarice.com>`.
- `DJANGO_SERVER_EMAIL` -- internal notices via `mail_admins()`. Defaults
  to `Clarice notices <notices@vinclarice.com>`. Django's own default,
  `root@localhost`, is not on the verified domain and Resend rejects it.
- `DJANGO_EMAIL_DOMAIN` -- the domain the two defaults above are built
  from.

Resend only sends. `support@vinclarice.com` receives through the IONOS
mailboxes the domain's MX records already point at.

## Error monitoring

Unhandled server errors are reported to [Sentry](https://sentry.io) when --
and only when -- a DSN is configured *and* `DJANGO_ENVIRONMENT=production`.
Both conditions are required: a DSN that finds its way into a development
environment would report a developer's own broken experiments into the
production project and bury real incidents underneath them. Without a DSN the
SDK is never even imported.

- `DJANGO_SENTRY_DSN` (optional) -- the project DSN from Sentry. Absent, no
  reporting is configured and the deploy proceeds normally; monitoring is
  something you add to a working deploy, never something that blocks one.
- `DJANGO_RELEASE` (optional) -- what events are tagged with, so a report
  names the deploy it came from. The playbook sets this from
  `git describe --always --dirty`; it defaults to `unknown`.

The playbook reads the DSN from `~/.sentry-dsn` on the server, the same way
it reads the Resend key. To set it up:

```bash
umask 077 && read -rsp 'Sentry DSN: ' DSN && printf '%s' "$DSN" > ~/.sentry-dsn && unset DSN && echo ok
```

**To verify it after a deploy**, run this against the running container.
Sentry's own onboarding suggests adding a `/sentry-debug/` route that
divides by zero; don't. That is a permanent public URL anyone can use to
burn your event quota, and this answers the same question without one:

```bash
ssh <user>@<host> 'docker exec -i clarice python manage.py shell' <<'EOF'
import os, sentry_sdk
from django.conf import settings
print("enabled:", settings.ERROR_MONITORING_ENABLED)
print("release:", os.environ.get("DJANGO_RELEASE"))
print("integrations:", sorted(sentry_sdk.get_client().integrations))
sentry_sdk.capture_message("B4 verification probe")
print("event sent")
EOF
```

Three things to read, and they fail in different ways:

- `enabled: False` -- the DSN never reached the container. Check
  `~/.sentry-dsn` on the server before looking at anything in Sentry.
- `release:` should name a commit. `git describe` anchors it to the last
  deploy tag, so it reads like
  `DEPLOYED-2026-08-01/1156-41-g6f2e47d70f7e`. A `-dirty` suffix means the
  deploy was built from an unclean tree.
- **`django` must appear in the integrations list.** Without it the SDK can
  still send explicit messages while unhandled 500s go unreported -- the
  failure that looks exactly like success, which is the whole reason B4
  exists.

The flush line may say more events are pending than you sent; the extra is
a release-health session envelope the SDK tracks on its own.
