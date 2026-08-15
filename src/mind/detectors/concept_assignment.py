"""Concept assignment: "this looks like it is about Indonesian."

The accretive mechanic. Every other detector here answers *what did you forget*,
which needs a corpus that is both large and old — so from a cold start they are
silent for months (`cold-start.md`). This one answers *what is this about*, which
is answerable from the fourth note, and it is what lets the concept layer grow
without a person naming every note by hand.

**Anchored, not pairwise.** One end is a confirmed concept — a decision somebody
actually made — so this is not two uncertain things being guessed at.
`precision.md` calls that the tier-2 shape: the anchor does the precision work
and a rarity test does the rest.

That anchoring is also why this is better conditioned than the whole-document
similarity the shadow evaluation measured at **0% precision**. The failure there
was register: two same-register personal notes mostly report that they are both
first-person prose. A profile aggregated from several confirmed notes has
something to be similar *to*, and a term has to survive appearing in more than
one of them.

What it produces is an unconfirmed `Mention` — a proposal, soft-applied and
dismissible. Never an edge, never a hypothesis, and never something the matcher
may then read back as ground truth: `queries.confirmed_concepts` is what enforces
that, and it is the rule that stops a classifier feeding on its own guesses.
"""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass
from datetime import datetime

from .. import queries, services
from ..models import ConceptCandidate, Mention, Node
from ..similarity import SimilarityIndex, default_index

logger = logging.getLogger(__name__)

DETECTOR = "concept_assignment"

# A profile built from one note *is* that note, so matching against it would be
# ordinary pairwise similarity wearing a better name. The anchor's whole value is
# that it aggregates confirmed material, and two is the smallest number that
# aggregates anything.
DEFAULT_MIN_MEMBERS = 2

# How many of a concept's members a term must appear in before it counts toward
# the profile. Two, for the same reason: a word from a single member is that
# member's vocabulary, not the concept's, and letting it through is how a profile
# turns back into a note.
DEFAULT_MIN_MEMBER_SUPPORT = 2

# Shared terms needed to propose. The anchor supplies most of the precision here,
# but one word in common is a coincidence at any corpus size.
DEFAULT_MIN_SHARED_TERMS = 2

# Precision beats recall, and this runs on every capture. A handful of proposals
# that mostly land beats thirty that mostly do not.
DEFAULT_MAX_PROPOSALS = 3

# Stamped on every mention this proposes, so a later change to the profile rule
# is distinguishable from what the current one produced -- the same reason the
# embedding index carries a model version.
INDEX_VERSION = "concept-profile-v1"


@dataclass(frozen=True)
class Assignment:
    """A concept this note may be about, and why."""

    concept: ConceptCandidate
    shared_terms: tuple[str, ...]
    member_count: int

    @property
    def reason(self) -> str:
        """The words that matched, named so the claim can be disagreed with.

        "Similar to Indonesian" asks somebody to take the system's word for it.
        Naming the terms lets them read the sentence and say no, which is the
        difference between a proposal and an assertion.
        """
        words = ", ".join(self.shared_terms)
        return (
            f"shares {words} with the {self.member_count} notes "
            f"about {self.concept.label}"
        )


def _profile(
    concept: ConceptCandidate,
    *,
    owner,
    index: SimilarityIndex,
    min_support: int,
) -> tuple[set[str], int]:
    """The vocabulary a concept's confirmed notes have in common.

    Built from `significant_terms`, so the personal stop words a corpus develops
    -- "think", "want", "today" -- are already gone before anything is counted.
    """
    members = list(queries.nodes_mentioning(owner, concept))
    if len(members) < DEFAULT_MIN_MEMBERS:
        return set(), len(members)

    counts: Counter[str] = Counter()
    for member in members:
        counts.update(
            set(
                index.significant_terms(
                    queries.current_body(member), owner=owner, exclude_node_id=member.pk
                )
            )
        )
    return {term for term, seen in counts.items() if seen >= min_support}, len(members)


def find_concept_assignments(
    node: Node,
    *,
    now: datetime,
    index: SimilarityIndex | None = None,
    min_shared_terms: int = DEFAULT_MIN_SHARED_TERMS,
    min_member_support: int = DEFAULT_MIN_MEMBER_SUPPORT,
    limit: int = DEFAULT_MAX_PROPOSALS,
) -> list[Assignment]:
    """Which confirmed concepts this note looks like it is about. Writes nothing.

    `now` is unused today and taken anyway, so every detector is called the same
    way and adding a recency term later is not a signature change rippling
    through the runner.
    """
    index = index or default_index()
    owner = node.owner

    terms = set(
        index.significant_terms(
            queries.current_body(node), owner=owner, exclude_node_id=node.pk
        )
    )
    if not terms:
        return []

    # Already recorded, by extraction or by hand. Proposing it again spends
    # attention to report something the note already says.
    already = set(
        Mention.objects.filter(node=node).values_list("concept_id", flat=True)
    )

    found: list[Assignment] = []
    for concept in queries.confirmed_concepts(owner):
        if concept.pk in already:
            continue

        profile, member_count = _profile(
            concept, owner=owner, index=index, min_support=min_member_support
        )
        shared = terms & profile
        if len(shared) < min_shared_terms:
            continue

        found.append(
            Assignment(
                concept=concept,
                shared_terms=tuple(sorted(shared)),
                member_count=member_count,
            )
        )

    # Most shared vocabulary first, then by label so a tie does not vary between
    # runs and produce different proposals for the same note.
    found.sort(key=lambda a: (-len(a.shared_terms), a.concept.label))
    return found[:limit]


def propose_concept_assignments(
    node: Node,
    *,
    now: datetime,
    actor: str = "system",
    index: SimilarityIndex | None = None,
    **kwargs,
) -> list[Mention]:
    """Record each assignment as an unconfirmed mention.

    Through `services.propose_mention` rather than by writing rows here, so the
    provenance columns and the log entry are the same ones every other proposal
    gets.

    A second run over the same note proposes nothing, because `find` skips a
    concept the note already mentions -- which matters, since this is meant to
    run after every batch of captures. That is the same filter that stops
    extraction's own findings being re-proposed, doing double duty rather than
    a separate idempotency guard.
    """
    recorded = []
    for assignment in find_concept_assignments(node, now=now, index=index, **kwargs):
        recorded.append(
            services.propose_mention(
                node,
                assignment.concept,
                now=now,
                actor=actor,
                reason=assignment.reason,
                index_version=INDEX_VERSION,
            )
        )
    return recorded
