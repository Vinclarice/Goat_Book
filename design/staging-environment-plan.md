# Staging environment

Vince · brief · written August 11, 2026 · **deliberately deferred August 12,
2026 — see §6 for the trigger that revives it.** The decisions are made and a
real code gap was found and closed on the way; provisioning the droplet, DNS
and database is still Vince's own step — see §5.

## 1. Why

`architecture-trajectory.md` §6 names this "next, because it gates everything
below it": an asynchronous task queue, Terraform, independent backup restores
and CI-built images all wait on staging existing first. `CLAUDE.md` already
identifies its absence as the reason read-only diagnosis must precede any
redeploy that would overwrite evidence — there has never been anywhere to
rehearse a risky change.

**This is not the first time this project has had something called "staging."**
`infra/staging-inventory.ini` once named `staging.vinclarice.com`, which had
always been the same droplet as production; it was renamed away in `d001020`
(August 1, 2026) rather than left to invite someone to treat production as a
scratch target. This plan builds the real thing for the first time.

## 2. Decisions

Asked directly rather than guessed, since either is expensive to unwind once
real infrastructure exists:

- **A second DigitalOcean droplet**, same provider and region as production,
  cheapest tier. Not a container or a second process on the production host:
  that droplet has 458MB of RAM and one core, already tight per
  `architecture-trajectory.md` §6's swap finding, and a staging incident would
  be able to take production down — which defeats the entire point.
- **Its own database on production's existing Postgres cluster**, not a second
  managed cluster. `provision-postgres.sh` already reuses a cluster named
  `$CLUSTER_NAME` if one exists, and `restrict-database-user.sh` already
  creates a role scoped to one database with every other database's `CONNECT`
  privilege revoked — which is what stops a staging credential reading
  production's data despite shared hardware. No new managed-database cost.

## 3. The gap found while designing rather than while deploying

`settings.py`'s `DEBUG = DEPLOYMENT_ENVIRONMENT != "production"` has only two
states and neither fits staging. `DEPLOYMENT_ENVIRONMENT=staging` puts
`DEBUG=True` on a publicly reachable host — tracebacks to anyone, no required
`DJANGO_SECRET_KEY`, no HSTS, no secure cookies. Calling staging "production"
to dodge that makes `clarice/monitoring.py` report staging's errors into
production's own Sentry project, which is exactly the noise its
`environment == "production"` guard exists to prevent.

**Fixed and shipped**, following the pattern `monitoring.py` already set — pull
the decision into a tested function rather than an inline branch in a config
file. `clarice/deployment.py`'s `is_debug()` treats `"production"` and
`"staging"` identically, both getting the full production-grade block, while
`monitoring.py` is untouched and still refuses everything but the literal
string `"production"`. An unrecognised or missing `DJANGO_ENVIRONMENT` still
fails safe into `DEBUG=True`. TDD: `clarice/tests/test_deployment.py` written
first and confirmed failing on `ModuleNotFoundError`, then the module. 937
backend tests green, up from 933.

This fix stays regardless of whether staging is ever built.

## 4. Scope

**In:** a second droplet running the same Docker image as production, its own
restricted database on the shared cluster, its own subdomain and TLS cert, and
`deployment_environment: staging` so it gets production's security posture
without polluting production's Sentry project.

**Out, deliberately:**

- **A separate Sentry project for staging.** Nothing needs staging error
  visibility beyond watching a deploy run. Revisit if staging ever runs
  unattended long enough that silent failure there would matter.
- **Automatic promotion or CI wiring.** Staging is a place to run the same
  playbook by hand against a different inventory first, not a gate
  production's deploy waits on. That is the later CI-built-images item, which
  waits on staging existing rather than being bundled into it.
- **Terraform.** Named in `architecture-trajectory.md` §6 as the item *after*
  staging, specifically so it can be written against staging first.
  Provisioning staging itself stays Ansible plus the existing shell scripts.

## 5. What staging needs to actually exist — Vince's own steps

Nothing here can run from this machine: `doctl auth` and the production SSH key
both live in WSL, and creating a droplet or a database user is real spending
and a real credential — the same category of action a deploy already is.

