"""The dormant-thread detector's mechanics.

Each test here pins one of the three conditions that make a proposal worth
surfacing, or one of the filters that keeps precision high. The costs are
asymmetric — a missed connection costs one connection, a stream of poor ones
teaches the person to skim past the review surface — so most of these are about
what the detector must *refuse*.
"""

from datetime import datetime, timedelta, timezone as dt_timezone

import pytest

from mind import services
from mind.detectors import find_dormant_threads, propose_dormant_threads
from mind.detectors.dormant_thread import DETECTOR
from mind.models import ConnectionHypothesis, Edge, EdgeRelation, EventType, Node
from mind.similarity import PostgresFullTextIndex

pytestmark = pytest.mark.django_db

UTC = dt_timezone.utc
NOW = datetime(2026, 8, 12, 12, 0, tzinfo=UTC)
LONG_AGO = "2019-05-01"
RECENTLY = "2026-07-01"

# Long enough to clear the length floor, and sharing distinctive vocabulary.
OLD_LESSONS = (
    "I keep putting the Mondly lessons off until the evening, and then I am too "
    "tired to start them. The intention is there every morning and gone by nine."
)
NEW_LESSONS = (
    "Signed up for Mondly again this week. Determined to do the lessons in the "
    "morning this time rather than leaving them until the evening when I am tired."
)
UNRELATED = (
    "The furnace filter needs changing every three months. Last one went in "
    "during July and the house has smelled dusty since the middle of August."
)


def _capture(owner, content, when, source=Node.Source.WEB):
    return services.capture(
        owner,
        content=content,
        captured_at=datetime.fromisoformat(when).replace(tzinfo=UTC),
        source=source,
        actor="vince",
    )


# ---------------------------------------------------------------------------
# The three conditions
# ---------------------------------------------------------------------------


def test_a_dormant_related_note_is_found(owner):
    old = _capture(owner, OLD_LESSONS, LONG_AGO)
    new = _capture(owner, NEW_LESSONS, "2026-08-01")

    findings = find_dormant_threads(new, now=NOW)

    assert [f.candidate.pk for f in findings] == [old.pk]
    assert findings[0].match.shared_count >= 3
    assert "mond" in findings[0].match.shared_terms


def test_a_recently_captured_note_is_not_a_dormant_thread(owner):
    """Similarity alone would surface things the person would have found by
    searching. Age is the whole non-obviousness proxy."""
    _capture(owner, OLD_LESSONS, RECENTLY)
    new = _capture(owner, NEW_LESSONS, "2026-08-01")

    assert find_dormant_threads(new, now=NOW) == []


def test_an_unrelated_old_note_is_not_found(owner):
    _capture(owner, UNRELATED, LONG_AGO)
    new = _capture(owner, NEW_LESSONS, "2026-08-01")

    assert find_dormant_threads(new, now=NOW) == []


def test_a_note_already_linked_is_not_proposed(owner):
    """A connection the person already made is not a discovery, and offering it
    spends attention to say something they know."""
    old = _capture(owner, OLD_LESSONS, LONG_AGO)
    new = _capture(owner, NEW_LESSONS, "2026-08-01")
    services.link(new, old, relation=EdgeRelation.RELATES_TO, now=NOW, actor="vince")

    assert find_dormant_threads(new, now=NOW) == []


def test_a_link_in_either_direction_counts_as_connected(owner):
    old = _capture(owner, OLD_LESSONS, LONG_AGO)
    new = _capture(owner, NEW_LESSONS, "2026-08-01")
    services.link(old, new, relation=EdgeRelation.DEVELOPED_FROM, now=NOW, actor="vince")

    assert find_dormant_threads(new, now=NOW) == []


def test_a_note_being_reviewed_is_not_forgotten(owner):
    """Whatever its age, a note the person keeps revisiting is not a
    rediscovery."""
    old = _capture(owner, OLD_LESSONS, LONG_AGO)
    new = _capture(owner, NEW_LESSONS, "2026-08-01")
    services._record(
        owner,
        EventType.REVIEWED,
        node=old,
        occurred_at=datetime(2026, 6, 1, tzinfo=UTC),
        actor="vince",
    )

    assert find_dormant_threads(new, now=NOW) == []


