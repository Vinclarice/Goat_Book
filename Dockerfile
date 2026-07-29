FROM node:24-slim AS frontend

WORKDIR /frontend

RUN corepack enable

COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile

COPY frontend/ ./
RUN pnpm build

FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

COPY requirements.txt /tmp/requirements.txt
RUN pip install --disable-pip-version-check -r /tmp/requirements.txt

COPY src /src
COPY --from=frontend /src/lists/static/frontend /src/lists/static/frontend

WORKDIR /src

RUN DJANGO_ENVIRONMENT=production \
    DJANGO_SECRET_KEY=build-only-secret \
    DJANGO_ALLOWED_HOST=localhost \
    DJANGO_DATABASE_URL=sqlite:////tmp/build.sqlite3 \
    DJANGO_EMAIL_HOST_USER=build-only@example.com \
    DJANGO_EMAIL_HOST_PASSWORD=build-only-secret \
    python manage.py collectstatic --noinput

ENV DJANGO_ENVIRONMENT=production
ENV ALLOW_DATABASE_FLUSH=0

RUN adduser --disabled-password --gecos "" --uid 1234 nonroot
USER nonroot

CMD ["gunicorn", "--bind", "0.0.0.0:8888", "clarice.wsgi:application"]
