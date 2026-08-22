"""A dump's own record, and the budgets that make one safe — Track D 13.

**Ordered deliberately, and the plan says the order is the whole safety of the
feature**: *ship the surface first and the first dump is the one that teaches a
person to skim past the review surface, which is not recoverable.* So this
exists before anything can dump into it.

The flow the brief specifies, in eight rules:

1. Save every fragment immediately. *Capture is durable before it is clever.*
2. **During the dump, create nothing that requires attention.**
3. When the session ends, run all producers in read-only mode.
4. **Aggregate and deduplicate across the whole session.** Forty fragments
   about one project must not become forty findings about it.
5. Materialize a small total — five — with **no producer contributing more
   than two.**
6. Show at most three immediately.
7. **Mark the session processed**, so the next maintenance run cannot process
   its forty nodes independently and walk straight around the cap.
8. Keep every fragment as a candidate for future captures and retrievals.

**`CaptureSession` earns its own model** by `architecture-trajectory.md` §4's
test, and the v3 plan says why: *a session has duration, completion state, a
budget, prompt provenance and a processing flag. A shared timestamp carries
none of them.*

**A dump is not a container node.** Provenance is a session record, not graph
content — `NodeSource.THREAD` is a semantic conclusion that participates in the
graph, and a dump is neither.
"""

import datetime

import pytest

from mind import services
from mind.models import CaptureSession, Facet, FacetKind, Node


NOW = datetime.datetime(2026, 5, 4, 21, 0, tzinfo=datetime.timezone.utc)


def later(**offset):
    return NOW + datetime.timedelta(**offset)


def dump(owner, *fragments, session=None, now=NOW):
    session = session or services.begin_capture_session(owner, now=now)
    for index, text in enumerate(fragments):
        services.capture(
            owner,
            content=text,
            captured_at=now + datetime.timedelta(seconds=index),
            source=Node.Source.WEB,
            actor="vince",
            session=session,
        )
    return session


def facets_on(session):
    return Facet.objects.filter(node__session=session, retired_at__isnull=True)


# ---------------------------------------------------------------------------
# 1 and 2 — every fragment saved, and nothing asking for attention yet
# ---------------------------------------------------------------------------


def test_every_fragment_is_saved_immediately(db, owner):
    """*Capture is durable before it is clever*, and nothing here weakens it.
    A dump that batched its writes would lose the thing a dump is for."""
    session = dump(owner, "call the dentist by Friday", "the venue idea", "Mum's birthday")

    assert Node.objects.filter(session=session).count() == 3


def test_nothing_during_the_dump_asks_for_attention(db, owner):
    """Rule 2, and the one that makes a dump bearable. *call the dentist by
    Friday* would normally propose a commitment on the spot; forty of those
    mid-flow is the surface teaching somebody to skim past it."""
    session = dump(owner, "call the dentist by Friday", "email Sam on Tuesday")

    assert facets_on(session).count() == 0


def test_an_ordinary_capture_still_proposes(db, owner):
    """The suppression is a property of the session, not a change to capture.
    Outside a dump, a commitment is still offered on the way back."""
    services.capture(
        owner,
        content="call the dentist by Friday",
        captured_at=NOW,
        source=Node.Source.WEB,
        actor="vince",
    )

    assert Facet.objects.filter(kind=FacetKind.ACTIONABLE).exists()


# ---------------------------------------------------------------------------
# 3, 4 and 5 — one pass at the end, aggregated, and capped
# ---------------------------------------------------------------------------


def test_ending_the_session_is_when_producers_run(db, owner):
    session = dump(owner, "call the dentist by Friday")

    services.end_capture_session(session, now=later(minutes=5))

    assert facets_on(session).count() == 1


def test_forty_fragments_about_one_thing_do_not_become_forty_findings(db, owner):
    """Rule 4, in the brief's own words. The failure a dump invites most: a
    person empties their head about one project and the system hands back a
    finding per sentence."""
    session = dump(owner, *[f"call the dentist by Friday about thing {i}" for i in range(40)])

    services.end_capture_session(session, now=later(minutes=5))

    assert facets_on(session).count() <= services.SESSION_TOTAL_BUDGET


