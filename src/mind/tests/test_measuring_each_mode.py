"""Four modes fail differently — Track B increment 10, and **D8 answered**.

`retirement_gate`'s three conditions are confirmed hypotheses, detector accept
rates and retrieval misses falling; `producer_performance` reports which
proposer is worth hearing from. **Every one grades a machine that proposes
links between notes** — which is what the numbers described, and what got
built. Retrieval is not measured at all.

**A search miss, a dismissed resurfacing and an irrelevant planning suggestion
are three different failures, and any single number over them reports health.**

**D8 asked what the four metrics are, and said to say so if one has no honest
signal rather than grade it by proxy. The answer is two, and it is not a
shortfall — it is the point of asking.**

- **Lookup has one, and it is the best instrument in the project.**
  `RetrievalMiss` with `MissContext.SEARCH`: the person knows what they wrote,
  so the right answer is known and the failure is loud and recordable.
- **Recollection gets one here**, from the source the brief registered on
  August 21: the search page's miss button, borrowed verbatim onto the note
  page — *"there was more to that morning."* `MissContext` gains a value and
  nothing else has to change, which is why that suggestion was worth taking.
- **Planning has none, honestly**, because no surface declares itself Planning
  yet — `retrieval.retrieve` raises on it. A metric for a mode nothing runs
  would be a zero that reads as success.
- **Resurfacing has none and structurally cannot.** *A missed resurfacing
  leaves no trace at all.* A dismissed one is recordable and a missed one is
  not, so any rate built from dismissals grades the half that leaves evidence
  and calls it the whole.

**Saying "no honest signal" in the numbers is the increment**, not a gap in it.
A blank where a number should be is the one thing that cannot be mistaken for
health.
"""

from datetime import datetime, timedelta, timezone as dt_timezone

import pytest

from mind import instrumentation, services
from mind.models import MissContext, Node, RetrievalMiss


WRITTEN = datetime(2026, 5, 4, 9, 0, tzinfo=dt_timezone.utc)


def later(**offset):
    return WRITTEN + timedelta(**offset)


@pytest.fixture
def signed_in(client, owner):
    client.force_login(owner)
    return client


@pytest.fixture
def note(owner):
    return services.capture(
        owner,
        content="ask Maya about the venue",
        captured_at=WRITTEN,
        source=Node.Source.WEB,
        actor="vince",
    )


def modes(owner):
    return instrumentation.retrieval_by_mode(owner, now=later(days=1))


# ---------------------------------------------------------------------------
# D8: four modes, two honest signals, and the other two said out loud
# ---------------------------------------------------------------------------


def test_every_mode_that_can_be_asked_for_is_reported(db, owner):
    """One row per mode, including the ones with nothing to report. A mode
    missing from the numbers is a mode nobody is watching, which is how
    retrieval came to be unmeasured while `/numbers/` read as complete."""
    assert {row["mode"] for row in modes(owner)} == {
        "lookup",
        "recollection",
        "discovery",
        "planning",
        "reflection",
        "resurfacing",
    }


def test_lookup_counts_the_misses_somebody_recorded(db, owner):
    services.record_retrieval_miss(
        owner, query_text="chicken", context=MissContext.SEARCH, now=WRITTEN
    )

    lookup = [row for row in modes(owner) if row["mode"] == "lookup"][0]

    assert lookup["misses"] == 1
    assert lookup["has_an_honest_signal"]


def test_recollection_counts_its_own_misses_separately(db, owner):
    """Separately, which is the whole increment. One number over both would
    make a search that failed and a morning that came back thin the same
    event."""
    services.record_retrieval_miss(
        owner, query_text="chicken", context=MissContext.SEARCH, now=WRITTEN
    )
    services.record_retrieval_miss(
        owner,
        query_text="that morning",
        context=MissContext.RECOLLECTION,
        now=WRITTEN,
    )

    by_mode = {row["mode"]: row for row in modes(owner)}

    assert by_mode["lookup"]["misses"] == 1
    assert by_mode["recollection"]["misses"] == 1


def test_planning_says_it_has_no_signal_rather_than_reporting_zero(db, owner):
    """A zero for a mode nothing runs reads as success. No surface declares
    itself Planning -- `retrieval.retrieve` raises on it -- so there is nothing
    to have missed."""
    planning = [row for row in modes(owner) if row["mode"] == "planning"][0]

    assert not planning["has_an_honest_signal"]
    assert planning["misses"] is None
    assert "no surface" in planning["why_not"]


def test_resurfacing_says_its_signal_cannot_exist(db, owner):
    """Different from Planning's, and the difference matters: Planning has no
    signal *yet*, and Resurfacing cannot have one. *A missed resurfacing leaves
    no trace at all* -- a rate built from dismissals grades the half that
    leaves evidence and calls it the whole."""
    resurfacing = [row for row in modes(owner) if row["mode"] == "resurfacing"][0]

    assert not resurfacing["has_an_honest_signal"]
    assert "leaves no trace" in resurfacing["why_not"]


def test_no_single_number_is_offered_over_the_modes(db, owner):
    """*Any single number over the three will report health.* Asserted as an
    absence, because the temptation is real and the failure is silent."""
    summary = instrumentation.lab_summary(owner, now=later(days=1))

    assert "retrieval_health" not in summary
    assert "misses" not in summary


# ---------------------------------------------------------------------------
# Recollection's signal, borrowed from the one that works
# ---------------------------------------------------------------------------


def test_the_note_page_offers_a_way_to_say_there_was_more(signed_in, note):
    """The source D8 registered on August 21: the search page's miss button,
    verbatim. It is the strongest instrument here because the person knows
    something is missing, and a mode with a recordable failure is worth more
    than one with a plausible metric."""
    body = signed_in.get(f"/mind/notes/{note.public_id}/").content.decode()

    assert "there was more to that" in body.lower()


def test_saying_there_was_more_records_a_recollection_miss(signed_in, note):
    signed_in.post(f"/mind/notes/{note.public_id}/thin/")

    miss = RetrievalMiss.objects.get(context=MissContext.RECOLLECTION)
    assert str(note.public_id) in miss.query_text


def test_another_persons_note_records_nothing(client, other_owner, note):
    client.force_login(other_owner)
    client.post(f"/mind/notes/{note.public_id}/thin/")

    assert RetrievalMiss.objects.count() == 0


def test_saying_there_was_more_needs_a_post(signed_in, note):
    response = signed_in.get(f"/mind/notes/{note.public_id}/thin/")

    assert response.status_code == 405


# ---------------------------------------------------------------------------
# The numbers page
# ---------------------------------------------------------------------------


def test_the_numbers_page_shows_each_mode(signed_in, owner):
    body = signed_in.get("/mind/numbers/").content.decode()

    assert "Lookup" in body
    assert "Recollection" in body


def test_the_numbers_page_says_where_there_is_no_honest_signal(signed_in, owner):
    """The increment, in one line of a page: a blank where a number should be
    is the one thing that cannot be mistaken for health."""
    body = signed_in.get("/mind/numbers/").content.decode()

    assert "no honest signal" in body.lower()
