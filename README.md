# Clarice

A private Django to-do application with focused React enhancements for task and
archive management. Django forms remain usable if JavaScript is unavailable.

## Local Windows development

Install the Python requirements in the project virtual environment, then install
the frontend packages:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
cd frontend
pnpm install
```

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
.\.venv\Scripts\python.exe src\manage.py test accounts lists functional_tests
pnpm --dir frontend test
pnpm --dir frontend build
```

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

## Brute-force protection

Login attempts are rate-limited by client IP in nginx
(`infra/templates/nginx-clarice.conf.j2`) and by account via
[django-axes](https://github.com/jazzband/django-axes), which locks an
account out for an hour after 5 failed attempts, independent of which IP
they come from. Both layers email `ADMINS` when they're triggered.

## Production environment variables

In addition to `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOST`, and
`DJANGO_DB_PATH`, production (`DJANGO_ENVIRONMENT=production`) requires:

- `DJANGO_EMAIL_HOST_USER` / `DJANGO_EMAIL_HOST_PASSWORD` -- Gmail SMTP
  credentials used to send admin notification emails. Use a
  [Gmail app password](https://myaccount.google.com/apppasswords), not
  your regular password.
- `DJANGO_ADMIN_EMAIL` (optional) -- where notifications are sent;
  defaults to vincentjg01@gmail.com.

`infra/deploy-playbook.yaml` reads the app password from
`~/.email-app-password` on the server rather than accepting it as a
playbook variable -- see that file for how to create it.
