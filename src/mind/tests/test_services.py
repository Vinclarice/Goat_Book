"""The write side.

Where test_invariants.py proves the database refuses bad writes, this proves the
service refuses them *first*, with an error a caller can act on — and enforces
the rules no constraint can state at all:

  * a node has content or an attachment
  * a hypothesis has at least two members
  * records in one operation share an owner
  * deleted material invalidates the evidence that cited it
  * re-running a detector has no side effects

The clock is injected everywhere, so nothing here depends on when it runs.
"""

from datetime import datetime, timedelta, timezone as dt_timezone

import pytest

from mind import queries, services
from mind.models import (
    ActivityEvent,
    Attachment,
    ConceptCandidate,
    ConceptType,
    ConnectionHypothesis,
    Edge,
    EdgeRelation,
    EventType,
    HypothesisResolution,
    InferenceOrigin,
    Mention,
    Node,
    NodeSource,
)

pytestmark = pytest.mark.django_db

UTC = dt_timezone.utc
JAN = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)
JUN = datetime(2026, 6, 1, 9, 0, tzinfo=UTC)


def _capture(owner, content="a thought", when=JAN, **kw):
    return services.capture(
        owner,
        content=content,
        captured_at=when,
        source=NodeSource.WEB,
        actor="vince",
        **kw,
    )


# ---------------------------------------------------------------------------
# Capture
# ---------------------------------------------------------------------------


def test_capture_records_the_node_and_an_event(owner):
    node = _capture(owner, "learning Mondly again")
    assert node.original_content == "learning Mondly again"
    event = ActivityEvent.objects.get()
    assert event.event_type == EventType.CAPTURED
    assert event.node_id == node.pk
    assert event.occurred_at == JAN


def test_a_retried_capture_returns_the_same_node(owner):
    """A client that never saw its request succeed must not create a second."""
    first = _capture(owner, "a thought")
    again = _capture(owner, "a thought", public_id=first.public_id)

    assert again.pk == first.pk
    assert Node.objects.count() == 1
    assert ActivityEvent.objects.count() == 1, "a retry is not a second capture"


def test_a_retry_cannot_claim_another_persons_node(owner, other_owner):
    mine = _capture(owner)
    with pytest.raises(services.NotYours):
        services.capture(
            other_owner,
            content="theirs",
            captured_at=JAN,
            source=NodeSource.WEB,
            actor="them",
            public_id=mine.public_id,
        )


def test_reimport_returns_the_existing_node(owner):
    first = services.capture(
        owner,
        content="from the journal",
        captured_at=datetime(2024, 3, 1, tzinfo=UTC),
        source=NodeSource.IMPORT,
        actor="importer",
        import_key="journal:42",
    )
    again = services.capture(
        owner,
        content="from the journal",
        captured_at=datetime(2024, 3, 1, tzinfo=UTC),
        source=NodeSource.IMPORT,
        actor="importer",
        import_key="journal:42",
    )
    assert again.pk == first.pk
    assert Node.objects.count() == 1


def test_import_keeps_the_original_timestamp(owner):
    node = services.capture(
        owner,
        content="two years ago",
        captured_at=datetime(2024, 3, 1, tzinfo=UTC),
        source=NodeSource.IMPORT,
        actor="importer",
        import_key="journal:1",
    )
    assert node.captured_at.year == 2024
    assert ActivityEvent.objects.get().event_type == EventType.IMPORTED


def test_an_empty_node_is_refused(owner):
    with pytest.raises(services.EmptyNode):
        _capture(owner, "   ")


def test_an_attachment_only_node_is_allowed(owner):
    """Empty content is legal when something is attached — the invariant is
    "content or attachment", and it is cross-table so no constraint can say it."""
    node = _capture(
        owner,
        "",
        attachments=[
            services.AttachmentSpec(
                kind="image",
                mime_type="image/jpeg",
                byte_size=1024,
                checksum="abc",
                content=b"jpegbytes",
            )
        ],
    )
    assert node.original_content == ""
    assert Attachment.objects.filter(node=node).count() == 1


# ---------------------------------------------------------------------------
# Revision
# ---------------------------------------------------------------------------


