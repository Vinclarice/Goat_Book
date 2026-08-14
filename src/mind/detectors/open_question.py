"""Open question answered: "you asked this in April; this looks like an answer."

The second detector that works from a cold start, and the cheapest evidence this
project can produce in week one. A brain dump is mostly unresolved questions, and
ordinary capture over the following days supplies the answers — so this fires on
a corpus days old, where every retrospective detector needs one that is months
old (`cold-start.md`).

**It reads question-shaped text, not a facet.** The design document's stated
signal is a node's `question` epistemic status, and the lab has no facet table.
Rather than block on one, the shape of the sentence stands in: rule-based and
deterministic, the same side of the line concept extraction sits on.

The cost is real and is a substitution to revisit, not a final answer. A question
phrased as a statement — "no idea whether the tutor takes evenings" — is
invisible to this, and a rhetorical question is a false positive. A facet would
be exact where this is a heuristic, and the moment facets exist this should read
one instead.

**Direction is the finding, which is why the relation is typed.** An answer
arrives after its question, and a detector indifferent to that would propose the
question as an answer to itself about half the time. `answers` carries which way
round the pair goes; `relates_to` would throw exactly that away, and the
direction is the whole content here.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta

from .. import queries, services
from ..models import ConnectionHypothesis, EdgeRelation, Node
from ..similarity import SimilarityIndex, default_index
from .dormant_thread import _already_connected_ids, _previously_proposed_ids

logger = logging.getLogger(__name__)

DETECTOR = "open_question"

# Only has to clear the sitting, not the memory. Dormancy needs a long gap
# because elapsed time is the only thing making an old note non-obvious; here
# the person labelled a question and later wrote something that resolves it,
# which is a fact about their material rather than about their recall. A
# question asked and answered in one sitting is one thought, and that is all this
# is excluding -- which is what keeps the detector usable in week one.
DEFAULT_MIN_GAP = timedelta(days=1)

DEFAULT_MIN_SHARED_TERMS = 2

# The evidence is a heuristic about sentence shape plus lexical overlap, so this
# sits well below shared_referent's 0.9, whose evidence is an exact confirmation.
DEFAULT_CONFIDENCE = 0.55

DEFAULT_MAX_PROPOSALS = 3

# Words that open a question when they open the sentence. Deliberately short and
# deliberately not a parser: over-matching here costs a proposal somebody
# dismisses, and the alternative is a dependency this project has refused.
_OPENERS = frozenset(
    """
    am are can could did do does had has have is may might should was were
    what when where which who whom whose why will would
    """.split()
)

# "wondering whether", "no idea if" -- a question wearing a statement's clothes,
# common enough in a capture stream to be worth the two patterns.
_HEDGES = re.compile(r"\b(wondering|not sure|unsure|no idea)\b", re.IGNORECASE)

_FIRST_WORD = re.compile(r"[a-z']+", re.IGNORECASE)


def looks_like_a_question(text: str) -> bool:
    """Whether a note reads as asking something.

    Three signals, in the order they are trusted. A trailing question mark is
    the strongest and is checked against the *last* character rather than
    anywhere in the note, because "Bought the book called Why Nations Fail? and
    started it" contains one and asks nothing. An interrogative opener catches
    the common unpunctuated case, which a capture stream is full of. A hedge
    catches the question worn as a statement.
    """
    stripped = text.strip()
    if not stripped:
        return False

    if stripped.endswith("?"):
        return True

    opener = _FIRST_WORD.match(stripped)
    if opener and opener.group(0).lower() in _OPENERS:
        return True

    return bool(_HEDGES.search(stripped))


@dataclass(frozen=True)
class Answered:
    """An earlier question this note may resolve."""

    question: Node
    shared_terms: tuple[str, ...]

    def reason(self) -> str:
        return "asked " + ", ".join(self.shared_terms) + " — this looks like an answer"

    def label(self) -> str:
        return self.question.original_content.strip()[:60]


def find_open_questions(
    node: Node,
    *,
    now: datetime,
    index: SimilarityIndex | None = None,
    min_gap: timedelta = DEFAULT_MIN_GAP,
    min_shared_terms: int = DEFAULT_MIN_SHARED_TERMS,
    limit: int = DEFAULT_MAX_PROPOSALS,
) -> list[Answered]:
    """Earlier questions this note looks like an answer to. Writes nothing."""
    index = index or default_index()

    body = queries.current_body(node)
    # A question is not an answer to another question. Asking the same thing
    # twice is a recurrence, which is a different finding and a different thing
    # to say about it.
    if looks_like_a_question(body):
        return []

    excluded = {node.pk} | _already_connected_ids(node) | _previously_proposed_ids(node)
    matches = index.similar_to(
        body,
        owner=node.owner,
        source_node_id=node.pk,
        exclude_node_ids=excluded,
        limit=limit * 8,  # room to lose candidates to the filters below
        min_shared_terms=min_shared_terms,
    )
    if not matches:
        return []

    # Strictly earlier, by at least the gap. An answer cannot precede its
    # question, and this is the filter that makes the typed relation honest.
    cutoff = node.captured_at - min_gap
    candidates = {
        candidate.pk: candidate
        for candidate in queries.live_nodes(node.owner).filter(
            pk__in=[m.node_id for m in matches], captured_at__lte=cutoff
        )
    }

    found: list[Answered] = []
    for match in matches:
        candidate = candidates.get(match.node_id)
        if candidate is None or not looks_like_a_question(
            queries.current_body(candidate)
        ):
            continue
        found.append(
            Answered(question=candidate, shared_terms=tuple(match.shared_terms))
        )
        if len(found) == limit:
            break
    return found


def propose_open_questions(
    node: Node,
    *,
    now: datetime,
    actor: str = "system",
    **thresholds,
) -> list[ConnectionHypothesis]:
    """Record each finding as a hypothesis. Nothing is surfaced or promoted here."""
    proposed: list[ConnectionHypothesis] = []
    for finding in find_open_questions(node, now=now, **thresholds):
        proposed.append(
            services.propose_hypothesis(
                node.owner,
                detector=DETECTOR,
                citations=[
                    services.Citation(node=node, reason="the note just captured"),
                    services.Citation(node=finding.question, reason=finding.reason()),
                ],
                confidence=DEFAULT_CONFIDENCE,
                label=finding.label(),
                index_version="fts-v1",
                relation=EdgeRelation.ANSWERS,
                now=now,
                actor=actor,
            )
        )

    if proposed:
        logger.info(
            "open_question proposed %d answer(s) for node %s", len(proposed), node.pk
        )
    return proposed
