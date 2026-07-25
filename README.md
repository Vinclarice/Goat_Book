# Superlists

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