def test_revising_allocates_sequential_numbers(owner):
    node = _capture(owner, "first")
    a = services.revise(node, body="second", actor="vince", now=JAN)
    b = services.revise(node, body="third", actor="vince", now=JAN)
    assert (a.seq, b.seq) == (1, 2)


def test_revising_never_touches_the_original(owner):
    node = _capture(owner, "as first written")
    services.revise(node, body="rewritten", actor="vince", now=JAN)
    node.refresh_from_db()
    assert node.original_content == "as first written"
    assert queries.current_body(node) == "rewritten"


def test_deleted_material_cannot_be_revised(owner):
    node = _capture(owner)
    services.delete_node(node, now=JAN, actor="vince")
    with pytest.raises(services.Deleted):
        services.revise(node, body="x", actor="vince", now=JAN)


# ---------------------------------------------------------------------------
# Concepts and aliases
# ---------------------------------------------------------------------------


def _concept(owner, label, ctype=ConceptType.PERSON):
    return services.propose_concept(
        owner, label=label, concept_type=ctype, now=JAN, actor="system", reason="test"
    )


def test_a_proposed_concept_is_not_yet_trusted(owner):
    concept = _concept(owner, "Bob")
    assert concept.confirmed_at is None
    assert list(queries.confirmed_concepts(owner)) == []


def test_confirming_admits_a_concept_to_the_corpus(owner):
    concept = services.confirm_concept(_concept(owner, "Bob"), now=JAN, actor="vince")
    assert concept.confirmed_at == JAN
    assert list(queries.confirmed_concepts(owner)) == [concept]


def test_confirming_twice_is_harmless_and_does_not_relog(owner):
    concept = _concept(owner, "Bob")
    services.confirm_concept(concept, now=JAN, actor="vince")
    services.confirm_concept(concept, now=JUN, actor="vince")
    concept.refresh_from_db()
    assert concept.confirmed_at == JAN, "the first confirmation stands"
    assert (
        ActivityEvent.objects.filter(event_type=EventType.CONCEPT_CONFIRMED).count() == 1
    )


def test_merging_resolves_an_alias(owner):
    bob = _concept(owner, "Bob")
    brother = _concept(owner, "my brother")
    services.merge_concept(brother, bob, now=JAN, actor="vince")
    brother.refresh_from_db()
    assert queries.canonical_concept(brother) == bob


def test_cannot_merge_concepts_across_owners(owner, other_owner):
    """Isolation gets its own direct test: a view looks both up owner-scoped and
    404s first, so it cannot construct this pair at all."""
    mine = _concept(owner, "Bob")
    theirs = _concept(other_owner, "Bob")
    with pytest.raises(services.NotYours):
        services.merge_concept(theirs, mine, now=JAN, actor="vince")


def test_cannot_merge_into_an_alias(owner):
    bob = _concept(owner, "Bob")
    brother = _concept(owner, "my brother")
    services.merge_concept(brother, bob, now=JAN, actor="vince")

    him = _concept(owner, "him")
    with pytest.raises(services.HierarchyTooDeep, match="itself an alias"):
        services.merge_concept(him, brother, now=JAN, actor="vince")


def test_a_concept_with_aliases_cannot_become_one(owner):
    bob = _concept(owner, "Bob")
    brother = _concept(owner, "my brother")
    services.merge_concept(brother, bob, now=JAN, actor="vince")

    robert = _concept(owner, "Robert")
    with pytest.raises(services.HierarchyTooDeep, match="aliases of its own"):
        services.merge_concept(bob, robert, now=JAN, actor="vince")


def test_a_concept_cannot_be_an_alias_of_itself(owner):
    bob = _concept(owner, "Bob")
    with pytest.raises(services.HierarchyTooDeep):
        services.merge_concept(bob, bob, now=JAN, actor="vince")


# ---------------------------------------------------------------------------
# Mentions
# ---------------------------------------------------------------------------


def test_mentions_cannot_cross_owners(owner, other_owner):
    node = _capture(owner)
    theirs = _concept(other_owner, "Bob")
    with pytest.raises(services.NotYours):
        services.propose_mention(
            node, theirs, index_version="fts-v1", now=JAN, actor="system"
        )


