"""Reading a commitment out of a capture.

Deterministic and rule-based, which is what lets it run on the live path.
`design-concept.md` is explicit that capture, routing and planning stay off any
model: no per-call cost, no prompt sensitivity, no hallucinated due date, and a
result a test can pin exactly.

**It proposes; it never commits.** The actionable facet is the one
classification that creates an obligation, so this offers one and a person
accepts it. A parser confident enough to attach a due date by itself would be
putting things into somebody's week that they never agreed to.

The two failure directions are not symmetric, and everything here is shaped by
that. Missing a date costs one tap. Inventing one puts a commitment nobody made
into an agenda, where it will be trusted precisely because the system is
supposed to be trustworthy. So this prefers silence to a guess at every point
where it could go either way — which is why an ordinal only reads as a date in
the positions a date can actually occupy, and why a cadence the task core
cannot store is dropped rather than rounded to the nearest one it can.
"""

from __future__ import annotations

import re
from calendar import monthrange
from dataclasses import dataclass
from datetime import date, timedelta

# The three the task core can hold. A parser that read "every third Tuesday"
# would promise a cadence `Item.Recurrence` cannot store, and a commitment
# silently recorded as the wrong one is worse than one not recognised at all.
DAILY, WEEKLY, MONTHLY = "daily", "weekly", "monthly"

_WEEKDAYS = (
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
)
_DAY = "|".join(_WEEKDAYS)

_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}
_MONTH = "|".join(sorted(_MONTHS, key=len, reverse=True))

_COUNTS = {
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
    "twelve": 12,
}

# Checked before anything else, and the whole point is that matching one means
# proposing *no* cadence. `Item.Recurrence` has three values, so a fortnightly
# commitment recorded as weekly would put twenty-six extra tasks a year into
# somebody's agenda while looking like it had understood them.
#
# Most of these would fall through the patterns below anyway. They are named
# explicitly because that is a property worth stating rather than relying on:
# the next person to widen `every ...` should have to delete a line here first.
_UNHOLDABLE = re.compile(
    r"\bevery other\b|\bevery \d+\b|\bevery few\b|\bfortnight|\bbi-?weekly\b"
    r"|\bbi-?monthly\b|\bevery now and then\b|\bevery so often\b"
    r"|\bevery (?:{days}) and\b".format(days=_DAY),
    re.I,
)

_EVERY = r"(?:every|each)"
_CADENCES = (
    (re.compile(rf"\b{_EVERY} ?day\b|\bdaily\b", re.I), DAILY),
    (re.compile(rf"\b{_EVERY} week\b|\bweekly\b|\b{_EVERY} (?:{_DAY})\b", re.I), WEEKLY),
    (re.compile(rf"\b{_EVERY} month\b|\bmonthly\b", re.I), MONTHLY),
)

_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")

# Both orders people write a named month in, with the year optional.
_DAY_MONTH = re.compile(
    rf"\b(?:the\s+)?(\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?({_MONTH})\b"
    r"(?:,?\s+(\d{4}))?",
    re.I,
)
_MONTH_DAY = re.compile(
    rf"\b({_MONTH})\s+(?:the\s+)?(\d{{1,2}})(?:st|nd|rd|th)?\b(?:,?\s+(\d{{4}}))?",
    re.I,
)

# A bare day of the month, and the restriction is the interesting part. The
# ordinal must be introduced by "the", and what follows it must be nothing,
# punctuation, "of", or a time -- the positions a date can actually occupy.
# Without that, "the 4th time I tried this" and "the 3rd person to say that"
# both read as commitments, which is the expensive direction to be wrong in.
_ORDINAL = re.compile(
    r"\bthe\s+(\d{1,2})(?:st|nd|rd|th)\b(?=$|\s*[.,;:!?)]|\s+of\b|\s+at\b)",
    re.I,
)

_IN = re.compile(
    r"\bin\s+(\d{1,3}|" + "|".join(_COUNTS) + r")\s+(day|week|month)s?\b", re.I
)
_WEEKDAY = re.compile(rf"\b(next|this|every|each)?\s*({_DAY})\b", re.I)
_TODAY = re.compile(r"\btoday\b", re.I)
_TOMORROW = re.compile(r"\btomorrow\b", re.I)


@dataclass(frozen=True)
class Commitment:
    """What a capture appears to be committing to, and the words that said so."""

    due_date: date
    recurrence: str | None
    matched_date: str | None
    matched_cadence: str | None

    @property
    def reason(self) -> str:
        """Names the phrases, so a reader can disagree without trusting anything.

        "Looks like a task" asks for trust. "read '4th' — repeats monthly" lets
        somebody see exactly what was matched and say no, which is the whole
        difference between a proposal and an assertion. Both halves are quoted
        when both were read, because either one can be the wrong one.
        """
        parts = []
        if self.matched_date:
            parts.append(f"read {self.matched_date!r}")
        if self.recurrence:
            quoted = f" ({self.matched_cadence!r})" if self.matched_cadence else ""
            parts.append(f"repeats {self.recurrence}{quoted}")
        return " — ".join(parts) or "read a date"


