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
.\.venv\Scripts\python.exe src\manage.py test accounts lists capture
pnpm --dir frontend test
pnpm --dir frontend build
```

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

Preview it without sending anything:

```powershell
.\.venv\Scripts\python.exe src\manage.py send_due_digest --dry-run
```

On the server, run it once each morning from cron:

```
0 7 * * * docker exec clarice python manage.py send_due_digest
```

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

- `DJANGO_EMAIL_HOST_USER` / `DJANGO_EMAIL_HOST_PASSWORD` -- Gmail SMTP
  credentials used to send admin notification emails. Use a
  [Gmail app password](https://myaccount.google.com/apppasswords), not
  your regular password.
- `DJANGO_ADMIN_EMAIL` (optional) -- where notifications are sent;
  defaults to vincentjg01@gmail.com.

`infra/deploy-playbook.yaml` reads the app password from
`~/.email-app-password` on the server rather than accepting it as a
playbook variable -- see that file for how to create it.
