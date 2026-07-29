#!/usr/bin/env bash
# Provisions a DigitalOcean Managed PostgreSQL cluster for Clarice, in the
# same region as an existing droplet, and locks its firewall down to that
# droplet only.
#
# Prerequisites (run on your own machine, not on the server):
#   - doctl installed and authenticated: `doctl auth init`
#   - the production droplet already exists (`doctl compute droplet list`)
#
# Usage:
#   ./provision-postgres.sh <production-droplet-name>
#
# Example:
#   ./provision-postgres.sh clarice-prod
#
# Idempotent: if a cluster named $CLUSTER_NAME already exists (e.g. you're
# adding a second project to a cluster you already provisioned), this reuses
# it instead of creating a new one -- DigitalOcean's own guidance is to
# share one cluster across small apps rather than pay per cluster. Override
# with `CLUSTER_NAME=my-shared-db ./provision-postgres.sh ...`.
#
# NOTE on multi-project clusters: by default every database user on a DO
# Postgres cluster can connect to *every* database in that cluster, not
# just the one it "belongs to". That's fine while Clarice is the only
# thing on this cluster. The day a second project joins it, come back and
# create per-database restricted users (see design/subtasks-plan.md, "One
# cluster, several projects") instead of continuing to share the doadmin
# credential this script uses today.
#
# On success this prints a DJANGO_DATABASE_URL value. Copy it, then on the
# server run:
#   umask 077 && echo -n '<the URL printed below>' > ~/.db-connection-url
#
# See MIGRATION.md for the full cutover procedure (this script only creates
# the empty cluster -- it does not move any data).

set -euo pipefail

DROPLET_NAME="${1:?Usage: $0 <production-droplet-name>}"
CLUSTER_NAME="${CLUSTER_NAME:-clarice-db}"
DB_NAME="${DB_NAME:-clarice}"
ENGINE_VERSION="${ENGINE_VERSION:-17}"
SIZE="${SIZE:-db-s-1vcpu-1gb}"   # cheapest managed Postgres tier; raise if needed

echo "==> Looking up droplet '$DROPLET_NAME'..." >&2
DROPLET_ID=$(doctl compute droplet list --format ID,Name --no-header \
  | awk -v n="$DROPLET_NAME" '$2==n{print $1}')

if [ -z "$DROPLET_ID" ]; then
  echo "Could not find a droplet named '$DROPLET_NAME'." >&2
  echo "Run 'doctl compute droplet list' to see exact names." >&2
  exit 1
fi

REGION=$(doctl compute droplet get "$DROPLET_ID" --format Region --no-header)
echo "==> Droplet '$DROPLET_NAME' ($DROPLET_ID) is in region '$REGION'" >&2

CLUSTER_ID=$(doctl databases list --format ID,Name --no-header \
  | awk -v n="$CLUSTER_NAME" '$2==n{print $1}')

if [ -n "$CLUSTER_ID" ]; then
  echo "==> Reusing existing cluster '$CLUSTER_NAME' ($CLUSTER_ID)" >&2
else
  echo "==> Creating Postgres $ENGINE_VERSION cluster '$CLUSTER_NAME' ($SIZE) in $REGION..." >&2
  doctl databases create "$CLUSTER_NAME" \
    --engine pg \
    --version "$ENGINE_VERSION" \
    --region "$REGION" \
    --size "$SIZE" \
    --num-nodes 1 \
    --wait

  CLUSTER_ID=$(doctl databases list --format ID,Name --no-header \
    | awk -v n="$CLUSTER_NAME" '$2==n{print $1}')
fi

echo "==> Creating database '$DB_NAME'..." >&2
doctl databases db create "$CLUSTER_ID" "$DB_NAME"

echo "==> Restricting network access to droplet '$DROPLET_NAME' only..." >&2
doctl databases firewalls append "$CLUSTER_ID" --rule "droplet:$DROPLET_ID"

echo "==> Building connection URL for database '$DB_NAME'..." >&2
BASE_URI=$(doctl databases connection "$CLUSTER_ID" --format URI --no-header)
# The base URI points at the cluster's default database ("defaultdb");
# swap in the one we just created.
APP_URI=$(echo "$BASE_URI" | sed "s#/defaultdb?#/$DB_NAME?#")

echo >&2
echo "==> Done. Cluster '$CLUSTER_NAME' ($CLUSTER_ID) is up, reachable only from '$DROPLET_NAME'." >&2
echo >&2
echo "DJANGO_DATABASE_URL:"
echo "$APP_URI"
echo >&2
echo "Next: on the server, run:" >&2
echo "  umask 077 && echo -n '$APP_URI' > ~/.db-connection-url" >&2
echo "Then follow MIGRATION.md to move the data and deploy." >&2
