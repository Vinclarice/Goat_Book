"""Every invariant the schema claims, proved through the ORM.

These are regression guards, written after the models rather than before them —
said plainly, per practice. Their value is specific: the raw DDL was already
validated against Postgres directly, so what is under test here is that the
*Django* declarations actually reach the database. `nulls_distinct=False`
becoming real `NULLS NOT DISTINCT`, `GeneratedField` becoming a real generated
tsvector, and the trigger migration actually firing are all things that could
silently not happen.

Several of these encode a product principle rather than a mechanical rule, and
those are the ones worth keeping forever:
  * silence is not consent  -> the surfacing constraint
  * a dismissal is permanent -> the fingerprint constraint
  * the log is evidence      -> append-only
"""

import uuid
from datetime import datetime, timezone as dt_timezone

import pytest
from django.contrib.postgres.search import SearchQuery
from django.db import DatabaseError, IntegrityError, transaction
from django.utils import timezone

from mind.models import (
    ActivityEvent,
    ConceptCandidate,
    ConnectionHypothesis,
    Edge,
    EdgeRelation,
    HypothesisMember,
    InferenceOrigin,
    Mention,
    Node,
)

pytestmark = pytest.mark.django_db

UTC = dt_timezone.utc


def _at(iso: str):
    return datetime.fromisoformat(iso).replace(tzinfo=UTC)


# --------------------------------------------------------------------------
# Node identity and import provenance
# --------------------------------------------------------------------------


def test_duplicate_public_id_is_rejected(owner, make_node):
    """A retried capture must not become a second node."""
    node = make_node("learning Mondly again tonight")

    with pytest.raises(IntegrityError), transaction.atomic():
        Node.objects.create(
            owner=owner,
            public_id=node.public_id,
            original_content="a retry of the same capture",
            captured_at=_at("2026-01-01"),
            source=Node.Source.MOBILE,
        )


def test_import_key_requires_import_source(owner):
    with pytest.raises(IntegrityError), transaction.atomic():
        Node.objects.create(
            owner=owner,
            original_content="x",
            captured_at=_at("2026-01-01"),
            source=Node.Source.WEB,
            import_key="journal:42",
        )


def test_import_key_unique_per_owner_so_reimport_cannot_duplicate(owner):
    Node.objects.create(
        owner=owner,
        original_content="from the journal",
        captured_at=_at("2024-03-01"),
        source=Node.Source.IMPORT,
        import_key="journal:42",
    )
    with pytest.raises(IntegrityError), transaction.atomic():
        Node.objects.create(
            owner=owner,
            original_content="from the journal, imported twice",
            captured_at=_at("2024-03-01"),
            source=Node.Source.IMPORT,
            import_key="journal:42",
        )


def test_captured_at_is_independent_of_created_at(owner):
    """Imported material keeps its original date, or dormancy is meaningless."""
    node = Node.objects.create(
        owner=owner,
        original_content="a thought from two years ago",
        captured_at=_at("2024-03-01"),
        source=Node.Source.IMPORT,
        import_key="journal:1",
    )
    assert node.captured_at.year == 2024
    assert node.created_at.year >= 2026
    assert node.captured_at < node.created_at


# --------------------------------------------------------------------------
# Concepts and alias depth
# --------------------------------------------------------------------------


@pytest.fixture
def concepts(owner):
    def _make(label, ctype=ConceptCandidate.Type.PERSON, confirmed=False):
        return ConceptCandidate.objects.create(
            owner=owner,
            label=label,
            concept_type=ctype,
            confirmed_at=timezone.now() if confirmed else None,
        )

    return _make


def test_alias_of_an_alias_is_rejected(concepts):
    bob = concepts("Bob")
    brother = concepts("my brother")
    brother.merged_into = bob
    brother.save()

    third = concepts("him")
    third.merged_into = brother
    with pytest.raises(DatabaseError, match="itself an alias"), transaction.atomic():
        third.save()


def test_concept_with_aliases_cannot_itself_become_an_alias(concepts):
    bob = concepts("Bob")
    brother = concepts("my brother")
    brother.merged_into = bob
    brother.save()

    robert = concepts("Robert")
    bob.merged_into = robert
    with pytest.raises(DatabaseError, match="aliases of its own"), transaction.atomic():
        bob.save()


