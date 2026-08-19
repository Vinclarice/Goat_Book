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
#    rather than opening the cluster firewall to do it. The `table|count`
#    format and the ordering are deliberate: they match infra/table-counts.sh
#    exactly, so step 4 is a diff rather than a reading exercise.
ssh <user>@<droplet> 'docker exec -i clarice python manage.py shell' <<'EOF' > live-counts.txt
from django.db import connection
with connection.cursor() as c:
    c.execute("SELECT table_name FROM information_schema.tables "
              "WHERE table_schema='public' AND table_type='BASE TABLE' "
              "ORDER BY table_name")
    for (t,) in c.fetchall():
        c.execute(f'SELECT COUNT(*) FROM "{t}"')
        print(f"{t}|{c.fetchone()[0]}")
EOF

# 2. Restore the whole cluster into a scratch one. Omitting a timestamp
#    takes the most recent backup.
doctl databases create clarice-restore-drill \
  --restore-from-cluster-name db-pgsql-nyc1-16061 \
  --region nyc1 --size db-s-1vcpu-1gb --num-nodes 1 --engine pg --version 18

# 3. Lock it down before using it -- a fresh cluster with no rules is open
#    to the internet, which is the exact hole roadmap item A5 closed.
doctl databases firewalls append <new-id> --rule ip_addr:<your-ip>

# 4. Compare every table's row count against step 1. Connect to Clarice_todo,
#    NOT defaultdb -- that mistake looks exactly like a failed restore.
#    Empty output is a pass; anything printed is a table that did not come back
#    whole, and django_migrations is in there with the rest.
infra/table-counts.sh 'postgresql://user:pass@<new-host>:<port>/Clarice_todo?sslmode=require' \
  > restored-counts.txt
diff live-counts.txt restored-counts.txt && echo "row counts match"

# 5. Then check what the restore still *enforces*, which step 4 cannot see.
#    Row counts and django_migrations are data; the extension, the append-only
#    and depth-one triggers, mention_unique's NULLS NOT DISTINCT and the task
#    core's five constraints are DDL. A restore missing every one of them
#    passes step 4 exactly, because the migration rows say the migration ran
#    and the trigger it created is not a row.
infra/check-restore-integrity.sh   'postgresql://user:pass@<new-host>:<port>/Clarice_todo?sslmode=require'

# 6. Tear it down. It bills by the hour.
doctl databases delete <new-id> --force
```

**Step 5 checks behaviour, not just presence.** A trigger can be in
`pg_trigger` and disabled, which enforces nothing — verified by disabling
`mind_activity_event_no_update` on a local database and watching the name check
pass while the UPDATE it should refuse was accepted. The script writes nothing:
its one write is inside a transaction it rolls back, so it is safe to point at
production if you want to prove the check itself works.

**Run August 1, 2026 (roadmap item A2). Result: passed.** All 18 tables
matched the live cluster exactly — `lists_item` 24, `lists_list` 17,
`accounts_user` 3, `django_migrations` 53 — on Postgres 18.4, restored
from the 2026-07-31 06:56 UTC backup. Provisioning the clone took about
seven minutes end to end.

**That pass is narrower than it reads, and the schema has moved a long way under
it.** It compared row counts and `django_migrations` and nothing else, across 18
tables at 53 migrations. There are 46 tables now. Since August 1 the database has
gained the `vector` extension, `ActivityEvent`'s append-only triggers, the
depth-one triggers and the knowledge core's tables — none of which is a row, and
all of which a count-only drill reports as fine before failing on the first
write.

**Closed August 19, 2026, and this paragraph's own instruction is superseded
rather than done.** It asked for `\dx` and `information_schema.triggers` at step
4. Step 5 answers both, and answers them *behaviourally* — attempting the write
the guarantee should refuse, rather than reading a name out of a catalogue that
a disabled trigger satisfies just as well. Do not add the presence checks; they
would be the weaker half of something already covered.

What did need doing, and was: step 5 checked the knowledge core's DDL and none
of the task core's, so a restore that lost `unique_active_item`,
`unique_active_arealess_item`, `unique_open_checklist_step_text`,
`valid_item_status_timestamps` and `valid_project_completion` printed *"All
checked guarantees are intact."* All five are checked now, and step 4 is a diff
rather than a comparison by eye over forty-six tables at the end of a billed
hour.

**So the next run is the first that can honestly be called a pass**, and what it
must record is here rather than left to memory: the migration count and engine
version it ran at, that step 4's diff was empty, and that step 5 exited zero.

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
