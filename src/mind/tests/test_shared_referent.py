"""The shared-referent detector.

Its evidence is *exact* — a confirmed alias plus confirmed mentions at both ends —
so precision comes from the architecture rather than from a threshold. That makes
these tests mostly about the gate: **the labels must differ**, because two notes
both saying "Bob" are already findable by searching for Bob.

The last test is the one that matters most. It is the pair the lexical detector
misses by construction, and the reason this detector exists.
"""

from datetime import datetime, timedelta, timezone as dt_timezone

import pytest

from mind import services
from mind.detectors import (
    find_dormant_threads,
    find_shared_referents,
    propose_shared_referents,
)
from mind.detectors.shared_referent import DETECTOR
from mind.models import (
    ConceptCandidate,
    ConceptType,
    ConnectionHypothesis,
    Edge,
    EdgeRelation,
    InferenceOrigin,
    Node,
)

pytestmark = pytest.mark.django_db

UTC = dt_timezone.utc
NOW = datetime(2026, 8, 12, 12, 0, tzinfo=UTC)


def _capture(owner, content, when):
    return services.capture(
        owner,
        content=content,
        captured_at=datetime.fromisoformat(when).replace(tzinfo=UTC),
        source=Node.Source.WEB,
        actor="vince",
    )


def _concept(owner, label, confirmed=True):
    concept = services.propose_concept(
        owner,
        label=label,
        concept_type=ConceptType.PERSON,
        now=NOW,
        actor="system",
    )
    if confirmed:
        services.confirm_concept(concept, now=NOW, actor="vince")
    return concept


def _mention(node, concept, confirmed=True):
    mention = services.propose_mention(
        node,
        concept,
        index_version="rules-v1",
        now=NOW,
        actor="system",
    )
    if confirmed:
        services.confirm_mention(mention, now=NOW, actor="vince")
    return mention


@pytest.fixture
def aliased_pair(owner):
    """Two notes naming one person differently, with the alias confirmed."""
    old = _capture(
        owner,
        "The woman in 4B practises most evenings. She played in an orchestra in Lyon "
        "before she moved here, apparently for years.",
        "2019-06-02",
    )
    new = _capture(
        owner,
        "Marguerite from upstairs invited us to a recital. I had no idea she still "
        "performed.",
        "2025-04-11",
    )

    canonical = _concept(owner, "Marguerite")
    alias = _concept(owner, "the woman in 4B")
    services.merge_concept(alias, canonical, now=NOW, actor="vince")

    _mention(old, alias)
    _mention(new, canonical)
    return {"old": old, "new": new, "canonical": canonical, "alias": alias}


# ---------------------------------------------------------------------------
# The gate: labels must differ
# ---------------------------------------------------------------------------


def test_a_referent_named_differently_is_surfaced(aliased_pair):
    findings = find_shared_referents(aliased_pair["new"], now=NOW)

    assert [f.candidate.pk for f in findings] == [aliased_pair["old"].pk]
    assert findings[0].concept.pk == aliased_pair["canonical"].pk


def test_the_same_label_in_both_notes_is_not_surfaced(owner):
    """Both notes say "Marguerite" — findable by searching for Marguerite, so
    proposing it spends attention to report something already retrievable."""
    concept = _concept(owner, "Marguerite")
    old = _capture(owner, "Marguerite practises most evenings downstairs.", "2019-06-02")
    new = _capture(owner, "Marguerite invited us to a recital upstairs.", "2025-04-11")
    _mention(old, concept)
    _mention(new, concept)

    assert find_shared_referents(new, now=NOW) == []


def test_an_unconfirmed_alias_does_not_connect_anything(owner):
    """Without the merge the two labels are simply two referents. Resolution is
    the person's act, and nothing is inferred in its place."""
    old = _capture(owner, "The woman in 4B practises most evenings.", "2019-06-02")
    new = _capture(owner, "Marguerite invited us to a recital.", "2025-04-11")
    _mention(old, _concept(owner, "the woman in 4B"))
    _mention(new, _concept(owner, "Marguerite"))

    assert find_shared_referents(new, now=NOW) == []


