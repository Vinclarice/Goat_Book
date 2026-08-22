"""What memory notices — Track C, increments 11 and 12.

Sleep, alcohol, mood, exercise, illness and energy **cannot be understood
reliably through textual similarity at all.** They are quantities and states
over time, and Reflection mode is worthless without them.

**No new model, and the schema already says why.** `Facet` attaches to a
`daily.DailyEntry`, carries `data`, separates `EXPLICIT` from `INFERRED`,
records its `producer`, and has `confirmed_at` and `retired_at`. And the
constraint that made D6 hard does not bite here: entry facets are unique by
`(entry, fingerprint)`, **deliberately not one per kind** — *"a day's writing
may carry three separate promises, and copying the node rule across would let a
Tuesday propose one of them and drop the rest silently."* A day carries several
observations for exactly that reason.

**Two refusals travel with increment 12 and the brief calls them
non-negotiable:**

- **It must not say drinking causes low energy.** The reading is a comparison
  of recorded rates and nothing else.
- **It must not read an unrecorded drink as sobriety.** A silent night is *not
  recorded*, never *did not happen* — the same absence problem as D5, in the
  place where it is most tempting to forget.

The honest-denominator discipline already exists in `review/reads.py` and this
carries it into a new domain: **recorded mornings**, not all mornings, and the
denominator is stated rather than implied.
"""

import datetime

import pytest

from daily.models import DailyEntry
from mind import observations, reflection, services
from mind.models import Facet, FacetKind, InferenceOrigin


MONDAY = datetime.date(2026, 5, 4)
NOW = datetime.datetime(2026, 5, 4, 21, 0, tzinfo=datetime.timezone.utc)


def an_entry(owner, day, **fields):
    return DailyEntry.objects.create(owner=owner, date=day, **fields)


def observations_on(entry):
    return sorted(
        facet.data["observation"]
        for facet in Facet.objects.filter(
            entry=entry, kind=FacetKind.OBSERVATION, retired_at__isnull=True
        )
    )


# ---------------------------------------------------------------------------
# 11 — extraction, namespaced, and honest about what it knows
# ---------------------------------------------------------------------------


def test_it_notices_a_drink(db, owner):
    entry = an_entry(owner, MONDAY, happenings="Two glasses of wine with dinner.")

    observations.propose_from(entry, now=NOW)

    assert "alcohol.consumed" in observations_on(entry)


def test_it_notices_a_bad_night(db, owner):
    entry = an_entry(owner, MONDAY, happenings="Slept badly, awake at four again.")

    observations.propose_from(entry, now=NOW)

    assert "sleep.poor" in observations_on(entry)


def test_it_notices_low_energy(db, owner):
    entry = an_entry(owner, MONDAY, happenings="Exhausted all morning.")

    observations.propose_from(entry, now=NOW)

    assert "energy.low" in observations_on(entry)


def test_one_day_can_carry_several(db, owner):
    """The reason this needs no new model: entry facets are unique by
    `(entry, fingerprint)` and deliberately not one per kind."""
    entry = an_entry(
        owner, MONDAY, happenings="Two glasses of wine. Slept badly. Exhausted."
    )

    observations.propose_from(entry, now=NOW)

    assert len(observations_on(entry)) >= 3


def test_what_it_parses_is_an_inference_and_says_so(db, owner):
    """*Explicit statements are recorded as facts; parsed ones stay labeled
    inferences until confirmed or supported.* The soft-apply rule again: a
    guess is never treated as fact by anything downstream."""
    entry = an_entry(owner, MONDAY, happenings="Two glasses of wine with dinner.")

    observations.propose_from(entry, now=NOW)

    facet = Facet.objects.get(entry=entry, kind=FacetKind.OBSERVATION)
    assert facet.origin == InferenceOrigin.INFERRED
    assert facet.confirmed_at is None


def test_it_names_the_producer_that_proposed_it(db, owner):
    """`Facet.producer` exists so accept rates can be read per proposer, and a
    producer shipping without a row in `/numbers/` is the un-switched seam this
    repository keeps catching."""
    entry = an_entry(owner, MONDAY, happenings="Two glasses of wine.")

    observations.propose_from(entry, now=NOW)

    assert Facet.objects.get(entry=entry).producer == observations.PRODUCER


def test_it_quotes_the_words_that_caused_it(db, owner):
    """The same discipline as every other proposer here: a proposal a person
    cannot check is one they can only accept or distrust."""
    entry = an_entry(owner, MONDAY, happenings="Nothing much. Two glasses of wine.")

    observations.propose_from(entry, now=NOW)

    facet = Facet.objects.get(entry=entry)
    assert "wine" in entry.happenings[facet.span_start : facet.span_end]


