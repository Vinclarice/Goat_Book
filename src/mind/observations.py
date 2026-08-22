"""What memory notices in a day's writing — Track C increment 11.

Sleep, alcohol, mood, exercise, illness and energy **cannot be understood
reliably through textual similarity at all.** They are quantities and states
over time, and Reflection mode is worthless without them — which is why they
get proposed as structure beside the entry rather than left in prose for a
similarity search to fail at.

**No new model, and the schema already anticipated this.** `Facet` attaches to
a `daily.DailyEntry`, carries `data`, separates `EXPLICIT` from `INFERRED`,
records which `producer` proposed it, and has `confirmed_at` and `retired_at`.
And the constraint that decided D6 does not bite here: entry facets are unique
by `(entry, fingerprint)` and **deliberately not one per kind**, because *"a
day's writing may carry three separate promises."* A day carries several
observations for exactly that reason.

**Namespaced**, so a reading can ask about `alcohol` without knowing every
phrasing that produced one.

**Everything here is an inference and says so.** The brief allows explicit
statements to be recorded as facts, and nothing in the journal is explicit
today — there is no form that asks *did you drink*, and the product's first
principle is that nothing demands a decision at the moment of entry. So the
parser proposes, `origin` stays `INFERRED`, and a person confirms. The moment a
surface exists that asks outright, it writes `EXPLICIT` and this module does
not change.

**Rules, not a model.** Part 2's instinct — *predicates before ranking* —
applies harder here than anywhere: a classifier deciding somebody drank last
night is a claim about their life made by a number nobody can inspect. Every
pattern below can be read, disagreed with and corrected.
"""

import hashlib
import re

from django.db import transaction

from .models import Facet, FacetKind, InferenceOrigin, entry_body


#: Named so its accept rate is its own question. `Facet.producer` exists
#: because *"which producer is worth hearing from"* cannot be answered by one
#: blended number — the same argument as Track B increment 10, one layer down.
PRODUCER = "journal_observation"


#: What the parser can notice, namespaced, with the words that trigger each.
#:
#: **Readable on purpose.** A person disagreeing with an observation should be
#: able to see exactly which words caused it, and change them. That is not
#: available from a classifier, and this is a claim about somebody's life.
#:
#: Eight of Part 3's namespaces, and the vocabulary is deliberately narrow:
#: over-generating here is not the cheap failure it is for concept extraction,
#: because a false *alcohol.consumed* is a wrong statement about a person
#: rather than a spare row.
PATTERNS = (
    ("alcohol.consumed", r"\b(wine|beer|whisky|whiskey|gin|vodka|pint|pints|drinks?|drank|cocktail)\b"),
    ("sleep.poor", r"\b(slept badly|couldn't sleep|could not sleep|awake at|insomnia|bad night|barely slept)\b"),
    ("sleep.late", r"\b(woke late|slept in|overslept|lie[- ]in)\b"),
    ("energy.low", r"\b(exhausted|shattered|knackered|no energy|drained|wiped out)\b"),
    ("mood.low", r"\b(miserable|low mood|down all day|fed up|flat all day)\b"),
    ("mood.anxious", r"\b(anxious|anxiety|panicky|on edge|dread)\b"),
    ("exercise.completed", r"\b(ran|run|gym|swim|swam|cycled|walked \d|workout|yoga)\b"),
    ("health.symptom", r"\b(headache|migraine|sore throat|fever|nauseous|cold coming)\b"),
)

_COMPILED = tuple((name, re.compile(pattern, re.IGNORECASE)) for name, pattern in PATTERNS)


def _fingerprint(entry, name, matched):
    """Stable per observation, blind to where in the entry it sits.

    The rule `_commitment_fingerprint` already established and for the same
    reason: typing a line at the top shifts every offset below it, so a
    fingerprint including the span would re-propose the whole day on one
    insertion.
    """
    digest = hashlib.sha256(f"{name}|{matched.lower()}".encode()).hexdigest()
    return f"{PRODUCER}:{digest[:32]}"


@transaction.atomic
def propose_from(entry, *, now):
    """Propose structured observations beside a day's writing.

    **The entry is never altered.** What somebody wrote stays what they wrote;
    the structure sits next to it, corrigible, and retiring every proposal
    leaves the day exactly as it was.

    Reads all three text fields, because a day's drinking is as likely to be in
    *gratitude* as in *happenings* and coverage that depended on which box
    somebody typed in would be a property of the form rather than of the day.
    """
    text = entry_body(entry)
    if not text.strip():
        return []

    proposed = []
    for name, pattern in _COMPILED:
        match = pattern.search(text)
        if match is None:
            continue
        facet, created = Facet.objects.get_or_create(
            entry=entry,
            fingerprint=_fingerprint(entry, name, match.group()),
            defaults={
                "kind": FacetKind.OBSERVATION,
                # Always an inference, and always said so. Nothing in the
                # journal is an explicit statement today: no form asks *did you
                # drink*, and nothing may ask at the moment of entry.
                "origin": InferenceOrigin.INFERRED,
                "producer": PRODUCER,
                "reason": f"the entry says {match.group()!r}",
                "span_start": match.start(),
                "span_end": match.end(),
                "data": {"observation": name},
            },
        )
        if created:
            proposed.append(facet)
    return proposed


#: What each namespace reads as on a page a person looks at.
#:
#: The namespaces are for asking -- `alcohol` without knowing every phrasing
#: that produced one -- and a person should never see them. The same bend the
#: note page had with `facet_confirmed`, and the fallback matters more than the
#: phrases: a new pattern must degrade to something readable rather than blank.
READS_AS = {
    "alcohol.consumed": "drinking",
    "sleep.poor": "a bad night",
    "sleep.late": "waking late",
    "energy.low": "low energy",
    "mood.low": "low mood",
    "mood.anxious": "feeling anxious",
    "exercise.completed": "exercise",
    "health.symptom": "feeling unwell",
}


def reads_as(name):
    """A person's words for an observation, falling back to the namespace."""
    return READS_AS.get(name) or name.split(".")[-1].replace("_", " ")
