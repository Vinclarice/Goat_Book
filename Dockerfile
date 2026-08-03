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

# Sized against the droplet rather than the textbook. It has one core,
# 458MB of RAM and no swap, and the container measured 94MB serving with
# gunicorn's default of a single sync worker -- which means one request at a
# time, so any slow query blocked the whole site.
#
# (2 x cores) + 1 = 3 workers is the usual formula and would be wrong here:
# roughly 204MB against ~152MB available, with no swap to absorb it, so the
# OOM killer takes the container rather than the site merely slowing down.
#
# Two workers for redundancy -- one wedged or dying worker should not be a
# full outage -- and threads for the concurrency, because nearly every
# request is "ask Postgres, wait, render" and a thread costs almost nothing
# while a worker costs ~55MB. Extra workers would buy no more CPU on a single
# core anyway.
#
# max-requests recycles each worker periodically so a slow leak can never
# accumulate into an OOM; the jitter stops both recycling at the same moment.
CMD ["gunicorn", "--bind", "0.0.0.0:8888", \
     "--workers", "2", "--threads", "4", \
     "--max-requests", "500", "--max-requests-jitter", "50", \
     "clarice.wsgi:application"]
