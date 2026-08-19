#!/usr/bin/env bash
# Does a restored database still enforce what the live one enforces?
#
# The drill in MIGRATION.md compared row counts and `django_migrations`, which
# is a check on *data*. Everything below is DDL, and a restore that came back
# without it would pass that comparison exactly: the migration rows are data and
# say the migration ran, while the trigger it created is not.
#
# The append-only guarantee is the one that matters most. `mind.ActivityEvent`
# refuses UPDATE and DELETE by trigger, `accounts.services.purge_account` is the
# single exemption, and `mind/tests/test_erasure.py` fails on purpose if anyone
# widens it. A restored cluster that silently accepted an UPDATE on that table
# would keep every one of those tests green -- they run in CI against a database
# built from migrations, not against the restore.
#
# **Behaviour, not presence, wherever it can be.** Asserting a trigger exists in
# `pg_trigger` proves a row in a catalogue. Attempting the UPDATE and requiring
# it to fail proves the guarantee. Both are here, because a missing trigger and
# a trigger that no longer fires are different faults and only the second one
# survives a catalogue check.
#
# Everything runs inside a transaction that is rolled back, so this is safe
# against any database -- including, if you want to prove the check itself
# works, production.
#
# Usage:
#   ./check-restore-integrity.sh 'postgresql://user:pass@host:port/dbname?sslmode=require'
#
# Exits non-zero on the first failure, and says which guarantee went.

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

failures=0

report() {
  local ok=$1 what=$2
  if [[ "$ok" == "yes" ]]; then
    printf '  ok    %s\n' "$what"
  else
    printf '  FAIL  %s\n' "$what"
    failures=$((failures + 1))
  fi
}

query() {
  psql "$DSN" -tA -c "$1" 2>/dev/null
}

echo "Checking what this database still enforces:"

# --- Extensions -------------------------------------------------------------
# mind's migrations CreateExtension("vector"). Without it the SentenceEmbedding
# column has no type and the HNSW index has nothing to index.
got=$(query "SELECT count(*) FROM pg_extension WHERE extname = 'vector'")
[[ "$got" == "1" ]] && report yes "vector extension present" \
                    || report no  "vector extension present (found: ${got:-error})"

# --- Triggers, by name ------------------------------------------------------
for trigger in \
  mind_concept_merge_depth_one_trigger \
  mind_member_of_depth_one_trigger \
  mind_activity_event_no_update
do
  got=$(query "SELECT count(*) FROM pg_trigger WHERE tgname = '$trigger' AND NOT tgisinternal")
  [[ "$got" == "1" ]] && report yes "trigger $trigger" \
                      || report no  "trigger $trigger (found: ${got:-error})"
done

# --- The append-only guarantee, exercised -----------------------------------
# A trigger present in the catalogue but disabled (ALTER TABLE ... DISABLE
# TRIGGER) passes the check above and enforces nothing. This one writes a row,
# tries to change it, and requires the attempt to be refused -- then rolls the
# whole thing back.
appended=$(psql "$DSN" -tA <<'SQL' 2>&1
BEGIN;
DO $$
DECLARE refused boolean := false;
BEGIN
    BEGIN
        UPDATE mind_activityevent SET actor = actor WHERE id IN (
            SELECT id FROM mind_activityevent LIMIT 1
        );
    EXCEPTION WHEN OTHERS THEN
        refused := true;
    END;
    IF (SELECT count(*) FROM mind_activityevent) = 0 THEN
        RAISE NOTICE 'EMPTY';
    ELSIF refused THEN
        RAISE NOTICE 'REFUSED';
    ELSE
        RAISE NOTICE 'ACCEPTED';
    END IF;
END $$;
ROLLBACK;
SQL
)
case "$appended" in
  *REFUSED*) report yes "an UPDATE on the activity log is refused" ;;
  *EMPTY*)   printf '  skip  activity log is empty; presence checked above, behaviour not\n' ;;
  *ACCEPTED*) report no "an UPDATE on the activity log is refused (it was ACCEPTED)" ;;
  *)         report no  "an UPDATE on the activity log is refused (check errored)" ;;
esac

# --- Constraints Django cannot express the same way on SQLite ---------------
# nulls_distinct=False, "Postgres 15+ only" per its own comment. A restore onto
# an older engine, or a hand-rebuilt schema, loses the NULLS NOT DISTINCT half
# while keeping a same-named constraint.
got=$(query "SELECT count(*) FROM pg_constraint WHERE conname = 'mention_unique'")
[[ "$got" == "1" ]] && report yes "constraint mention_unique" \
                    || report no  "constraint mention_unique (found: ${got:-error})"

got=$(query "SELECT indnullsnotdistinct FROM pg_index i
             JOIN pg_class c ON c.oid = i.indexrelid
             WHERE c.relname = 'mention_unique'")
[[ "$got" == "t" ]] && report yes "mention_unique treats NULLs as equal" \
                    || report no  "mention_unique treats NULLs as equal (found: ${got:-error})"

echo
if [[ "$failures" -gt 0 ]]; then
  # stdout, not stderr: the two interleave unpredictably when this runs under
  # `docker exec` or a CI log, and a summary that prints before the last check
  # reads as if it belonged to an earlier line. The exit code is what a caller
  # should branch on anyway.
  echo "$failures guarantee(s) missing. This restore is not equivalent to the original."
  exit 1
fi
echo "All checked guarantees are intact."
