# Staging environment

Vince · brief · written August 11, 2026 · **decisions made, a real code
gap found and closed; provisioning the actual droplet/DNS/database is
still Vince's own step — see §5.** **Deliberately deferred August 12,
2026 — see §8.**

## 1. Trigger and diagnosis

`architecture-trajectory.md` §6 names this "next, because it gates
everything below it": an asynchronous task queue, Terraform, independent
backup restores and CI-built images are all listed as waiting on staging
existing first. `CLAUDE.md` already identifies its absence as the reason
read-only diagnosis must precede any redeploy that would overwrite
evidence — there has never been anywhere to rehearse a risky change
before running it against the only environment that exists.

**This is not the first time this project has had something called
"staging."** `infra/production-inventory.ini`'s own header records that
`infra/staging-inventory.ini` once named the host `staging.vinclarice.com`
— but that environment "no longer exist[ed] and had always been the same
droplet as production," so the file was renamed rather than left to invite
someone to treat production as a scratch target (`d001020`, August 1,
2026). Named here so this plan is read as building the real thing for the
first time, not restoring something that existed before.

## 2. Decisions

Asked directly rather than guessed, since getting either wrong here is
expensive to unwind once real infrastructure exists:

- **A second DigitalOcean droplet**, same provider and region as
  production, cheapest tier. Not a container or a second process on the
  production host itself — the droplet has 458MB of RAM and one core,
  already tight per `architecture-trajectory.md` §6's own swap finding,
  and sharing it would mean a staging incident could take production down
  too. Defeats the point of rehearsing risk somewhere it can't reach the
  real thing.
- **Its own database, on production's existing Postgres cluster** rather
  than a second managed cluster. `provision-postgres.sh` already supports
  this exactly — it reuses a cluster named `$CLUSTER_NAME` if one exists,
  "DigitalOcean's own guidance is to share one cluster across small apps
  rather than pay per cluster" — and `restrict-database-user.sh` already
  creates a role scoped to exactly one database with every other
  database's `CONNECT` privilege revoked, which is what keeps a staging
  credential from being able to read or write production's data even
  though they share hardware. No new managed-database cost.

## 3. A real gap, found while designing rather than while deploying

`clarice/settings.py`'s `DEBUG = DEPLOYMENT_ENVIRONMENT != "production"`
only has two states. Neither fits staging cleanly:

- Give staging `DEPLOYMENT_ENVIRONMENT=staging`: `DEBUG` becomes `True` on
  a publicly reachable host — debug tracebacks served to anyone, no
  `DJANGO_SECRET_KEY` required (falls back to `"insecure-key-for-dev"`),
  no HSTS, no secure cookies. A real security problem, not a cosmetic one.
