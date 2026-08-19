"""A facet can cite a journal entry, not only a node — increment 2, slice A.

`planning-assistant-plan.md` increment 2 proposes commitments out of
`DailyEntry`, which is where most writing in this product actually happens and
which no producer has ever read. The design question it named was **what a
confirmation creates**, and the answer — Vince, August 19, 2026 — is that a
`Facet` learns to point at an entry.

**Why not mint a node.** A capture and a journal entry are both durable records
the person wrote; turning the second into the first on confirmation would put
the same sentence in two places and quietly make the journal a capture surface,
which is what Heron deleted. The `Facet.task` foreign key already crosses from
the knowledge core into `lists`, so a second crossing into `daily` is the same
move rather than a new kind of one.

**Why not a new model.** `architecture-trajectory.md` §4: a concept earns a
model when it has a different *life cycle*, and a commitment proposed from an
entry has precisely the life cycle of one proposed from a capture — proposed,
then accepted or dismissed, and accepted means a task exists.

Three things change here, and two of them are the shared contract arriving:

* **`node` becomes nullable and `entry` appears**, with a check constraint
  saying exactly one is set. A facet floating free of both would be evidence
  for nothing.
* **Spans.** `Facet.reason` was free text, so a commitment proposal could not
  be checked against the passage that caused it. The contract asks for cited
  evidence and this is it — the same span-level citation `HypothesisMember`
  has had all along.
* **A fingerprint**, unique per entry across *every* state including retired.
  A journal entry is edited all day; without this, every save re-proposes what
  was dismissed an hour ago.
"""

from datetime import date, datetime, timezone as dt_timezone

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction

from daily.models import DailyEntry
from mind.models import Facet, FacetKind, InferenceOrigin, Node, NodeSource

pytestmark = pytest.mark.django_db

UTC = dt_timezone.utc
NOW = datetime(2026, 6, 1, 9, 0, tzinfo=UTC)


@pytest.fixture
def entry(owner):
    return DailyEntry.objects.create(
        owner=owner,
        date=date(2026, 6, 1),
        happenings="I still need to ask Maya about the venue.",
    )


@pytest.fixture
def node(owner):
    return Node.objects.create(
        owner=owner,
        original_content="Ring the venue on Thursday.",
        captured_at=NOW,
        source=NodeSource.WEB,
    )


def test_a_facet_can_cite_an_entry(entry):
    facet = Facet.objects.create(
        entry=entry,
        kind=FacetKind.ACTIONABLE,
        origin=InferenceOrigin.INFERRED,
        reason="commitment language",
        span_start=8,
        span_end=44,
        fingerprint="abc123",
    )

    assert facet.entry == entry
    assert facet.node is None


def test_a_facet_still_cites_a_node(node):
    facet = Facet.objects.create(
        node=node,
        kind=FacetKind.ACTIONABLE,
        origin=InferenceOrigin.INFERRED,
        reason="commitment language",
    )

    assert facet.node == node
    assert facet.entry is None


def test_a_facet_citing_neither_is_refused(owner):
    """Evidence for nothing is not a proposal.

    The database says so rather than the service remembering to check, because
    the second producer to write a facet is the one that forgets.
    """
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Facet.objects.create(
                kind=FacetKind.ACTIONABLE, origin=InferenceOrigin.INFERRED,
            )


def test_a_facet_citing_both_is_refused(node, entry):
    """One passage, one source. Two would make "where did this come from"
    ambiguous at exactly the moment somebody is deciding whether to trust it."""
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Facet.objects.create(
                node=node,
                entry=entry,
                kind=FacetKind.ACTIONABLE,
                origin=InferenceOrigin.INFERRED,
            )


