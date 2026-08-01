#!/usr/bin/env bash
# Answers one question: when did this cluster last successfully back up?
#
# "We moved to managed Postgres" is not the same claim as "backups work",
# and the gap between them is invisible until you need a restore. The full
# drill (see MIGRATION.md, "Restore drill") proves recovery end to end, but
# it costs a cluster and half an hour. This is the cheap check you can run
# any time in between, so a silently broken backup surfaces on its own
# rather than the day you need it.
#
# Prerequisites (run on your own machine, not on the server):
#   - doctl installed and authenticated: `doctl auth init`
#
# Usage:
#   ./check-backup-freshness.sh [cluster-name] [max-age-hours]
#
# Defaults to the live cluster and a 48-hour threshold: DigitalOcean takes
# a daily backup, so 48 hours is one missed day plus room for the window
# drifting, and anything beyond that is a real signal rather than noise.
#
# Exit status is the point -- 0 fresh, 1 stale or missing -- so this drops
# straight into cron or a CI schedule without anyone reading the output.

set -euo pipefail

CLUSTER_NAME="${1:-db-pgsql-nyc1-16061}"
MAX_AGE_HOURS="${2:-48}"

CLUSTER_ID=$(doctl databases list --format ID,Name --no-header \
  | awk -v n="$CLUSTER_NAME" '$2==n{print $1}')

if [ -z "$CLUSTER_ID" ]; then
  echo "FAIL: no cluster named '$CLUSTER_NAME' on this account." >&2
  exit 1
fi

# Newest first is not guaranteed by the API, so sort rather than assume.
# The column is `Created`, not `CreatedAt` -- the latter silently yields
# "<nil>" for every row rather than erroring, which reads exactly like a
# cluster with no backups.
LATEST=$(doctl databases backups "$CLUSTER_ID" --format Created --no-header \
  | sort -r | head -1)

if [ -z "$LATEST" ]; then
  # The case this script exists for: the cluster is up, the app is fine,
  # and there is nothing to restore from.
  echo "FAIL: '$CLUSTER_NAME' reports no backups at all." >&2
  exit 1
fi

# doctl prints Go's time format -- "2026-07-31 06:56:11 +0000 UTC" -- whose
# trailing zone name after the numeric offset is something `date` refuses
# to parse. Drop it rather than reformatting the whole string.
LATEST_EPOCH=$(date -u -d "${LATEST% UTC}" +%s)
NOW_EPOCH=$(date -u +%s)
AGE_HOURS=$(( (NOW_EPOCH - LATEST_EPOCH) / 3600 ))

echo "Cluster:      $CLUSTER_NAME ($CLUSTER_ID)"
echo "Last backup:  $LATEST"
echo "Age:          ${AGE_HOURS}h (threshold ${MAX_AGE_HOURS}h)"

if [ "$AGE_HOURS" -gt "$MAX_AGE_HOURS" ]; then
  echo "FAIL: last backup is older than ${MAX_AGE_HOURS}h." >&2
  exit 1
fi

echo "OK: backups are current."