- Give staging `DEPLOYMENT_ENVIRONMENT=production` instead, to dodge that:
  `clarice/monitoring.py` reports exclusively when
  `environment == "production"` (deliberately, per its own docstring — a
  DSN leaking into a non-production environment would bury real incidents
  under a developer's own broken experiments). Staging would start
  reporting its own errors into the *same Sentry project* production
  uses, exactly the noise that guard exists to prevent.

**Fixed, following the same pattern `monitoring.py` already set: pull the
decision out into a tested function rather than an inline branch in a
config file.** `clarice/deployment.py`'s `is_debug()` treats `"production"`
and `"staging"` identically — both get the full production-grade block
(required `SECRET_KEY`, secure cookies, HSTS, no tracebacks) — and
`clarice/monitoring.py` is untouched, so it keeps refusing everything but
the literal string `"production"`. An unrecognised or missing
`DJANGO_ENVIRONMENT` still fails safe into `DEBUG=True`, same as before.

TDD: `clarice/tests/test_deployment.py` written first (confirmed failing
on `ModuleNotFoundError: No module named 'clarice.deployment'`), then
`clarice/deployment.py` implemented. 937 backend tests green (up from
933), including the four new ones.

## 4. Scope

**In:** a second droplet running the same Docker image as production, its
own restricted database on the shared cluster, its own subdomain and
TLS cert, `deployment_environment: staging` so it gets production's real
security posture without polluting production's Sentry project.

**Out, deliberately:**

- **A separate Sentry project for staging.** Nothing today needs staging
  error visibility beyond watching a deploy run — `roadmap.md`'s later
  infra items (the task queue, Terraform, CI-built images) are the actual
  reasons staging exists, and none of them need monitoring on staging
  itself yet. Designing that now would be exactly the "design for
  hypothetical future requirements" `principles.md` warns against; revisit
  if staging ever runs unattended for long enough that silent failure
  there would matter.
- **Automatic promotion or CI wiring between staging and production.**
  Nothing here makes staging part of the deploy pipeline — it's a place
  to run the same playbook by hand against a different inventory before
  running it against production, not a gate production's own deploy waits
  on. That's the CI-built-images/health-checks item later in the
  infrastructure track, which explicitly waits on staging existing first
  rather than being bundled into standing it up.
- **Terraform.** Named in `architecture-trajectory.md` §6 as the next
  infrastructure item after staging exists, specifically so it can be
  written against staging first — provisioning staging itself stays
  Ansible plus the existing shell scripts, the same tools that already
  provisioned production.

## 5. What staging needs to actually exist — Vince's own steps

Nothing here can run from this machine: `doctl auth` and the production
SSH key both live in WSL (`CLAUDE.md`), and creating a droplet or a
database user is real spending and a real credential, the same category
of action a deploy already is.

1. **Create the droplet.** `doctl compute droplet create` (or the
   DigitalOcean console), same region as production, cheapest size.
2. **Point DNS at it.** A `staging` subdomain — `staging.vinclarice.com` —
   at the new droplet's IP, wherever `vinclarice.com`'s other records
   already live.
3. **Create its database**, reusing the existing cluster:
   ```bash
   CLUSTER_NAME=clarice-db DB_NAME=clarice_staging \
     ./infra/provision-postgres.sh <staging-droplet-name>
   ```
4. **Restrict its credential** the same way production's already is:
   ```bash
   ./infra/restrict-database-user.sh clarice_staging_app clarice_staging
   ```
   Follow the script's own printed "Next" steps — the connection URL goes
   in `~/.db-connection-url` on the *staging* droplet, not production's.
5. **Write `infra/staging-inventory.ini`**, the same shape as
   `production-inventory.ini` but pointed at the new droplet's IP and
   user.
6. **Deploy to it**, overriding exactly the two vars the playbook's own
   comment already anticipates, plus the environment:
   ```bash
   .venv-wsl/bin/ansible-playbook -i infra/staging-inventory.ini \
     infra/deploy-playbook.yaml -K \
     --extra-vars '{"site_domain":"staging.vinclarice.com","include_www_alias":false,"deployment_environment":"staging"}'
   ```
   `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOST`, and the database connection
   file all need setting up on the new host the same way they are on
   production — a fresh `DJANGO_SECRET_KEY`, not production's.

## 6. Acceptance

- Staging serves over HTTPS at `staging.vinclarice.com` with a real
  Let's Encrypt cert, `DEBUG=False`, and its own database — confirmed by
  logging in and seeing an empty account, not production's data.
- A garbage request to staging's `/api/v1/day` still 401s, same baseline
  sanity every production deploy already gets.
- Staging's own errors do not appear in the production Sentry project —
  confirmed by triggering one deliberately (e.g. a bad request) and
  checking Sentry stays quiet.
- Production's database is unreachable from the staging credential —
  confirmed the same way `restrict-database-user.sh`'s own script already
  verifies for any restricted user, by attempting to connect to the wrong
  database and getting refused.

## 7. What this doesn't decide yet

Whether staging gets its own scheduled backups (the "independent
long-retention encrypted backups" item is about production's backups
being restorable, not about backing up staging itself, which holds no
real data). Whether staging stays running continuously or gets started
only when a rehearsal is needed — DigitalOcean bills by the hour either
way, so this is a cost decision rather than an engineering one, and
belongs to whoever is paying for it.

## 8. Deferred, August 12, 2026

Revisited before any of §5 was run. This plan's entire value is a place
to rehearse a risky deploy-mechanism change before it reaches
production — nothing currently in flight touches
`deploy-playbook.yaml`, nginx config, or a migration risky enough to
want that rehearsal, and Clarice doesn't yet hold real user data whose
loss staging protects against. Against that, a second droplet is a real
recurring cost and a second environment's secrets, inventory and TLS
cert are an ongoing tax. Nothing to offset yet, so this stays decided
but unbuilt rather than built ahead of need.

**Not abandoned.** §2's decisions stand as the answer whenever this is
picked back up, and §3's `is_debug()` fix is shipped and stays regardless
— it was cheap, correct on its own terms, and already closed a real gap
in `settings.py` independent of whether staging itself ever exists. §5
is exactly what to run when the trigger below fires.

**What would revive this**, matching the "what would promote it" test
used elsewhere in `roadmap.md` for deferred items: a deploy-mechanism
change worth rehearsing before it hits production, or the project
holding real user data worth protecting from an untested migration —
whichever happens first.
