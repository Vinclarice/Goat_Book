# Moving Clarice's database to DigitalOcean Managed PostgreSQL

**This cutover has been performed.** Production runs `Clarice_todo` on the
managed cluster `db-pgsql-nyc1-16061`. The steps below are kept as the record of
how it was done and as the procedure if it is ever done again; the live parts of
this file are the **restore drill** and the **notes** at the end.

It covered the one-time move from the SQLite file on the production droplet to a
DigitalOcean Managed PostgreSQL cluster. `settings.py` reads
`DJANGO_DATABASE_URL` in production (via `dj-database-url`), `requirements.txt`
has `psycopg`, and `infra/deploy-playbook.yaml` wires that env var from
`~/.db-connection-url` on the server instead of bind-mounting a SQLite file. Do
it at a quiet time -- there's a few minutes of downtime, and a small window where
writes made after the data dump wouldn't carry over.

## 1. Provision the cluster (run locally, not on the server)

Requires `doctl` installed and authenticated (`doctl auth init`).

```
./infra/provision-postgres.sh <production-droplet-name>
```

Find the exact droplet name with `doctl compute droplet list` if you don't
have it memorized. The script creates a `db-s-1vcpu-1gb` Postgres 18
cluster in the same region as that droplet, creates a `clarice` database,
and restricts the cluster's firewall to that droplet only. It prints a
`DJANGO_DATABASE_URL` value at the end -- copy it.

## 2. Save the connection URL on the server

SSH into the production droplet, then:

```
umask 077 && echo -n 'postgresql://...the URL from step 1...' > ~/.db-connection-url
```

The deploy playbook reads this file the same way it already reads
`~/.resend-api-key` -- it's never committed or passed on the CLI.

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
ansible-playbook -i infra/production-inventory.ini infra/deploy-playbook.yaml -K
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

Log into `/admin/` and check lists, tasks and accounts against
`clarice-data.json`; log in as a normal user and confirm the dashboard renders;
tail `docker logs -f clarice` for errors.

## 7. Clean up

After a day or two of normal use, `rm ~/db.sqlite3 ~/clarice-data.json` on the
server. Keep the `scp`'d copy of `clarice-data.json` somewhere safe for longer.

## Restore drill

Managed Postgres was chosen partly so backups would be someone else's problem,
which is only true once a restore has actually been performed. This is the
procedure, and the record of it having been run.

**Backups are cluster-wide, not per-database.** Recovering Clarice means
restoring the *whole* cluster to a new one and taking `Clarice_todo` out of
it — there is no single-database restore, and testing one would prove
nothing about the procedure a real incident forces. Run the drill the
awkward way or don't bother.

```bash
# 1. What does the live data look like right now? Read it from the droplet
#    rather than opening the cluster firewall to do it.
ssh <user>@<droplet> 'docker exec -i clarice python manage.py shell' <<'EOF'
from django.db import connection
with connection.cursor() as c:
    c.execute("SELECT table_name FROM information_schema.tables "
              "WHERE table_schema='public' ORDER BY table_name")
    for (t,) in c.fetchall():
        c.execute(f'SELECT COUNT(*) FROM "{t}"')
        print(t, c.fetchone()[0])
EOF

# 2. Restore the whole cluster into a scratch one. Omitting a timestamp
#    takes the most recent backup.
doctl databases create clarice-restore-drill \
  --restore-from-cluster-name db-pgsql-nyc1-16061 \
  --region nyc1 --size db-s-1vcpu-1gb --num-nodes 1 --engine pg --version 18

# 3. Lock it down before using it -- a fresh cluster with no rules is open
#    to the internet, which is the exact hole roadmap item A5 closed.
doctl databases firewalls append <new-id> --rule ip_addr:<your-ip>

# 4. Compare row counts per table and django_migrations against step 1,
#    connecting to Clarice_todo (not defaultdb) on the restored cluster.

# 5. Tear it down. It bills by the hour.
doctl databases delete <new-id> --force
```

