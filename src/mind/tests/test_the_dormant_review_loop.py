"""Saying what to do with something that came back — **D15, answered**.

> **D15. The dormant review loop: wire it, fold it into the modes, or delete
> it.** `mark_reviewed` has no production caller, so the spaced resurfacing
> schedule has never run for a real note and `attention_tier`'s review-candidate
> tier is reachable only through open hypotheses. Part 2's Resurfacing mode is
> the natural home for the decision; **the one wrong option is leaving built
> machinery dark and undecided**, per the seam rule.

**Answered: wire it, into the mode**, which is both of the two right options at
once and was not available until this morning. D15 named Resurfacing as the
natural home while Resurfacing was itself a `NotImplementedError`; **D17 built
it**, and a mode with a page is a caller.

**What was dark and why it stayed dark.** The mechanism is complete:
`mark_reviewed` records a `REVIEWED` event with a response, `review_state` folds
those events into a stretching interval, `is_due_for_review` reads it, and
`attention_tier` has a *review candidate* tier waiting for it. **Every piece
except the one where a person says something.** Production held two `reviewed`
rows and both were owner-scoped from `/mind/review/` — zero node-scoped — so
`review_state` returned zero for every node and the schedule had never run once.

**Deleting it was the real alternative and is rejected on the evidence, not on
sunk cost.** The schedule is derived from an append-only log rather than stored
in a mutable column, which is the expensive and correct half; and *burying*
stretching six times faster than *keeping* is the difference between a review
surface and a nag. That is a designed behaviour with nowhere to happen, not
speculative machinery.

**Six of these passed on their first run, and that is a signal rather than
luck.** `principles.md` asks for it to be named. Four are refusals that passed
because the surface did not exist yet — `POST` was unhandled, and the second
generator was unwritten — so they were vacuous then and are guards now. One is
`test_the_anniversary_wins_when_a_note_is_both`, which passed because there was
only one generator to win. **And one is the admission:**
`test_the_review_candidate_tier_is_now_reachable` passed because `mark_reviewed`
has always been callable — the tier was never unreachable in code, only
unreachable *in the application*, which is the entire content of D15 and the
reason a passing test was not evidence of anything.

**It stays opt-in, and that is what makes wiring it safe.**
`is_due_for_review` returns False for a node never reviewed — *"a corpus of
thousands would otherwise all become due at once the moment the feature
exists."* So nothing changes for anybody until they answer something, and the
schedule begins from the person's own first answer.
"""

import datetime

import pytest

from mind import queries, retrieval, services
from mind.models import EventType, Node


NEW_YORK = "America/New_York"

NOW = datetime.datetime(2026, 8, 22, 15, 0, tzinfo=datetime.timezone.utc)
A_YEAR_AGO = datetime.datetime(2025, 8, 22, 15, 0, tzinfo=datetime.timezone.utc)

LONG_ENOUGH = (
    "The venue wants a deposit by the end of the month and I still have not "
    "heard back from the other two, which means the decision is really about "
    "whether waiting is worth the risk of losing this one."
)

ON_THE_DAY = "/mind/this-time-before/?on=2026-08-22"


@pytest.fixture
def vince(owner):
    owner.time_zone = NEW_YORK
    owner.save(update_fields=["time_zone"])
    return owner


@pytest.fixture
def signed_in(client, vince):
    client.force_login(vince)
    return client


@pytest.fixture
def note(vince):
    return services.capture(
        vince,
        content=LONG_ENOUGH,
        captured_at=A_YEAR_AGO,
        source=Node.Source.WEB,
        actor="vince",
    )


def resurfacing(owner, *, now=NOW):
    return retrieval.retrieve(
        retrieval.Moment(owner=owner, mode=retrieval.Mode.RESURFACING, now=now)
    )


# ---------------------------------------------------------------------------
# The caller that was missing
# ---------------------------------------------------------------------------


def test_the_page_offers_a_response(signed_in, note):
    """The whole of what was missing: somewhere a person says something."""
    body = signed_in.get(ON_THE_DAY).content.decode()

    assert "Keep" in body
    assert "Less often" in body


def test_keeping_it_records_a_review(signed_in, vince, note):
    signed_in.post(ON_THE_DAY, {"node": str(note.public_id), "response": "kept"})

    assert note.events.filter(event_type=EventType.REVIEWED).count() == 1


def test_the_schedule_starts_from_the_first_answer(signed_in, vince, note):
    """`review_state` returned zero for every node in production, because no
    node had ever been reviewed. One answer is the whole difference."""
    assert queries.review_state(note)["due_at"] is None

    signed_in.post(ON_THE_DAY, {"node": str(note.public_id), "response": "kept"})

    assert queries.review_state(note)["due_at"] is not None


