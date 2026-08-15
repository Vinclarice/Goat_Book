"""The walking skeleton, as the design document specifies it.

One test, following the whole path rather than any single layer:

    capture a thought → revise it without losing its origin → add one explicit link
    → be shown an older related thought the system found on its own, and accept it
    → review the note later even if it never became actionable

The design document's success criterion has two clauses, and only the first is
testable here: *ideas can live freely in the system, while the few things that
matter still become deliberate action.* The second clause — that at least once the
system surfaced something forgotten and welcome — is subjective and deliberately
left so. There is no proxy for it, and inventing one would be worse than admitting
the gap.

The commitment half of the slice is absent because the lab has no facet table.
That is scope, not omission: planning is downstream of a premise this exists to
test.
"""

from datetime import datetime, timedelta, timezone as dt_timezone

import pytest

from mind import instrumentation, queries, services
from mind.detectors import propose_dormant_threads
from mind.models import (
    ActivityEvent,
    Edge,
    EdgeRelation,
    EventType,
    HypothesisResolution,
    Node,
    NodeSource,
)

pytestmark = pytest.mark.django_db

UTC = dt_timezone.utc

OLD = datetime(2019, 5, 4, 21, 30, tzinfo=UTC)
NEW = datetime(2026, 8, 1, 8, 15, tzinfo=UTC)
LATER = datetime(2026, 8, 12, 9, 0, tzinfo=UTC)
MUCH_LATER = datetime(2027, 6, 1, 9, 0, tzinfo=UTC)


def test_the_whole_loop(owner):
    # --- an old thought, imported with its own date ------------------------
    #
    # Imported rather than captured, because material that arrives already old is
    # the only way a dormant thread can exist at all on a young corpus.
    old = services.capture(
        owner,
        content=(
            "The scanner utility died halfway through the receipts again. Third "
            "time this month. I lose the whole batch and have to start from the "
            "beginning, and by then the evening is gone and I have not filed "
            "anything at all."
        ),
        captured_at=OLD,
        source=NodeSource.IMPORT,
        actor="importer",
        import_key="journal:2019-05-04",
    )
    assert old.captured_at.year == 2019, "the source's date, never the ingestion date"

    # --- a thought captured today ----------------------------------------
    new = services.capture(
        owner,
        content=(
            "Sat down to do the receipts and the scanner batch failed halfway "
            "through, so I lost the lot. Gave up for the evening rather than "
            "starting the whole batch from the beginning again."
        ),
        captured_at=NEW,
        source=NodeSource.WEB,
        actor="vince",
    )

    # --- revised, without losing what it first said ------------------------
    services.revise(
        new,
        body=(
            "Sat down to do the receipts and the scanner batch failed halfway "
            "through. Losing the batch is the part that makes me stop."
        ),
        actor="vince",
        now=NEW,
    )
    new.refresh_from_db()
    assert "Gave up for the evening" in new.original_content, "the original survives"
    assert "makes me stop" in queries.current_body(new), "and the revision is current"

    # --- one explicit link, made by hand ----------------------------------
    aside = services.capture(
        owner, content="Filing goes better in the morning.", captured_at=NEW,
        source=NodeSource.WEB, actor="vince",
    )
    services.link(new, aside, relation=EdgeRelation.RELATES_TO, now=NEW, actor="vince")

    # --- the system finds the older thought on its own --------------------
    [proposal] = propose_dormant_threads(new, now=NEW)

    assert proposal.detector == "dormant_thread"
    assert {m.node_id for m in proposal.members.all()} == {new.pk, old.pk}
    assert proposal.claim_text is None, "nothing generated, ever, in v1"
    assert "shares:" in proposal.label, "the reason is extractive"

    # Nothing has been shown yet, so no clock is running.
    assert proposal.first_surfaced_at is None
    assert proposal.review_window_expires_at is None
    assert queries.attention_tier(old, now=NEW) == "review candidate"

    # --- shown, which is what starts the clock ----------------------------
    [shown] = services.open_review(owner, now=LATER, actor="vince")
    shown.refresh_from_db()

    assert shown.pk == proposal.pk
    assert shown.first_surfaced_at == LATER, "silence only counts once seen"
    assert shown.review_window_expires_at == LATER + services.DEFAULT_REVIEW_WINDOW

    # --- accepted, which is the person's act ------------------------------
    [edge] = services.confirm_hypothesis(shown, now=LATER, actor="vince")

    assert edge.relation == EdgeRelation.RELATES_TO
    assert edge.origin == "inferred"
    assert {edge.from_node_id, edge.to_node_id} == {new.pk, old.pk}
    shown.refresh_from_db()
    assert shown.resolution == HypothesisResolution.CONFIRMED

    # The same connection is never offered twice.
    assert propose_dormant_threads(new, now=LATER) == []

    # --- reviewed much later, having never become actionable --------------
    #
    # The point of the whole design: a thought that was never a task is still
    # first-class, and still comes back.
    services.mark_reviewed(old, now=MUCH_LATER, actor="vince")
    state = queries.review_state(old)

    assert state["reviews"] == 1
    assert state["due_at"] > MUCH_LATER
    assert queries.is_due_for_review(old, now=MUCH_LATER + timedelta(days=1)) is False

    # --- and the whole path is legible afterwards -------------------------
    kinds = list(
        ActivityEvent.objects.filter(owner=owner)
        .order_by("id")
        .values_list("event_type", flat=True)
    )
    for expected in (
        EventType.IMPORTED,
        EventType.CAPTURED,
        EventType.REVISED,
        EventType.EDGE_CREATED,
        EventType.HYPOTHESIS_PROPOSED,
        EventType.HYPOTHESIS_SURFACED,
        EventType.HYPOTHESIS_RESOLVED,
        EventType.REVIEWED,
    ):
        assert expected in kinds, f"{expected} missing from the log"

    summary = instrumentation.lab_summary(owner, now=MUCH_LATER)
    assert summary["nodes"] == 3
    assert summary["confirmed_connections"] == 1, "the accepted proposal"
    assert summary["explicit_links"] == 1, "the one made by hand"

    [performance] = summary["detectors"]
    assert performance.detector == "dormant_thread"
    assert performance.accept_rate == 1.0


