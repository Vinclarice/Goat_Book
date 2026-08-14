"""The semantic-echo detector.

Slow by nature — a real model is loaded and real vectors are computed, because a
stubbed encoder would test the plumbing and not the thing that was measured. The model
is cached across tests, so the cost is paid once.

Skipped entirely when the optional dependency is absent, which is also the point:
the application must work without it.

The final test is the one that justifies this detector's existence. It is the pair the
lexical detector cannot reach, and it is a strict `xfail` over there.
"""

import os

# Set before anything imports sentence-transformers: the model is already cached, and
# the hub is not needed. Without this the suite depends on network reachability.
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

from datetime import datetime, timedelta, timezone as dt_timezone  # noqa: E402

import pytest  # noqa: E402

from mind import embeddings, services  # noqa: E402
from mind.detectors import find_dormant_threads  # noqa: E402
from mind.detectors.semantic_echo import (  # noqa: E402
    DEFAULT_MIN_SCORE,
    DETECTOR,
    Unavailable,
    find_semantic_echoes,
    propose_semantic_echoes,
)
from mind.models import (  # noqa: E402
    ConnectionHypothesis,
    Edge,
    EdgeRelation,
    Node,
    NodeSource,
    SentenceEmbedding,
)

pytestmark = [
    pytest.mark.django_db,
    pytest.mark.skipif(
        not embeddings.encoder_available(),
        reason="sentence-transformers is optional and not installed",
    ),
]

UTC = dt_timezone.utc
NOW = datetime(2026, 8, 12, 12, 0, tzinfo=UTC)

# The measured pair: the same scanner failing the same way, years apart. Heavy but
# unremarkable vocabulary overlap, which is exactly why the lexical detector's
# distinctive-term gate rejects it.
OLD_SCANNER = (
    "Third time this month the scanner utility has died halfway through a batch of "
    "receipts. I lose everything scanned so far and have to start the pile again from "
    "the beginning, and by then the evening is gone."
)
NEW_SCANNER = (
    "Sat down to deal with the receipts and the scanner gave up midway through, so the "
    "whole batch was lost. Rather than start the pile over I gave up for the night."
)
UNRELATED = (
    "The furnace filter needs changing every three months. The last one went in during "
    "July and the house has smelled dusty since the middle of August."
)


def _capture(owner, content, when, source=NodeSource.WEB):
    node = services.capture(
        owner,
        content=content,
        captured_at=datetime.fromisoformat(when).replace(tzinfo=UTC),
        source=source,
        actor="vince",
    )
    embeddings.embed_node(node)
    return node


# ---------------------------------------------------------------------------
# Vectors
# ---------------------------------------------------------------------------


def test_embedding_a_node_stores_one_vector_per_sentence(owner):
    node = _capture(owner, OLD_SCANNER, "2019-05-01")
    rows = SentenceEmbedding.objects.filter(node=node).order_by("seq")

    assert rows.count() >= 2
    assert all(row.index_version == embeddings.INDEX_VERSION for row in rows)
    assert all(len(row.embedding) == SentenceEmbedding.DIMENSIONS for row in rows)


def test_the_stored_spans_quote_the_real_sentence(owner):
    """The span is the citation a person reads, so it has to be exact."""
    node = _capture(owner, OLD_SCANNER, "2019-05-01")
    for row in SentenceEmbedding.objects.filter(node=node):
        quoted = node.original_content[row.span_start : row.span_end]
        assert quoted.strip() == quoted
        assert len(quoted) >= embeddings.MIN_SENTENCE_CHARS


def test_re_embedding_replaces_rather_than_duplicates(owner):
    """A partial backfill must be safe to simply run again."""
    node = _capture(owner, OLD_SCANNER, "2019-05-01")
    first = SentenceEmbedding.objects.filter(node=node).count()
    embeddings.embed_node(node)

    assert SentenceEmbedding.objects.filter(node=node).count() == first


def test_a_node_with_no_vectors_is_reported_not_silently_empty(owner):
    """An unembedded node and a node with no echoes are different situations, and
    conflating them would hide a broken backfill for months."""
    old = _capture(owner, OLD_SCANNER, "2019-05-01")
    unembedded = services.capture(
        owner,
        content=NEW_SCANNER,
        captured_at=NOW,
        source=NodeSource.WEB,
        actor="vince",
    )
    assert old  # embedded

    with pytest.raises(Unavailable, match="no sentence vectors"):
        find_semantic_echoes(unembedded, now=NOW)


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------


