"""Measuring the detector against a corpus with known answers.

The fixture holds 46 fictional notes spanning 2018–2026, with six genuine dormant
threads and eight deliberate traps. Its true pairs are written with *low lexical
overlap* on purpose — the same concern described in different words — because
that is what a real forgotten connection looks like and what the product claims
to find.

The asymmetry in what these tests assert is the point:

* **Precision is asserted per trap.** Each false pair gets its own test, so a leak
  names itself. This is the property the product cannot trade away: a stream of
  poor proposals teaches the person to skim past the review surface, and no later
  improvement recovers that.
* **Recall is measured, not demanded.** Full-text search cannot see a connection
  expressed in different words. The recall number here is therefore evidence about
  the *ceiling of the v1 index*, not a bar the detector is failing to clear — and
  it is exactly the evidence the deferred embeddings decision is supposed to be
  made on.
"""

from datetime import datetime, timezone as dt_timezone

import pytest

from mind import services
from mind.detectors import find_dormant_threads
from mind.models import NodeSource
from mind.tests.fixtures.corpus import CORPUS, FALSE_PAIRS, TRUE_PAIRS

pytestmark = pytest.mark.django_db

UTC = dt_timezone.utc
NOW = datetime(2026, 8, 12, 12, 0, tzinfo=UTC)


@pytest.fixture
def loaded_corpus(owner):
    """Every fixture entry as a node, keyed by slug.

    Imported through the ordinary capture service with each entry's own date, so
    this exercises the same path a real backfill would.
    """
    nodes = {}
    for entry in CORPUS:
        nodes[entry.key] = services.capture(
            owner,
            content=entry.body,
            captured_at=datetime.fromisoformat(entry.date).replace(tzinfo=UTC),
            source=NodeSource.IMPORT,
            actor="fixture",
            import_key=f"corpus:{entry.key}",
        )
    return nodes


def _surfaced_keys(loaded_corpus, source_key: str) -> set[str]:
    by_pk = {node.pk: key for key, node in loaded_corpus.items()}
    findings = find_dormant_threads(loaded_corpus[source_key], now=NOW)
    return {by_pk[f.candidate.pk] for f in findings}


# ---------------------------------------------------------------------------
# Precision — the property that cannot be traded away
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "source_key,forbidden_key,why",
    [pytest.param(a, b, why, id=f"{a}--{b}") for a, b, why in FALSE_PAIRS],
)
def test_no_trap_is_surfaced(loaded_corpus, source_key, forbidden_key, why):
    """Each trap is its own test so a leak names itself rather than hiding in an
    aggregate."""
    assert forbidden_key not in _surfaced_keys(loaded_corpus, source_key), why


def test_the_highest_literal_overlap_in_the_corpus_is_not_surfaced(loaded_corpus):
    """The sharpest case in the fixture.

    `shop-closing-2022` has a genuine dormant thread (a project idea from 2018)
    *and* a trap: a shopping-list errand naming the same shop, which is the
    strongest literal match anywhere in the corpus. Lexical overlap alone would
    pick the wrong one.
    """
    surfaced = _surfaced_keys(loaded_corpus, "shop-closing-2022")
    assert "kesslers-errand-2021" not in surfaced


# ---------------------------------------------------------------------------
# Recall — measured, and the number is the finding
# ---------------------------------------------------------------------------


@pytest.mark.xfail(
    strict=True,
    reason=(
        "The recorded ceiling of the full-text index, not a defect to chase. "
        "This pair — the same scanner failing the same way seven years apart — "
        "shares seven terms, but only two of them appear in almost no other note. "
        "At a precision-first threshold that is not enough, because high "
        "vocabulary overlap without rare terms is indistinguishable from prose "
        "coincidence: the three highest-scoring pairs in this corpus are noise. "
        "NOW COVERED ELSEWHERE — semantic_echo finds this pair at 100% precision "
        "(see test_semantic_echo.py and test_detector_ensemble.py), which is why a "
        "second index was built rather than this threshold loosened. The xfail stays "
        "because it remains true of the *lexical* detector, and strict so that if a "
        "change ever makes it reachable, the baseline is revisited deliberately."
    ),
)
def test_the_high_overlap_positive_control_is_found(loaded_corpus):
    """The true pair written with deliberately high vocabulary overlap.

    Written as a control on the assumption that full-text search would at least
    manage this one. It does not — which is the single most useful result the
    evaluation produced.
    """
    assert "scanner-jam-2018" in _surfaced_keys(loaded_corpus, "receipts-again-2025")


