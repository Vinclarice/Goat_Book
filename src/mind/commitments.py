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
where it could go either way.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta

# The three the task core can actually hold. A parser that read "every third
# Tuesday" would be promising a cadence `Item.Recurrence` cannot store, and a
# commitment silently recorded as the wrong one is worse than one not recognised.
DAILY, WEEKLY, MONTHLY = "daily", "weekly", "monthly"

_RECURRENCES = (
    (re.compile(r"\bevery ?day\b|\bdaily\b", re.I), DAILY),
    (re.compile(r"\bevery week\b|\bweekly\b", re.I), WEEKLY),
    (re.compile(r"\bevery month\b|\bmonthly\b", re.I), MONTHLY),
)

_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_TODAY = re.compile(r"\btoday\b", re.I)
_TOMORROW = re.compile(r"\btomorrow\b", re.I)

_WEEKDAYS = (
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
)
_WEEKDAY = re.compile(r"\b(next )?(" + "|".join(_WEEKDAYS) + r")\b", re.I)


@dataclass(frozen=True)
class Commitment:
    """What a capture appears to be committing to, and the words that said so."""

    due_date: date
    recurrence: str | None
    matched: str

    @property
    def reason(self) -> str:
        """Names the phrase, so the reader can disagree without trusting anything.

        "Looks like a task" asks for trust. "read 'Friday'" lets somebody see
        exactly what was matched and say no, which is the difference between a
        proposal and an assertion.
        """
        if self.recurrence:
            return f"read {self.matched!r} — repeats {self.recurrence}"
        return f"read {self.matched!r}"


def _next_weekday(today: date, name: str, *, explicitly_next: bool) -> date:
    """The coming occurrence of a named day.

    Today counts as zero days away, so a bare weekday naming today means today
    and "next Wednesday" said on a Wednesday means the one after. Treating both
    the same would make one of them wrong, and which one depends on a habit no
    parser can see.
    """
    ahead = (_WEEKDAYS.index(name) - today.weekday()) % 7
    if explicitly_next and ahead == 0:
        ahead = 7
    return today + timedelta(days=ahead)


def find_commitment(text: str, *, today: date) -> Commitment | None:
    """A due date and cadence read from ordinary writing, or None.

    `today` is passed in rather than read here, so the result depends on nothing
    but its arguments -- the same injected-clock rule the rest of the domain
    follows, and what lets a weekday test mean the same thing whenever it runs.
    """
    if not text or not text.strip():
        return None

    recurrence = None
    matched = None
    for pattern, cadence in _RECURRENCES:
        found = pattern.search(text)
        if found:
            recurrence, matched = cadence, found.group(0)
            break

    due = None
    if iso := _ISO.search(text):
        try:
            due = date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))
            matched = matched or iso.group(0)
        except ValueError:
            # A well-formed number that is not a date -- 2026-13-40. Silence
            # rather than a guess, per the asymmetry in the module docstring.
            due = None
    elif _TOMORROW.search(text):
        due, matched = today + timedelta(days=1), matched or "tomorrow"
    elif _TODAY.search(text):
        due, matched = today, matched or "today"
    elif weekday := _WEEKDAY.search(text):
        due = _next_weekday(
            today, weekday.group(2).lower(), explicitly_next=bool(weekday.group(1))
        )
        matched = matched or weekday.group(0)

    if due is None and recurrence is None:
        return None

    # A repeating commitment needs a first occurrence, and today is the only
    # honest default: any other start date is one nobody chose.
    return Commitment(due_date=due or today, recurrence=recurrence, matched=matched)