def test_a_dormant_echo_is_found(owner):
    old = _capture(owner, OLD_SCANNER, "2019-05-01")
    new = _capture(owner, NEW_SCANNER, "2026-08-01")

    findings = find_semantic_echoes(new, now=NOW)

    assert [f.candidate.pk for f in findings] == [old.pk]
    assert findings[0].match.score >= DEFAULT_MIN_SCORE


def test_the_finding_quotes_both_sentences(owner):
    """Stronger evidence than any score: the person reads the two sentences and
    judges, rather than trusting a number."""
    _capture(owner, OLD_SCANNER, "2019-05-01")
    new = _capture(owner, NEW_SCANNER, "2026-08-01")

    [finding] = find_semantic_echoes(new, now=NOW)

    assert finding.source_quote() in new.original_content
    assert finding.candidate_quote() in finding.candidate.original_content
    assert "scanner" in (
        finding.source_quote() + finding.candidate_quote()
    ).lower()


def test_an_unrelated_note_is_not_an_echo(owner):
    _capture(owner, UNRELATED, "2019-05-01")
    new = _capture(owner, NEW_SCANNER, "2026-08-01")

    assert find_semantic_echoes(new, now=NOW) == []


def test_a_recent_note_is_not_an_echo(owner):
    """Age is the non-obviousness proxy, as with the lexical detector."""
    _capture(owner, OLD_SCANNER, "2026-07-01")
    new = _capture(owner, NEW_SCANNER, "2026-08-01")

    assert find_semantic_echoes(new, now=NOW) == []


def test_the_threshold_is_respected(owner):
    _capture(owner, OLD_SCANNER, "2019-05-01")
    new = _capture(owner, NEW_SCANNER, "2026-08-01")

    assert find_semantic_echoes(new, now=NOW, min_score=0.3) != []
    assert find_semantic_echoes(new, now=NOW, min_score=0.99) == []


def test_an_already_linked_pair_is_not_proposed(owner):
    old = _capture(owner, OLD_SCANNER, "2019-05-01")
    new = _capture(owner, NEW_SCANNER, "2026-08-01")
    services.link(new, old, relation=EdgeRelation.RELATES_TO, now=NOW, actor="vince")

    assert find_semantic_echoes(new, now=NOW) == []


def test_a_short_note_proposes_nothing(owner):
    _capture(owner, OLD_SCANNER, "2019-05-01")
    new = _capture(owner, "scanner died again, lost the batch", "2026-08-01")

    assert find_semantic_echoes(new, now=NOW) == []


def test_deleted_notes_are_not_candidates(owner):
    old = _capture(owner, OLD_SCANNER, "2019-05-01")
    new = _capture(owner, NEW_SCANNER, "2026-08-01")
    assert find_semantic_echoes(new, now=NOW) != []

    services.delete_node(old, now=NOW, actor="vince")
    assert find_semantic_echoes(new, now=NOW) == []


def test_another_persons_notes_are_never_candidates(owner, other_owner):
    theirs = services.capture(
        other_owner,
        content=OLD_SCANNER,
        captured_at=datetime(2019, 5, 1, tzinfo=UTC),
        source=NodeSource.WEB,
        actor="them",
    )
    embeddings.embed_node(theirs)
    new = _capture(owner, NEW_SCANNER, "2026-08-01")

    assert find_semantic_echoes(new, now=NOW) == []


# ---------------------------------------------------------------------------
# Proposing
# ---------------------------------------------------------------------------


def test_finding_writes_nothing(owner):
    _capture(owner, OLD_SCANNER, "2019-05-01")
    new = _capture(owner, NEW_SCANNER, "2026-08-01")

    find_semantic_echoes(new, now=NOW)
    assert ConnectionHypothesis.objects.count() == 0


def test_the_proposal_carries_span_citations_at_both_ends(owner):
    """The design's span-level citation, actually used: a claim must be checkable
    against the passage, not the whole note."""
    old = _capture(owner, OLD_SCANNER, "2019-05-01")
    new = _capture(owner, NEW_SCANNER, "2026-08-01")

    [hypothesis] = propose_semantic_echoes(new, now=NOW)

    assert hypothesis.detector == DETECTOR
    assert hypothesis.index_version == embeddings.INDEX_VERSION
    assert hypothesis.claim_text is None, "nothing generated, still"

    spans = {m.node_id: (m.span_start, m.span_end) for m in hypothesis.members.all()}
    assert all(start is not None and end > start for start, end in spans.values())
    quoted = old.original_content[spans[old.pk][0] : spans[old.pk][1]]
    assert quoted in old.original_content