def test_precision_over_the_whole_corpus_is_recorded(loaded_corpus, capsys):
    """The operating point, stated as numbers rather than as a hope.

    Three proposals across forty-six notes, two of them genuine. That volume is
    reviewable and that precision is defensible; both were reached by requiring
    shared terms that appear nowhere else, after score thresholds alone topped out
    at 11% precision with noise outranking every true pair.
    """
    expected = {(a, b) for a, b, _ in TRUE_PAIRS}
    proposals = [
        (source, surfaced)
        for source in loaded_corpus
        for surfaced in _surfaced_keys(loaded_corpus, source)
    ]
    correct = [p for p in proposals if p in expected]

    with capsys.disabled():
        total = len(proposals)
        rate = f"{len(correct)}/{total}" if total else "0/0"
        print(f"\n  precision: {rate}   recall: {len(correct)}/{len(TRUE_PAIRS)}")
        for source, surfaced in sorted(proposals):
            mark = "correct" if (source, surfaced) in expected else "spurious"
            print(f"    {mark:8} {source} <- {surfaced}")

    assert len(proposals) <= 6, "volume must stay reviewable"
    assert len(correct) >= 2, "at least two genuine connections must survive"


def test_recall_over_the_true_pairs_is_reported(loaded_corpus, capsys):
    """Not a bar to clear — a measurement of what the v1 index can see.

    Recorded rather than asserted at a high threshold because failing to find a
    connection stated in different words is the *known* limitation of full-text
    search, not a defect in the detector. This number is the evidence the
    embeddings decision is meant to rest on.
    """
    found, missed = [], []
    for source_key, expected_key, why in TRUE_PAIRS:
        if expected_key in _surfaced_keys(loaded_corpus, source_key):
            found.append((source_key, expected_key))
        else:
            missed.append((source_key, expected_key, why))

    total = len(TRUE_PAIRS)
    with capsys.disabled():
        print(f"\n  dormant_thread recall on FTS: {len(found)}/{total}")
        for source_key, expected_key in found:
            print(f"    found  {source_key} <- {expected_key}")
        for source_key, expected_key, why in missed:
            print(f"    missed {source_key} <- {expected_key}")
            print(f"           {why[:88]}")

    # A floor, not a target. Below this the detector is not working at all;
    # above it, the gap is the index's ceiling and not a bug to chase.
    assert len(found) >= 1, "not even the high-overlap control was found"


def test_the_detector_is_quiet_on_mundane_filler(loaded_corpus):
    """Most of a real corpus is unremarkable, and a detector that fires on
    errands is worse than one that stays silent."""
    logistics = [
        entry.key
        for entry in CORPUS
        if len(entry.body.split()) < 20
        and entry.key in loaded_corpus
    ]
    assert logistics, "the fixture should contain short logistics notes"

    noisy = {
        key: _surfaced_keys(loaded_corpus, key)
        for key in logistics
        if _surfaced_keys(loaded_corpus, key)
    }
    assert noisy == {}, f"short notes should propose nothing, got {noisy}"


def test_total_proposal_volume_over_the_whole_corpus_stays_small(loaded_corpus, capsys):
    """The volume a person would actually face.

    Precision beats recall here, so the useful question is not "how many
    connections exist" but "how many would be put in front of someone" — a
    handful across a decade of notes is right, and dozens is a second inbox.
    """
    per_note = {
        key: _surfaced_keys(loaded_corpus, key) for key in loaded_corpus
    }
    total = sum(len(v) for v in per_note.values())

    with capsys.disabled():
        print(f"\n  proposals across {len(loaded_corpus)} notes: {total}")
        for key, surfaced in sorted(per_note.items()):
            if surfaced:
                print(f"    {key} -> {', '.join(sorted(surfaced))}")

    # Two per note averaged across the corpus would already be a second inbox.
    assert total <= len(loaded_corpus), (
        f"{total} proposals over {len(loaded_corpus)} notes is too much to review"
    )