def test_an_explicit_mention_is_confirmed_on_arrival(owner):
    """A person naming a concept is not a guess needing confirmation."""
    node = _capture(owner)
    concept = _concept(owner, "Bob")
    mention = services.propose_mention(
        node,
        concept,
        index_version="manual",
        origin=InferenceOrigin.EXPLICIT,
        now=JAN,
        actor="vince",
    )
    assert mention.confirmed_at == JAN


def test_an_explicit_mention_is_logged_as_a_decision_not_a_suggestion(owner):
    """The event has to agree with `confirmed_at` two lines above it.

    `code-review-2026-08-21.md` R2: an explicit mention arrived already
    confirmed and was logged as `MENTION_PROPOSED` anyway, which made a person
    typing a tag indistinguishable from a detector guessing overnight. The
    symptom surfaced a layer up, where `clarice.recall.around` treats proposals
    as machine activity -- so tagging an existing note vanished from its own
    morning.
    """
    node = _capture(owner)
    concept = _concept(owner, "Bob")
    services.propose_mention(
        node,
        concept,
        index_version="manual",
        origin=InferenceOrigin.EXPLICIT,
        now=JAN,
        actor="vince",
    )
    assert node.events.filter(event_type=EventType.MENTION_CONFIRMED).exists()
    assert not node.events.filter(event_type=EventType.MENTION_PROPOSED).exists()


def test_an_inferred_mention_is_still_logged_as_a_proposal(owner):
    """The other half, so the repair stays narrow: nothing asked for this one,
    and a detector's guess is exactly what `MENTION_PROPOSED` is for."""
    node = _capture(owner)
    concept = _concept(owner, "Bob")
    services.propose_mention(
        node, concept, index_version="fts-v1", span=(0, 3), now=JAN, actor="system"
    )
    assert node.events.filter(event_type=EventType.MENTION_PROPOSED).exists()


def test_an_inferred_mention_waits_for_confirmation(owner):
    node = _capture(owner)
    concept = _concept(owner, "Bob")
    mention = services.propose_mention(
        node, concept, index_version="fts-v1", span=(0, 3), now=JAN, actor="system"
    )
    assert mention.confirmed_at is None
    services.confirm_mention(mention, now=JUN, actor="vince")
    mention.refresh_from_db()
    assert mention.confirmed_at == JUN


# ---------------------------------------------------------------------------
# Edges
# ---------------------------------------------------------------------------


def test_linking_the_same_pair_twice_returns_one_edge(owner):
    a, b = _capture(owner, "one"), _capture(owner, "two")
    first = services.link(a, b, relation=EdgeRelation.RELATES_TO, now=JAN, actor="vince")
    again = services.link(a, b, relation=EdgeRelation.RELATES_TO, now=JAN, actor="vince")
    assert again.pk == first.pk
    assert Edge.objects.count() == 1


def test_a_symmetric_link_is_idempotent_in_reverse(owner):
    """A relates_to B and B relates_to A are one fact, so the reverse assertion
    finds the existing edge instead of failing on the constraint."""
    a, b = _capture(owner, "one"), _capture(owner, "two")
    first = services.link(a, b, relation=EdgeRelation.RELATES_TO, now=JAN, actor="vince")
    reverse = services.link(
        b, a, relation=EdgeRelation.RELATES_TO, now=JAN, actor="vince"
    )
    assert reverse.pk == first.pk
    assert Edge.objects.count() == 1


def test_a_directed_link_is_not_idempotent_in_reverse(owner):
    a, b = _capture(owner, "one"), _capture(owner, "two")
    services.link(a, b, relation=EdgeRelation.DEVELOPED_FROM, now=JAN, actor="vince")
    services.link(b, a, relation=EdgeRelation.DEVELOPED_FROM, now=JAN, actor="vince")
    assert Edge.objects.count() == 2, "these are different claims"


def test_cannot_link_across_owners(owner, other_owner):
    mine = _capture(owner)
    theirs = services.capture(
        other_owner, content="theirs", captured_at=JAN, source=NodeSource.WEB, actor="x"
    )
    with pytest.raises(services.NotYours):
        services.link(mine, theirs, relation=EdgeRelation.RELATES_TO, now=JAN, actor="v")


