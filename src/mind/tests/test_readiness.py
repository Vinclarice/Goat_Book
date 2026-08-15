"""Can each detector say anything yet, and if not, what is missing?

The difference between *no connections found* and *no connections possible*.
Without it, neither the builder at week three nor a stranger at minute four can
tell a quiet mechanic from a broken one — and the honest response to an ambiguous
disappointment is usually to abandon the idea, which is the failure
`cold-start.md` is written to prevent.

So a blocked detector has to say what it is waiting for, in terms of the person's
own corpus. "Unavailable" alone is barely better than silence.
"""

from datetime import datetime, timedelta, timezone as dt_timezone

import pytest

from mind import instrumentation, services
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


def _capture(owner, content, days_ago):
    return services.capture(
        owner,
        content=content,
        captured_at=NOW - timedelta(days=days_ago),
        source=NodeSource.WEB,
        actor="vince",
    )


def _by_name(owner, name, *, now=NOW):
    return {r.detector: r for r in instrumentation.detector_readiness(owner, now=now)}[
        name
    ]


def _confirmed_concept_with(owner, members, label="Indonesian"):
    concept = ConceptCandidate.objects.create(
        owner=owner, label=label, concept_type=ConceptType.UNKNOWN, confirmed_at=NOW
    )
    for node in members:
        Mention.objects.create(
            node=node,
            concept=concept,
            origin=InferenceOrigin.EXPLICIT,
            index_version="rules-v1",
            confirmed_at=NOW,
        )
    return concept


def test_every_detector_is_reported_even_when_none_can_fire(owner):
    """Absence is the finding on an empty corpus. Reporting only the ready ones
    would show a blank list, which is the ambiguity this exists to remove."""
    names = {r.detector for r in instrumentation.detector_readiness(owner, now=NOW)}

    assert names == {
        "concept_assignment",
        "open_question",
        "shared_referent",
        "dormant_thread",
        "semantic_echo",
    }


def test_a_blocked_detector_says_what_it_is_waiting_for(owner):
    blocked = _by_name(owner, "concept_assignment")

    assert not blocked.ready
    assert "confirm" in blocked.blocked_by.lower()


def test_concept_assignment_is_ready_once_a_concept_has_two_notes(owner):
    """Its stated precondition, and nothing more: no elapsed time at all, which
    is why it is the detector that can work in week one."""
    members = [_capture(owner, "Indonesian vocabulary drill", days_ago=d) for d in (2, 1)]
    _confirmed_concept_with(owner, members)

    assert _by_name(owner, "concept_assignment").ready


def test_one_note_behind_a_concept_is_not_enough(owner):
    """The threshold the detector actually enforces, reported honestly rather
    than as "you have a concept, so it is ready"."""
    _confirmed_concept_with(owner, [_capture(owner, "Indonesian drill", days_ago=1)])

    assert not _by_name(owner, "concept_assignment").ready


def test_shared_referent_waits_for_a_confirmed_alias(owner):
    blocked = _by_name(owner, "shared_referent")

    assert not blocked.ready
    assert "alias" in blocked.blocked_by.lower()


def test_shared_referent_is_ready_once_two_labels_are_merged(owner):
    canonical = ConceptCandidate.objects.create(
        owner=owner, label="Marguerite", concept_type=ConceptType.PERSON,
        confirmed_at=NOW,
    )
    alias = ConceptCandidate.objects.create(
        owner=owner, label="the woman in 4B", concept_type=ConceptType.PERSON,
        confirmed_at=NOW,
    )
    services.merge_concept(alias, canonical, now=NOW, actor="vince")

    assert _by_name(owner, "shared_referent").ready


def test_open_question_waits_for_a_question(owner):
    _capture(owner, "Changed the furnace filter today.", days_ago=10)

    blocked = _by_name(owner, "open_question")

    assert not blocked.ready
    assert "question" in blocked.blocked_by.lower()


def test_open_question_is_ready_once_one_has_been_asked(owner):
    _capture(owner, "Should I ask the tutor about evening lessons?", days_ago=10)

    assert _by_name(owner, "open_question").ready


def test_dormant_thread_reports_the_gap_against_the_corpus_it_has(owner):
    """The number that makes the wait legible. "Unavailable" tells somebody
    nothing; "needs 548 days between two notes, your oldest is 12" tells them
    whether to wait or to stop expecting anything."""
    _capture(owner, "the scanner jammed again", days_ago=12)

    blocked = _by_name(owner, "dormant_thread")

    assert not blocked.ready
    assert "548" in blocked.blocked_by
    assert "12" in blocked.blocked_by


def test_dormant_thread_is_ready_once_the_corpus_spans_the_gap(owner):
    _capture(owner, "the scanner jammed again", days_ago=700)
    _capture(owner, "the scanner jammed once more", days_ago=1)

    assert _by_name(owner, "dormant_thread").ready


def test_semantic_echo_reports_its_missing_dependency(owner):
    """Already had this behaviour inside the detector; it is reported here so a
    person can see it without running anything."""
    blocked = _by_name(owner, "semantic_echo")

    assert not blocked.ready
    assert "embed" in blocked.blocked_by.lower()


def test_readiness_is_in_the_summary(owner):
    summary = instrumentation.lab_summary(owner, now=NOW)

    assert "readiness" in summary
    assert len(summary["readiness"]) == 5


def test_another_persons_corpus_does_not_make_your_detectors_ready(owner, other_owner):
    services.capture(
        other_owner,
        content="Should I ask the tutor about evening lessons?",
        captured_at=NOW - timedelta(days=10),
        source=NodeSource.WEB,
        actor="them",
    )

    assert not _by_name(owner, "open_question").ready