# ---------------------------------------------------------------------------
# Precision filters
# ---------------------------------------------------------------------------


def test_a_one_line_errand_is_never_a_dormant_thread(owner):
    """"buy milk" is not a forgotten insight. A crude salience floor, but it uses
    a signal already present rather than asking the person to rate notes."""
    _capture(owner, "mondly lessons", LONG_AGO)
    new = _capture(owner, NEW_LESSONS, "2026-08-01")

    assert find_dormant_threads(new, now=NOW) == []


def test_a_short_new_note_proposes_nothing(owner):
    _capture(owner, OLD_LESSONS, LONG_AGO)
    new = _capture(owner, "mondly again", "2026-08-01")

    assert find_dormant_threads(new, now=NOW) == []


def test_the_shared_term_floor_is_respected(owner):
    old = _capture(owner, OLD_LESSONS, LONG_AGO)
    new = _capture(owner, NEW_LESSONS, "2026-08-01")

    assert find_dormant_threads(new, now=NOW, min_shared_terms=3) != []
    assert find_dormant_threads(new, now=NOW, min_shared_terms=50) == []


def test_the_source_note_is_never_its_own_candidate(owner):
    new = _capture(owner, NEW_LESSONS, LONG_AGO)
    assert find_dormant_threads(new, now=NOW) == []


def test_deleted_and_archived_notes_are_not_candidates(owner):
    old = _capture(owner, OLD_LESSONS, LONG_AGO)
    new = _capture(owner, NEW_LESSONS, "2026-08-01")
    assert find_dormant_threads(new, now=NOW) != []

    services.delete_node(old, now=NOW, actor="vince")
    assert find_dormant_threads(new, now=NOW) == []


def test_another_persons_notes_are_never_candidates(owner, other_owner):
    services.capture(
        other_owner,
        content=OLD_LESSONS,
        captured_at=datetime.fromisoformat(LONG_AGO).replace(tzinfo=UTC),
        source=Node.Source.WEB,
        actor="them",
    )
    new = _capture(owner, NEW_LESSONS, "2026-08-01")

    assert find_dormant_threads(new, now=NOW) == []


def test_proposals_are_capped_per_capture(owner):
    """A handful that mostly land beats thirty that mostly do not.

    Each old note carries its own rare vocabulary, because a term repeated across
    several notes is not distinctive — see the test below.
    """
    topics = [
        ("kiln", "glaze", "earthenware"),
        ("sourdough", "levain", "banneton"),
        ("zither", "tuning", "fretboard"),
        ("bouldering", "chalk", "overhang"),
    ]
    for words in topics:
        _capture(
            owner,
            f"Spent the evening on {words[0]} again. The {words[1]} still needs "
            f"work and the {words[2]} was a mistake, but it is becoming a habit.",
            LONG_AGO,
        )
    new = _capture(
        owner,
        "Thinking about the evening habits I keep starting and dropping: kiln, "
        "glaze, earthenware, sourdough, levain, banneton, zither, tuning, "
        "fretboard, bouldering, chalk, overhang. Too many at once, as usual.",
        "2026-08-01",
    )

    assert len(find_dormant_threads(new, now=NOW, limit=2)) == 2
    assert len(find_dormant_threads(new, now=NOW, limit=10)) == 4


def test_a_term_repeated_across_several_notes_is_not_distinctive(owner):
    """A real consequence of the gate, worth pinning.

    Distinctive means "appears in exactly one other note". Write about the same
    specific thing three times and no term is distinctive any more, so this
    detector stops connecting them — a pairwise rediscovery is not what a recurring
    theme is. That case belongs to *Recurring preoccupation*, which is deferred.
    """
    for _ in range(3):
        _capture(owner, OLD_LESSONS, LONG_AGO)
    new = _capture(owner, NEW_LESSONS, "2026-08-01")

    assert find_dormant_threads(new, now=NOW) == []


