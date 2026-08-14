"""Invariants Django cannot express, plus the pgvector extension.

Three triggers live here because no declarative constraint can state them:

  * concept alias merge depth capped at 1
  * `member_of` hierarchy depth capped at 1
  * `ActivityEvent` is append-only

Each takes an advisory lock on the owner before checking. Without it, two
concurrent inserts each pass their own snapshot check and jointly produce
depth 2 — the check is individually correct and collectively wrong. At one
user there is no contention cost.

Capping depth at 1 rather than enforcing general acyclicity is deliberate:
deep hierarchies are already deferred, so this is that deferral expressed as
a constraint instead of a convention, and resolution stays a single join. When
hierarchies are un-deferred, this is what gets replaced — and the replacement
is a recursive-CTE trigger with the same locking discipline.
"""

from django.contrib.postgres.operations import CreateExtension
from django.db import migrations

CONCEPT_MERGE_DEPTH = """
CREATE OR REPLACE FUNCTION mind_concept_merge_depth_one() RETURNS trigger AS $$
BEGIN
    IF NEW.merged_into_id IS NULL THEN
        RETURN NEW;
    END IF;

    PERFORM pg_advisory_xact_lock(NEW.owner_id);

    IF EXISTS (SELECT 1 FROM mind_conceptcandidate
               WHERE id = NEW.merged_into_id AND merged_into_id IS NOT NULL) THEN
        RAISE EXCEPTION
            'concept % cannot merge into %, which is itself an alias',
            NEW.id, NEW.merged_into_id;
    END IF;

    IF EXISTS (SELECT 1 FROM mind_conceptcandidate WHERE merged_into_id = NEW.id) THEN
        RAISE EXCEPTION
            'concept % has aliases of its own and cannot become an alias', NEW.id;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER mind_concept_merge_depth_one_trigger
    BEFORE INSERT OR UPDATE OF merged_into_id ON mind_conceptcandidate
    FOR EACH ROW EXECUTE FUNCTION mind_concept_merge_depth_one();
"""

CONCEPT_MERGE_DEPTH_REVERSE = """
DROP TRIGGER IF EXISTS mind_concept_merge_depth_one_trigger ON mind_conceptcandidate;
DROP FUNCTION IF EXISTS mind_concept_merge_depth_one();
"""

MEMBER_OF_DEPTH = """
CREATE OR REPLACE FUNCTION mind_member_of_depth_one() RETURNS trigger AS $$
BEGIN
    IF NEW.relation <> 'member_of' THEN
        RETURN NEW;
    END IF;

    PERFORM pg_advisory_xact_lock(NEW.owner_id);

    IF EXISTS (SELECT 1 FROM mind_edge
               WHERE relation = 'member_of' AND to_node_id = NEW.from_node_id) THEN
        RAISE EXCEPTION
            'node % already has members and cannot become a member itself',
            NEW.from_node_id;
    END IF;

    IF EXISTS (SELECT 1 FROM mind_edge
               WHERE relation = 'member_of' AND from_node_id = NEW.to_node_id) THEN
        RAISE EXCEPTION
            'node % is already a member and cannot contain members', NEW.to_node_id;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER mind_member_of_depth_one_trigger
    BEFORE INSERT OR UPDATE ON mind_edge
    FOR EACH ROW EXECUTE FUNCTION mind_member_of_depth_one();
"""

MEMBER_OF_DEPTH_REVERSE = """
DROP TRIGGER IF EXISTS mind_member_of_depth_one_trigger ON mind_edge;
DROP FUNCTION IF EXISTS mind_member_of_depth_one();
"""

APPEND_ONLY_LOG = """
CREATE OR REPLACE FUNCTION mind_activity_event_append_only() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'activity_event is append-only (attempted %)', TG_OP;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER mind_activity_event_no_update
    BEFORE UPDATE OR DELETE ON mind_activityevent
    FOR EACH ROW EXECUTE FUNCTION mind_activity_event_append_only();
"""

APPEND_ONLY_LOG_REVERSE = """
DROP TRIGGER IF EXISTS mind_activity_event_no_update ON mind_activityevent;
DROP FUNCTION IF EXISTS mind_activity_event_append_only();
"""


class Migration(migrations.Migration):
    dependencies = [("mind", "0001_initial")]

    operations = [
        # Nothing uses vectors yet. Installed now so the embedding migration is
        # an ALTER rather than an extension request against production.
        CreateExtension("vector"),
        migrations.RunSQL(CONCEPT_MERGE_DEPTH, CONCEPT_MERGE_DEPTH_REVERSE),
        migrations.RunSQL(MEMBER_OF_DEPTH, MEMBER_OF_DEPTH_REVERSE),
        migrations.RunSQL(APPEND_ONLY_LOG, APPEND_ONLY_LOG_REVERSE),
    ]
