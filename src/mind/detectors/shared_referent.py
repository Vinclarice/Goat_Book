"""Shared referent: "these describe the same thing, named differently."

Not a similarity finding — a **resolution** finding. Two notes connect *through* a
referent rather than through their wording, which is why this can see what
full-text search cannot: the neighbour described once as "the woman in 4B who
played in a French orchestra" and later as "Marguerite from upstairs" shares almost
no vocabulary between the two notes. Measured, that pair was one of four the
dormant-thread detector missed, and it is missed by construction rather than by
tuning.

**The gate is that the labels differ.** Two notes both saying "Bob" are findable by
searching for Bob; proposing that pair spends attention to report something already
retrievable. The discovery is when *different* descriptions turn out to name one
thing — and the only way to know they do is that the person said so once, by
confirming the alias.

That gives this detector a property the lexical one cannot have: its evidence is
**exact**. A confirmed alias is not a guess with a score attached, so precision
comes from the architecture rather than from a threshold. The cost is that it
cannot fire before the person has done the confirming, which is a real dependency
on their participation and not a hidden one.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from django.db.models import Q

from .. import services
from ..models import ConceptCandidate, ConnectionHypothesis, Edge, Mention, Node
from .dormant_thread import _already_connected_ids

logger = logging.getLogger(__name__)

DETECTOR = "shared_referent"

# The evidence is exact — a confirmed alias, and confirmed mentions at both ends —
# so the only inference left is that a shared referent is worth connecting through.
# High, but not 1.0: certainty about the referent is not certainty that the person
# wants the link.
DEFAULT_CONFIDENCE = 0.9

# Zero, and the parameter is kept so a gap can be reintroduced on evidence rather
# than by editing this file.
#
# It was thirty days, on the reasoning that two notes from one sitting are not a
# discovery. That reasoning was already contradicted two paragraphs up: this
# detector's non-obviousness comes from the descriptions *differing*, not from
# elapsed time, and the gate that enforces it is the label check rather than this.
#
# The floor also made the detector silent on the one corpus a new person actually
# has. A brain dump is one sitting by definition, and cold-start.md turns on this
# being the detector that can fire earliest -- its evidence is a confirmed alias,
# so it needs a person's participation but no accumulated history at all. Thirty
# days of nothing is a poor first impression from the only mechanic available in
# week one.
#
# Nothing about the evidence is weaker without it. The alias is still confirmed,
# both mentions are still confirmed, and two notes describing one person in two
# ways is a connection the person did not record, whether they wrote them a minute
# or a decade apart.
DEFAULT_MIN_GAP = timedelta(0)

DEFAULT_MAX_PROPOSALS = 3


@dataclass(frozen=True)
class Finding:
    """A candidate reached through a named referent."""

    candidate: Node
    concept: ConceptCandidate
    source_label: str
    candidate_label: str
    apart: timedelta

    def label(self) -> str:
        return f"both about {self.concept.label}"

    def reason(self) -> str:
        """States the resolution, which is the whole evidence.

        A person can check this in one glance: they either agree the two
        descriptions name one thing or they do not, and they already said they do.
        """
        months = int(self.apart.days / 30.44)
        return (
            f"names {self.concept.label} as {self.candidate_label!r}, where the "
            f"other calls it {self.source_label!r}; about {months} months apart"
        )


def _canonical(concept: ConceptCandidate) -> ConceptCandidate:
    return concept.merged_into or concept


def find_shared_referents(
    node: Node,
    *,
    now: datetime,
    min_gap: timedelta = DEFAULT_MIN_GAP,
    limit: int = DEFAULT_MAX_PROPOSALS,
) -> list[Finding]:
    """Notes reaching the same referent under a different name. Reads only.

    Only **confirmed** mentions count, at both ends. An unconfirmed extraction is
    the system's own guess, and letting one guess justify a proposal is how a
    classifier starts feeding on its output with no way back.
    """
    source_mentions = list(
        Mention.objects.filter(
            node=node, confirmed_at__isnull=False
        ).select_related("concept", "concept__merged_into")
    )
    if not source_mentions:
        return []

    excluded = {node.pk} | _already_connected_ids(node) | _previously_proposed_ids(node)

    findings: list[Finding] = []
    seen_nodes: set[int] = set()

    for mention in source_mentions:
        canonical = _canonical(mention.concept)

        others = (
            Mention.objects.filter(
                Q(concept=canonical) | Q(concept__merged_into=canonical),
                confirmed_at__isnull=False,
                node__deleted_at__isnull=True,
                node__archived_at__isnull=True,
            )
            # The gate: a *different* concept row means a different label, which is
            # what makes the connection non-obvious. Two notes both saying "Bob"
            # are already findable by searching for Bob.
            .exclude(concept=mention.concept)
            .exclude(node_id__in=excluded)
            .select_related("node", "concept")
            .order_by("node__captured_at")
        )

        for other in others:
            if other.node_id in seen_nodes:
                continue
            apart = abs(node.captured_at - other.node.captured_at)
            if apart < min_gap:
                continue

            seen_nodes.add(other.node_id)
            findings.append(
                Finding(
                    candidate=other.node,
                    concept=canonical,
                    source_label=mention.concept.label,
                    candidate_label=other.concept.label,
                    apart=apart,
                )
            )
            if len(findings) >= limit:
                return findings

    return findings


def _previously_proposed_ids(node: Node) -> set[int]:
    """Nodes already put forward alongside this one by this detector.

    Two queries rather than a chained exclude, for the same reason as in
    dormant_thread: each lookup on a multi-valued relation gets its own join, so
    `.filter(members__node=n).exclude(members__node=n)` discards everything the
    filter selected and quietly returns nothing.
    """
    from ..models import HypothesisMember

    hypothesis_ids = ConnectionHypothesis.objects.filter(
        owner=node.owner, detector=DETECTOR, members__node=node
    ).values_list("pk", flat=True)

    return set(
        HypothesisMember.objects.filter(hypothesis_id__in=list(hypothesis_ids))
        .exclude(node=node)
        .values_list("node_id", flat=True)
    )


def propose_shared_referents(
    node: Node,
    *,
    now: datetime,
    actor: str = "system",
    **thresholds,
) -> list[ConnectionHypothesis]:
    """Record each finding as a hypothesis. Nothing is surfaced or promoted here."""
    findings = find_shared_referents(node, now=now, **thresholds)

    proposed: list[ConnectionHypothesis] = []
    for finding in findings:
        proposed.append(
            services.propose_hypothesis(
                node.owner,
                detector=DETECTOR,
                citations=[
                    services.Citation(node=node, reason="the note just captured"),
                    services.Citation(node=finding.candidate, reason=finding.reason()),
                ],
                confidence=DEFAULT_CONFIDENCE,
                label=finding.label(),
                index_version="concepts-v1",
                concept=finding.concept,
                relation=None,
                now=now,
                actor=actor,
            )
        )

    if proposed:
        logger.info(
            "shared_referent proposed %d connection(s) for node %s",
            len(proposed),
            node.pk,
        )
    return proposed
