# Moving Clarice's database to DigitalOcean Managed PostgreSQL

This covers the one-time cutover from the SQLite file on the production
droplet to a DigitalOcean Managed PostgreSQL cluster. Staging keeps SQLite
for now -- this is production only.

Code side is already done: `settings.py` reads `DJANGO_DATABASE_URL` in
production (via `dj-database-url`), `requirements.txt` has `psycopg`, and
`infra/deploy-playbook.yaml` wires that env var from `~/.db-connection-url`
on the server instead of bind-mounting a SQLite file. What's left is
provisioning the cluster and moving the existing data. Do this at a quiet
time -- there's a few minutes of downtime, and a small window where writes
made after the data dump wouldn't carry over.

## 1. Provision the cluster (run locally, not on the server)

Requires `doctl` installed and authenticated (`doctl auth init`).

```
./infra/provision-postgres.sh <production-droplet-name>
```

Find the exact droplet name with `doctl compute droplet list` if you don't
have it memorized. The script creates a `db-s-1vcpu-1gb` Postgres 17
cluster in the same region as that droplet, creates a `clarice` database,
and restricts the cluster's firewall to that droplet only. It prints a
`DJANGO_DATABASE_URL` value at the end -- copy it.

## 2. Save the connection URL on the server

SSH into the production droplet, then:

```
umask 077 && echo -n 'postgresql://...the URL from step 1...' > ~/.db-connection-url
```

The deploy playbook reads this file the same way it already reads
`~/.email-app-password` -- it's never committed or passed on the CLI.

## 3. Dump the existing SQLite data

Still on the server, with the current container still running:

```
docker exec clarice ./manage.py dumpdata \
  --natural-foreign --natural-primary \
  -e contenttypes -e auth.permission -e sessions \
  --indent 2 -o /home/nonroot/clarice-data.json

docker cp clarice:/home/nonroot/clarice-data.json ~/clarice-data.json
```

`contenttypes`, `auth.permission`, and `sessions` are excluded: Django
repopulates content types and permissions on `migrate` against the new
Postgres database, and sessions are ephemeral (everyone just logs back in).

Copy `~/clarice-data.json` somewhere off the server too (`scp` it to your
machine) as a backup before continuing.

## 4. Stop writes and redeploy

```
docker stop clarice
```

From your own machine, run the existing deploy playbook against
production (same as any normal deploy):

```
ansible-playbook -i <your-production-inventory> infra/deploy-playbook.yaml
```

This builds the new image (with `psycopg`/`dj-database-url`), starts the
container with `DJANGO_DATABASE_URL` instead of the old SQLite mount, and
runs `manage.py migrate` inside it -- which creates all tables fresh in
Postgres, including default content types and permissions.

## 5. Load the data

Back on the server:

```
docker cp ~/clarice-data.json clarice:/tmp/clarice-data.json
docker exec clarice ./manage.py loaddata /tmp/clarice-data.json
```

## 6. Verify

- Log into `/admin/` and confirm lists, tasks, and user accounts look
  right (spot-check counts against what you remember, or diff against
  `clarice-data.json`).
- Log in as a normal user and confirm the dashboard/agenda renders.
- Tail logs for errors: `docker logs -f clarice`.

## 7. Clean up

Once you're confident the cutover worked (give it a day or two of normal
use):

```
rm ~/db.sqlite3 ~/clarice-data.json   # on the server
```

Keep the `scp`'d backup copy of `clarice-data.json` somewhere safe for a
while longer, just in case.

## Rollback

If something goes wrong before step 7's cleanup, the old `~/db.sqlite3` on
the server is untouched. Revert the code changes (`git checkout` the
previous commit), rebuild, and redeploy with the old playbook -- your data
is still there.

## Notes from design/subtasks-plan.md

This migration was already scoped out in `design/subtasks-plan.md` (Step 2)
before this change -- worth reading in full, but the load-bearing points:

- The migration history is all `RunPython`, no SQLite-specific `RunSQL` or
  PRAGMAs, so it replays cleanly on an empty Postgres database.
- `reset_test_database` (used by the functional test suite) is guarded by
  both `DJANGO_ENVIRONMENT=test` and `ALLOW_DATABASE_FLUSH=1` -- production
  always sets `DJANGO_ENVIRONMENT=production`, so this stays refused
  regardless of database engine. Confirmed unchanged by this migration.
- **This cluster currently uses the default `doadmin` credential**, which
  can connect to every database on the cluster, not just `clarice`. That's
  fine as the only project on it. If a second project ever shares this
  cluster, create a restricted per-database user for each one first --
  see "One cluster, several projects" in `design/subtasks-plan.md`.
- `CONN_MAX_AGE=600` is set in `settings.py` because connection reuse
  matters far more over a network round trip than it did with a local
  SQLite file.
- If connection pooling (PgBouncer, built into DO's managed offering) is
  ever turned on in transaction mode, `DISABLE_SERVER_SIDE_CURSORS = True`
  needs to be added to `settings.py` -- not needed for a direct connection,
  which is what this migration sets up.
