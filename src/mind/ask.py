"""Asking your memory a question — Track E increment 22, the last of the track.

**Declined on August 21 and built the same evening**, and both were right. On
nothing, this box is `search_ranked` with a prompt in front of it: one blended
ordering, unable to say where an answer came from, **failing silently** — which
is the property that makes a thin version worth refusing rather than shipping.
Once Track B's 7–9 and Recollection existed, the objection stopped applying.

Three things, all of them the plan's words:

**Extractive.** An answer is a sentence the person wrote, lifted with its
offsets from the note that holds it. **Nothing here generates, summarises or
paraphrases anything.** A second mind that writes new prose about your life is
one you have to fact-check, and then the store's whole value — that it holds
what you actually said — is gone.

**Cited.** Every passage names its note and carries the explanation the
retrieval pipeline gave for reaching it. Without that a person cannot argue
with an answer, only distrust it.

**Per-mode**, decided by **an enumerable rule and not a classifier**. Part 2's
instinct is *predicates before ranking*: a rule can be read, argued with and
corrected, where a score can only be believed. A question about *when* or *what
else* is a Recollection anchored on the best Lookup hit; everything else is a
Lookup. The page says which fired, so a wrong choice is visible.

**It can say it does not know**, which is the failure a question box invites:
an answer assembled from nothing looks exactly like an answer.
"""

from dataclasses import dataclass, field

from clarice.search import to_question_query

from . import queries, retrieval
from .models import Node
from .services import _sentences


#: Words that make a question about *the moment* rather than *the fact*.
#:
#: Deliberately small and readable. This is the whole mode-selection rule, and
#: it is meant to be arguable — somebody who disagrees can see exactly what
#: fired and say so, which is not true of a classifier that scores 0.61.
#:
#: The cost of being wrong is bounded in both directions: a Lookup misread as a
#: Recollection returns the note *and* its surroundings, and a Recollection
#: misread as a Lookup returns the note alone. Neither invents anything.
RECOLLECTION_CUES = (
    "what else",
    "what was going on",
    "when i wrote",
    "when did i write",
    "around the time",
    "that morning",
    "that day",
)

#: How many passages an answer carries. Small on purpose: a question box that
#: returns thirty passages has answered nothing and handed back a search.
DEFAULT_PASSAGES = 5


@dataclass(frozen=True)
class Passage:
    """One sentence the person wrote, and where it came from.

    ``start`` and ``end`` are offsets into the note's current body, so a
    surface can show the sentence in place rather than out of it.
    """

    node: Node
    text: str
    start: int
    end: int
    #: The retrieval pipeline's explanation for reaching this note at all —
    #: increment 9, carried through rather than restated.
    why: str
    #: Whether this note was reached through wording its author edited away.
    #: `original_content` is never mutated, so finding it is the design
    #: working — but the passage then does not contain the word asked about,
    #: which is baffling rather than wrong unless the page says which version
    #: matched. The search page has labelled this since August 20.
    from_earlier_wording: bool = False


@dataclass(frozen=True)
class Answer:
    """What memory had to say, and how it decided to look."""

    question: str
    mode: retrieval.Mode
    #: Why this mode and not another, in words. The rule is arguable only if
    #: the page can say which part of it fired.
    why_this_mode: str
    passages: list[Passage] = field(default_factory=list)

    @property
    def found_anything(self):
        return bool(self.passages)


def _wants_recollection(question):
    lowered = question.lower()
    return any(cue in lowered for cue in RECOLLECTION_CUES)


#: Words that carry no subject, stripped when working out what to anchor on.
#: Short and readable for the same reason `RECOLLECTION_CUES` is: this is a
#: rule somebody should be able to disagree with precisely.
_NOT_A_SUBJECT = frozenset(
    """
    what else was going on when i wrote about around the time that day
    morning did my me a an the of is are and or to in on at it this
    """.split()
)


def _content_words(question):
    """The question with its scaffolding removed.

    **A question box that only works when you type keywords is a search box
    with a longer placeholder.** *"What did I say about the venue"* went to the
    full-text index verbatim, which ANDs its terms — so no note contained
    *what* and *did* and *say*, and the page replied that nothing answered it
    with the answer two lines away. Found by opening the page, not by a test.

    Returns empty when nothing survives, which is not the same as an answer
    being absent and is reported differently.
    """
    return " ".join(
        word
        for word in question.strip(" ?.,").split()
        if word.lower().strip(" ?.,") not in _NOT_A_SUBJECT
    )