def test_an_unconfirmed_mention_does_not_count(owner):
    """Letting the system's own extraction justify a proposal is how a classifier
    starts feeding on its output."""
    canonical = _concept(owner, "Marguerite")
    alias = _concept(owner, "the woman in 4B")
    services.merge_concept(alias, canonical, now=NOW, actor="vince")

    old = _capture(owner, "The woman in 4B practises most evenings.", "2019-06-02")
    new = _capture(owner, "Marguerite invited us to a recital.", "2025-04-11")
    _mention(old, alias, confirmed=False)
    _mention(new, canonical)

    assert find_shared_referents(new, now=NOW) == []


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------


def test_the_gap_is_a_knob_and_still_filters_when_turned_up(aliased_pair, owner):
    """The parameter survives the default going to zero, so a gap can be
    reintroduced on evidence rather than by editing the detector."""
    same_day = _capture(owner, "Marguerite mentioned the recital again.", "2025-04-12")
    _mention(same_day, aliased_pair["canonical"])

    assert find_shared_referents(same_day, now=NOW, min_gap=timedelta(days=30)) != []
    assert (
        find_shared_referents(same_day, now=NOW, min_gap=timedelta(days=365 * 20)) == []
    )


def test_two_notes_from_one_sitting_connect_through_a_confirmed_alias(owner):
    """The cold-start case, and the reason the default gap went to zero.

    A brain dump is one sitting by definition, so a thirty-day floor made this
    detector silent on the only corpus a new person has -- see cold-start.md.
    Nothing about the evidence is weaker here: the alias is still confirmed, the
    mentions are still confirmed, and the labels still differ, which is what
    makes the pair non-obvious. Elapsed time was never what supplied that; the
    detector's own docstring says so.
    """
    first = _capture(owner, "The woman in 4B practises most evenings.", "2026-03-01")
    minutes_later = _capture(
        owner, "Marguerite from upstairs invited us to a recital.", "2026-03-01"
    )
    canonical = _concept(owner, "Marguerite")
    alias = _concept(owner, "the woman in 4B")
    services.merge_concept(alias, canonical, now=NOW, actor="vince")
    _mention(first, alias)
    _mention(minutes_later, canonical)

    findings = find_shared_referents(minutes_later, now=NOW)

    assert [f.candidate for f in findings] == [first]


def test_one_sitting_still_will_not_connect_two_notes_saying_the_same_name(owner):
    """Dropping the gap does not drop the gate. Two notes both saying
    "Marguerite" are findable by searching for Marguerite, and that is true
    whether they were written a minute or a decade apart."""
    first = _capture(owner, "Marguerite practises most evenings.", "2026-03-01")
    minutes_later = _capture(owner, "Marguerite invited us to a recital.", "2026-03-01")
    canonical = _concept(owner, "Marguerite")
    _mention(first, canonical)
    _mention(minutes_later, canonical)

    assert find_shared_referents(minutes_later, now=NOW) == []


def test_an_already_linked_pair_is_not_proposed(aliased_pair):
    services.link(
        aliased_pair["new"],
        aliased_pair["old"],
        relation=EdgeRelation.RELATES_TO,
        now=NOW,
        actor="vince",
    )
    assert find_shared_referents(aliased_pair["new"], now=NOW) == []


def test_deleted_notes_are_not_candidates(aliased_pair):
    services.delete_node(aliased_pair["old"], now=NOW, actor="vince")
    assert find_shared_referents(aliased_pair["new"], now=NOW) == []


def test_a_note_with_no_confirmed_mentions_proposes_nothing(owner):
    assert find_shared_referents(_capture(owner, "A thought.", "2025-01-01"), now=NOW) == []


