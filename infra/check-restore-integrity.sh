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

# --- The task core's constraints --------------------------------------------
# Everything above belongs to the knowledge core. These are the task core's, and
# until August 19 this script checked none of them -- so a restore that came
# back having lost every one would have printed "All checked guarantees are
# intact." That is health.py's own objection turned on this script: a check
# narrower than the failures it watches for reports healthy through the ones it
# forgot.

# Two CHECK constraints. `convalidated` is the half a presence check misses: a
# constraint added NOT VALID is present in the catalogue and does enforce new
# rows, while silently tolerating every row already there -- which after a
# restore is all of them.
for constraint in valid_item_status_timestamps valid_project_completion
do
  got=$(query "SELECT count(*) FROM pg_constraint
               WHERE conname = '$constraint' AND contype = 'c' AND convalidated")
  [[ "$got" == "1" ]] && report yes "constraint $constraint, validated" \
                      || report no  "constraint $constraint, validated (found: ${got:-error})"
done

# Three partial unique constraints -- and they are **not** in pg_constraint with
# the two above. Django compiles `UniqueConstraint(condition=...)` to a bare
# partial unique index, so a check that looked for them beside the CHECKs would
# report all three missing on a perfectly good database.
#
# `indpred IS NOT NULL` is the part worth explaining: the WHERE clause *is* the
# constraint. Rebuilt without it the index is still present, still unique and
# still valid, while now forbidding a duplicate among archived rows -- which the
# application deliberately allows, since archiving a task and writing it again
# is an ordinary thing to do.
for index in unique_active_item unique_active_arealess_item unique_open_checklist_step_text
do
  got=$(query "SELECT count(*) FROM pg_index i JOIN pg_class c ON c.oid = i.indexrelid
               WHERE c.relname = '$index'
                 AND i.indisunique AND i.indisvalid AND i.indisready
                 AND i.indpred IS NOT NULL")
  [[ "$got" == "1" ]] && report yes "partial unique index $index" \
                      || report no  "partial unique index $index (found: ${got:-error})"
done

# --- The duplicate-task guarantee, exercised --------------------------------
# The catalogue checks above answer presence and validity. This answers whether
# the thing actually refuses a duplicate on the data that came back, which is
# the guarantee a person would feel: `unique_active_item` is what stops a phone
# retrying a share from writing the note twice.
#
# The row is cloned through jsonb rather than by naming columns, so adding a
# column to lists_item does not quietly turn this check into a syntax error --
# and the clone takes a fresh id so the refusal that matters is the unique
# violation rather than a primary-key collision.
#
# Verified in both directions before being trusted, on a local database inside a
# transaction that was rolled back: with the index present the insert was
# refused, and with `DROP INDEX unique_active_item` first it was accepted. A
# probe that cannot fail proves nothing.
duplicate=$(psql "$DSN" -tA <<'SQL' 2>&1
BEGIN;
DO $$
DECLARE refused boolean := false; candidates int;
BEGIN
    SELECT count(*) INTO candidates
      FROM lists_item WHERE status <> 'archived' AND list_id IS NOT NULL;
    IF candidates = 0 THEN
        RAISE NOTICE 'EMPTY';
        RETURN;
    END IF;
    BEGIN
        INSERT INTO lists_item
        SELECT (jsonb_populate_record(
                   NULL::lists_item,
                   to_jsonb(t) || jsonb_build_object('id', (SELECT max(id) + 1 FROM lists_item))
               )).*
          FROM lists_item t
         WHERE t.status <> 'archived' AND t.list_id IS NOT NULL
         LIMIT 1;
    EXCEPTION WHEN unique_violation THEN
        refused := true;
    END;
    IF refused THEN RAISE NOTICE 'REFUSED'; ELSE RAISE NOTICE 'ACCEPTED'; END IF;
END $$;
ROLLBACK;
SQL
)
case "$duplicate" in
  *REFUSED*)  report yes "a duplicate active task is refused" ;;
  *EMPTY*)    printf '  skip  no filed active task to duplicate; index checked above, behaviour not\n' ;;
  *ACCEPTED*) report no  "a duplicate active task is refused (it was ACCEPTED)" ;;
  *)          report no  "a duplicate active task is refused (check errored)" ;;
esac

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
