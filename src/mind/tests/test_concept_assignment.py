"""Node to concept: "this looks like it is about Indonesian."

The accretive mechanic, and the one that lets the concept layer grow without a
person naming everything by hand. A note that never says "Indonesian" still
belongs with the Indonesian ones if it talks about the same material.

**Anchored, not pairwise, and that is the whole design.** One end is a confirmed
concept -- a decision a person actually made -- so this is not two uncertain
things being guessed at. `precision.md` calls that the tier-2 shape: the anchor
does the precision work and a rarity test does the rest. It is also why this is
better conditioned than the whole-document similarity the shadow evaluation
measured at 0%: matching against a profile built from confirmed material has
something to be similar *to*, where two same-register personal notes mostly
report that they are both first-person prose.

What it produces is an unconfirmed [Mention] -- a proposal, soft-applied and
dismissible. Never an edge, never a hypothesis, and never something the matcher
is then allowed to read back as ground truth.
"""

from datetime import datetime, timedelta, timezone as dt_timezone

import pytest

from mind import services
from mind.detectors import find_concept_assignments, propose_concept_assignments
from mind.models import (
    ConceptCandidate,
    ConceptType,
    InferenceOrigin,
    Mention,
    NodeSource,
)

pytestmark = pytest.mark.django_db

UTC = dt_timezone.utc
NOW = datetime(2026, 6, 1, 9, 0, tzinfo=UTC)


def _capture(owner, content, days_ago=30):
    return services.capture(
        owner,
        content=content,
        captured_at=NOW - timedelta(days=days_ago),
        source=NodeSource.WEB,
        actor="vince",
    )


def _confirmed_concept(owner, label="Indonesian"):
    concept = ConceptCandidate.objects.create(
        owner=owner, label=label, concept_type=ConceptType.UNKNOWN, confirmed_at=NOW
    )
    return concept


def _mention(node, concept, *, confirmed=True):
    return Mention.objects.create(
        node=node,
        concept=concept,
        origin=InferenceOrigin.EXPLICIT,
        index_version="rules-v1",
        confirmed_at=NOW if confirmed else None,
    )


@pytest.fixture
def indonesian(owner):
    """A confirmed concept with three notes behind it, all naming it."""
    concept = _confirmed_concept(owner)
    for days in (60, 50, 40):
        node = _capture(
            owner,
            "Indonesian vocabulary drill again, mostly kitchen nouns and "
            "greetings from the phrasebook.",
            days_ago=days,
        )
        _mention(node, concept)
    return concept


def test_a_note_that_never_names_it_can_still_belong(owner, indonesian):
    """The finding this exists for. Nothing here says "Indonesian"."""
    arrived = _capture(
        owner,
        "Practised kitchen nouns and greetings with the tutor at the cafe, "
        "from the phrasebook again.",
        days_ago=1,
    )

    findings = find_concept_assignments(arrived, now=NOW)

    assert [f.concept for f in findings] == [indonesian]


def test_the_reason_quotes_the_words_that_matched(owner, indonesian):
    """Checkable, per "every proposal explains itself". "Similar to Indonesian"
    asks somebody to take the system's word for it; naming the shared words lets
    them disagree with it."""
    arrived = _capture(
        owner,
        "Practised kitchen nouns and greetings with the tutor at the cafe, "
        "from the phrasebook again.",
        days_ago=1,
    )

    reason = find_concept_assignments(arrived, now=NOW)[0].reason

    assert "phrasebook" in reason or "greetings" in reason or "nouns" in reason


def test_an_unrelated_note_is_not_assigned(owner, indonesian):
    arrived = _capture(
        owner, "The furnace filter needs changing before winter.", days_ago=1
    )

    assert find_concept_assignments(arrived, now=NOW) == []


def test_an_unconfirmed_concept_is_never_matched_against(owner):
    """The rule that stops the classifier feeding on its own output. An
    unconfirmed candidate is a guess, and a guess admitted to the corpus
    justifies the next guess with nothing human anywhere in the chain."""
    guess = ConceptCandidate.objects.create(
        owner=owner, label="Indonesian", concept_type=ConceptType.UNKNOWN
    )
    for days in (60, 50, 40):
        _mention(_capture(owner, "Indonesian vocabulary drill again.", days_ago=days), guess)
    arrived = _capture(owner, "vocabulary drill again", days_ago=1)

    assert find_concept_assignments(arrived, now=NOW) == []


def test_a_concept_the_note_already_mentions_is_not_proposed_again(owner, indonesian):
    """Extraction already caught it by name. Proposing what is already recorded
    spends attention to report nothing."""
    arrived = _capture(
        owner,
        "Practised kitchen nouns and greetings with the tutor, from the phrasebook.",
        days_ago=1,
    )
    _mention(arrived, indonesian, confirmed=False)

    assert find_concept_assignments(arrived, now=NOW) == []


def test_it_proposes_a_mention_and_nothing_stronger(owner, indonesian):
    """A proposal, soft-applied and dismissible -- not an edge, not a
    hypothesis. And unconfirmed, so `confirmed_concepts` still excludes it from
    the corpus the matcher searches."""
    arrived = _capture(
        owner,
        "Practised kitchen nouns and greetings with the tutor, from the phrasebook.",
        days_ago=1,
    )

    mentions = propose_concept_assignments(arrived, now=NOW)

    assert [m.concept for m in mentions] == [indonesian]
    assert mentions[0].confirmed_at is None
    assert mentions[0].origin == InferenceOrigin.INFERRED
    assert mentions[0].reason


def test_proposing_twice_records_one_mention(owner, indonesian):
    """Runs after every batch of captures, so a second pass must not double
    what it already proposed."""
    arrived = _capture(
        owner,
        "Practised kitchen nouns and greetings with the tutor, from the phrasebook.",
        days_ago=1,
    )

    propose_concept_assignments(arrived, now=NOW)
    propose_concept_assignments(arrived, now=NOW)

    assert Mention.objects.filter(node=arrived, concept=indonesian).count() == 1


def test_finding_writes_nothing(owner, indonesian):
    """The read half is pure, so a dry run can report what would be proposed
    without polluting the corpus it is reporting on."""
    arrived = _capture(
        owner,
        "Practised kitchen nouns and greetings with the tutor, from the phrasebook.",
        days_ago=1,
    )
    before = Mention.objects.count()

    find_concept_assignments(arrived, now=NOW)

    assert Mention.objects.count() == before


def test_another_persons_concepts_are_never_matched_against(owner, other_owner):
    theirs = _confirmed_concept(other_owner)
    for days in (60, 50, 40):
        node = services.capture(
            other_owner,
            content="Indonesian vocabulary drill, kitchen nouns and greetings.",
            captured_at=NOW - timedelta(days=days),
            source=NodeSource.WEB,
            actor="them",
        )
        _mention(node, theirs)
    mine = _capture(owner, "kitchen nouns and greetings drill", days_ago=1)

    assert find_concept_assignments(mine, now=NOW) == []


def test_a_concept_with_too_little_behind_it_proposes_nothing(owner):
    """A profile built from one note is that note, so this would collapse into
    ordinary pairwise similarity while looking like something better. The
    anchor's value comes from aggregating confirmed material."""
    thin = _confirmed_concept(owner, label="Reykjavik")
    _mention(_capture(owner, "kitchen nouns and greetings drill", days_ago=60), thin)
    arrived = _capture(owner, "kitchen nouns and greetings again", days_ago=1)

    assert find_concept_assignments(arrived, now=NOW) == []