def test_no_producer_may_fill_the_whole_budget(db, owner):
    """Rule 5's second half. One loud producer taking all five slots is the
    same inbox with fewer rows."""
    session = dump(owner, *[f"call the dentist by Friday about {i}" for i in range(10)])

    services.end_capture_session(session, now=later(minutes=5))

    by_producer = {}
    for facet in facets_on(session):
        by_producer[facet.producer] = by_producer.get(facet.producer, 0) + 1

    assert all(count <= services.SESSION_PRODUCER_BUDGET for count in by_producer.values())


def test_what_is_shown_now_is_smaller_than_what_was_kept(db, owner):
    """Two budgets, not one -- *what is materialised* and *how many are shown
    now* are different questions, and collapsing them is how a cap becomes a
    queue."""
    session = dump(owner, *[f"call the dentist by Friday about {i}" for i in range(10)])

    shown = services.end_capture_session(session, now=later(minutes=5))

    assert len(shown) <= services.SESSION_ATTENTION_BUDGET
    assert services.SESSION_ATTENTION_BUDGET < services.SESSION_TOTAL_BUDGET


def test_nothing_valuable_is_discarded(db, owner):
    """*Every fragment stays searchable and can produce a new finding the
    moment a future context makes it relevant.* The cap is on attention, never
    on what was kept."""
    session = dump(owner, *[f"call the dentist by Friday about {i}" for i in range(10)])

    services.end_capture_session(session, now=later(minutes=5))

    assert Node.objects.filter(session=session).count() == 10


# ---------------------------------------------------------------------------
# 7 — and the maintenance run cannot walk around the cap
# ---------------------------------------------------------------------------


def test_ending_a_session_marks_it_processed(db, owner):
    session = dump(owner, "call the dentist by Friday")

    services.end_capture_session(session, now=later(minutes=5))

    session.refresh_from_db()
    assert session.processed_at == later(minutes=5)


def test_a_processed_session_is_not_processed_again(db, owner):
    """Rule 7, and the reason it is a stored flag rather than an inference:
    *the next maintenance run cannot process its forty nodes independently and
    walk straight around the cap.*"""
    session = dump(owner, *[f"call the dentist by Friday about {i}" for i in range(10)])
    services.end_capture_session(session, now=later(minutes=5))
    before = facets_on(session).count()

    services.end_capture_session(session, now=later(hours=1))

    assert facets_on(session).count() == before


def test_maintenance_leaves_a_processed_sessions_nodes_alone(db, owner):
    """The cap is worth nothing if the nightly pass reaches the same forty
    nodes one at a time."""
    session = dump(owner, *[f"call the dentist by Friday about {i}" for i in range(10)])
    services.end_capture_session(session, now=later(minutes=5))
    before = facets_on(session).count()

    services.run_producers_over_unprocessed(owner, now=later(days=1))

    assert facets_on(session).count() == before


def test_maintenance_still_reaches_a_node_outside_any_session(db, owner):
    """The flag narrows what maintenance skips, not what it does."""
    node = Node.objects.create(
        owner=owner,
        original_content="call the dentist by Friday",
        captured_at=NOW,
        source=Node.Source.IMPORT,
    )

    services.run_producers_over_unprocessed(owner, now=later(days=1))

    assert Facet.objects.filter(node=node).exists()


# ---------------------------------------------------------------------------
# The session is a record, not content
# ---------------------------------------------------------------------------


def test_a_session_is_not_a_node(db, owner):
    """*A dump is not a container node.* `NodeSource.THREAD` is a semantic
    conclusion that participates in the graph; provenance is neither."""
    session = dump(owner, "one", "two")

    assert not Node.objects.filter(source=Node.Source.THREAD).exists()
    assert CaptureSession.objects.filter(pk=session.pk).exists()


def test_a_session_knows_when_it_ran(db, owner):
    session = services.begin_capture_session(owner, now=NOW)

    assert session.started_at == NOW
    assert session.processed_at is None


def test_one_person_never_ends_anothers_session(db, owner, other_owner):
    session = services.begin_capture_session(other_owner, now=NOW)

    with pytest.raises(services.NotYours):
        services.end_capture_session(session, now=later(minutes=5), owner=owner)