def test_concept_cannot_merge_into_itself(concepts):
    bob = concepts("Bob")
    bob.merged_into = bob
    with pytest.raises((IntegrityError, DatabaseError)), transaction.atomic():
        bob.save()


def test_concept_label_unique_per_owner_and_type_case_insensitively(concepts):
    concepts("Mondly", ConceptCandidate.Type.PROJECT)
    with pytest.raises(IntegrityError), transaction.atomic():
        concepts("mondly", ConceptCandidate.Type.PROJECT)


def test_same_label_allowed_across_concept_types(concepts):
    concepts("Mondly", ConceptCandidate.Type.PROJECT)
    concepts("Mondly", ConceptCandidate.Type.ACTIVITY)  # different thing, legal


# --------------------------------------------------------------------------
# Mentions — the NULLS NOT DISTINCT case
# --------------------------------------------------------------------------


def test_node_level_mention_cannot_be_inserted_twice(make_node, concepts):
    """Both spans NULL. Standard SQL would accept this twice; we must not.

    This is the constraint SQLite omits in silence, which is why the suite
    requires Postgres 15+.
    """
    node = make_node("Mondly again")
    concept = concepts("Mondly", ConceptCandidate.Type.PROJECT)
    Mention.objects.create(
        node=node, concept=concept, origin=InferenceOrigin.INFERRED, index_version="fts-v1"
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        Mention.objects.create(
            node=node,
            concept=concept,
            origin=InferenceOrigin.INFERRED,
            index_version="fts-v1",
        )


def test_distinct_spans_of_the_same_concept_are_allowed(make_node, concepts):
    node = make_node("Mondly in the morning and Mondly at night")
    concept = concepts("Mondly", ConceptCandidate.Type.PROJECT)
    Mention.objects.create(
        node=node,
        concept=concept,
        span_start=0,
        span_end=6,
        origin=InferenceOrigin.INFERRED,
        index_version="fts-v1",
    )
    Mention.objects.create(
        node=node,
        concept=concept,
        span_start=26,
        span_end=32,
        origin=InferenceOrigin.INFERRED,
        index_version="fts-v1",
    )
    assert Mention.objects.filter(node=node).count() == 2


def test_empty_span_is_rejected(make_node, concepts):
    node = make_node("Mondly")
    concept = concepts("Mondly", ConceptCandidate.Type.PROJECT)
    with pytest.raises(IntegrityError), transaction.atomic():
        Mention.objects.create(
            node=node,
            concept=concept,
            span_start=3,
            span_end=3,
            origin=InferenceOrigin.INFERRED,
            index_version="fts-v1",
        )


def test_half_a_span_is_rejected(make_node, concepts):
    node = make_node("Mondly")
    concept = concepts("Mondly", ConceptCandidate.Type.PROJECT)
    with pytest.raises(IntegrityError), transaction.atomic():
        Mention.objects.create(
            node=node,
            concept=concept,
            span_start=0,
            origin=InferenceOrigin.INFERRED,
            index_version="fts-v1",
        )


# --------------------------------------------------------------------------
# Edges
# --------------------------------------------------------------------------


def _edge(owner, a, b, relation=EdgeRelation.RELATES_TO):
    return Edge.objects.create(
        owner=owner,
        from_node=a,
        to_node=b,
        relation=relation,
        origin=InferenceOrigin.EXPLICIT,
    )


def test_symmetric_relation_cannot_be_stored_in_both_directions(owner, make_node):
    a, b = make_node("one"), make_node("two")
    _edge(owner, a, b)
    with pytest.raises(IntegrityError), transaction.atomic():
        _edge(owner, b, a)


def test_directed_relations_may_coexist_in_both_directions(owner, make_node):
    """`developed_from` is not symmetric, so A->B and B->A are different claims."""
    a, b = make_node("one"), make_node("two")
    _edge(owner, a, b, EdgeRelation.DEVELOPED_FROM)
    _edge(owner, b, a, EdgeRelation.DEVELOPED_FROM)
    assert Edge.objects.filter(relation=EdgeRelation.DEVELOPED_FROM).count() == 2


def test_self_link_is_rejected(owner, make_node):
    a = make_node("one")
    with pytest.raises(IntegrityError), transaction.atomic():
        _edge(owner, a, a)


def test_confidence_outside_zero_to_one_is_rejected(owner, make_node):
    a, b = make_node("one"), make_node("two")
    with pytest.raises(IntegrityError), transaction.atomic():
        Edge.objects.create(
            owner=owner,
            from_node=a,
            to_node=b,
            relation=EdgeRelation.RELATES_TO,
            origin=InferenceOrigin.INFERRED,
            confidence=1.5,
        )


def test_member_of_depth_two_is_rejected(owner, make_node):
    """A container cannot itself be contained. Deep hierarchies are deferred,
    and this constraint is that deferral rather than a convention."""
    member, thread, outer = make_node("a"), make_node("thread"), make_node("outer")
    _edge(owner, member, thread, EdgeRelation.MEMBER_OF)

    with pytest.raises(DatabaseError, match="already has members"), transaction.atomic():
        _edge(owner, thread, outer, EdgeRelation.MEMBER_OF)


def test_a_member_cannot_gain_members_of_its_own(owner, make_node):
    member, thread, other = make_node("a"), make_node("thread"), make_node("other")
    _edge(owner, member, thread, EdgeRelation.MEMBER_OF)

    with pytest.raises(DatabaseError, match="already a member"), transaction.atomic():
        _edge(owner, other, member, EdgeRelation.MEMBER_OF)


def test_a_thread_may_hold_many_members(owner, make_node):
    thread = make_node("thread")
    for i in range(4):
        _edge(owner, make_node(f"member {i}"), thread, EdgeRelation.MEMBER_OF)
    assert Edge.objects.filter(to_node=thread, relation=EdgeRelation.MEMBER_OF).count() == 4


# --------------------------------------------------------------------------
# Connection hypotheses — where product principles become constraints
# --------------------------------------------------------------------------


def _hypothesis(owner, fingerprint="fp-a", **kw):
    defaults = dict(
        owner=owner,
        detector="dormant_thread",
        confidence=0.7,
        label="Mondly",
        index_version="fts-v1",
        fingerprint=fingerprint,
        # Injected rather than automatic: expiry logic reads this field, so it
        # is domain state (see ConnectionHypothesis.created_at).
        created_at=_at("2026-01-01"),
    )
    defaults.update(kw)
    return ConnectionHypothesis.objects.create(**defaults)


def test_review_window_cannot_be_set_before_the_hypothesis_was_shown(owner):
    """Silence is not consent.

    A window anchored to creation would expire on hypotheses the person never
    saw, and 'undismissed' would mean 'unseen' rather than 'accepted'.
    """
    with pytest.raises(IntegrityError), transaction.atomic():
        _hypothesis(owner, review_window_expires_at=_at("2026-06-01"))


def test_review_window_is_allowed_once_surfaced(owner):
    h = _hypothesis(
        owner,
        first_surfaced_at=_at("2026-05-01"),
        surface_count=1,
        review_window_expires_at=_at("2026-06-01"),
    )
    assert h.review_window_expires_at is not None


def test_surface_count_must_agree_with_having_been_surfaced(owner):
    with pytest.raises(IntegrityError), transaction.atomic():
        _hypothesis(owner, surface_count=3)


def test_a_dismissed_hypothesis_is_never_proposed_again(owner):
    """Dedupe is against everything seen, not against what was confirmed —
    otherwise every batch run resurrects last week's dismissals."""
    _hypothesis(owner, fingerprint="fp-x", resolved_at=timezone.now(),
                resolution=ConnectionHypothesis.Resolution.DISMISSED)
    with pytest.raises(IntegrityError), transaction.atomic():
        _hypothesis(owner, fingerprint="fp-x")


def test_the_same_fingerprint_may_belong_to_two_different_people(owner, other_owner):
    _hypothesis(owner, fingerprint="fp-shared")
    _hypothesis(other_owner, fingerprint="fp-shared")


def test_resolution_and_resolved_at_travel_together(owner):
    with pytest.raises(IntegrityError), transaction.atomic():
        _hypothesis(owner, resolved_at=timezone.now())
    with pytest.raises(IntegrityError), transaction.atomic():
        _hypothesis(
            owner,
            fingerprint="fp-b",
            resolution=ConnectionHypothesis.Resolution.CONFIRMED,
        )


def test_claim_text_is_absent_by_default(owner):
    """v1 ships no generative producer; articulation arrives with the motif
    detectors and is user-initiated."""
    assert _hypothesis(owner).claim_text is None


def test_members_carry_span_level_citations(owner, make_node):
    h = _hypothesis(owner)
    node = make_node("I will start the lessons tomorrow")
    HypothesisMember.objects.create(
        hypothesis=h, node=node, span_start=2, span_end=25,
        contribution_reason="describes deferral",
    )
    member = h.members.get()
    assert (member.span_start, member.span_end) == (2, 25)


def test_a_node_appears_at_most_once_in_a_hypothesis(owner, make_node):
    h = _hypothesis(owner)
    node = make_node("one")
    HypothesisMember.objects.create(hypothesis=h, node=node)
    with pytest.raises(IntegrityError), transaction.atomic():
        HypothesisMember.objects.create(hypothesis=h, node=node)


# --------------------------------------------------------------------------
# The append-only log
# --------------------------------------------------------------------------


def _event(owner, node=None):
    return ActivityEvent.objects.create(
        owner=owner,
        node=node,
        event_type=ActivityEvent.Type.CAPTURED,
        occurred_at=_at("2026-01-01"),
        actor="vince",
        payload={"source": "web"},
    )


def test_the_log_cannot_be_updated(owner):
    _event(owner)
    with pytest.raises(DatabaseError, match="append-only"), transaction.atomic():
        ActivityEvent.objects.update(actor="someone-else")


def test_the_log_cannot_be_deleted(owner):
    _event(owner)
    with pytest.raises(DatabaseError, match="append-only"), transaction.atomic():
        ActivityEvent.objects.all().delete()


def test_a_node_with_events_can_still_be_deleted(owner, make_node):
    """Real deletion must not be blocked by the log's immutability.

    The log holds a non-constraining reference precisely so this works: every
    referential action available (CASCADE, SET_NULL, SET_DEFAULT) is a mutation
    of the log, which the append-only trigger refuses. A real foreign key here
    would make any node with events undeletable — and every node has events.
    """
    node = make_node("something")
    _event(owner, node)
    node_id = node.pk

    node.delete()  # must not raise

    event = ActivityEvent.objects.get()
    assert event.node_id == node_id, "the event still records what it happened to"
    assert event.event_type == ActivityEvent.Type.CAPTURED
    assert not Node.objects.filter(pk=node_id).exists()


def test_a_hypothesis_citing_a_deleted_node_is_invalidated(owner, make_node):
    """Unlike the log, evidence must not dangle: a thread cannot cite a note
    that no longer exists."""
    h = _hypothesis(owner, fingerprint="fp-del")
    node = make_node("cited")
    HypothesisMember.objects.create(hypothesis=h, node=node)

    node.delete()

    assert h.members.count() == 0


def test_schema_version_defaults_to_one(owner):
    assert _event(owner).schema_version == 1


# --------------------------------------------------------------------------
# Generated search columns
# --------------------------------------------------------------------------


def test_generated_tsvector_indexes_the_original_capture(make_node):
    make_node("learning Mondly again tonight")
    hits = Node.objects.filter(
        search_original=SearchQuery("Mondly", config="english")
    ).count()
    assert hits == 1


def test_generated_tsvector_stems(make_node):
    """`postponed` must match a search for `postpone`, or recall is brittle."""
    node = make_node("x")
    node.revisions.create(seq=1, body="postponed the practice", actor="vince")
    from mind.models import Revision

    hits = Revision.objects.filter(
        search_body=SearchQuery("postpone", config="english")
    ).count()
    assert hits == 1


def test_the_original_stays_searchable_after_revision(make_node):
    """A thought remains findable by the words it was first written in."""
    node = make_node("Mondly again tonight")
    node.revisions.create(seq=1, body="Spanish practice, rewritten", actor="vince")

    assert Node.objects.filter(
        search_original=SearchQuery("Mondly", config="english")
    ).count() == 1
    assert node.revisions.filter(
        search_body=SearchQuery("Spanish", config="english")
    ).count() == 1


def test_revision_seq_is_unique_per_node(make_node):
    node = make_node("x")
    node.revisions.create(seq=1, body="first", actor="vince")
    with pytest.raises(IntegrityError), transaction.atomic():
        node.revisions.create(seq=1, body="racing for the same seq", actor="vince")


def test_revision_seq_must_be_positive(make_node):
    node = make_node("x")
    with pytest.raises(IntegrityError), transaction.atomic():
        node.revisions.create(seq=0, body="x", actor="vince")