# ---------------------------------------------------------------------------
# Proposing
# ---------------------------------------------------------------------------


def test_finding_writes_nothing(owner):
    """Thresholds must be explorable without polluting the accept-rate history
    that is the only evidence about whether this detector works."""
    _capture(owner, OLD_LESSONS, LONG_AGO)
    new = _capture(owner, NEW_LESSONS, "2026-08-01")

    find_dormant_threads(new, now=NOW)
    assert ConnectionHypothesis.objects.count() == 0


def test_proposing_records_a_hypothesis_with_its_evidence(owner):
    old = _capture(owner, OLD_LESSONS, LONG_AGO)
    new = _capture(owner, NEW_LESSONS, "2026-08-01")

    [hypothesis] = propose_dormant_threads(new, now=NOW)

    assert hypothesis.detector == DETECTOR
    assert hypothesis.index_version == PostgresFullTextIndex.version
    assert 0 < hypothesis.confidence <= 1
    assert set(hypothesis.members.values_list("node_id", flat=True)) == {new.pk, old.pk}
    assert all(m.contribution_reason for m in hypothesis.members.all())


def test_the_label_is_extractive_and_names_the_shared_terms(owner):
    """v1 ships no generative producer. For a term-mediated connection none is
    needed: naming the overlap states the dimension plainly."""
    _capture(owner, OLD_LESSONS, LONG_AGO)
    new = _capture(owner, NEW_LESSONS, "2026-08-01")

    [hypothesis] = propose_dormant_threads(new, now=NOW)

    assert hypothesis.label.startswith("shares: ")
    assert "mond" in hypothesis.label
    assert hypothesis.claim_text is None


def test_the_candidates_reason_states_the_dormancy(owner):
    _capture(owner, OLD_LESSONS, LONG_AGO)
    new = _capture(owner, NEW_LESSONS, "2026-08-01")

    [hypothesis] = propose_dormant_threads(new, now=NOW)
    reasons = [m.contribution_reason for m in hypothesis.members.all()]

    assert any("shared terms" in r and "months" in r for r in reasons)


def test_a_proposal_starts_unsurfaced_with_no_review_clock(owner):
    """Silence is not consent: the window cannot begin before the person has
    seen it."""
    _capture(owner, OLD_LESSONS, LONG_AGO)
    new = _capture(owner, NEW_LESSONS, "2026-08-01")

    [hypothesis] = propose_dormant_threads(new, now=NOW)

    assert hypothesis.first_surfaced_at is None
    assert hypothesis.surface_count == 0
    assert hypothesis.review_window_expires_at is None
    assert hypothesis.resolved_at is None


def test_nothing_is_promoted_by_proposing(owner):
    _capture(owner, OLD_LESSONS, LONG_AGO)
    new = _capture(owner, NEW_LESSONS, "2026-08-01")

    propose_dormant_threads(new, now=NOW)
    assert Edge.objects.count() == 0


def test_rerunning_the_detector_proposes_nothing_new(owner):
    """The detector will be re-run while it is tuned, and re-running must be
    free of side effects.

    The second call returns an empty list rather than the same hypothesis again:
    it proposed nothing, and reporting what it *found* rather than what it tried
    is what keeps a proposal count meaningful.
    """
    _capture(owner, OLD_LESSONS, LONG_AGO)
    new = _capture(owner, NEW_LESSONS, "2026-08-01")

    first = propose_dormant_threads(new, now=NOW)
    second = propose_dormant_threads(new, now=NOW)

    assert len(first) == 1
    assert second == []
    assert ConnectionHypothesis.objects.count() == 1


