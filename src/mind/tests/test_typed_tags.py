"""A tag somebody typed is a concept somebody confirmed.

Step 1 of `design/one-capture-surface-plan.md`, and the decision that unblocked
the whole crossover: the Inbox models tags as first-class rows, the knowledge
core deliberately models none, and neither position survives a merge unchanged.

**The reconciliation is about what the gravity gate is for.** A candidate has to
earn its question — three mentions spanning a day — because *extraction*
over-generates on purpose, and a queue of every capitalised run would be the
inbox this design exists to avoid. That gate filters the system's guesses. A
person typing a tag is not a guess, and owes it nothing: it is exactly the
"somebody decided this" signal the concept layer is built around.

So a typed tag goes straight to a confirmed concept and an explicit mention,
skipping the gate entirely. What it replaces is a placeholder that wrote the
strings onto the activity log under the note "tags kept, not yet modelled" —
honest about discarding nothing, and read by nothing.
"""

from datetime import datetime, timedelta, timezone as dt_timezone

import pytest

from mind import queries, services
from mind.models import (
    ConceptCandidate,
    EventType,
    InferenceOrigin,
    Mention,
    NodeSource,
)

pytestmark = pytest.mark.django_db

UTC = dt_timezone.utc
NOW = datetime(2026, 6, 10, 9, 0, tzinfo=UTC)


@pytest.fixture
def node(owner):
    return services.capture(
        owner, content="the boiler is making that noise again",
        captured_at=NOW, source=NodeSource.MOBILE, actor="vince",
    )


def tag(node, *labels, now=NOW):
    return services.record_typed_tags(node, list(labels), now=now, actor="vince")


# ---------------------------------------------------------------------------
# What a typed tag becomes
# ---------------------------------------------------------------------------


def test_a_typed_tag_becomes_a_confirmed_concept(owner, node):
    tag(node, "boiler")

    concept = ConceptCandidate.objects.get(label="boiler")
    assert concept.owner == owner
    assert concept.confirmed_at is not None


def test_it_skips_the_gravity_gate_entirely(owner, node):
    """One mention, one sitting — nowhere near the three-across-a-day an
    extracted candidate must reach. That gate is for guesses, and this is not
    one, so the concept is usable immediately rather than after a week."""
    tag(node, "boiler")

    assert queries.confirmed_concepts(owner).filter(label="boiler").exists()


def test_the_node_carries_an_explicit_mention_of_it(owner, node):
    """A confirmed concept nothing points at is a word in a list. The mention
    is what puts this node into the concept's evidence."""
    tag(node, "boiler")

    mention = Mention.objects.get()
    assert mention.node == node
    assert mention.origin == InferenceOrigin.EXPLICIT
    assert mention.confirmed_at is not None


def test_several_tags_all_land(owner, node):
    tag(node, "boiler", "flat", "landlord")

    assert ConceptCandidate.objects.count() == 3
    assert Mention.objects.count() == 3


# ---------------------------------------------------------------------------
# Not making a second referent for a thing that already has one
# ---------------------------------------------------------------------------


def test_the_same_tag_on_two_notes_is_one_concept(owner, node):
    second = services.capture(
        owner, content="rang about the boiler", captured_at=NOW + timedelta(days=1),
        source=NodeSource.WEB, actor="vince",
    )

    tag(node, "boiler")
    tag(second, "boiler", now=NOW + timedelta(days=1))

    assert ConceptCandidate.objects.filter(label__iexact="boiler").count() == 1
    assert Mention.objects.count() == 2


@pytest.mark.parametrize("second_form", ["Boiler", "BOILER", "  boiler  "])
def test_case_and_padding_do_not_make_a_second_concept(owner, node, second_form):
    """Mirrors the partial unique index on `(owner, lower(label))` the concept
    layer already enforces: "Mondly" and "mondly" are one referent."""
    tag(node, "boiler")
    tag(node, second_form)

    assert ConceptCandidate.objects.count() == 1