1. **Create the droplet.** `doctl compute droplet create` (or the DigitalOcean
   console), same region as production, cheapest size.
2. **Point DNS at it.** A `staging.vinclarice.com` record at the new droplet's
   IP, wherever `vinclarice.com`'s other records already live.
3. **Create its database**, reusing the existing cluster:
   ```bash
   CLUSTER_NAME=clarice-db DB_NAME=clarice_staging \
     ./infra/provision-postgres.sh <staging-droplet-name>
   ```
4. **Restrict its credential** the same way production's already is:
   ```bash
   ./infra/restrict-database-user.sh clarice_staging_app clarice_staging
   ```
   Follow the script's own printed "Next" steps — the connection URL goes in
   `~/.db-connection-url` on the *staging* droplet, not production's.
5. **Write `infra/staging-inventory.ini`**, the same shape as
   `production-inventory.ini` but pointed at the new droplet's IP and user.
6. **Deploy to it**, overriding exactly the two vars the playbook's own comment
   anticipates, plus the environment:
   ```bash
   .venv-wsl/bin/ansible-playbook -i infra/staging-inventory.ini \
     infra/deploy-playbook.yaml -K \
     --extra-vars '{"site_domain":"staging.vinclarice.com","include_www_alias":false,"deployment_environment":"staging"}'
   ```
   `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOST` and the database connection file
   all need setting up on the new host the same way they are on production —
   with a fresh `DJANGO_SECRET_KEY`, not production's.

Acceptance, once it runs: HTTPS at `staging.vinclarice.com` with a real Let's
Encrypt cert, `DEBUG=False`, and an empty account rather than production's
data; a garbage request to `/api/v1/day` still 401s; a deliberately triggered
staging error leaves the production Sentry project quiet; and the staging
credential is refused when it tries to connect to production's database, the
same check `restrict-database-user.sh` already runs for any restricted user.

## 6. Deferred, August 12, 2026 — and what would revive it

Revisited before any of §5 was run. This plan's entire value is somewhere to
rehearse a risky deploy-mechanism change before it reaches production. Nothing
in flight touches `deploy-playbook.yaml`, nginx config, or a migration risky
enough to want that, and Clarice does not yet hold real user data whose loss
staging protects against. Against nothing, a second droplet is a real recurring
cost plus a second environment's secrets, inventory and TLS cert. So this stays
decided but unbuilt.

**What would revive it**, matching the "what would promote it" test `roadmap.md`
uses for deferred items: a deploy-mechanism change worth rehearsing before it
hits production, or the project holding real user data worth protecting from an
untested migration — whichever happens first. §2's decisions stand as the answer
when it does.

**One of the two has arguably fired — August 26, 2026.** This deferral reasoned
from *"Clarice does not yet hold real user data whose loss staging protects
against"*, and that is **no longer true**: `clarice-v4-plan.md`'s V1 was answered
as *Vince plus one invited person*, and she has her own login and her own month
in the database.

**The argument has changed rather than collapsed, and the change is about who
bears the cost.** A bad migration used to lose Vince's own material, which is a
risk a person is entitled to take with their own tool. It now loses somebody
else's, and she cannot restore it, read the playbook, or know it happened.
Against that, the costs §6 named are unchanged and real: a second droplet
billed monthly, a second set of secrets, a second inventory and TLS cert.

**Still deferred, because a cheaper control covers most of it.**
[`MIGRATION.md`](../MIGRATION.md)'s restore drill is the actual undo for a bad
migration — rollback covers code and not the database — and it **ran and passed
on August 19, 2026**, which is the thing staging would have been rehearsing.
**What is Vince's now is narrower and sharper**: re-running that drill matters
more than it did this morning, and it is the same two hours it always was.

**This is not a refusal and should not become one by silence.** The trigger
fired and the answer was *not yet, for these reasons* — which is a different
thing, and the reasons are above where the next reader can disagree with them.

Still undecided at that point: whether staging gets its own scheduled backups,
and whether it runs continuously or is started only for a rehearsal.
DigitalOcean bills by the hour either way, so the second is a cost decision for
whoever is paying, not an engineering one.
