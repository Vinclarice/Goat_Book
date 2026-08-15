"""Dormant thread: "you wrote about this before, and have probably forgotten."

The cheapest useful detector, and the only one of the three named for v1 that
needs nothing which does not already exist. *Shared referent* requires a
populated concept layer, and *Open question answered* keys off an epistemic
status — a facet, which the lab deliberately has none of.

The signal is three conditions together, and the middle one is what makes this
worth surfacing at all:

1. The candidate shares significant terms with what was just captured.
2. It was captured long ago and has not been touched since.
3. It is not already connected to the new note.

**Condition 2 is the non-obviousness proxy.** Recent material the person
remembers; a note from two years ago they do not. Similarity alone would surface
things they would have found by searching — costing attention and returning
nothing. Age is what makes a true connection feel like a discovery rather than a
reminder.

Precision is chosen over recall throughout, because the costs are asymmetric: a
missed connection costs one connection, while a stream of poor ones teaches the
person to skim past the review surface, and no later improvement recovers that.
So: a shared-term floor, a length floor that excludes errands, and a hard cap of
a few proposals per capture.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from django.db.models import Q

from .. import services
from ..models import ConnectionHypothesis, Edge, EventType, HypothesisMember, Node
from ..similarity import Match, SimilarityIndex, default_index

logger = logging.getLogger(__name__)

DETECTOR = "dormant_thread"

# A note has to have been out of mind to be rediscovered. Eighteen months is a
# deliberate starting point rather than a tuned one — long enough that the person
# genuinely will not be holding it in memory.
DEFAULT_MIN_DORMANCY = timedelta(days=548)

# "buy milk" is not a dormant thread. A crude salience floor, but it uses a signal
# already present rather than asking the person to rate their own notes.
DEFAULT_MIN_LENGTH = 120

DEFAULT_MIN_SHARED_TERMS = 3

# The gate that actually works, and the reason this detector is shippable.
#
# Measured against a 46-note corpus with known answers: a score threshold alone
# reached 11% precision at best, and the three highest-scoring pairs in the whole
# corpus were noise — the top one matching on "already, last, year". Requiring
# three shared terms that appear in at most two notes each took precision to 67%
# at three proposals across the corpus.
#
# The trade is recall, deliberately. Two of six known connections are found. The
# four missed are ones stated in different words, which full-text search cannot
# see by construction — a ceiling to record, not a threshold to tune around.
DEFAULT_MIN_DISTINCTIVE_TERMS = 3

# Per capture. Precision beats recall: a handful that mostly land beats thirty
# that mostly do not.
DEFAULT_MAX_PROPOSALS = 3

# Shared terms at which confidence saturates. Confidence is reported, never used
# as a gate on its own — the shared-term count and the terms themselves are the
# signal a person actually reads.
CONFIDENCE_SATURATION = 8


@dataclass(frozen=True)
class Finding:
    """A candidate that passed every filter, with why it did."""

    candidate: Node
    match: Match
    dormant_for: timedelta

    @property
    def confidence(self) -> float:
        return min(1.0, self.match.shared_count / CONFIDENCE_SATURATION)

    def label(self) -> str:
        """Extractive, never generated.

        The distinctive terms *are* the label — the ones appearing in almost no
        other note, since those are what carried the match. v1 ships no
        generative producer and for a term-mediated connection none is needed:
        naming the overlap states the dimension of the connection plainly.
        """
        shown = ", ".join(
            (self.match.distinctive_terms or self.match.shared_terms)[:5]
        )
        return f"shares: {shown}"

    def reason(self) -> str:
        """A fact the person can check, not a score they must trust."""
        months = int(self.dormant_for.days / 30.44)
        distinctive = self.match.distinctive_count
        return (
            f"{distinctive} of {self.match.shared_count} shared terms appear in "
            f"almost none of your other notes; written about {months} months apart"
        )


def _already_connected_ids(node: Node) -> set[int]:
    """Nodes already linked to this one, in either direction.

    A connection the person already made is not a discovery, and proposing it
    would spend attention to tell them something they know.
    """
    pairs = Edge.objects.filter(Q(from_node=node) | Q(to_node=node)).values_list(
        "from_node_id", "to_node_id"
    )
    connected = {end for pair in pairs for end in pair}
    connected.discard(node.pk)
    return connected


def _previously_proposed_ids(node: Node) -> set[int]:
    """Nodes already put forward alongside this one by this detector.

    Includes resolved hypotheses, so a dismissal is permanent here too. The
    fingerprint constraint would collapse the duplicate anyway, but
    `propose_hypothesis` returns the *existing* row in that case — so without
    this filter a re-run would report a dismissed proposal as freshly made, and
    a caller trying to surface it would hit `AlreadyResolved`.

    Two queries deliberately. Chaining `.exclude(members__node=...)` onto a
    queryset already filtered on `members__node` does not mean "the other
    members": each lookup on a multi-valued relation gets its own join, so the
    exclude discards every hypothesis the filter just selected and the result is
    always empty. Resolving the ids first, then filtering members, avoids it.
    """
    hypothesis_ids = ConnectionHypothesis.objects.filter(
        owner=node.owner, detector=DETECTOR, members__node=node
    ).values_list("pk", flat=True)

    return set(
        HypothesisMember.objects.filter(hypothesis_id__in=list(hypothesis_ids))
        .exclude(node=node)
        .values_list("node_id", flat=True)
    )


def find_dormant_threads(
    node: Node,
    *,
    now: datetime,
    index: SimilarityIndex | None = None,
    min_dormancy: timedelta = DEFAULT_MIN_DORMANCY,
    min_length: int = DEFAULT_MIN_LENGTH,
    min_shared_terms: int = DEFAULT_MIN_SHARED_TERMS,
    min_distinctive_terms: int = DEFAULT_MIN_DISTINCTIVE_TERMS,
    limit: int = DEFAULT_MAX_PROPOSALS,
) -> list[Finding]:
    """Candidates worth proposing alongside `node`. Reads only; writes nothing.

    Separated from proposing so that thresholds can be explored against a real
    corpus without writing a single hypothesis — which matters, because tuning
    against live proposals would mean polluting the accept-rate history that is
    the only evidence about whether this detector works.
    """
    index = index or default_index()
    body = node.original_content
    if len(body.strip()) < min_length:
        return []

    # Dormancy is the gap between the two *notes*, not between the candidate and
    # today. The question is whether the person had forgotten the older note when
    # they wrote the newer one, and only the interval between them answers it.
    #
    # For a live capture the two measures coincide, which is why this is easy to
    # get wrong. For imported material they diverge completely: measured against
    # today, every pair of old notes looks dormant, so two notes written eighteen
    # days apart in 2022 would be offered to each other as a rediscovery. Backfill
    # is the main source of material, so that is the common case, not the corner.
    anchor = node.captured_at
    cutoff = anchor - min_dormancy
    excluded = {node.pk} | _already_connected_ids(node) | _previously_proposed_ids(node)

    matches = index.similar_to(
        body,
        owner=node.owner,
        source_node_id=node.pk,
        exclude_node_ids=excluded,
        limit=limit * 8,  # room to lose candidates to the filters below
        min_shared_terms=min_shared_terms,
        min_distinctive_terms=min_distinctive_terms,
    )
    if not matches:
        return []

    candidates = {
        candidate.pk: candidate
        for candidate in Node.objects.filter(
            pk__in=[m.node_id for m in matches], captured_at__lte=cutoff
        )
    }
    if not candidates:
        return []

    # A note being reviewed is not a forgotten one, whatever its age.
    reviewed = set(
        Node.objects.filter(
            pk__in=candidates, events__event_type=EventType.REVIEWED
        ).values_list("pk", flat=True)
    )

    findings: list[Finding] = []
    for match in matches:
        candidate = candidates.get(match.node_id)
        if candidate is None or candidate.pk in reviewed:
            continue
        if len(candidate.original_content.strip()) < min_length:
            continue
        findings.append(
            Finding(
                candidate=candidate,
                match=match,
                dormant_for=anchor - candidate.captured_at,
            )
        )
        if len(findings) >= limit:
            break

    return findings


def propose_dormant_threads(
    node: Node,
    *,
    now: datetime,
    index: SimilarityIndex | None = None,
    actor: str = "system",
    **thresholds,
) -> list[ConnectionHypothesis]:
    """Record each finding as a hypothesis. Nothing is surfaced or promoted here.

    A proposal is not a claim and not an edge — it waits in the review surface,
    and its window does not begin until it is actually shown. Confirming is the
    person's act; this only offers.
    """
    index = index or default_index()
    findings = find_dormant_threads(node, now=now, index=index, **thresholds)

    proposed: list[ConnectionHypothesis] = []
    for finding in findings:
        hypothesis = services.propose_hypothesis(
            node.owner,
            detector=DETECTOR,
            citations=[
                services.Citation(node=node, reason="the note just captured"),
                services.Citation(node=finding.candidate, reason=finding.reason()),
            ],
            confidence=finding.confidence,
            label=finding.label(),
            index_version=getattr(index, "version", "unknown"),
            relation=None,  # confirming makes it relates_to; nothing stronger is claimed
            now=now,
            actor=actor,
        )
        proposed.append(hypothesis)

    if proposed:
        logger.info(
            "dormant_thread proposed %d connection(s) for node %s",
            len(proposed),
            node.pk,
        )
    return proposed
