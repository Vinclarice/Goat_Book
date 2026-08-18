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

# collectstatic runs settings.py's *production* branch, so every variable
# that branch requires has to be here -- as placeholders, since none is used
# for anything but getting the module imported.
#
# DJANGO_EMAIL_BACKEND=console is the load-bearing one. The default when
# DEBUG is off became `resend` on 2026-08-18, and that backend refuses to
# boot without a key, so this step began demanding a credential the build has
# no business holding. collectstatic sends no mail; console needs nothing. It
# replaces the two SMTP placeholders, which existed only to satisfy a branch
# this no longer takes.
#
# clarice/tests/test_build_environment.py reads these back out and boots
# Django with exactly them, so the next required setting fails a test rather
# than a thirteen-second image build in the middle of a deploy.
RUN DJANGO_ENVIRONMENT=production \
    DJANGO_SECRET_KEY=build-only-secret \
    DJANGO_ALLOWED_HOST=localhost \
    DJANGO_DATABASE_URL=sqlite:////tmp/build.sqlite3 \
    DJANGO_EMAIL_BACKEND=console \
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
# **One worker, and that number was learned the hard way.** Two workers took
# the container from 94MB to 154MB, leaving ~95MB free on the host --
# comfortable at rest, and not enough for the host's own maintenance. On the
# very next deploy `apt-mark manual docker.io` thrashed for four minutes and
# was OOM-killed outright (rc 137), failing the play at "Install nginx and
# certbot". The site stayed up and dpkg stayed consistent, but the deploy did
# not finish.
#
# The sizing error was measuring the container at rest against available
# memory rather than against the peak the *host* needs while apt and dpkg
# run. A planned threshold of "drop to one worker if it settles above 180MB"
# never fired, because 154MB was never the problem.
#
# One worker restores roughly the pre-change footprint. The threads are what
# actually fix the defect: the default was a single *sync* worker, so the
# site served one request at a time and any slow query blocked all of it.
# Nearly every request here is "ask Postgres, wait, render", which threads
# handle at a few MB each where a worker costs ~55MB -- and on one core extra
# workers buy no more CPU regardless.
#
# What this gives up is worker redundancy, so a wedged worker is a brief
# outage. At three users that is the cheaper thing to lose on a 458MB box
# with no swap.
#
# **The real fix is not in this file.** 458MB with no swap has no room for an
# application and routine package management at once. Swap, or a larger
# droplet, is what would make two workers safe.
#
# max-requests recycles the worker periodically so a slow leak cannot
# accumulate into an OOM; the jitter keeps it off a fixed boundary.
CMD ["gunicorn", "--bind", "0.0.0.0:8888", \
     "--workers", "1", "--threads", "4", \
     "--max-requests", "500", "--max-requests-jitter", "50", \
     "clarice.wsgi:application"]
