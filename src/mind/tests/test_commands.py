"""The entry points.

Commands are kept thin here and their pieces tested directly, so this file only
covers what a thin command can still get wrong: not being wired to anything.

That is not hypothetical. `services.extract_and_record_concepts` existed, was
tested, and was called by nothing outside its own tests — so no concept candidate
was ever created in real use, and the layer `cold-start.md` makes the whole
cold-start mechanic could not have worked however good it was. A test that runs
the command end to end is the cheapest guard against that recurring.

Regression guards rather than a failing-test-first cycle, and said plainly per
this project's own rule about tests that pass on their first run.
"""

import pytest
from django.core.management import CommandError, call_command
from django.utils import timezone

from mind import queries
from mind.models import ConceptCandidate, Mention

pytestmark = pytest.mark.django_db


def _run(command, **options):
    from io import StringIO

    out = StringIO()
    call_command(command, stdout=out, **options)
    return out.getvalue()


def test_extraction_reaches_real_notes(owner, make_node):
    """The guard the missing caller needed.

    Note the names sit mid-sentence. `extraction` deliberately ignores a
    capitalised word at a sentence start, because that position says nothing
    about whether it names anything -- so a corpus where every mention opens a
    sentence extracts nothing, which is correct and surprising enough to be
    worth writing down here.
    """
    make_node("Practised with Mondly again this evening", captured="2026-03-01")
    make_node("Going better with Mondly today", captured="2026-03-04")

    _run("extract_concepts", owner=owner.username, all=True)

    assert ConceptCandidate.objects.filter(owner=owner, label="Mondly").exists()
    assert Mention.objects.count() >= 2


def test_it_reports_what_earned_a_question_not_just_what_was_found(owner, make_node):
    """Two numbers, because they answer different things. A run that extracts
    forty names and surfaces none of them is working correctly, and a report of
    only the first would make that look productive."""
    for day in ("2026-03-01", "2026-03-04", "2026-03-09"):
        make_node(f"Practised Indonesian on {day}", captured=day)
    # Seen once: extracted, and deliberately never asked about.
    make_node("A note about Reykjavik", captured="2026-03-02")

    output = _run("extract_concepts", owner=owner.username, all=True)

    assert "Indonesian" in output
    assert "Reykjavik" not in output
    assert [c.label for c in queries.concept_candidates(owner)] == ["Indonesian"]


def test_a_dry_run_writes_nothing(owner, make_node):
    """The point of a dry run is deciding whether the rules are picking up
    referents or picking up sentence starts, and a run that pollutes the corpus
    to tell you cannot be repeated."""
    make_node("Practised with Mondly again this evening", captured="2026-03-01")

    output = _run("extract_concepts", owner=owner.username, all=True, dry_run=True)

    assert "Mondly" in output
    assert not ConceptCandidate.objects.exists()
    assert not Mention.objects.exists()


def test_extraction_is_idempotent(owner, make_node):
    """Re-running is ordinary — after every capture, or after changing a rule —
    so a second pass must not double every mention it already recorded."""
    make_node("Practised with Mondly again this evening", captured="2026-03-01")

    _run("extract_concepts", owner=owner.username, all=True)
    first = Mention.objects.count()
    _run("extract_concepts", owner=owner.username, all=True)

    assert Mention.objects.count() == first


def test_it_will_not_silently_do_nothing_for_an_unknown_person(owner):
    """A typo'd username that reported "no notes in range" would look like an
    empty corpus rather than a mistake."""
    with pytest.raises(CommandError):
        _run("extract_concepts", owner="nobody-by-that-name")


def test_another_persons_notes_are_not_extracted(owner, other_owner, make_node):
    from mind.models import Node

    Node.objects.create(
        owner=other_owner,
        original_content="Reykjavik and Mondly and Indonesian",
        captured_at=timezone.now(),
        source=Node.Source.WEB,
    )

    _run("extract_concepts", owner=owner.username, all=True)

    assert not ConceptCandidate.objects.filter(owner=other_owner).exists()
    assert not Mention.objects.exists()
