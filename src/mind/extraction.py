"""Concept extraction: finding the referents a note names.

Deliberately crude, and safe *because* it is crude. Every concept this produces is
a **candidate** — unconfirmed, and excluded by `queries.confirmed_concepts` from
the corpus any inference is allowed to search. Over-generation therefore costs a
row and a line in a review list, not a wrong connection. That is the whole reason a
rule-based extractor is acceptable here: the confirmation gate absorbs its errors,
so it does not need to be clever.

Rule-based rather than a model, per the ML policy: local, deterministic, no
per-call cost, and no generation. Runs in the same asynchronous path as indexing,
so capture is never blocked waiting for it.

What it finds: runs of capitalised words that are not merely sentence beginnings —
people, places, products, projects. What it misses, knowingly: any referent named
in lowercase ("my brother", "the corner shop"), which is exactly the kind of
description an alias is for. That gap is not a defect to fix by widening the rules;
it is what makes the alias mechanism necessary, and the person supplies it once.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Collection

# Words that commonly begin an English sentence and are therefore capitalised for
# reasons that have nothing to do with naming anything. Deliberately short: this
# only has to catch the frequent cases, because a false candidate is cheap.
SENTENCE_STARTERS = frozenset(
    """
    a about after again all also am an and another any are as at back be because
    been before being both but by came can couldday did do does doing done down
    each even every few finally first for from get got had has have he her here
    him his how i if in into is it its just keep last later let like little look
    made make many maybe me might more most much must my never new next no not
    now of off on once one only or other our out over perhaps put really said
    same saw see she should since so some still such take than that the their
    them then there these they thing think this those though through to today
    tomorrow too took two under until up us very was we well went were what when
    where whether which while who why will with would yesterday yet you your
    """.split()
)

# A run of capitalised words, allowing internal lowercase particles ("of", "the")
# so that "Bank of England" survives as one name.
CAPITALISED_RUN = re.compile(
    r"\b([A-Z][\w’'-]*(?:\s+(?:of|the|de|van|von|and|&)\s+[A-Z][\w’'-]*|\s+[A-Z][\w’'-]*)*)"
)

SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+|\n+")

# Trailing possessives and plurals that would otherwise split one referent into
# two candidates: "Kessler's" and "Kessler".
POSSESSIVE = re.compile(r"[’']s?$")

# Days and months are capitalised without naming a referent worth connecting two
# notes through. Cheap to exclude, and they would otherwise be among the most
# frequent candidates in any dated personal corpus.
CALENDAR_WORDS = frozenset(
    """
    monday tuesday wednesday thursday friday saturday sunday mondays tuesdays
    wednesdays thursdays fridays saturdays sundays january february march april
    may june july august september october november december
    """.split()
)

MIN_LABEL_LENGTH = 2
MAX_LABEL_WORDS = 5


@dataclass(frozen=True)
class ConceptMention:
    """One candidate referent and where in the text it was found.

    The span matters: it is the citation a proposal will show, and the reason a
    person can check a claim against the passage rather than trusting a score.
    """

    label: str
    span_start: int
    span_end: int

    @property
    def normalised(self) -> str:
        return self.label.casefold()


def _plausible_shape(phrase: str) -> bool:
    words = phrase.split()
    return MIN_LABEL_LENGTH <= len(phrase) and len(words) <= MAX_LABEL_WORDS


def extract_concepts(
    text: str, *, known_labels: Collection[str] = ()
) -> list[ConceptMention]:
    """Candidate referents, in order of appearance, deduplicated by label.

    `known_labels` are casefolded labels already established as names elsewhere in
    the corpus. They let the concept layer bootstrap itself: the first note to use
    "Bob" mid-sentence establishes it, and from then on "Bob called today." —
    which is an extremely common note shape and carries no positional evidence at
    all — resolves to the same referent. Without it that note yields nothing.

    Two passes, because position carries most of the signal.

    A capital *mid-sentence* is already evidence of naming — English does not
    capitalise otherwise. A capital at a *sentence start* is evidence of nothing,
    since every sentence begins with one. So a single-word candidate found only at
    sentence starts is kept only when the same word also appears mid-sentence
    somewhere: "Bob called. I rang Bob back." keeps Bob, while "Changed the filter
    today." does not keep Changed.

    That recurrence test replaces an ever-growing list of verbs and adverbs to
    exclude, and it costs one extra pass over candidates already collected. It does
    trade away a referent named exactly once at a sentence start and nowhere else —
    accepted knowingly, because the alternative is a review list flooded with
    "Signed", "Determined", "Finally", which is the failure that makes the concept
    layer unusable rather than merely incomplete.

    Multi-word runs skip the test entirely: two capitalised words in a row are
    rarely an accident of punctuation.

    The first occurrence of each label wins its span. Later ones are dropped rather
    than recorded separately — one node mentioning "Bob" four times names one
    referent, and four mentions would quadruple its apparent weight.
    """
    if not text:
        return []

    # Character offset of each sentence start, so position within a sentence can
    # be judged without losing the offset into the whole text.
    sentence_starts = {0}
    for match in SENTENCE_BREAK.finditer(text):
        sentence_starts.add(match.end())

    runs: list[tuple[str, int, bool]] = []
    # Casefolded tokens that are capitalised for naming reasons somewhere in this
    # text. Word-level rather than run-level, because the question asked of a run's
    # *first* word is whether that particular word is ever a name.
    evidence: set[str] = set()

    for match in CAPITALISED_RUN.finditer(text):
        raw = POSSESSIVE.sub("", match.group(1).strip()).strip()
        if not raw:
            continue
        at_start = match.start() in sentence_starts
        runs.append((raw, match.start(), at_start))

        words = [word.casefold() for word in raw.split()]
        # Words after the first are attested wherever the run sits: a sentence's
        # grammatical capital only reaches its opening word, so anything capitalised
        # behind it is named deliberately. Without this, "The Bank of England …
        # Bank of England …" yields both "Bank of England" and "England" as
        # separate referents, because neither run could attest its own first word.
        evidence.update(words[1:])
        if not at_start:
            evidence.update(words[:1])

    known = {label.casefold() for label in known_labels}
    attested = evidence | known

    found: dict[str, ConceptMention] = {}
    for raw, offset, at_start in runs:
        label, start = raw, offset

        if at_start and raw.split()[0].casefold() not in attested:
            # The first word of a sentence is capitalised for grammatical reasons
            # and carries no evidence of naming anything. Where it has no
            # independent attestation, drop it and keep what follows.
            #
            # This is what makes "Opened MONDLY on the train." yield MONDLY rather
            # than "Opened MONDLY" — a shape common enough to matter, since a great
            # many notes open with a verb and a name ("Called Bob", "Met
            # Marguerite"). Treating two adjacent capitals as necessarily one name
            # gets exactly this case backwards, losing the real referent and
            # inventing a false one.
            label, start = _drop_leading_word(raw, offset)
            if label is None:
                continue

        key = label.casefold()
        if key in found:
            continue
        if not _plausible_shape(label):
            continue
        if " " not in label and (key in SENTENCE_STARTERS or key in CALENDAR_WORDS):
            continue

        # A run that began mid-sentence, or whose leading grammatical word has just
        # been removed, is self-evident. One still sitting at a sentence start needs
        # attestation from elsewhere.
        self_evident = not at_start or label != raw
        if self_evident or key in attested:
            found[key] = ConceptMention(
                label=label, span_start=start, span_end=start + len(label)
            )

    return list(found.values())


def _drop_leading_word(raw: str, offset: int) -> tuple[str | None, int]:
    """Remove a run's first word, and any lowercase particles left leading.

    Stripping "Bank" from "Bank of England" would otherwise leave "of England",
    which is not a name. Removing the particle too yields "England" — a degradation
    rather than an error, and only reached when "Bank" is attested nowhere else in
    the text.
    """
    words = raw.split()
    remainder = words[1:]
    while remainder and remainder[0][:1].islower():
        remainder = remainder[1:]
    if not remainder:
        return None, offset

    label = " ".join(remainder)
    try:
        return label, offset + raw.rindex(label)
    except ValueError:  # whitespace inside the run was not a single space
        return label, offset