def test_member_of_depth_is_refused_with_a_clean_error(owner):
    """The trigger would also stop this; the service says why first."""
    member, thread, outer = (
        _capture(owner, "a"),
        _capture(owner, "thread"),
        _capture(owner, "outer"),
    )
    services.link(member, thread, relation=EdgeRelation.MEMBER_OF, now=JAN, actor="v")
    with pytest.raises(services.HierarchyTooDeep, match="already has members"):
        services.link(thread, outer, relation=EdgeRelation.MEMBER_OF, now=JAN, actor="v")


# ---------------------------------------------------------------------------
# Hypotheses
# ---------------------------------------------------------------------------


def _hypothesis(owner, nodes, detector="dormant_thread", relation=None, **kw):
    return services.propose_hypothesis(
        owner,
        detector=detector,
        citations=[services.Citation(node=n) for n in nodes],
        confidence=0.7,
        label="Mondly",
        index_version="fts-v1",
        relation=relation,
        now=JAN,
        **kw,
    )


def test_a_hypothesis_needs_two_distinct_nodes(owner):
    node = _capture(owner)
    with pytest.raises(services.InvalidHypothesis):
        _hypothesis(owner, [node])
    with pytest.raises(services.InvalidHypothesis, match="two distinct"):
        _hypothesis(owner, [node, node])


def test_re_running_a_detector_has_no_side_effects(owner):
    """The batch job runs repeatedly; proposing must be free."""
    a, b = _capture(owner, "one"), _capture(owner, "two")
    first = _hypothesis(owner, [a, b])
    again = _hypothesis(owner, [a, b])
    assert again.pk == first.pk
    assert ConnectionHypothesis.objects.count() == 1


def test_member_order_does_not_change_the_fingerprint(owner):
    a, b = _capture(owner, "one"), _capture(owner, "two")
    assert _hypothesis(owner, [a, b]).pk == _hypothesis(owner, [b, a]).pk


def test_a_dismissal_is_not_re_proposed(owner):
    """Dedupe is against everything seen. A weekly resurrected dismissal would
    train the person to ignore the review surface."""
    a, b = _capture(owner, "one"), _capture(owner, "two")
    h = _hypothesis(owner, [a, b])
    services.dismiss_hypothesis(h, now=JAN, actor="vince")

    again = _hypothesis(owner, [a, b])
    assert again.pk == h.pk
    assert again.resolution == HypothesisResolution.DISMISSED


def test_different_detectors_may_propose_the_same_nodes(owner):
    a, b = _capture(owner, "one"), _capture(owner, "two")
    assert (
        _hypothesis(owner, [a, b], detector="dormant_thread").pk
        != _hypothesis(owner, [a, b], detector="shared_referent").pk
    )


def test_a_hypothesis_cannot_cite_another_persons_node(owner, other_owner):
    mine = _capture(owner)
    theirs = services.capture(
        other_owner, content="theirs", captured_at=JAN, source=NodeSource.WEB, actor="x"
    )
    with pytest.raises(services.NotYours):
        _hypothesis(owner, [mine, theirs])


def test_claim_text_is_never_generated_in_v1(owner):
    a, b = _capture(owner, "one"), _capture(owner, "two")
    assert _hypothesis(owner, [a, b]).claim_text is None


# --- surfacing: silence is not consent -------------------------------------


def test_the_review_window_starts_when_the_hypothesis_is_shown(owner):
    a, b = _capture(owner, "one"), _capture(owner, "two")
    h = _hypothesis(owner, [a, b])
    assert h.review_window_expires_at is None, "not yet seen, so no clock"

    services.surface_hypothesis(
        h, now=JUN, actor="vince", review_window=timedelta(days=14)
    )
    h.refresh_from_db()
    assert h.first_surfaced_at == JUN
    assert h.review_window_expires_at == JUN + timedelta(days=14)


def test_surfacing_again_counts_the_view_but_does_not_extend_the_window(owner):
    a, b = _capture(owner, "one"), _capture(owner, "two")
    h = _hypothesis(owner, [a, b])
    services.surface_hypothesis(
        h, now=JUN, actor="vince", review_window=timedelta(days=14)
    )
    services.surface_hypothesis(
        h, now=JUN + timedelta(days=3), actor="vince", review_window=timedelta(days=14)
    )
    h.refresh_from_db()
    assert h.surface_count == 2
    assert h.first_surfaced_at == JUN
    assert h.review_window_expires_at == JUN + timedelta(days=14)