def test_a_dismissed_proposal_is_not_offered_again(owner):
    """The fingerprint spans resolved rows, so a dismissal is permanent — and
    the detector filters it out before proposing, so the count stays honest."""
    _capture(owner, OLD_LESSONS, LONG_AGO)
    new = _capture(owner, NEW_LESSONS, "2026-08-01")

    [hypothesis] = propose_dormant_threads(new, now=NOW)
    services.dismiss_hypothesis(hypothesis, now=NOW, actor="vince")

    assert propose_dormant_threads(new, now=NOW) == []
    assert ConnectionHypothesis.objects.count() == 1


def test_confirming_a_proposal_creates_a_relates_to_edge(owner):
    """Nothing stronger is claimed than "these relate" — the detector observes an
    overlap, not a direction."""
    old = _capture(owner, OLD_LESSONS, LONG_AGO)
    new = _capture(owner, NEW_LESSONS, "2026-08-01")

    [hypothesis] = propose_dormant_threads(new, now=NOW)
    [edge] = services.confirm_hypothesis(hypothesis, now=NOW, actor="vince")

    assert edge.relation == EdgeRelation.RELATES_TO
    assert {edge.from_node_id, edge.to_node_id} == {new.pk, old.pk}
    assert edge.origin == "inferred"


def test_a_confirmed_connection_is_not_re_proposed(owner):
    old = _capture(owner, OLD_LESSONS, LONG_AGO)
    new = _capture(owner, NEW_LESSONS, "2026-08-01")

    [hypothesis] = propose_dormant_threads(new, now=NOW)
    services.confirm_hypothesis(hypothesis, now=NOW, actor="vince")

    assert propose_dormant_threads(new, now=NOW) == []


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def test_a_candidate_that_is_mostly_the_shared_terms_ranks_higher(owner):
    """Both share the same terms with the new note; one is padded with filler.

    The weighted score cannot tell them apart — it is normalised by the query's own
    vocabulary, so candidate length is invisible to it. Dice breaks the tie in the
    right direction: a note largely about the shared terms is a better match than
    one that merely mentions them somewhere in three hundred words.

    Tested through the index rather than the detector, with the distinctive gate
    off. Two candidates sharing the same terms make those terms appear in two
    notes, so by construction neither can be distinctive — which is correct
    behaviour and would leave nothing to order.
    """
    focused = _capture(owner, OLD_LESSONS, LONG_AGO)
    padded = _capture(
        owner,
        OLD_LESSONS
        + " "
        + " ".join(f"unrelated{i} filler sentence here." for i in range(80)),
        LONG_AGO,
    )
    new = _capture(owner, NEW_LESSONS, "2026-08-01")

    matches = PostgresFullTextIndex().similar_to(
        new.original_content,
        owner=owner,
        source_node_id=new.pk,
        min_shared_terms=2,
        min_distinctive_terms=0,
    )
    ranked = [m.node_id for m in matches]

    assert ranked[:2] == [focused.pk, padded.pk]
    assert matches[0].dice > matches[1].dice


def test_confidence_saturates_rather_than_exceeding_one(owner):
    from mind.detectors.dormant_thread import CONFIDENCE_SATURATION, Finding
    from mind.similarity import Match

    match = Match(
        node_id=1,
        shared_terms=tuple(f"t{i}" for i in range(CONFIDENCE_SATURATION * 3)),
        candidate_term_count=100,
        query_term_count=40,
    )
    finding = Finding(candidate=None, match=match, dormant_for=timedelta(days=600))
    assert finding.confidence == 1.0


def test_dice_is_symmetric_in_both_documents(owner):
    """Dice is the tiebreak, and being symmetric is the whole reason.

    The primary score is normalised by the *query's* weight mass, so it cannot see
    how long the candidate is. Dice can, in both directions — which is what lets
    it separate a candidate that is mostly the shared terms from one that merely
    contains them.
    """
    from mind.similarity import Match

    a = Match(
        node_id=1, shared_terms=("x", "y"), candidate_term_count=10, query_term_count=20
    )
    b = Match(
        node_id=2, shared_terms=("x", "y"), candidate_term_count=20, query_term_count=10
    )
    assert a.dice == b.dice == pytest.approx(4 / 30)