def test_another_persons_notes_are_never_candidates(owner, other_owner, aliased_pair):
    theirs = services.capture(
        other_owner,
        content="Marguerite next door.",
        captured_at=NOW,
        source=Node.Source.WEB,
        actor="them",
    )
    their_concept = services.propose_concept(
        other_owner,
        label="Marguerite",
        concept_type=ConceptType.PERSON,
        now=NOW,
        actor="system",
    )
    services.confirm_concept(their_concept, now=NOW, actor="them")
    services.confirm_mention(
        services.propose_mention(
            theirs, their_concept, index_version="rules-v1", now=NOW, actor="system"
        ),
        now=NOW,
        actor="them",
    )

    findings = find_shared_referents(aliased_pair["new"], now=NOW)
    assert theirs.pk not in [f.candidate.pk for f in findings]


# ---------------------------------------------------------------------------
# Proposing
# ---------------------------------------------------------------------------


def test_finding_writes_nothing(aliased_pair):
    find_shared_referents(aliased_pair["new"], now=NOW)
    assert ConnectionHypothesis.objects.count() == 0


def test_the_proposal_names_the_referent_and_both_descriptions(aliased_pair):
    """A person can check this in one glance — they either agree the descriptions
    name one thing or they do not, and they already said they do."""
    [hypothesis] = propose_shared_referents(aliased_pair["new"], now=NOW)

    assert hypothesis.detector == DETECTOR
    assert hypothesis.label == "both about Marguerite"
    assert hypothesis.concept_id == aliased_pair["canonical"].pk
    assert hypothesis.claim_text is None

    reasons = " ".join(m.contribution_reason or "" for m in hypothesis.members.all())
    assert "the woman in 4B" in reasons
    assert "Marguerite" in reasons


def test_the_confidence_is_high_because_the_evidence_is_exact(aliased_pair):
    [hypothesis] = propose_shared_referents(aliased_pair["new"], now=NOW)
    assert hypothesis.confidence == pytest.approx(0.9)


def test_a_proposal_starts_unsurfaced(aliased_pair):
    [hypothesis] = propose_shared_referents(aliased_pair["new"], now=NOW)
    assert hypothesis.first_surfaced_at is None
    assert hypothesis.review_window_expires_at is None


def test_nothing_is_promoted_by_proposing(aliased_pair):
    propose_shared_referents(aliased_pair["new"], now=NOW)
    assert Edge.objects.count() == 0


def test_rerunning_proposes_nothing_new(aliased_pair):
    first = propose_shared_referents(aliased_pair["new"], now=NOW)
    second = propose_shared_referents(aliased_pair["new"], now=NOW)

    assert len(first) == 1
    assert second == []
    assert ConnectionHypothesis.objects.count() == 1


def test_a_dismissed_proposal_is_not_offered_again(aliased_pair):
    [hypothesis] = propose_shared_referents(aliased_pair["new"], now=NOW)
    services.dismiss_hypothesis(hypothesis, now=NOW, actor="vince")

    assert propose_shared_referents(aliased_pair["new"], now=NOW) == []


def test_confirming_creates_a_relates_to_edge(aliased_pair):
    [hypothesis] = propose_shared_referents(aliased_pair["new"], now=NOW)
    [edge] = services.confirm_hypothesis(hypothesis, now=NOW, actor="vince")

    assert edge.relation == EdgeRelation.RELATES_TO
    assert edge.origin == InferenceOrigin.INFERRED
    assert {edge.from_node_id, edge.to_node_id} == {
        aliased_pair["new"].pk,
        aliased_pair["old"].pk,
    }


# ---------------------------------------------------------------------------
# The reason this detector exists
# ---------------------------------------------------------------------------


def test_it_finds_what_the_lexical_detector_cannot(aliased_pair):
    """The same neighbour under two descriptions, six years apart.

    This pair was one of four the dormant-thread detector missed against the
    evaluation corpus, and it is missed by construction rather than by tuning: the
    two notes share almost no vocabulary, so no amount of threshold work reaches
    it. A confirmed alias does, because it is a fact rather than a resemblance.
    """
    assert find_dormant_threads(aliased_pair["new"], now=NOW) == []
    assert [f.candidate.pk for f in find_shared_referents(aliased_pair["new"], now=NOW)] == [
        aliased_pair["old"].pk
    ]
