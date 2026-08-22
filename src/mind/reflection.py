"""Reading observations back, with the denominator said out loud — increment 12.

The brief's own worked example, and the shape every reading here takes:

> *Alcohol was recorded on 8 nights this quarter. Low energy was recorded the
> following morning on 6 of those 8, compared with 5 of 19 other recorded
> mornings.*

**Two refusals travel with this and the brief calls them non-negotiable.**

**It must not say drinking causes low energy.** The reading is a comparison of
recorded rates and nothing more. Every sentence this module produces is checked
against the words that would turn it into a claim — not as a formality, but
because the difference between *recorded on 6 of 8* and *makes you tired* is
the difference between an instrument and an opinion about somebody's life.

**It must not read an unrecorded drink as sobriety.** A silent night is *not
recorded*, never *did not happen* — the same absence problem as D5, in the
place where it is most tempting to forget, because the days in between look
exactly like zeroes.

**The honest-denominator discipline already exists** in `review/reads.py`,
where `DailyFocus` snapshots what was *chosen* so a denominator cannot drift.
This carries it into a domain where the temptation is stronger: **recorded
mornings**, not all mornings, and stated rather than implied.
"""

import datetime
from dataclasses import dataclass

from daily.models import DailyEntry

from .models import Facet, FacetKind
from .observations import reads_as


#: Below this, a rate is a number that will be believed and should not be.
#:
#: `retirement_gate` already refuses to grade on too small a sample, and the
#: argument is stronger here: that one is about a detector, and this is about
#: somebody's own life.
ENOUGH_TO_COMPARE = 3


@dataclass(frozen=True)
class Comparison:
    """Two recorded rates, side by side, and never a conclusion."""

    #: Nights on which the first observation was recorded.
    nights_recorded: int
    #: Days in the window with no entry at all. **Not sober nights.**
    nights_not_recorded: int
    #: Of `nights_recorded`, mornings after which the second was recorded.
    mornings_after: int
    #: Other recorded mornings, which is the denominator that matters.
    other_mornings_recorded: int
    #: Of those, how many carried the second observation.
    other_mornings_with: int
    reads_as: str
    denominator_says: str
    absence_says: str

    @property
    def worth_reading(self):
        return self.nights_recorded >= ENOUGH_TO_COMPARE


def _days_with(owner, name, since, until):
    entries = DailyEntry.objects.filter(owner=owner, date__gte=since, date__lte=until)
    marked = set(
        Facet.objects.filter(
            entry__in=entries,
            kind=FacetKind.OBSERVATION,
            retired_at__isnull=True,
            data__observation=name,
        ).values_list("entry__date", flat=True)
    )
    return {entry.date for entry in entries}, marked


def after_a_recorded_night(owner, night, morning, *, since, until=None):
    """How often ``morning`` was recorded the day after ``night`` was.

    Compared against the other recorded mornings, which is the only comparison
    available — and stated, because a rate whose denominator is unstated is a
    rate somebody will read as *of all mornings*.

    **Returns counts and sentences, never a verdict.** The sentences are the
    product: a number without its denominator is what this exists to prevent,
    and the two cannot be allowed to travel separately.
    """
    until = until or (since + datetime.timedelta(days=90))
    recorded, drinking_nights = _days_with(owner, night, since, until)
    _, low_mornings = _days_with(owner, morning, since, until)

    mornings_after = sum(
        1
        for day in drinking_nights
        if day + datetime.timedelta(days=1) in low_mornings
    )
    # **Other recorded mornings**, and every word of that is load-bearing.
    #
    # A morning qualifies only when the night before it was **recorded and did
    # not carry the observation**. The first version asked merely whether the
    # previous day was absent from `drinking_nights`, which admitted every
    # morning after a night nobody wrote in — and that is the refusal itself,
    # in code: **an unrecorded night read as a sober one.** The test that
    # caught it is `test_the_denominator_is_recorded_days_and_never_all_days`,
    # and it caught it on the first run.
    others = {
        day
        for day in recorded
        if (day - datetime.timedelta(days=1)) in recorded
        and (day - datetime.timedelta(days=1)) not in drinking_nights
    }
    other_with = sum(1 for day in others if day in low_mornings)

    span = (until - since).days + 1
    not_recorded = span - len(recorded)

    if len(drinking_nights) < ENOUGH_TO_COMPARE:
        summary = (
            f"too few recorded nights to compare — {len(drinking_nights)} so far"
        )
    else:
        # Past tense, and *recorded* in every clause. The sentence is a report
        # of what the journal holds, not a finding about the person.
        summary = (
            f"{reads_as(night)} was recorded on {len(drinking_nights)} nights. "
            f"{reads_as(morning)} was recorded the following morning on "
            f"{mornings_after} of those {len(drinking_nights)}, compared with "
            f"{other_with} of {len(others)} other recorded mornings"
        )

    return Comparison(
        nights_recorded=len(drinking_nights),
        nights_not_recorded=not_recorded,
        mornings_after=mornings_after,
        other_mornings_recorded=len(others),
        other_mornings_with=other_with,
        reads_as=summary,
        denominator_says=(
            "the denominator is recorded mornings, not all mornings — days "
            "with no entry are not counted on either side"
        ),
        absence_says=(
            f"{not_recorded} days in this window were not recorded at all. "
            f"A day with no entry is not recorded, which is not the same as "
            f"{reads_as(night)} not happening"
        ),
    )
