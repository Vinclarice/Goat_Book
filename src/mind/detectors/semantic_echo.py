"""Semantic echo: "you have said this before, in other words."

The third detector, and the one the shadow evaluation argued for. It exists because
the two shipped before it cannot reach a whole class of connection:

* **dormant_thread** is lexical. It requires shared terms that appear almost nowhere
  else, which is what gives it 67% precision — and which structurally excludes a pair
  whose vocabulary overlaps heavily but unremarkably.
* **shared_referent** needs a confirmed alias. Exact evidence, but silent until the
  person has named something twice and said so.

This one scores a pair by its **best-matching sentence pair**, which is what a real
forgotten connection looks like: one sentence in each note about the same concern,
surrounded by material that has nothing to do with it. Measured, that recovers
`receipts-again ← scanner-jam` — the same scanner failing the same way seven years
apart — which the lexical detector provably cannot reach at any precision-first
threshold.

**Complementary, not a replacement.** At three proposals each, the two indexes reach
the same precision and find *different* pairs; together they cover three of six known
connections rather than two. Whole-document embeddings, by contrast, scored 0%
precision — so this is emphatically not "swap the index for vectors". See
docs/embedding-shadow-evaluation.md.

Optional: without `sentence-transformers` installed there are no vectors, and the
detector reports itself unavailable rather than failing.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from django.db.models import Q

from .. import services
from ..embeddings import INDEX_VERSION, PostgresSentenceIndex, SentenceMatch
from ..models import ConnectionHypothesis, HypothesisMember, Node, SentenceEmbedding
from .dormant_thread import _already_connected_ids, _previously_proposed_ids

logger = logging.getLogger(__name__)

DETECTOR = "semantic_echo"

# Cosine similarity floor, taken from measurement rather than intuition. On the
# evaluation corpus the two genuine pairs scored 0.604 and 0.584 and the first trap
# scored 0.530, so this admits both and excludes it. Tuned on 46 notes, which is thin
# — treat it as a starting point that the per-detector accept rate should move.
DEFAULT_MIN_SCORE = 0.55

# Same reasoning as the lexical detector: recent material the person remembers, older
# material they do not, and the gap is what makes a true connection feel like a
# discovery rather than a reminder.
DEFAULT_MIN_DORMANCY = timedelta(days=548)

DEFAULT_MIN_LENGTH = 120
DEFAULT_MAX_PROPOSALS = 3


class Unavailable(RuntimeError):
    """No vectors exist, so this detector cannot run."""


@dataclass(frozen=True)
class Finding:
    candidate: Node
    match: SentenceMatch
    source: Node
    apart: timedelta

    @property
    def confidence(self) -> float:
        """The cosine, used directly.

        Rescaling it to look more decisive would misrepresent a similarity as a
        certainty. 0.6 means the sentences are close, not that the connection is real —
        which is the person's call, and the reason both sentences are quoted.
        """
        return min(1.0, max(0.0, self.match.score))

    def source_quote(self) -> str:
        start, end = self.match.source_span
        return self.source.original_content[start:end]

    def candidate_quote(self) -> str:
        start, end = self.match.candidate_span
        return self.candidate.original_content[start:end]

    def label(self) -> str:
        """Extractive: a quotation, not a description.

        Still nothing generated. The clearest available statement of what the two
        notes have in common is the sentence itself.
        """
        quote = self.candidate_quote()
        trimmed = quote if len(quote) <= 70 else quote[:69].rstrip() + "…"
        return f"echoes: “{trimmed}”"

    def reason(self) -> str:
        months = int(self.apart.days / 30.44)
        return (
            f"a sentence here closely matches one written about {months} months "
            f"earlier: “{self.candidate_quote()}”"
        )


def available(index_version: str = INDEX_VERSION) -> bool:
    """Whether any vectors exist for this model version."""
    return SentenceEmbedding.objects.filter(index_version=index_version).exists()


def find_semantic_echoes(
    node: Node,
    *,
    now: datetime,
    index: PostgresSentenceIndex | None = None,
    min_score: float = DEFAULT_MIN_SCORE,
    min_dormancy: timedelta = DEFAULT_MIN_DORMANCY,
    min_length: int = DEFAULT_MIN_LENGTH,
    limit: int = DEFAULT_MAX_PROPOSALS,
) -> list[Finding]:
    """Candidates whose best sentence pair clears the threshold. Reads only.

    Raises `Unavailable` when the node has no vectors, rather than returning an empty
    list — an unembedded node and a node with no echoes are different situations, and
    silently conflating them would hide a broken backfill for months.
    """
    index = index or PostgresSentenceIndex()

    if len(node.original_content.strip()) < min_length:
        return []
    if not SentenceEmbedding.objects.filter(
        node=node, index_version=index.index_version
    ).exists():
        raise Unavailable(
            f"node {node.pk} has no sentence vectors for {index.index_version}; "
            "run `manage.py embed_nodes` first"
        )

    # Dormancy is measured between the two notes, never against today — for imported
    # material those diverge completely, and every pair of old notes would look
    # dormant. Same correction as in dormant_thread.
    anchor = node.captured_at
    cutoff = anchor - min_dormancy
    excluded = (
        {node.pk}
        | _already_connected_ids(node)
        | _previously_proposed_ids(node, DETECTOR)
    )

    matches = index.similar_to(
        node,
        owner=node.owner,
        exclude_node_ids=excluded,
        limit=limit * 8,
        min_score=min_score,
    )
    if not matches:
        return []

    candidates = {
        candidate.pk: candidate
        for candidate in Node.objects.filter(
            pk__in=[m.node_id for m in matches], captured_at__lte=cutoff
        )
    }

    findings: list[Finding] = []
    for match in matches:
        candidate = candidates.get(match.node_id)
        if candidate is None:
            continue
        if len(candidate.original_content.strip()) < min_length:
            continue
        findings.append(
            Finding(
                candidate=candidate,
                match=match,
                source=node,
                apart=anchor - candidate.captured_at,
            )
        )
        if len(findings) >= limit:
            break
    return findings


def propose_semantic_echoes(
    node: Node,
    *,
    now: datetime,
    index: PostgresSentenceIndex | None = None,
    actor: str = "system",
    **thresholds,
) -> list[ConnectionHypothesis]:
    """Record each finding as a hypothesis. Nothing is surfaced or promoted here."""
    index = index or PostgresSentenceIndex()
    findings = find_semantic_echoes(node, now=now, index=index, **thresholds)

    proposed: list[ConnectionHypothesis] = []
    for finding in findings:
        proposed.append(
            services.propose_hypothesis(
                node.owner,
                detector=DETECTOR,
                citations=[
                    services.Citation(
                        node=node,
                        span=finding.match.source_span,
                        reason="the sentence just captured",
                    ),
                    services.Citation(
                        node=finding.candidate,
                        span=finding.match.candidate_span,
                        reason=finding.reason(),
                    ),
                ],
                confidence=finding.confidence,
                label=finding.label(),
                index_version=finding.match.index_version,
                relation=None,
                now=now,
                actor=actor,
            )
        )

    if proposed:
        logger.info(
            "semantic_echo proposed %d connection(s) for node %s", len(proposed), node.pk
        )
    return proposed
