#!/usr/bin/env bash
# Creates a restricted, per-database Postgres user on Clarice's DigitalOcean
# managed cluster, so the app's live credential can no longer read or write
# every other database sharing the cluster -- see "One cluster, several
# projects" in design/subtasks-plan.md and roadmap item A1 in
# design/roadmap.md.
#
# The cluster was provisioned with `doadmin` (see provision-postgres.sh),
# which by default can connect to *every* database on the cluster, and
# that's the credential DJANGO_DATABASE_URL has used since the Postgres
# cutover (see MIGRATION.md). This script creates a new role scoped to
# exactly one database, revokes its CONNECT privilege on every other
# database on the cluster, and prints a DJANGO_DATABASE_URL for that role.
#
# This script only provisions the new credential and prints it -- it does
# NOT touch the app's live credential. Swapping ~/.db-connection-url on the
# server and redeploying is a separate, deliberate step (see the printed
# "Next" instructions at the end, and MIGRATION.md).
#
# Prerequisites (run on your own machine, not the server):
#   - doctl installed and authenticated: `doctl auth init`
#   - psql installed locally -- this script shells out to it to run the
#     REVOKE/GRANT statements; doctl has no equivalent for that.
#
# Usage:
#   ./restrict-database-user.sh <username> <database>
#
# Example:
#   ./restrict-database-user.sh clarice_app clarice
#
# Not idempotent on the create step: doctl has no way to fetch an existing
# user's password back out, so re-running this against a username that
# already exists fails fast at `doctl databases user create` with DO's own
# "already exists" error -- drop the user first or pick a new name.

set -euo pipefail

USERNAME="${1:?Usage: $0 <username> <database>}"
DB_NAME="${2:?Usage: $0 <username> <database>}"
CLUSTER_NAME="${CLUSTER_NAME:-clarice-db}"

echo "==> Looking up cluster '$CLUSTER_NAME'..." >&2
CLUSTER_ID=$(doctl databases list --format ID,Name --no-header \
  | awk -v n="$CLUSTER_NAME" '$2==n{print $1}')

if [ -z "$CLUSTER_ID" ]; then
  echo "Could not find a cluster named '$CLUSTER_NAME'." >&2
  echo "Run 'doctl databases list' to see exact names, or set CLUSTER_NAME=..." >&2
  exit 1
fi

if ! doctl databases db list "$CLUSTER_ID" --format Name --no-header | grep -qx "$DB_NAME"; then
  echo "Database '$DB_NAME' does not exist on cluster '$CLUSTER_NAME'." >&2
  echo "Run 'doctl databases db list $CLUSTER_ID' to see what's there." >&2
  exit 1
fi

echo "==> Creating restricted user '$USERNAME'..." >&2
doctl databases user create "$CLUSTER_ID" "$USERNAME"

PASSWORD=$(doctl databases user get "$CLUSTER_ID" "$USERNAME" --format Password --no-header)
HOST=$(doctl databases connection "$CLUSTER_ID" --format Host --no-header)
PORT=$(doctl databases connection "$CLUSTER_ID" --format Port --no-header)
ADMIN_URI=$(doctl databases connection "$CLUSTER_ID" --format URI --no-header)

echo "==> Revoking CONNECT on every other database on this cluster..." >&2
psql "$ADMIN_URI" -v ON_ERROR_STOP=1 <<SQL
DO \$\$
DECLARE
  other_db text;
BEGIN
  FOR other_db IN
    SELECT datname FROM pg_database
    WHERE datistemplate = false AND datname <> '$DB_NAME'
  LOOP
    EXECUTE format('REVOKE CONNECT ON DATABASE %I FROM %I', other_db, '$USERNAME');
  END LOOP;
END
\$\$;

GRANT CONNECT ON DATABASE $DB_NAME TO $USERNAME;
SQL

echo "==> Granting schema privileges on '$DB_NAME'..." >&2
DB_URI=$(echo "$ADMIN_URI" | sed "s#/defaultdb?#/$DB_NAME?#")

psql "$DB_URI" -v ON_ERROR_STOP=1 <<SQL
GRANT USAGE, CREATE ON SCHEMA public TO $USERNAME;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO $USERNAME;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO $USERNAME;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO $USERNAME;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO $USERNAME;
SQL

APP_URI="postgresql://$USERNAME:$PASSWORD@$HOST:$PORT/$DB_NAME?sslmode=require"

echo >&2
echo "==> Done. '$USERNAME' can now only connect to '$DB_NAME' on this cluster." >&2
echo >&2
echo "DJANGO_DATABASE_URL:"
echo "$APP_URI"
echo >&2
echo "Next (see MIGRATION.md and design/roadmap.md item A1):" >&2
echo "  1. SSH to the production droplet." >&2
echo "  2. umask 077 && echo -n '$APP_URI' > ~/.db-connection-url" >&2
echo "  3. Redeploy (ansible-playbook -i <inventory> infra/deploy-playbook.yaml)" >&2
echo "     so the container picks up the new credential." >&2
echo "  4. Verify: log into /admin/, confirm data looks right, tail" >&2
echo "     'docker logs clarice' for connection errors." >&2
echo "  5. Once confirmed working, doadmin goes back to being an" >&2
echo "     admin-only credential -- it's no longer what the app connects" >&2
echo "     with day to day." >&2
