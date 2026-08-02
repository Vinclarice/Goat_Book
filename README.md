# Clarice

A private Django to-do application with focused React enhancements for task and
archive management. Django forms remain usable if JavaScript is unavailable.

## The agenda

`/dashboard/` is an agenda rather than a list of lists: every open task across
every list, grouped by how soon it's due (overdue, today, this week, later, no
due date). Lists and tags become filters in the sidebar; the archive has its own
page at `/archive/`.

The bucketing rules live in one place, `src/lists/agenda.py`, and are mirrored by
`frontend/src/agenda.ts` so the server-rendered page, the React enhancement and
the daily digest email all agree on what "overdue" means. If you change the
window in one, change it in the other -- `WEEK_HORIZON_DAYS` exists in both.

The page is server-rendered in full and works without JavaScript: completing,
snoozing, quick-add and filtering are all plain form posts and `?scope=`/`?list=`
/`?tag=` query parameters. `AgendaWorkspace` then replaces the region with the
same markup plus inline updates and undo.

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

```powershell
.\.venv\Scripts\python.exe src\manage.py test accounts lists capture clarice
pnpm --dir frontend test
pnpm --dir frontend build
```

### Browser smoke tests

A separate suite that drives a real browser against a real server, covering
the seams the other two cannot: routing, the built bundle, static file
serving, session cookies, and browser navigation. It is a separate test
label because it needs a built bundle and a browser binary.

```powershell
.\.venv\Scripts\python.exe -m playwright install chromium   # once
pnpm --dir frontend build
.\.venv\Scripts\python.exe src\manage.py test functional_tests
```

Build first, or the tests run against whatever the last build produced --
they load the real files from `src/lists/static/frontend/`. Set `HEADED=1`
to watch them in a visible browser.

CI (`.github/workflows/ci.yml`) runs the same three checks on every push and
pull request, with the Django suite run against a Postgres service
container instead of SQLite, matching production's database engine.

Keep the Django app list here matching CI's. It previously omitted `capture`,
so following this file ran every suite except the one covering the capture
API -- the reason an idempotency change could be committed claiming its
tests had never been run.

The local recovery path for a forgotten password is Django's authenticated
management command:

```powershell
.\.venv\Scripts\python.exe src\manage.py changepassword USERNAME
```

## Account approval

Signups are not self-activating: `/accounts/signup/` creates the account
with `is_active=False` and shows a "pending approval" message instead of
logging them in. Approve (or reject) accounts at `/admin/`, where you can
also manage lists directly. The signup and each account lockout (see
below) sends a notification email to `ADMINS` in settings.py.

Making yourself a superuser so you can reach `/admin/` in the first place:

```powershell
.\.venv\Scripts\python.exe src\manage.py createsuperuser
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
no longer expresses an intended send time -- it wakes the command, and the
command decides per recipient. `User.last_digest_date` records the user's own
local date of the last send, so the other twenty-three runs are no-ops and a
retry, restart, or DST repeat cannot send twice.

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

Token-authenticated API requests are outside this, because Ninja resolves the
token inside the view and `request.user` is still anonymous at middleware
time. Capture stores timestamps rather than local dates, so it is unaffected;
a future date-bearing token endpoint must activate the owner's zone itself.

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
environment would otherwise report a developer's own broken experiments into
the production project and bury real incidents underneath them. Without a
DSN the SDK is never even imported.

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
