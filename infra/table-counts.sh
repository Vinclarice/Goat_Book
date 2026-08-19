#!/usr/bin/env bash
# Every table in `public` and how many rows it holds, one per line, sorted.
#
# This exists to be diffed. MIGRATION.md's restore drill compared the live
# cluster against the restored one by eye at step 4 -- eighteen tables when it
# was written, forty-six now, at the end of a scratch cluster billed by the
# hour. That was the one manual step in a procedure whose other steps are
# scripted, and it was the step most likely to be skimmed.
#
# **Counts only, deliberately.** What a restore *enforces* -- extensions,
# triggers, constraints -- is not a row and cannot be counted;
# check-restore-integrity.sh answers that half, and a restore missing all of it
# matches this output exactly.
#
# The format is `table|count` so two runs diff cleanly, and the ordering comes
# from the query rather than from a pipe, so the same DSN twice gives
# byte-identical output.
#
# Counting is one query rather than one per table: query_to_xml runs the count
# inside the row it belongs to, so this stays a single round trip. The estimates
# in pg_class.reltuples would be faster and are worthless here -- they drift
# with vacuum, and "did every row come back" is the entire question.
#
# Usage:
#   ./table-counts.sh 'postgresql://user:pass@host:port/dbname?sslmode=require'
#
# For the live side the cluster firewall usually forbids a direct connection;
# MIGRATION.md carries the equivalent read through the droplet's Django shell,
# which prints this same format on purpose.

set -uo pipefail

DSN="${1:-}"
if [[ -z "$DSN" ]]; then
  echo "usage: $0 <postgres-dsn>" >&2
  exit 2
fi

if ! command -v psql >/dev/null 2>&1; then
  echo "psql is not installed; this needs the postgres client." >&2
  exit 2
fi

psql "$DSN" -tA -F'|' -v ON_ERROR_STOP=1 -c "
SELECT table_name,
       (xpath('/row/cnt/text()', query_to_xml(
           format('SELECT count(*) AS cnt FROM %I.%I', table_schema, table_name),
           false, true, '')))[1]::text::bigint
  FROM information_schema.tables
 WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
 ORDER BY table_name;
"