def test_a_resolved_hypothesis_cannot_be_surfaced(owner):
    a, b = _capture(owner, "one"), _capture(owner, "two")
    h = _hypothesis(owner, [a, b])
    services.dismiss_hypothesis(h, now=JAN, actor="vince")
    with pytest.raises(services.AlreadyResolved):
        services.surface_hypothesis(h, now=JUN, actor="vince")


def test_an_unseen_hypothesis_expires_without_being_promoted(owner):
    """The whole point of anchoring the window to surfacing: inaction on
    something never shown must not become acceptance."""
    a, b = _capture(owner, "one"), _capture(owner, "two")
    h = _hypothesis(owner, [a, b])

    closed = services.expire_stale_hypotheses(
        owner, now=JUN, unsurfaced_after=timedelta(days=30)
    )
    h.refresh_from_db()
    assert closed == 1
    assert h.resolution == HypothesisResolution.EXPIRED
    assert Edge.objects.count() == 0, "nothing was promoted"


def test_a_surfaced_but_undecided_hypothesis_expires_without_promotion(owner):
    """Soft-apply ripening is deliberately not wired up in the lab: a
    confirmation nobody made would corrupt the accept-rate measurement the lab
    exists to produce."""
    a, b = _capture(owner, "one"), _capture(owner, "two")
    h = _hypothesis(owner, [a, b])
    services.surface_hypothesis(
        h, now=JAN, actor="vince", review_window=timedelta(days=14)
    )

    services.expire_stale_hypotheses(owner, now=JUN, unsurfaced_after=timedelta(days=30))
    h.refresh_from_db()
    assert h.resolution == HypothesisResolution.EXPIRED
    assert Edge.objects.count() == 0


def test_a_recent_unseen_hypothesis_is_left_alone(owner):
    a, b = _capture(owner, "one"), _capture(owner, "two")
    h = _hypothesis(owner, [a, b])
    closed = services.expire_stale_hypotheses(
        owner, now=JAN + timedelta(days=2), unsurfaced_after=timedelta(days=30)
    )
    h.refresh_from_db()
    assert closed == 0
    assert h.resolved_at is None


# --- confirmation ----------------------------------------------------------


def test_confirming_a_pair_creates_one_edge(owner):
    a, b = _capture(owner, "one"), _capture(owner, "two")
    h = _hypothesis(owner, [a, b], relation=EdgeRelation.ANSWERS)
    edges = services.confirm_hypothesis(h, now=JUN, actor="vince")

    h.refresh_from_db()
    assert h.resolution == HypothesisResolution.CONFIRMED
    assert len(edges) == 1
    edge = edges[0]
    assert edge.relation == EdgeRelation.ANSWERS
    assert edge.origin == InferenceOrigin.INFERRED
    assert edge.confidence == pytest.approx(0.7), "the score is retained"


def test_a_pair_without_a_stated_relation_becomes_relates_to(owner):
    a, b = _capture(owner, "one"), _capture(owner, "two")
    edges = services.confirm_hypothesis(
        _hypothesis(owner, [a, b]), now=JUN, actor="vince"
    )
    assert edges[0].relation == EdgeRelation.RELATES_TO


def test_confirming_a_thread_creates_a_meta_node_and_memberships(owner):
    nodes = [_capture(owner, f"note {i}") for i in range(4)]
    h = _hypothesis(owner, nodes)
    edges = services.confirm_hypothesis(h, now=JUN, actor="vince")

    assert len(edges) == 4
    thread = Node.objects.get(source=NodeSource.THREAD)
    assert thread.original_content == "Mondly", "the extractive label, not a claim"
    assert thread.captured_at == JUN
    assert set(Edge.objects.filter(relation=EdgeRelation.MEMBER_OF).values_list(
        "from_node", flat=True
    )) == {n.pk for n in nodes}
    assert all(e.to_node_id == thread.pk for e in edges)