def test_the_label_is_a_quotation_not_a_description(owner):
    _capture(owner, OLD_SCANNER, "2019-05-01")
    new = _capture(owner, NEW_SCANNER, "2026-08-01")

    [hypothesis] = propose_semantic_echoes(new, now=NOW)
    assert hypothesis.label.startswith("echoes: ")


def test_the_confidence_is_the_cosine_not_a_rescaling(owner):
    """Rescaling to look decisive would misrepresent a similarity as a certainty."""
    _capture(owner, OLD_SCANNER, "2019-05-01")
    new = _capture(owner, NEW_SCANNER, "2026-08-01")

    [finding] = find_semantic_echoes(new, now=NOW)
    [hypothesis] = propose_semantic_echoes(new, now=NOW)

    assert hypothesis.confidence == pytest.approx(finding.match.score, abs=1e-6)


def test_nothing_is_promoted_by_proposing(owner):
    _capture(owner, OLD_SCANNER, "2019-05-01")
    new = _capture(owner, NEW_SCANNER, "2026-08-01")

    propose_semantic_echoes(new, now=NOW)
    assert Edge.objects.count() == 0


def test_rerunning_proposes_nothing_new(owner):
    _capture(owner, OLD_SCANNER, "2019-05-01")
    new = _capture(owner, NEW_SCANNER, "2026-08-01")

    first = propose_semantic_echoes(new, now=NOW)
    second = propose_semantic_echoes(new, now=NOW)

    assert len(first) == 1
    assert second == []
    assert ConnectionHypothesis.objects.count() == 1


def test_a_dismissed_echo_is_not_offered_again(owner):
    _capture(owner, OLD_SCANNER, "2019-05-01")
    new = _capture(owner, NEW_SCANNER, "2026-08-01")

    [hypothesis] = propose_semantic_echoes(new, now=NOW)
    services.dismiss_hypothesis(hypothesis, now=NOW, actor="vince")

    assert propose_semantic_echoes(new, now=NOW) == []


def test_confirming_creates_a_relates_to_edge(owner):
    old = _capture(owner, OLD_SCANNER, "2019-05-01")
    new = _capture(owner, NEW_SCANNER, "2026-08-01")

    [hypothesis] = propose_semantic_echoes(new, now=NOW)
    [edge] = services.confirm_hypothesis(hypothesis, now=NOW, actor="vince")

    assert edge.relation == EdgeRelation.RELATES_TO
    assert {edge.from_node_id, edge.to_node_id} == {new.pk, old.pk}


# ---------------------------------------------------------------------------
# The reason this detector exists
# ---------------------------------------------------------------------------


SCANNER_FILLER = [
    "Took the receipts to the accountant's office in a shoe box this time, which was "
    "not much better than the scanner but at least the batch stayed in one pile.",
    "The office scanner jammed on a batch of contracts and I had to feed the pile "
    "through one sheet at a time, which took most of the morning.",
    "Started a fresh pile for this quarter's receipts. Keeping the batch small so the "
    "scanner has less chance to lose the lot.",
]


def test_it_finds_what_the_lexical_detector_cannot_once_vocabulary_recurs(owner):
    """The measured case, reproduced faithfully — and the condition matters.

    The lexical detector's blindness here is **corpus-dependent, not absolute.** In a
    two-note corpus every shared term appears in exactly one other note, so all of them
    are distinctive and it finds this pair easily. What puts the pair out of reach is a
    corpus where "scanner", "batch", "receipt" and "pile" have become ordinary
    vocabulary — which is what the 46-note evaluation corpus reproduces and why the
    positive control is a strict `xfail` there.

    Which means the complementarity **strengthens as a corpus grows**: the more a
    person's vocabulary recurs, the more pairs fall outside a distinctive-term gate, and
    the more a semantic index is the only thing that can reach them.
    """
    for index, text in enumerate(SCANNER_FILLER):
        _capture(owner, text, f"2021-0{index + 1}-15")

    old = _capture(owner, OLD_SCANNER, "2019-05-01")
    new = _capture(owner, NEW_SCANNER, "2026-08-01")

    assert find_dormant_threads(new, now=NOW) == [], "lexical: out of reach"

    # Membership, not exclusivity. Making those four terms unremarkable requires
    # notes that actually use them, and notes that use them are genuinely about the
    # same thing — so the other matches are correct rather than noise. The vocabulary
    # cannot be made common without also making the topic common; that is the honest
    # shape of the problem, and it is why volume is capped and a person decides.
    found = {f.candidate.pk for f in find_semantic_echoes(new, now=NOW)}
    assert old.pk in found
