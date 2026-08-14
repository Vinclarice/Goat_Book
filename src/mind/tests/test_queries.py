"""The read side.

`current_body` and `confirmed_concepts` both exist because the answer must be
defined in exactly one place: what a node currently says, and which concepts
the matcher is allowed to search.
"""

import pytest
from django.utils import timezone

from mind import queries
from mind.models import ConceptCandidate, InferenceOrigin, Mention, Node

pytestmark = pytest.mark.django_db


def test_current_body_falls_back_to_the_original_capture(make_node):
    node = make_node("as first written")
    assert queries.current_body(node) == "as first written"


def test_current_body_is_the_latest_revision(make_node):
    node = make_node("as first written")
    node.revisions.create(seq=1, body="second thoughts", actor="vince")
    node.revisions.create(seq=2, body="third thoughts", actor="vince")
    assert queries.current_body(node) == "third thoughts"


def test_the_original_capture_is_never_overwritten(make_node):
    node = make_node("as first written")
    node.revisions.create(seq=1, body="rewritten entirely", actor="vince")
    node.refresh_from_db()
    assert node.original_content == "as first written"


def test_live_nodes_excludes_deleted_and_archived(owner, make_node):
    keep = make_node("keep")
    gone = make_node("deleted")
    filed = make_node("archived")
    Node.objects.filter(pk=gone.pk).update(deleted_at=timezone.now())
    Node.objects.filter(pk=filed.pk).update(archived_at=timezone.now())

    assert list(queries.live_nodes(owner)) == [keep]


def test_live_nodes_is_newest_capture_first(owner, make_node):
    old = make_node("older", captured="2026-01-01")
    new = make_node("newer", captured="2026-06-01")
    assert list(queries.live_nodes(owner)) == [new, old]


def test_live_nodes_is_owner_scoped(owner, other_owner, make_node):
    """Isolation gets its own test rather than inheriting one."""
    mine = make_node("mine")
    Node.objects.create(
        owner=other_owner,
        original_content="theirs",
        captured_at=mine.captured_at,
        source=Node.Source.WEB,
    )
    assert list(queries.live_nodes(owner)) == [mine]
    assert list(queries.live_nodes(other_owner)) != [mine]


def test_canonical_concept_resolves_an_alias_in_one_hop(owner):
    bob = ConceptCandidate.objects.create(
        owner=owner, label="Bob", concept_type=ConceptCandidate.Type.PERSON
    )
    brother = ConceptCandidate.objects.create(
        owner=owner,
        label="my brother",
        concept_type=ConceptCandidate.Type.PERSON,
        merged_into=bob,
    )
    assert queries.canonical_concept(brother) == bob
    assert queries.canonical_concept(bob) == bob


def test_confirmed_concepts_excludes_unconfirmed_candidates(owner):
    """The classifier must not feed on its own guesses."""
    ConceptCandidate.objects.create(
        owner=owner,
        label="confirmed",
        concept_type=ConceptCandidate.Type.PERSON,
        confirmed_at=timezone.now(),
    )
    ConceptCandidate.objects.create(
        owner=owner, label="just a guess", concept_type=ConceptCandidate.Type.PERSON
    )
    labels = list(queries.confirmed_concepts(owner).values_list("label", flat=True))
    assert labels == ["confirmed"]


def test_confirmed_concepts_excludes_aliases_and_retired(owner):
    canonical = ConceptCandidate.objects.create(
        owner=owner,
        label="Bob",
        concept_type=ConceptCandidate.Type.PERSON,
        confirmed_at=timezone.now(),
    )
    ConceptCandidate.objects.create(
        owner=owner,
        label="my brother",
        concept_type=ConceptCandidate.Type.PERSON,
        confirmed_at=timezone.now(),
        merged_into=canonical,
    )
    ConceptCandidate.objects.create(
        owner=owner,
        label="an old idea",
        concept_type=ConceptCandidate.Type.MOTIF,
        confirmed_at=timezone.now(),
        retired_at=timezone.now(),
    )
    assert list(queries.confirmed_concepts(owner)) == [canonical]


