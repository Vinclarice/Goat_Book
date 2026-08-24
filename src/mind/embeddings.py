"""Sentence embeddings: the encoder, and the index detectors ask through.

**Optional by design.** `sentence-transformers` pulls in torch, which is a very large
dependency for one detector, so the application must run without it — capture, the
lexical detector, import and the review surface are all unaffected. Everything here
raises `EncoderUnavailable` with a usable message rather than failing at import, and
the detector that needs it reports itself unavailable instead of crashing.

    ./.venv/Scripts/python.exe -m pip install -r requirements-embeddings.txt

**Local, and the only ML dependency.** Per the ML policy: self-hosted, deterministic
for a given model version, no external call, no per-use cost, nothing generative. A
vector is not a claim — it ranks candidates, and the person still reads the two
sentences and decides.

Encoding never happens on the capture path. It runs in the same asynchronous position
as index generation, so a lost model file or a slow machine can never cost a thought.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

from django.db import connection

from .models import Node, SentenceEmbedding

DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

# Stamped on every stored vector. Changing the model changes this, which turns an
# upgrade into a visible re-embedding migration instead of a silent shift in what
# "similar" meant when a suggestion was recorded.
INDEX_VERSION = "st-all-MiniLM-L6-v2"

SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+|\n+")

# Short fragments carry little and match everything. A floor here is also the cheapest
# guard against the known weakness of max-pooling — one broad sentence becoming the
# best match for half the corpus.
MIN_SENTENCE_CHARS = 25


class EncoderUnavailable(RuntimeError):
    """The optional embedding dependency is not installed."""


@dataclass(frozen=True)
class Sentence:
    seq: int
    text: str
    span_start: int
    span_end: int


def split_sentences(text: str) -> list[Sentence]:
    """Sentences with their offsets into the original text.

    Offsets are tracked rather than recomputed, because they become the citation a
    person reads. A sentence found by searching for its own text would land on the
    wrong occurrence whenever a note repeats a phrase.
    """
    if not text or not text.strip():
        return []

    found: list[Sentence] = []
    cursor = 0
    seq = 0
    for piece in SENTENCE_BREAK.split(text):
        start = text.find(piece, cursor) if piece else cursor
        if start == -1:
            start = cursor
        cursor = start + len(piece)
        stripped = piece.strip()
        if len(stripped) < MIN_SENTENCE_CHARS:
            continue
        offset = start + piece.index(stripped) if stripped in piece else start
        found.append(
            Sentence(
                seq=seq,
                text=stripped,
                span_start=offset,
                span_end=offset + len(stripped),
            )
        )
        seq += 1

    # A note that is one long fragment still deserves a vector.
    if not found and text.strip():
        stripped = text.strip()
        offset = text.index(stripped)
        found.append(
            Sentence(seq=0, text=stripped, span_start=offset, span_end=offset + len(stripped))
        )
    return found


@lru_cache(maxsize=2)
def _load_model(model_name: str):
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:  # pragma: no cover - depends on the environment
        raise EncoderUnavailable(
            "sentence-transformers is not installed. It is optional: install it with "
            "`pip install -r requirements-embeddings.txt` to enable the semantic-echo "
            "detector. Everything else works without it."
        ) from exc
    return SentenceTransformer(model_name)


def encoder_available(model_name: str = DEFAULT_MODEL) -> bool:
    """Whether the optional dependency and model are present.

    Used to report a detector as unavailable rather than let it raise from inside a
    batch job.
    """
    try:
        _load_model(model_name)
    except Exception:
        return False
    return True


def encode(texts: list[str], *, model_name: str = DEFAULT_MODEL):
    """Unit-normalised vectors, so a dot product *is* cosine similarity."""
    if not texts:
        return []
    model = _load_model(model_name)
    return model.encode(texts, normalize_embeddings=True, show_progress_bar=False)


def embed_node(
    node: Node, *, model_name: str = DEFAULT_MODEL, index_version: str = INDEX_VERSION
) -> int:
    """Store one vector per sentence of a node. Returns how many were written.

    Idempotent per model version: re-running replaces this node's rows for that
    version rather than accumulating duplicates, so a partial backfill can simply be
    run again.
    """
    sentences = split_sentences(node.original_content)
    if not sentences:
        return 0

    vectors = encode([s.text for s in sentences], model_name=model_name)

    SentenceEmbedding.objects.filter(node=node, index_version=index_version).delete()
    SentenceEmbedding.objects.bulk_create(
        [
            SentenceEmbedding(
                node=node,
                seq=sentence.seq,
                span_start=sentence.span_start,
                span_end=sentence.span_end,
                embedding=list(vector),
                index_version=index_version,
            )
            for sentence, vector in zip(sentences, vectors)
        ]
    )
    return len(sentences)


@dataclass(frozen=True)
class SentenceMatch:
    """One candidate, and the sentence pair that matched.

    A distinct shape from the lexical `Match`, deliberately. Forcing both through one
    result type would mean either discarding the span citations — the strongest part of
    this evidence — or padding the lexical match with fields it can never fill.
    """

    node_id: int
    score: float
    source_span: tuple[int, int]
    candidate_span: tuple[int, int]
    index_version: str

    def quote(self, node: Node) -> str:
        body = node.original_content
        return body[self.candidate_span[0] : self.candidate_span[1]]


class PostgresSentenceIndex:
    """Nearest sentences by cosine distance, via pgvector.

    The maximum over sentence pairs, computed in the database rather than by pulling
    vectors into Python: at a few thousand notes that is tens of thousands of vectors,
    and the HNSW index exists precisely so this stays a query.
    """

    version = INDEX_VERSION

    def __init__(self, *, index_version: str = INDEX_VERSION) -> None:
        self.index_version = index_version

    def similar_to(
        self,
        node: Node,
        *,
        owner,
        exclude_node_ids=(),
        limit: int = 20,
        min_score: float = 0.0,
    ) -> list[SentenceMatch]:
        """Best-matching sentence pair per candidate node, highest first.

        `1 - (a <=> b)` converts pgvector's cosine *distance* into similarity, which is
        what the thresholds are expressed in — a distance threshold would read
        backwards everywhere else.
        """
        excluded = set(exclude_node_ids) | {node.pk}

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT ON (other.node_id)
                       other.node_id,
                       1 - (mine.embedding <=> other.embedding) AS score,
                       mine.span_start, mine.span_end,
                       other.span_start, other.span_end
                  FROM mind_sentenceembedding mine
                  JOIN mind_sentenceembedding other
                    ON other.node_id <> mine.node_id
                  JOIN mind_node n ON n.id = other.node_id
                 WHERE mine.node_id = %(node)s
                   AND mine.index_version = %(version)s
                   AND other.index_version = %(version)s
                   AND n.owner_id = %(owner)s
                   AND n.deleted_at IS NULL
                   AND n.archived_at IS NULL
                   AND NOT (other.node_id = ANY(%(excluded)s::bigint[]))
                   AND 1 - (mine.embedding <=> other.embedding) >= %(min_score)s
                 ORDER BY other.node_id, score DESC
                """,
                {
                    "node": node.pk,
                    "version": self.index_version,
                    "owner": owner.pk,
                    "excluded": list(excluded) or [0],
                    "min_score": min_score,
                },
            )
            rows = cursor.fetchall()

        matches = [
            SentenceMatch(
                node_id=node_id,
                score=float(score),
                source_span=(ms, me),
                candidate_span=(os_, oe),
                index_version=self.index_version,
            )
            for node_id, score, ms, me, os_, oe in rows
        ]
        # DISTINCT ON gives the best pair per candidate; this orders candidates
        # against each other, with the id tiebreak making the list assertable.
        matches.sort(key=lambda m: (-m.score, m.node_id))
        return matches[:limit]