def test_nothing_in_the_loop_promotes_without_being_accepted(owner):
    """The counterpart, and the commitment the design rests on.

    A proposal left alone expires. It does not ripen into an edge, and no amount of
    elapsed time substitutes for the person's decision — because a confirmation
    nobody made would corrupt the accept rate that is the only evidence about
    whether any of this works.
    """
    old = services.capture(
        owner,
        content=(
            "The scanner utility died halfway through the receipts again. Third "
            "time this month. I lose the whole batch and have to start from the "
            "beginning, and by then the evening is gone and nothing is filed."
        ),
        captured_at=OLD,
        source=NodeSource.IMPORT,
        actor="importer",
        import_key="journal:x",
    )
    new = services.capture(
        owner,
        content=(
            "Sat down to do the receipts and the scanner batch failed halfway "
            "through, so I lost the lot. Gave up for the evening rather than "
            "starting the whole batch from the beginning again."
        ),
        captured_at=NEW,
        source=NodeSource.WEB,
        actor="vince",
    )
    [proposal] = propose_dormant_threads(new, now=NEW)
    services.open_review(owner, now=LATER, actor="vince")

    closed = services.expire_stale_hypotheses(
        owner, now=MUCH_LATER, unsurfaced_after=timedelta(days=30)
    )

    proposal.refresh_from_db()
    assert closed == 1
    assert proposal.resolution == HypothesisResolution.EXPIRED
    assert Edge.objects.count() == 0, "silence promoted nothing"
    assert queries.attention_tier(old, now=MUCH_LATER) == "quiet knowledge"