def test_a_tag_matching_an_unconfirmed_candidate_confirms_it(owner, node):
    """Extraction may already have guessed at this name and be waiting for
    gravity. Somebody typing it is the answer that gate was waiting for, so it
    is promoted rather than duplicated."""
    guessed = services.propose_concept(
        owner, label="boiler", concept_type="unknown", now=NOW, actor="system",
    )
    assert guessed.confirmed_at is None

    tag(node, "boiler")

    guessed.refresh_from_db()
    assert guessed.confirmed_at is not None
    assert ConceptCandidate.objects.count() == 1


def test_tagging_the_same_note_twice_does_not_double_the_mention(owner, node):
    """A retried capture, or somebody adding a tag that is already there."""
    tag(node, "boiler")
    tag(node, "boiler")

    assert Mention.objects.count() == 1


def test_another_persons_concept_with_the_same_name_is_not_borrowed(owner, other_owner, node):
    services.propose_concept(
        other_owner, label="boiler", concept_type="unknown", now=NOW, actor="vince",
    )

    tag(node, "boiler")

    assert ConceptCandidate.objects.filter(owner=owner).count() == 1
    assert ConceptCandidate.objects.filter(owner=other_owner).count() == 1


# ---------------------------------------------------------------------------
# Edges
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("junk", [[], [""], ["   "], ["boiler", "boiler"]])
def test_nothing_and_repetition_are_handled_without_complaint(owner, node, junk):
    """Tags arrive from a phone, where a trailing comma is normal. None of this
    is an error worth failing a capture over -- the thought matters more than
    the tidiness of its labels."""
    tag(node, *junk)

    assert ConceptCandidate.objects.count() <= 1


def test_the_confirmation_is_recorded_in_the_log(owner, node):
    """Append-only, like every other decision here. "This concept was confirmed
    because somebody typed it" is a different fact from an extraction guess
    that later earned its gate, and the log should be able to tell them
    apart."""
    tag(node, "boiler")

    event = ConceptCandidate.objects.get(label="boiler")
    assert services.ActivityEvent.objects.filter(
        owner=owner, event_type=EventType.CONCEPT_CONFIRMED
    ).exists()
    assert "typed" in event.reason.lower()


# ---------------------------------------------------------------------------
# The tags already on the log
# ---------------------------------------------------------------------------


def placeholder_event(node, *labels, when=NOW):
    """What a tagged mobile capture used to write, before step 1."""
    return services._record(
        node.owner,
        EventType.CAPTURED,
        node=node,
        occurred_at=when,
        actor="vince",
        payload={"tags": list(labels), "note": "tags kept, not yet modelled"},
    )


def test_the_backfill_converts_what_the_placeholder_recorded(owner, node):
    from django.core.management import call_command

    placeholder_event(node, "boiler", "landlord")

    call_command("backfill_typed_tags")

    assert ConceptCandidate.objects.count() == 2
    assert Mention.objects.filter(node=node).count() == 2


def test_the_backfill_keeps_the_time_the_tag_was_typed(owner, node):
    """Recurrence is measured across time. Stamping a backfill with today would
    collapse months of history onto one afternoon and tell the gravity gate
    something untrue about how often a name came up."""
    from django.core.management import call_command

    long_ago = NOW - timedelta(days=200)
    placeholder_event(node, "boiler", when=long_ago)

    call_command("backfill_typed_tags")

    assert Mention.objects.get().confirmed_at == long_ago


def test_running_the_backfill_twice_changes_nothing(owner, node):
    """It reads an append-only log, which cannot be marked as processed -- so
    re-running is the only recovery from a partial run, and has to be safe."""
    from django.core.management import call_command

    placeholder_event(node, "boiler")
    call_command("backfill_typed_tags")

    call_command("backfill_typed_tags")

    assert ConceptCandidate.objects.count() == 1
    assert Mention.objects.count() == 1