def test_a_node_may_belong_to_several_threads(owner):
    """Depth-one caps *nesting*, not membership count.

    A note legitimately belongs to more than one thread — "language learning"
    and "evening routine" can both be true of it. In each chain it is still a
    member and never a container, so nothing is nested.
    """
    nodes = [_capture(owner, f"note {i}") for i in range(3)]
    services.confirm_hypothesis(_hypothesis(owner, nodes), now=JUN, actor="vince")
    services.confirm_hypothesis(
        _hypothesis(owner, nodes, detector="shared_referent"), now=JUN, actor="vince"
    )

    assert Node.objects.filter(source=NodeSource.THREAD).count() == 2
    assert (
        Edge.objects.filter(relation=EdgeRelation.MEMBER_OF, from_node=nodes[0]).count()
        == 2
    )


def test_a_thread_cannot_become_a_member_of_another_thread(owner):
    """This is what depth-one actually forbids: a container being contained.

    Deep hierarchies are deferred, so the constraint is that deferral enforced
    rather than merely intended.
    """
    nodes = [_capture(owner, f"note {i}") for i in range(3)]
    services.confirm_hypothesis(_hypothesis(owner, nodes), now=JUN, actor="vince")
    thread = Node.objects.get(source=NodeSource.THREAD)

    outer = _hypothesis(
        owner, [thread, *nodes[:2]], detector="recurring_preoccupation"
    )
    with pytest.raises(services.HierarchyTooDeep, match="already has members"):
        services.confirm_hypothesis(outer, now=JUN, actor="vince")


def test_a_hypothesis_is_resolved_only_once(owner):
    a, b = _capture(owner, "one"), _capture(owner, "two")
    h = _hypothesis(owner, [a, b])
    services.confirm_hypothesis(h, now=JUN, actor="vince")
    with pytest.raises(services.AlreadyResolved):
        services.dismiss_hypothesis(h, now=JUN, actor="vince")


# ---------------------------------------------------------------------------
# Deletion
# ---------------------------------------------------------------------------


def test_deleting_hides_the_node_and_invalidates_its_evidence(owner):
    """Evidence must not dangle: a claim citing a vanished passage cannot be
    judged, so it is expired rather than left standing."""
    a, b = _capture(owner, "one"), _capture(owner, "two")
    h = _hypothesis(owner, [a, b])

    services.delete_node(a, now=JUN, actor="vince")

    h.refresh_from_db()
    assert h.resolution == HypothesisResolution.EXPIRED
    assert list(queries.live_nodes(owner)) == [b]


def test_deleting_is_idempotent(owner):
    node = _capture(owner)
    services.delete_node(node, now=JAN, actor="vince")
    services.delete_node(node, now=JUN, actor="vince")
    node.refresh_from_db()
    assert node.deleted_at == JAN


def test_purging_takes_the_bytes_with_it(owner):
    """**Rewritten August 21, 2026, because the design under it changed.**

    This asserted that purging *returned the blobs the caller must remove*, and
    the reasoning was sound for object storage: it is not transactional with
    Postgres, so the boundary was made visible rather than hidden behind an
    abstraction that would have to lie.

    D9 moved the bytes into the row. There is no boundary left to be honest
    about -- `node.delete()` takes them, inside the transaction -- so the old
    assertion now describes a hazard that cannot occur, and a test asserting a
    caller's obligation that no longer exists would teach the next reader to
    write cleanup code for nothing.
    """
    node = _capture(
        owner,
        "with a photo",
        attachments=[
            services.AttachmentSpec(
                kind="image",
                mime_type="image/jpeg",
                byte_size=10,
                checksum="abc",
                content=b"jpegbytes",
            )
        ],
    )
    removed = services.purge_node(node, now=JUN, actor="vince")
    assert removed == 1
    assert Node.objects.count() == 0
    assert Attachment.objects.count() == 0


def test_purging_leaves_the_log_intact_and_still_pointing_at_the_node(owner):
    """An event asserts what happened, which stays true after a purge — the
    opposite treatment from a hypothesis, whose claim does not."""
    node = _capture(owner, "something")
    node_pk = node.pk
    services.purge_node(node, now=JUN, actor="vince")

    captured = ActivityEvent.objects.get(event_type=EventType.CAPTURED)
    assert captured.node_id == node_pk
    purged = ActivityEvent.objects.get(event_type=EventType.PURGED)
    assert purged.payload["node"] == node_pk
    assert "content" not in purged.payload