def test_nodes_mentioning_resolves_through_aliases(owner, make_node):
    """Asking about "Bob" must find the note that said "my brother"."""
    bob = ConceptCandidate.objects.create(
        owner=owner,
        label="Bob",
        concept_type=ConceptCandidate.Type.PERSON,
        confirmed_at=timezone.now(),
    )
    brother = ConceptCandidate.objects.create(
        owner=owner,
        label="my brother",
        concept_type=ConceptCandidate.Type.PERSON,
        confirmed_at=timezone.now(),
        merged_into=bob,
    )

    direct = make_node("called Bob today")
    via_alias = make_node("my brother rang")
    make_node("unrelated")

    Mention.objects.create(
        node=direct, concept=bob, origin=InferenceOrigin.EXPLICIT, index_version="fts-v1"
    )
    Mention.objects.create(
        node=via_alias,
        concept=brother,
        origin=InferenceOrigin.EXPLICIT,
        index_version="fts-v1",
    )

    found = set(queries.nodes_mentioning(owner, bob).values_list("pk", flat=True))
    assert found == {direct.pk, via_alias.pk}

# ---------------------------------------------------------------------------
# Concept candidates: the gravity gate
# ---------------------------------------------------------------------------


def _candidate(owner, label, *, confirmed=False):
    return ConceptCandidate.objects.create(
        owner=owner,
        label=label,
        concept_type=ConceptCandidate.Type.UNKNOWN,
        confirmed_at=timezone.now() if confirmed else None,
    )


def _mention(node, concept):
    return Mention.objects.create(
        node=node,
        concept=concept,
        origin=InferenceOrigin.INFERRED,
        index_version="rules-1",
    )


def test_a_name_seen_once_is_never_asked_about(owner, make_node):
    """Extraction over-generates on purpose, and that is only safe if the surplus
    stays silent. A hundred candidates a month is the inbox this design exists to
    avoid -- so a candidate costs a row until it earns a question."""
    indonesian = _candidate(owner, "Indonesian")
    _mention(make_node("one mention", captured="2026-03-01"), indonesian)

    assert list(queries.concept_candidates(owner)) == []


def test_a_name_that_recurs_across_days_earns_a_question(owner, make_node):
    indonesian = _candidate(owner, "Indonesian")
    for day in ("2026-03-01", "2026-03-04", "2026-03-09"):
        _mention(make_node("learning", captured=day), indonesian)

    earned = list(queries.concept_candidates(owner))

    assert [c.label for c in earned] == ["Indonesian"]
    assert earned[0].mention_count == 3


def test_a_flurry_in_one_sitting_does_not_earn_a_question(owner, make_node):
    """Three mentions in one brain dump is one moment of attention, not a pattern.
    Gravity is meant to find what *recurs*, and a single sitting cannot show that
    -- so the day span is a separate condition from the count, not a proxy for it."""
    mondly = _candidate(owner, "Mondly")
    for _ in range(4):
        _mention(make_node("dumped", captured="2026-03-01"), mondly)

    assert list(queries.concept_candidates(owner)) == []


def test_a_confirmed_concept_is_not_a_candidate_any_more(owner, make_node):
    """Answered questions stop being asked. This is the only reason the queue is
    finite."""
    indonesian = _candidate(owner, "Indonesian", confirmed=True)
    for day in ("2026-03-01", "2026-03-04", "2026-03-09"):
        _mention(make_node("learning", captured=day), indonesian)

    assert list(queries.concept_candidates(owner)) == []


def test_a_rejected_candidate_stays_rejected(owner, make_node):
    """Retiring is how a person says "that is not a thing". Re-proposing it on the
    next extraction run would make the answer worthless."""
    noise = _candidate(owner, "Sent From My Iphone")
    for day in ("2026-03-01", "2026-03-04", "2026-03-09"):
        _mention(make_node("signature", captured=day), noise)
    noise.retired_at = timezone.now()
    noise.save()

    assert list(queries.concept_candidates(owner)) == []


def test_candidates_arrive_heaviest_first(owner, make_node):
    """A handful of questions at a time, so the order decides which get asked."""
    light = _candidate(owner, "Kyoto")
    heavy = _candidate(owner, "Indonesian")
    for day in ("2026-03-01", "2026-03-04", "2026-03-09"):
        _mention(make_node("light", captured=day), light)
    for day in ("2026-03-01", "2026-03-04", "2026-03-09", "2026-03-11"):
        _mention(make_node("heavy", captured=day), heavy)

    assert [c.label for c in queries.concept_candidates(owner)] == [
        "Indonesian",
        "Kyoto",
    ]


def test_another_persons_candidates_are_invisible(owner, other_owner, make_node):
    theirs = _candidate(other_owner, "Theirs")
    for day in ("2026-03-01", "2026-03-04", "2026-03-09"):
        Mention.objects.create(
            node=Node.objects.create(
                owner=other_owner,
                original_content="theirs",
                captured_at=timezone.now(),
                source=Node.Source.WEB,
            ),
            concept=theirs,
            origin=InferenceOrigin.INFERRED,
            index_version="rules-1",
        )

    assert list(queries.concept_candidates(owner)) == []