def test_running_twice_proposes_once(db, owner):
    """`facet_entry_fingerprint_unique` is the guard, and this asserts the
    fingerprint is actually per-observation rather than per-entry."""
    entry = an_entry(owner, MONDAY, happenings="Two glasses of wine. Slept badly.")

    observations.propose_from(entry, now=NOW)
    before = observations_on(entry)
    observations.propose_from(entry, now=NOW)

    assert observations_on(entry) == before


def test_a_day_that_says_nothing_of_the_kind_proposes_nothing(db, owner):
    entry = an_entry(owner, MONDAY, happenings="Worked on the chapter all day.")

    observations.propose_from(entry, now=NOW)

    assert observations_on(entry) == []


def test_it_reads_every_part_of_the_entry(db, owner):
    """`DailyEntry` has three text fields and a day's drinking is as likely to
    be in *happenings* as anywhere. Reading one would make the extractor's
    coverage depend on which box somebody typed in."""
    entry = an_entry(owner, MONDAY, gratitude="A glass of wine with Sam.")

    observations.propose_from(entry, now=NOW)

    assert "alcohol.consumed" in observations_on(entry)


# ---------------------------------------------------------------------------
# 12 — reflection, with the denominator said out loud
# ---------------------------------------------------------------------------


def a_recorded_day(owner, day, *, drank=False, tired=False):
    entry = an_entry(owner, day, happenings="recorded")
    for name, present in (("alcohol.consumed", drank), ("energy.low", tired)):
        if present:
            Facet.objects.create(
                entry=entry,
                kind=FacetKind.OBSERVATION,
                data={"observation": name},
                origin=InferenceOrigin.EXPLICIT,
                confirmed_at=NOW,
                producer=observations.PRODUCER,
                fingerprint=f"{day}-{name}",
                reason="said so",
            )
    return entry


def test_it_compares_recorded_rates_and_states_both(db, owner):
    """The brief's own worked example: *alcohol was recorded on 8 nights this
    quarter; low energy was recorded the following morning on 6 of those 8,
    compared with 5 of 19 other recorded mornings.*"""
    for offset in range(3):
        a_recorded_day(owner, MONDAY + datetime.timedelta(days=offset * 2), drank=True)
        a_recorded_day(
            owner, MONDAY + datetime.timedelta(days=offset * 2 + 1), tired=True
        )

    reading = reflection.after_a_recorded_night(
        owner, "alcohol.consumed", "energy.low", since=MONDAY
    )

    assert reading.nights_recorded == 3
    assert reading.mornings_after == 3


def test_the_denominator_is_recorded_days_and_never_all_days(db, owner):
    """*Recorded mornings*, not all mornings. The honest-denominator discipline
    from `review/reads.py`, carried into a domain where the temptation is
    stronger because the days in between look like zeroes."""
    a_recorded_day(owner, MONDAY, drank=True)
    a_recorded_day(owner, MONDAY + datetime.timedelta(days=1), tired=True)
    # Three weeks of silence, which is not three weeks of anything else.

    reading = reflection.after_a_recorded_night(
        owner, "alcohol.consumed", "energy.low", since=MONDAY
    )

    assert reading.other_mornings_recorded == 0
    assert "recorded" in reading.denominator_says


def test_a_silent_night_is_not_a_sober_one(db, owner):
    """**The refusal the brief calls non-negotiable.** A night with no entry is
    *not recorded*, never *did not happen* — the same absence problem as D5, in
    the place where it is most tempting to forget."""
    a_recorded_day(owner, MONDAY, drank=True)
    # MONDAY + 1 has no entry at all.
    a_recorded_day(owner, MONDAY + datetime.timedelta(days=2), tired=True)

    reading = reflection.after_a_recorded_night(
        owner, "alcohol.consumed", "energy.low", since=MONDAY
    )

    assert reading.nights_recorded == 1
    assert reading.nights_not_recorded >= 1
    assert "not recorded" in reading.absence_says


def test_it_never_says_one_thing_caused_another(db, owner):
    """**The other non-negotiable refusal.** The reading is a comparison of
    recorded rates and nothing more, and the words that would turn it into a
    claim are the ones checked for."""
    a_recorded_day(owner, MONDAY, drank=True)
    a_recorded_day(owner, MONDAY + datetime.timedelta(days=1), tired=True)

    reading = reflection.after_a_recorded_night(
        owner, "alcohol.consumed", "energy.low", since=MONDAY
    )
    words = " ".join(
        [reading.reads_as, reading.denominator_says, reading.absence_says]
    ).lower()

    for forbidden in ("caus", "because", "leads to", "makes you", "due to", "effect of"):
        assert forbidden not in words