def test_purging_removes_confirmed_edges_that_cited_the_node(owner):
    a, b = _capture(owner, "one"), _capture(owner, "two")
    services.link(a, b, relation=EdgeRelation.RELATES_TO, now=JAN, actor="vince")
    services.purge_node(a, now=JUN, actor="vince")
    assert Edge.objects.count() == 0


# ---------------------------------------------------------------------------
# Instrumentation
# ---------------------------------------------------------------------------


def test_a_retrieval_miss_is_recorded_with_its_query(owner):
    miss = services.record_retrieval_miss(owner, now=JAN, query_text="that thing about delay")
    assert miss.query_text == "that thing about delay"
    assert miss.resolved_node is None


def test_resolving_a_miss_makes_it_diagnosable(owner):
    """A miss with a known target is what the embeddings decision is measured
    against: would a semantic index have surfaced this?"""
    node = _capture(owner, "postponed the practice again")
    miss = services.record_retrieval_miss(owner, now=JAN, query_text="procrastination")
    services.resolve_retrieval_miss(miss, node)
    miss.refresh_from_db()
    assert miss.resolved_node_id == node.pk


def test_a_miss_cannot_be_resolved_to_another_persons_node(owner, other_owner):
    theirs = services.capture(
        other_owner, content="theirs", captured_at=JAN, source=NodeSource.WEB, actor="x"
    )
    miss = services.record_retrieval_miss(owner, now=JAN, query_text="x")
    with pytest.raises(services.NotYours):
        services.resolve_retrieval_miss(miss, theirs)

# ---------------------------------------------------------------------------
# Retiring a candidate
# ---------------------------------------------------------------------------


def test_retiring_a_candidate_takes_it_out_of_the_queue(owner, make_node):
    """"Not a thing" is an answer, and it has to stick.

    Extraction runs again after every batch of captures and would re-propose the
    same name forever otherwise, which would make answering it worthless -- the
    same reasoning that makes a dismissed hypothesis permanent via `fingerprint`.
    """
    concept = services.propose_concept(
        owner, label="Sent From My Iphone", concept_type=ConceptCandidate.Type.UNKNOWN,
        now=JAN, actor="vince",
    )

    services.retire_concept(concept, now=JAN, actor="vince")

    concept.refresh_from_db()
    assert concept.retired_at == JAN


def test_retiring_is_recorded_in_the_log(owner):
    """A rejection is a decision, and the log is where decisions live. Without it
    there is no way to answer later why a name stopped being asked about."""
    concept = services.propose_concept(
        owner, label="Reykjavik", concept_type=ConceptCandidate.Type.UNKNOWN,
        now=JAN, actor="vince",
    )

    services.retire_concept(concept, now=JAN, actor="vince")

    event = ActivityEvent.objects.filter(event_type=EventType.CONCEPT_RETIRED).get()
    assert event.payload["label"] == "Reykjavik"
    assert event.owner == owner


def test_retiring_twice_is_harmless(owner):
    """Two taps, or a tap and a stale page. Neither should be an error, and the
    first decision's time is the one that counts."""
    concept = services.propose_concept(
        owner, label="Reykjavik", concept_type=ConceptCandidate.Type.UNKNOWN,
        now=JAN, actor="vince",
    )
    services.retire_concept(concept, now=JAN, actor="vince")

    services.retire_concept(concept, now=JAN + timedelta(days=1), actor="vince")

    concept.refresh_from_db()
    assert concept.retired_at == JAN
    assert ActivityEvent.objects.filter(event_type=EventType.CONCEPT_RETIRED).count() == 1


def test_a_confirmed_concept_cannot_be_retired_by_accident(owner):
    """Retiring is for candidates. A confirmed concept has mentions resolving
    through it and detectors reading it, so removing it is a different and much
    larger act than saying "that was never a thing"."""
    concept = services.propose_concept(
        owner, label="Indonesian", concept_type=ConceptCandidate.Type.UNKNOWN,
        now=JAN, actor="vince",
    )
    services.confirm_concept(concept, now=JAN, actor="vince")

    with pytest.raises(services.MindError):
        services.retire_concept(concept, now=JAN, actor="vince")