def _add_months(start: date, count: int) -> date:
    """`start` shifted by whole months, clamped into a month that is shorter.

    Clamping is right here and wrong in `_next_day_of_month` below, which is
    worth being awake to: "in 1 month" from January 31 can only reasonably mean
    the end of February, while "the 31st" naming a month without one is a date
    that does not exist and should move rather than be rounded.
    """
    month = start.month - 1 + count
    year = start.year + month // 12
    month = month % 12 + 1
    return start.replace(
        year=year, month=month, day=min(start.day, monthrange(year, month)[1])
    )


def _next_day_of_month(today: date, day: int) -> date | None:
    """The next date landing on that day of the month, today included.

    Walks forward to a month that actually *has* the day rather than clamping
    to the last one it does. "The 31st" in a thirty-day month is not the 30th;
    it is a month away. The task core clamps when it advances a monthly series,
    which is its own documented behaviour — inventing the first occurrence is a
    different act and not one to perform on somebody's behalf.
    """
    if not 1 <= day <= 31:
        return None
    cursor = today.replace(day=1)
    for _ in range(14):  # more than a year, so a 31st is always reachable
        if day <= monthrange(cursor.year, cursor.month)[1]:
            candidate = cursor.replace(day=day)
            if candidate >= today:
                return candidate
        cursor = _add_months(cursor, 1)
    return None


def _weekday_on_or_after(today: date, name: str, *, skip_today: bool) -> date:
    """The coming occurrence of a named day.

    Today counts as zero days away, so "every Wednesday" said on a Wednesday
    means today — a real answer, not an off-by-one. "Next Wednesday" on a
    Wednesday means the one after, which is why the two are distinguished at
    all; treating them the same makes one of them wrong, and which one depends
    on a habit no parser can see.
    """
    ahead = (_WEEKDAYS.index(name) - today.weekday()) % 7
    if skip_today and ahead == 0:
        ahead = 7
    return today + timedelta(days=ahead)


def _in_year(today: date, month: int, day: int, year: int | None) -> date | None:
    """A named month resolved forward when no year was given.

    "5 June" written in July means next June. An explicit year is obeyed
    exactly, including one in the past — somebody writing 2025 has said
    something specific, and second-guessing it would be the parser overruling
    the person.
    """
    if year is not None:
        try:
            return date(year, month, day)
        except ValueError:
            return None
    for candidate_year in (today.year, today.year + 1):
        try:
            candidate = date(candidate_year, month, day)
        except ValueError:
            return None
        if candidate >= today:
            return candidate
    return None


def _find_cadence(text: str) -> tuple[str | None, str | None]:
    if _UNHOLDABLE.search(text):
        return None, None
    for pattern, cadence in _CADENCES:
        found = pattern.search(text)
        if found:
            return cadence, found.group(0)
    return None, None


def _find_date(text: str, today: date) -> tuple[date | None, str | None]:
    """The first reading that lands, in order of how explicit it is.

    Order is doing real work. "The 24th of June" has to reach `_DAY_MONTH`
    before `_ORDINAL` sees it, or it becomes the 24th of whatever month comes
    next; a bare weekday has to come last, so "every Monday" is read once as a
    cadence and its date taken from the same words rather than twice.
    """
    if found := _ISO.search(text):
        try:
            return (
                date(int(found[1]), int(found[2]), int(found[3])),
                found.group(0),
            )
        except ValueError:
            # Well-formed digits that are not a date -- 2026-13-40. Falling
            # through rather than guessing which half was the typo.
            pass

    for pattern, day_first in ((_DAY_MONTH, True), (_MONTH_DAY, False)):
        if found := pattern.search(text):
            raw_day, raw_month = (found[1], found[2]) if day_first else (found[2], found[1])
            resolved = _in_year(
                today,
                _MONTHS[raw_month.lower()],
                int(raw_day),
                int(found[3]) if found[3] else None,
            )
            if resolved is not None:
                return resolved, found.group(0)

    if found := _ORDINAL.search(text):
        resolved = _next_day_of_month(today, int(found[1]))
        if resolved is not None:
            return resolved, found.group(0)

    if found := _TOMORROW.search(text):
        return today + timedelta(days=1), found.group(0)
    if found := _TODAY.search(text):
        return today, found.group(0)

    if found := _IN.search(text):
        raw, unit = found[1].lower(), found[2].lower()
        count = int(raw) if raw.isdigit() else _COUNTS[raw]
        if unit == "month":
            return _add_months(today, count), found.group(0)
        return today + timedelta(days=count * (7 if unit == "week" else 1)), found.group(0)

    if found := _WEEKDAY.search(text):
        qualifier = (found[1] or "").lower()
        return (
            _weekday_on_or_after(today, found[2].lower(), skip_today=qualifier == "next"),
            found.group(0).strip(),
        )

    return None, None


def find_commitment(text: str, *, today: date) -> Commitment | None:
    """A due date and cadence read from ordinary writing, or None.

    `today` is passed in rather than read here, so the result depends on
    nothing but its arguments — the same injected-clock rule the rest of the
    domain follows, and what lets a weekday test mean the same thing whenever
    it runs.
    """
    if not text or not text.strip():
        return None

    cadence, matched_cadence = _find_cadence(text)
    due, matched_date = _find_date(text, today)

    if due is None and cadence is None:
        return None

    # A repeating commitment needs a first occurrence, and today is the only
    # honest default: any other start date is one nobody chose.
    return Commitment(
        due_date=due or today,
        recurrence=cadence,
        matched_date=matched_date,
        matched_cadence=matched_cadence,
    )