def test_it_says_when_there_is_too_little_to_compare(db, owner):
    """A rate over one night is a number that will be believed and should not
    be. `retirement_gate`'s sample-floor instinct, in a place where the figure
    is about somebody's own life."""
    a_recorded_day(owner, MONDAY, drank=True)

    reading = reflection.after_a_recorded_night(
        owner, "alcohol.consumed", "energy.low", since=MONDAY
    )

    assert not reading.worth_reading
    assert "too few" in reading.reads_as.lower()


def test_one_person_never_reads_anothers_days(db, owner, other_owner):
    a_recorded_day(other_owner, MONDAY, drank=True)

    reading = reflection.after_a_recorded_night(
        owner, "alcohol.consumed", "energy.low", since=MONDAY
    )

    assert reading.nights_recorded == 0


# ---------------------------------------------------------------------------
# It has a caller, which the line above `propose_journal_commitments` already
# insists on: *a producer nothing calls is not a producer*
# ---------------------------------------------------------------------------


def test_writing_in_a_day_proposes_observations(db, owner):
    """Beside the commitment producer, invoked from the same place and for the
    same stated reason -- *the lesson `run_detectors` taught by being green and
    uninvoked for weeks.*"""
    from daily import services as daily_services

    entry = daily_services.write_entry(
        owner, MONDAY, happenings="Two glasses of wine, slept badly."
    )

    assert "alcohol.consumed" in observations_on(entry)


def test_writing_nothing_of_the_kind_proposes_nothing(db, owner):
    from daily import services as daily_services

    entry = daily_services.write_entry(owner, MONDAY, happenings="Worked on the chapter.")

    assert observations_on(entry) == []


def test_rewriting_a_day_does_not_propose_the_same_thing_twice(db, owner):
    """A journal is edited all day. `facet_entry_fingerprint_unique` is the
    guard and this is the path that actually exercises it."""
    from daily import services as daily_services

    daily_services.write_entry(owner, MONDAY, happenings="Two glasses of wine.")
    entry = daily_services.write_entry(
        owner, MONDAY, happenings="Two glasses of wine. And a walk."
    )

    assert observations_on(entry).count("alcohol.consumed") == 1


# ---------------------------------------------------------------------------
# The reading has a surface, and it carries both refusals onto the page
# ---------------------------------------------------------------------------


def recent_days(owner):
    """Days inside the page's own ninety-day window.

    The unit tests use a fixed May date, which is right for them -- the read
    takes `since` and nothing is guessed. The *page* looks back from now, so a
    fixed date puts every day outside the window and the section renders empty
    for a reason that has nothing to do with the reading.
    """
    from django.utils import timezone

    today = timezone.now().date()
    for offset in range(3):
        a_recorded_day(owner, today - datetime.timedelta(days=offset * 2 + 2), drank=True)
        a_recorded_day(owner, today - datetime.timedelta(days=offset * 2 + 1), tired=True)


def test_the_review_page_shows_the_reading(db, client, owner):
    client.force_login(owner)
    recent_days(owner)

    body = client.get("/mind/review/").content.decode()

    assert "was recorded on 3 nights" in body


def test_the_page_states_the_denominator_beside_the_number(db, client, owner):
    """A rate whose denominator is unstated is a rate somebody reads as *of all
    mornings*, and the two must not be able to travel separately."""
    client.force_login(owner)
    recent_days(owner)

    body = client.get("/mind/review/").content.decode()

    assert "recorded mornings, not all mornings" in body


def test_the_page_says_a_silent_night_is_not_a_sober_one(db, client, owner):
    client.force_login(owner)
    recent_days(owner)

    body = client.get("/mind/review/").content.decode()

    assert "not recorded" in body


def test_the_page_shows_nothing_when_there_is_too_little(db, client, owner):
    """Rather than a rate over one night, which is a number that will be
    believed and should not be."""
    client.force_login(owner)
    a_recorded_day(owner, MONDAY, drank=True)

    body = client.get("/mind/review/").content.decode()

    assert "was recorded on" not in body


def test_the_reading_uses_a_persons_words_for_what_was_observed(db, client, owner):
    """`alcohol.consumed` is a namespace, chosen so a reading can ask about
    `alcohol` without knowing every phrasing. It is not what somebody should
    read on a page -- the same bend the note page had with `facet_confirmed`,
    third time today.
    """
    client.force_login(owner)
    recent_days(owner)

    body = client.get("/mind/review/").content.decode()

    assert "drinking was recorded on 3 nights" in body
    assert "alcohol.consumed was recorded" not in body