def test_burying_stretches_much_harder_than_keeping(signed_in, vince, note):
    """*Burying is the person saying "less often", and honouring that is the
    difference between a review surface and a nag.* Designed behaviour that
    until now had nowhere to happen."""
    signed_in.post(ON_THE_DAY, {"node": str(note.public_id), "response": "buried"})
    buried = queries.review_state(note)["interval"]

    other = services.capture(
        vince, content=LONG_ENOUGH + " Another.", captured_at=A_YEAR_AGO,
        source=Node.Source.WEB, actor="vince",
    )
    signed_in.post(ON_THE_DAY, {"node": str(other.public_id), "response": "kept"})
    kept = queries.review_state(other)["interval"]

    assert buried > kept


def test_a_nonsense_response_is_ignored_rather_than_recorded(signed_in, note):
    signed_in.post(ON_THE_DAY, {"node": str(note.public_id), "response": "banana"})

    assert note.events.filter(event_type=EventType.REVIEWED).count() == 0


def test_one_person_cannot_review_anothers_note(client, other_owner, note):
    client.force_login(other_owner)

    client.post(ON_THE_DAY, {"node": str(note.public_id), "response": "kept"})

    assert note.events.filter(event_type=EventType.REVIEWED).count() == 0


# ---------------------------------------------------------------------------
# Folded into the mode
# ---------------------------------------------------------------------------


def test_a_note_whose_schedule_came_round_resurfaces(db, vince):
    """**The fold D15 offered.** Two cues now reach Resurfacing — the calendar
    (D17) and the person's own answer — and they are different questions. An
    anniversary is *the date cues this*; a due review is *you asked to see this
    again*."""
    note = services.capture(
        vince, content=LONG_ENOUGH, captured_at=datetime.datetime(
            2020, 1, 2, 9, 0, tzinfo=datetime.timezone.utc
        ),
        source=Node.Source.WEB, actor="vince",
    )
    services.mark_reviewed(
        note,
        response=services.ReviewResponse.KEPT,
        now=NOW - datetime.timedelta(days=30),
        actor="vince",
    )

    assert [result.node for result in resurfacing(vince)] == [note]


def test_it_says_which_cue_brought_it(db, vince):
    note = services.capture(
        vince, content=LONG_ENOUGH, captured_at=datetime.datetime(
            2020, 1, 2, 9, 0, tzinfo=datetime.timezone.utc
        ),
        source=Node.Source.WEB, actor="vince",
    )
    services.mark_reviewed(
        note,
        response=services.ReviewResponse.KEPT,
        now=NOW - datetime.timedelta(days=30),
        actor="vince",
    )

    (result,) = resurfacing(vince)

    assert "asked to see this again" in result.why


def test_a_note_not_yet_due_stays_where_it_is(db, vince):
    note = services.capture(
        vince, content=LONG_ENOUGH, captured_at=datetime.datetime(
            2020, 1, 2, 9, 0, tzinfo=datetime.timezone.utc
        ),
        source=Node.Source.WEB, actor="vince",
    )
    services.mark_reviewed(
        note,
        response=services.ReviewResponse.KEPT,
        now=NOW - datetime.timedelta(days=1),
        actor="vince",
    )

    assert resurfacing(vince) == []


def test_nothing_becomes_due_for_somebody_who_never_answered(db, vince):
    """**Why wiring this is safe.** *A corpus of thousands would otherwise all
    become due at once the moment the feature exists.* Nothing changes for
    anybody until they answer something."""
    services.capture(
        vince, content=LONG_ENOUGH, captured_at=datetime.datetime(
            2020, 1, 2, 9, 0, tzinfo=datetime.timezone.utc
        ),
        source=Node.Source.WEB, actor="vince",
    )

    assert resurfacing(vince) == []


def test_the_anniversary_wins_when_a_note_is_both(db, vince, note):
    """Deduplication is above the generators and the first one owns the
    explanation, which is why `GENERATORS` is ordered. The date is the more
    specific thing to be told."""
    services.mark_reviewed(
        note,
        response=services.ReviewResponse.KEPT,
        now=NOW - datetime.timedelta(days=30),
        actor="vince",
    )

    (result,) = resurfacing(vince)

    assert "a year ago today" in result.why


# ---------------------------------------------------------------------------
# The tier that was unreachable
# ---------------------------------------------------------------------------


def test_the_review_candidate_tier_is_now_reachable(db, vince, note):
    """It was reachable *only through open hypotheses* — a second route to a
    tier whose own mechanism had never run.

    **This test passed before any of this was built**, because it calls
    `mark_reviewed` directly and `mark_reviewed` has always worked. That is the
    point rather than a flaw in the test: nothing in the code was broken, and
    the tier was still unreachable for every real person, because no surface
    ever called it. A green test over a dark seam is exactly what D15 exists to
    stop being mistaken for working software.
    """
    services.mark_reviewed(
        note,
        response=services.ReviewResponse.KEPT,
        now=NOW - datetime.timedelta(days=30),
        actor="vince",
    )

    assert queries.attention_tier(note, now=NOW) == "review candidate"