**Run August 1, 2026 (roadmap item A2). Result: passed.** All 18 tables
matched the live cluster exactly — `lists_item` 24, `lists_list` 17,
`accounts_user` 3, `django_migrations` 53 — on Postgres 18.4, restored
from the 2026-07-31 06:56 UTC backup. Provisioning the clone took about
seven minutes end to end.

**That pass is narrower than it reads, and the schema has moved under it.** Step
4 compares row counts per table and `django_migrations` — nothing else. Since
August 1 the database has gained the `vector` extension, `ActivityEvent`'s
append-only triggers, and the knowledge core's tables; the migration count is 74,
not 53. A restore that came back without the extension or without the triggers
would pass this drill exactly as written and then fail on the first write. Before
calling the next run a pass, add explicit checks for extensions (`\dx`) and
triggers (`information_schema.triggers`) to step 4.

Three things worth knowing before the next one:

- **The restore inherits the source cluster's trusted sources.** The clone
  came up already carrying the droplet firewall rule, so A5's lockdown
  survives a recovery instead of needing to be redone under pressure. It
  does *not* mean a restored cluster is safe by default — one created from
  scratch has no rules at all.
- **The restored cluster's default database is `defaultdb`.** The URI
  `doctl databases connection` prints points there, not at `Clarice_todo`;
  connect to the wrong one and you will find an empty database and think
  the restore failed.
- **Retention is DigitalOcean's, not ours.** Daily backups, roughly one
  per day (observed 2026-07-29 22:59, 07-30 10:59, 07-31 06:56 UTC), kept
  for 7 days on this plan. That is the real answer to "how far back can a
  bad migration be undone" — a week, not indefinitely.

Between drills, `infra/check-backup-freshness.sh` answers the cheap half
of the question — when did this cluster last back up successfully — and
exits non-zero if the answer is "too long ago" or "never", so it can run
unattended.

## Rollback

If something goes wrong before step 7's cleanup, the old `~/db.sqlite3` on
the server is untouched. Revert the code changes (`git checkout` the
previous commit), rebuild, and redeploy with the old playbook -- your data
is still there.

## Notes

Scoped out in `design/subtasks-plan.md` (Step 2), which is now a stub -- so these
are the load-bearing points, kept here rather than cited:

- The migration history is all `RunPython`, no SQLite-specific `RunSQL` or
  PRAGMAs, so it replays cleanly on an empty Postgres database.
- **`ALLOW_DATABASE_FLUSH` is not a guard, and this file claimed it was.** It
  gated a `reset_test_database` command that no longer exists. The variable is
  still set to `0` in the `Dockerfile` and passed through by
  `infra/deploy-playbook.yaml`, but **nothing reads it** -- three references set
  it, zero consume it (checked August 16, 2026). What actually protects
  production is that there is no code path that flushes a database at all; the
  functional suite uses Django's ordinary test-database teardown. Either delete
  the variable or give it a reader, but do not cite it as protection.
- **Ground truth, since the examples above drifted from it**: the cluster is
  `db-pgsql-nyc1-16061` (not `clarice-db`), the database is `Clarice_todo`
  (mixed case, not `clarice`), and the engine is Postgres 18 (not 17).
- **The cluster used the default `doadmin` credential** until July 31, 2026,
  when `infra/restrict-database-user.sh` cut production over to a restricted
  per-database credential (roadmap item A1). That cutover surfaced that `GRANT
  ALL PRIVILEGES` does not transfer table ownership -- existing tables stayed
  owned by `doadmin`, which broke the next `ALTER TABLE`-style migration until
  `REASSIGN OWNED BY doadmin TO clarice_app` ran. That statement is now a
  permanent step in the script, so a second project sharing this cluster won't
  hit the same thing.
- `CONN_MAX_AGE=600` is set in `settings.py` because connection reuse
  matters far more over a network round trip than it did with a local
  SQLite file.
- If connection pooling (PgBouncer, built into DO's managed offering) is
  ever turned on in transaction mode, `DISABLE_SERVER_SIDE_CURSORS = True`
  needs to be added to `settings.py` -- not needed for a direct connection,
  which is what this migration sets up.
