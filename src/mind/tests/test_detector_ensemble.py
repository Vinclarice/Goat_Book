"""Both detectors over the evaluation corpus, and what they achieve together.

The claim being pinned is the one that justified building a second index instead of
replacing the first: the two find **different** connections, so the union beats either.
If a change quietly makes them redundant, this is where it shows.

Skipped without the optional embedding dependency, like everything else that needs it.
"""

import os

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

from datetime import datetime, timezone as dt_timezone  # noqa: E402

import pytest  # noqa: E402

from mind import embeddings, services  # noqa: E402
from mind.detectors import find_dormant_threads, find_semantic_echoes  # noqa: E402
from mind.detectors.semantic_echo import Unavailable  # noqa: E402
from mind.models import NodeSource  # noqa: E402
from mind.tests.fixtures.corpus import CORPUS, FALSE_PAIRS, TRUE_PAIRS  # noqa: E402

pytestmark = [
    pytest.mark.django_db,
    pytest.mark.skipif(
        not embeddings.encoder_available(),
        reason="sentence-transformers is optional and not installed",
    ),
]

UTC = dt_timezone.utc
NOW = datetime(2026, 8, 12, 12, 0, tzinfo=UTC)

TRUE_SET = {(a, b) for a, b, _ in TRUE_PAIRS}
FALSE_SET = {(a, b) for a, b, _ in FALSE_PAIRS}


@pytest.fixture
def embedded_corpus(owner):
    """The 46-note fixture, captured and embedded. Slow, and worth it."""
    nodes = {}
    for entry in CORPUS:
        node = services.capture(
            owner,
            content=entry.body,
            captured_at=datetime.fromisoformat(entry.date).replace(tzinfo=UTC),
            source=NodeSource.IMPORT,
            actor="fixture",
            import_key=f"corpus:{entry.key}",
        )
        embeddings.embed_node(node)
        nodes[entry.key] = node
    return nodes


def _proposals(nodes, finder) -> set[tuple[str, str]]:
    by_pk = {node.pk: key for key, node in nodes.items()}
    found = set()
    for key, node in nodes.items():
        try:
            findings = finder(node, now=NOW)
        except Unavailable:
            continue
        for finding in findings:
            found.add((key, by_pk[finding.candidate.pk]))
    return found


def test_each_detector_stays_at_its_measured_operating_point(embedded_corpus, capsys):
    """A regression guard on the numbers the documentation quotes.

    Ranges rather than exact figures: the point is that neither detector has drifted
    into noise, not that a particular count is sacred.
    """
    results = {}
    for name, finder in (
        ("dormant_thread", find_dormant_threads),
        ("semantic_echo", find_semantic_echoes),
    ):
        proposals = _proposals(embedded_corpus, finder)
        correct = proposals & TRUE_SET
        traps = proposals & FALSE_SET
        results[name] = (proposals, correct, traps)

        with capsys.disabled():
            precision = len(correct) / len(proposals) if proposals else 0
            print(
                f"\n  {name}: {len(proposals)} proposals, {len(correct)} correct, "
                f"{len(traps)} traps — precision {precision:.0%}, "
                f"recall {len(correct)}/{len(TRUE_PAIRS)}"
            )
            for source, other in sorted(proposals):
                kind = (
                    "correct"
                    if (source, other) in TRUE_SET
                    else "TRAP" if (source, other) in FALSE_SET else "spurious"
                )
                print(f"    {kind:8} {source} <- {other}")

    for name, (proposals, correct, traps) in results.items():
        assert not traps, f"{name} surfaced a trap"
        assert len(proposals) <= 6, f"{name} volume is no longer reviewable"
        assert len(correct) >= 2, f"{name} found fewer than two real connections"


def test_the_two_detectors_find_different_connections(embedded_corpus, capsys):
    """The whole argument for two indexes rather than one swapped.

    Whole-document embeddings scored 0% precision and would have been a regression.
    Sentence-level embeddings match the lexical detector's precision while reaching a
    connection it cannot — so the union is worth more than either, and this asserts the
    overlap is genuinely partial.
    """
    lexical = _proposals(embedded_corpus, find_dormant_threads) & TRUE_SET
    semantic = _proposals(embedded_corpus, find_semantic_echoes) & TRUE_SET

    union = lexical | semantic
    with capsys.disabled():
        print(
            f"\n  lexical {len(lexical)}/6, semantic {len(semantic)}/6, "
            f"union {len(union)}/6"
        )
        for pair in sorted(union):
            who = []
            if pair in lexical:
                who.append("lexical")
            if pair in semantic:
                who.append("semantic")
            print(f"    {'+'.join(who):18} {pair[0]} <- {pair[1]}")

    assert semantic - lexical, "semantic found nothing the lexical detector missed"
    assert len(union) > len(lexical), "the second index added no recall"
    assert len(union) > len(semantic), "the first index is now redundant"


def test_the_ensemble_stays_precise_as_well_as_broader(embedded_corpus):
    """Recall bought with noise would be the wrong trade.

    Precision beats recall throughout, so an ensemble that found more by proposing far
    more would be a regression dressed as an improvement.
    """
    proposals = _proposals(embedded_corpus, find_dormant_threads) | _proposals(
        embedded_corpus, find_semantic_echoes
    )
    correct = proposals & TRUE_SET

    assert not proposals & FALSE_SET
    assert len(correct) / len(proposals) >= 0.6
    assert len(proposals) <= 10, "across 46 notes, still a handful"