def _subject_of(question):
    """The part of a recollection question that names what to anchor on.

    *"what else was going on when I wrote about the caterer"* anchors on
    *caterer*. **Two rules, in order, and both readable**:

    1. Everything after the last *about*, which is how these questions are
       actually phrased.
    2. Otherwise, the words left once the cue and the filler are removed.

    Not parsed. A question box that needed grammar would fail on the way
    people type, and the cost of getting this wrong is bounded: a bad subject
    finds no anchor, and `answer` then says so rather than guessing.
    """
    lowered = question.lower()
    if " about " in lowered:
        return question[lowered.rfind(" about ") + len(" about ") :].strip(" ?.,")

    # Empty when nothing is left, rather than falling back to the whole
    # question. *"What else was going on that morning"* names no subject, and
    # saying so lets `answer` reply that there is nothing to anchor on --
    # which is true, where a query of the whole sentence would find nothing
    # and look like a failed search.
    return _content_words(question)


def _passages_from(node, terms, why, *, limit, matched_current=True):
    """Sentences of ``node`` that carry any of ``terms``, in written order.

    **Falls back to the opening sentence** when nothing matches, which is the
    case that matters: a note reached through a confirmed concept need not
    contain the typed word at all, and returning it with nothing to show would
    make the concept index look broken.
    """
    body = queries.current_body(node)
    wanted = [t for t in terms if t]
    found = []
    for start, end, text in _sentences(body):
        lowered = text.lower()
        if any(term in lowered for term in wanted):
            found.append(
                Passage(
                    node=node,
                    text=text,
                    start=start,
                    end=end,
                    why=why,
                    from_earlier_wording=not matched_current,
                )
            )
        if len(found) >= limit:
            break
    if found:
        return found
    for start, end, text in _sentences(body):
        return [
            Passage(
                node=node,
                text=text,
                start=start,
                end=end,
                why=why,
                from_earlier_wording=not matched_current,
            )
        ]
    return []


def answer(owner, question, *, limit=DEFAULT_PASSAGES):
    """What memory has to say about ``question``.

    Lookup unless the question asks about a moment, in which case the best
    Lookup hit becomes the anchor for a Recollection. **Two retrievals rather
    than one clever one**: finding the note and restoring what surrounded it
    are different questions, and the pipeline already answers each.
    """
    question = (question or "").strip()
    if not question:
        return Answer(
            question=question,
            mode=retrieval.Mode.LOOKUP,
            why_this_mode="there was no question",
        )

    # What a passage has to contain to be worth quoting. Drawn from the
    # content words for the same reason the query is: *did* and *say* appear in
    # half of everything.
    terms = [
        word.lower()
        for word in _content_words(question).split()
        if len(word) > 2
    ]

    if not _wants_recollection(question):
        # The content words, not the sentence. The scaffolding of a question is
        # not part of what is being asked, and the full-text index ANDs
        # whatever it is given.
        asked = _content_words(question)
        results = (
            retrieval.retrieve(
                retrieval.Moment(
                    owner=owner,
                    mode=retrieval.Mode.LOOKUP,
                    text=asked,
                    text_is_a_question=True,
                )
            )
            if asked
            else []
        )
        current = queries.current_text_matches(
            [r.node for r in results], to_question_query(asked)
        ) if results else set()
        passages = []
        for result in results:
            passages.extend(
                _passages_from(
                    result.node,
                    terms,
                    result.why,
                    limit=limit,
                    matched_current=result.node.pk in current,
                )
            )
        return Answer(
            question=question,
            mode=retrieval.Mode.LOOKUP,
            why_this_mode="you asked what something is, so I looked it up",
            passages=passages[:limit],
        )

    subject = _subject_of(question)
    anchors = retrieval.retrieve(
        retrieval.Moment(
            owner=owner,
            mode=retrieval.Mode.LOOKUP,
            text=subject,
            text_is_a_question=True,
        )
    )
    if not anchors:
        # **Said rather than quietly answered another way.** A recollection
        # question with no note to recollect around has no honest answer, and
        # falling back to a Lookup of the same words would return nothing while
        # looking like it had tried something else.
        return Answer(
            question=question,
            mode=retrieval.Mode.RECOLLECTION,
            why_this_mode=(
                f"you asked what was going on, but there is nothing to anchor "
                f"on — no note matches {subject!r}"
            ),
        )

    anchor = anchors[0].node
    around = retrieval.retrieve(
        retrieval.Moment(
            owner=owner, mode=retrieval.Mode.RECOLLECTION, anchor=anchor
        )
    )
    passages = []
    for result in around:
        passages.extend(_passages_from(result.node, terms, result.why, limit=limit))
    return Answer(
        question=question,
        mode=retrieval.Mode.RECOLLECTION,
        why_this_mode=(
            "you asked what was going on, so I found the note and looked "
            "around it"
        ),
        passages=passages[:limit],
    )