def test_one_entry_may_imply_several_commitments(entry):
    """The difference from a node, and the reason the old constraint could not
    simply be copied.

    A capture is one thought, so one actionable facet per node is right. A
    journal entry is a day's writing and may carry three separate promises;
    `unique(node, kind)` translated naively would let a Tuesday propose exactly
    one of them and silently drop the rest.
    """
    first = Facet.objects.create(
        entry=entry, kind=FacetKind.ACTIONABLE, origin=InferenceOrigin.INFERRED,
        span_start=0, span_end=10, fingerprint="one",
    )
    second = Facet.objects.create(
        entry=entry, kind=FacetKind.ACTIONABLE, origin=InferenceOrigin.INFERRED,
        span_start=20, span_end=30, fingerprint="two",
    )

    assert {first.pk, second.pk} == set(
        Facet.objects.filter(entry=entry).values_list("pk", flat=True)
    )


def test_the_same_suggestion_is_never_proposed_twice(entry):
    Facet.objects.create(
        entry=entry, kind=FacetKind.ACTIONABLE, origin=InferenceOrigin.INFERRED,
        span_start=0, span_end=10, fingerprint="same",
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Facet.objects.create(
                entry=entry, kind=FacetKind.ACTIONABLE,
                origin=InferenceOrigin.INFERRED,
                span_start=0, span_end=10, fingerprint="same",
            )


def test_a_dismissed_suggestion_stays_dismissed(entry):
    """Dedupe against everything seen, not against what survived.

    A journal entry is edited all day. If the fingerprint only excluded live
    facets, every save would re-propose the thing dismissed an hour earlier --
    which is how a surface teaches somebody to ignore it. The same rule
    `ConnectionHypothesis.fingerprint` follows, and for the same reason.
    """
    facet = Facet.objects.create(
        entry=entry, kind=FacetKind.ACTIONABLE, origin=InferenceOrigin.INFERRED,
        span_start=0, span_end=10, fingerprint="dismissed",
    )
    facet.retired_at = NOW
    facet.save(update_fields=["retired_at"])

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Facet.objects.create(
                entry=entry, kind=FacetKind.ACTIONABLE,
                origin=InferenceOrigin.INFERRED,
                span_start=0, span_end=10, fingerprint="dismissed",
            )


def test_a_span_needs_both_ends_or_neither(entry):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Facet.objects.create(
                entry=entry, kind=FacetKind.ACTIONABLE,
                origin=InferenceOrigin.INFERRED,
                span_start=3, fingerprint="half",
            )


def test_a_span_must_run_forwards(entry):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Facet.objects.create(
                entry=entry, kind=FacetKind.ACTIONABLE,
                origin=InferenceOrigin.INFERRED,
                span_start=9, span_end=4, fingerprint="backwards",
            )


def test_a_facet_knows_whose_it_is_either_way(node, entry, owner):
    """One accessor, so callers stop reaching through `facet.node.owner`.

    Every existing caller does exactly that, and every one of them would break
    on an entry-backed facet. Resolving it here is cheaper than teaching each
    of them which kind they are holding.
    """
    from_node = Facet.objects.create(
        node=node, kind=FacetKind.ACTIONABLE, origin=InferenceOrigin.INFERRED,
    )
    from_entry = Facet.objects.create(
        entry=entry, kind=FacetKind.ACTIONABLE, origin=InferenceOrigin.INFERRED,
        fingerprint="owned",
    )

    assert from_node.owner == owner
    assert from_entry.owner == owner


def test_the_cited_passage_is_readable_from_either_source(entry):
    """The evidence, not a description of it.

    A proposal that cannot show the sentence it came from is asking for trust,
    which is the one thing every other producer here refuses to do.
    """
    body = "I still need to ask Maya about the venue."
    start = body.index("need")
    facet = Facet.objects.create(
        entry=entry, kind=FacetKind.ACTIONABLE, origin=InferenceOrigin.INFERRED,
        span_start=start, span_end=len(body), fingerprint="quoted",
    )

    # Offsets computed rather than typed. Hand-counted ones are wrong often
    # enough that the first version of this test was, and a span assertion
    # that is off by six proves the accessor works on the wrong sentence.
    assert facet.cited_text == "need to ask Maya about the venue."
