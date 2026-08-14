"""Concept extraction.

The extractor is crude on purpose and safe because of it: everything it produces is
an unconfirmed candidate, excluded from the corpus any inference may search. So the
tests here are mostly about *not flooding* — a review list full of "Signed",
"Determined", "Finally" makes the concept layer unusable rather than merely
incomplete.
"""

from datetime import datetime, timezone as dt_timezone

import pytest

from mind import services
from mind.extraction import extract_concepts
from mind.models import ConceptCandidate, ConceptType, InferenceOrigin, Mention, Node

pytestmark = pytest.mark.django_db

UTC = dt_timezone.utc
NOW = datetime(2026, 8, 12, 12, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# The rules
# ---------------------------------------------------------------------------


def _labels(text, **kw):
    return [m.label for m in extract_concepts(text, **kw)]


def test_a_capital_mid_sentence_is_a_name():
    """English does not capitalise mid-sentence for any other reason."""
    assert _labels("Signed up for Mondly again this week.") == ["Mondly"]


def test_a_sentence_opening_verb_is_not_a_name():
    """The failure that makes a concept layer unusable if it gets through."""
    assert _labels("Changed the furnace filter today.") == []
    assert _labels("Determined to start earlier. Finally got going.") == []


def test_a_sentence_initial_name_survives_if_it_recurs_mid_sentence():
    assert _labels("Marguerite practises on Sundays. I saw Marguerite in the hall.") == [
        "Marguerite"
    ]


def test_a_sentence_initial_name_alone_is_dropped_knowingly():
    """The accepted trade: no positional evidence, and nothing else to go on.

    Recovered by `known_labels` once the corpus has seen the name elsewhere, which
    is what the next test covers.
    """
    assert _labels("Bob called today about the furnace.") == []


def test_a_known_label_is_recognised_without_positional_evidence():
    """How the concept layer bootstraps itself: one mid-sentence sighting anywhere
    teaches the commonest note shape of all."""
    assert _labels("Bob called today about the furnace.", known_labels=["Bob"]) == ["Bob"]


def test_a_verb_followed_by_a_name_yields_the_name(owner=None):
    """The case that disproves "two capitals in a row are one name".

    A great many notes open with a verb and a referent. Treating the pair as a
    single name gets it exactly backwards — inventing "Called Bob" while losing
    Bob.
    """
    assert _labels("Called Bob yesterday about the boiler.") == ["Bob"]
    assert _labels("Opened MONDLY on the train.") == ["MONDLY"]
    assert _labels("Met Marguerite in the hall.") == ["Marguerite"]


def test_a_multi_word_name_survives_when_its_first_word_is_attested():
    """"Bank" is capitalised mid-sentence in the first clause, so the sentence-initial
    run in the second keeps its full form — and both resolve to one referent."""
    assert _labels(
        "The Bank of England raised rates. Bank of England again today."
    ) == ["Bank of England"]


def test_an_unattested_leading_word_degrades_to_the_remainder():
    """With nothing attesting "Bank", the run loses it and keeps what follows.

    A degradation rather than an error: England is a real referent, and the
    alternative — trusting adjacency — is what produces "Called Bob".
    """
    assert _labels("Bank of England raised rates again.") == ["England"]


def test_possessives_do_not_split_one_referent_into_two():
    assert _labels("Went to Kessler's. Kessler had the brackets.") == ["Kessler"]


def test_days_and_months_are_not_referents():
    """Otherwise the most frequent candidates in any dated personal corpus."""
    assert _labels("Ordered it on Tuesday. Arrived in March, late as usual.") == []


def test_one_referent_named_repeatedly_is_recorded_once():
    """Four mentions of Bob name one referent; recording four would quadruple his
    apparent weight."""
    assert _labels("I saw Bob. Bob was late. Bob is always late.") == ["Bob"]


def test_the_span_points_at_the_first_occurrence():
    [mention] = extract_concepts("Signed up for Mondly again.")
    assert mention.span_start == 14
    assert "Signed up for Mondly again."[mention.span_start : mention.span_end] == "Mondly"


def test_empty_and_lowercase_text_yields_nothing():
    assert extract_concepts("") == []
    assert _labels("my brother rang about the house") == []


def test_extraction_is_deterministic():
    text = "Marguerite met Bob near the Bank of England. Marguerite was late."
    assert _labels(text) == _labels(text)


# ---------------------------------------------------------------------------
# Recording
# ---------------------------------------------------------------------------


def _capture(owner, content, when="2024-03-01"):
    return services.capture(
        owner,
        content=content,
        captured_at=datetime.fromisoformat(when).replace(tzinfo=UTC),
        source=Node.Source.WEB,
        actor="vince",
    )


def test_recording_creates_unconfirmed_candidates(owner):
    """Nothing downstream may treat these as fact — that is what makes a crude
    extractor safe."""
    node = _capture(owner, "Signed up for Mondly again this week.")
    [mention] = services.extract_and_record_concepts(node, now=NOW)

    assert mention.origin == InferenceOrigin.INFERRED
    assert mention.confirmed_at is None
    concept = mention.concept
    assert concept.label == "Mondly"
    assert concept.confirmed_at is None
    assert concept.concept_type == ConceptType.UNKNOWN


def test_the_type_is_unknown_rather_than_guessed(owner):
    """Capitalisation says a referent was named, not what kind of thing it is.
    Guessing would be a fabrication dressed as data."""
    node = _capture(owner, "Met Marguerite at Kessler's on the corner.")
    services.extract_and_record_concepts(node, now=NOW)

    types = set(ConceptCandidate.objects.values_list("concept_type", flat=True))
    assert types == {ConceptType.UNKNOWN}


def test_two_notes_naming_one_referent_share_a_concept(owner):
    first = _capture(owner, "Signed up for Mondly again this week.")
    second = _capture(owner, "Did two Mondly lessons before breakfast.")

    services.extract_and_record_concepts(first, now=NOW)
    services.extract_and_record_concepts(second, now=NOW)

    assert ConceptCandidate.objects.filter(label__iexact="mondly").count() == 1
    assert Mention.objects.filter(concept__label__iexact="mondly").count() == 2


def test_case_differences_do_not_create_a_second_referent(owner):
    """Mirrors the partial unique index on (owner, lower(label), type)."""
    services.extract_and_record_concepts(
        _capture(owner, "Started using Mondly daily."), now=NOW
    )
    services.extract_and_record_concepts(
        _capture(owner, "Opened MONDLY on the train."), now=NOW
    )
    assert ConceptCandidate.objects.count() == 1


def test_re_running_extraction_records_nothing_new(owner):
    node = _capture(owner, "Signed up for Mondly again this week.")
    services.extract_and_record_concepts(node, now=NOW)
    again = services.extract_and_record_concepts(node, now=NOW)

    assert again == []
    assert Mention.objects.count() == 1


def test_extraction_is_owner_scoped(owner, other_owner):
    services.extract_and_record_concepts(
        _capture(owner, "Signed up for Mondly again."), now=NOW
    )
    theirs = services.capture(
        other_owner,
        content="Signed up for Mondly again.",
        captured_at=NOW,
        source=Node.Source.WEB,
        actor="them",
    )
    services.extract_and_record_concepts(theirs, now=NOW)

    assert ConceptCandidate.objects.filter(owner=owner).count() == 1
    assert ConceptCandidate.objects.filter(owner=other_owner).count() == 1


def test_deleted_material_is_not_extracted_from(owner):
    node = _capture(owner, "Signed up for Mondly again.")
    services.delete_node(node, now=NOW, actor="vince")
    with pytest.raises(services.Deleted):
        services.extract_and_record_concepts(node, now=NOW)


def test_known_labels_come_from_the_owners_own_corpus(owner):
    """The bootstrap, end to end: the second note resolves a name it carries no
    positional evidence for, because the first note established it."""
    services.extract_and_record_concepts(
        _capture(owner, "Ran into Marguerite outside."), now=NOW
    )
    later = _capture(owner, "Marguerite dropped the parcel round.")
    [mention] = services.extract_and_record_concepts(later, now=NOW)

    assert mention.concept.label == "Marguerite"
    assert ConceptCandidate.objects.count() == 1
