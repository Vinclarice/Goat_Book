"""The similarity port, and its Postgres full-text implementation.

Every detector consumes this interface rather than talking to an index directly.
That is what makes the eventual move to local embeddings a change to one file:
the detectors keep asking the same question, and only what they can *see*
changes. It is also why *Vocabulary drift* — high semantic similarity with low
lexical overlap — is simply unavailable rather than approximated. Full-text
search cannot express it, so it is absent instead of quietly wrong.

**Scores are counts of shared significant terms, not `ts_rank` values.** That is
a deliberate choice with three consequences the product needs:

* **Explainable.** "shares 7 significant terms: mondly, lesson, evening…" is the
  concrete signal a proposal must carry. A rank of 0.0847 explains nothing.
* **Comparable across queries.** A `ts_rank` value is meaningful as an ordering
  *within* one query; it is not obvious that a fixed cutoff means the same thing
  for two different source documents. A shared-term count does mean the same
  thing, so a configurable threshold is coherent.
* **Right question.** For an OR query, `ts_rank` largely measures how often the
  candidate repeats matched terms. What matters here is how *many distinct* terms
  it matches — a note repeating one shared word ten times is not related, and a
  note touching seven of them is.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Protocol, Sequence

from django.db import connection

# Lexemes appearing in more than this fraction of a person's notes carry no
# discriminating power — for one person's corpus these are words like "think",
# "want", "today". Postgres' `english` configuration already strips true stop
# words before they ever reach a tsvector; this removes the *personal* ones,
# which no dictionary knows about.
DEFAULT_MAX_DOCUMENT_FRACTION = 0.25

# Below this the fraction filter is disabled: with a handful of notes every term
# looks common, and the filter would discard everything.
MIN_CORPUS_FOR_FREQUENCY_FILTER = 20

# Terms per source document. Enough to characterise a long journal entry, few
# enough that the overlap count stays meaningful.
DEFAULT_MAX_TERMS = 40

# A term in at most this many *other* notes counts as distinctive. One means "this
# note and one other, and nowhere else" — the whole point: a word occurring in
# exactly the pair under consideration is evidence, while a word in five notes is
# vocabulary.
#
# Frequencies throughout exclude the source note, which is what makes the figure
# mean the same thing whether or not that note has been saved yet. Counting the
# source made every shared term of an unsaved note look unique to it, so all of
# them were discarded as unmatchable and nothing was ever returned.
DEFAULT_DISTINCTIVE_DF = 1


@dataclass(frozen=True)
class Match:
    """One candidate, with the evidence for it."""

    node_id: int
    shared_terms: tuple[str, ...]
    candidate_term_count: int
    query_term_count: int
    weight: float = 0.0
    """Share of the query's *distinctive* vocabulary this candidate matches."""

    distinctive_terms: tuple[str, ...] = ()
    """Shared terms appearing in almost no other note.

    The signal that actually works. Measured against a corpus with known answers,
    neither raw overlap nor IDF-weighted overlap could separate real connections
    from prose coincidence at any threshold — the three highest-scoring pairs in
    the corpus were noise, the top one matching on "already, last, year". Counting
    shared terms that occur nowhere *else* took precision from 11% to 67%.

    It is also the more honest reason to show someone: "these two notes share
    three words that appear in none of your others" is a fact they can check,
    where a similarity score is a number they must trust.
    """

    @property
    def shared_count(self) -> int:
        return len(self.shared_terms)

    @property
    def distinctive_count(self) -> int:
        return len(self.distinctive_terms)

    @property
    def dice(self) -> float:
        """Unweighted set overlap, kept for reporting and as a tiebreak.

        Deliberately not the score. Measured against a corpus with known answers,
        plain overlap could not separate true connections from noise at any
        threshold — noise scored *higher* at the top of the range than genuine
        pairs did — because it counts "year" and "scanner" as equally meaningful.
        """
        total = self.query_term_count + self.candidate_term_count
        if not total:
            return 0.0
        return (2 * self.shared_count) / total

    @property
    def score(self) -> float:
        """Inverse-document-frequency weighted overlap, bounded 0…1.

        The fraction of the source note's *distinctive* vocabulary that the
        candidate shares. A term appearing in a quarter of someone's notes
        contributes almost nothing; one appearing twice in a decade contributes
        most of the score.

        This is the discrimination raw overlap lacks. Rarity is what makes a
        shared word mean something, and because the weights come from the
        person's own corpus, "distinctive" means distinctive *to them* — which no
        general dictionary could tell us.

        Normalising by the query's own weight mass keeps the value comparable
        across different source notes, so a fixed threshold means the same thing
        twice.
        """
        return self.weight


class SimilarityIndex(Protocol):
    """What a detector is allowed to ask.

    `version` is stamped onto every proposal, so a change of implementation
    becomes a re-indexing migration rather than a silent drift in what "similar"
    meant when a suggestion was made.
    """

    version: str

    def significant_terms(self, text: str, *, owner) -> list[str]: ...

    def similar_to(
        self,
        text: str,
        *,
        owner,
        source_node_id: int | None = None,
        exclude_node_ids: Iterable[int] = (),
        limit: int = 20,
        min_shared_terms: int = 2,
        min_distinctive_terms: int = 0,
    ) -> list[Match]: ...


class PostgresFullTextIndex:
    """v1: Postgres `english` full-text search over stored tsvectors.

    Deterministic given a corpus, needs no extension, costs nothing per call, and
    is testable with plain fixtures. What it cannot do is find a connection
    expressed in different words — which is the known ceiling, recorded rather
    than papered over.
    """

    version = "pg-fts-english-v1"

    def __init__(
        self,
        *,
        max_terms: int = DEFAULT_MAX_TERMS,
        max_document_fraction: float = DEFAULT_MAX_DOCUMENT_FRACTION,
        distinctive_df: int = DEFAULT_DISTINCTIVE_DF,
    ) -> None:
        self.max_terms = max_terms
        self.max_document_fraction = max_document_fraction
        self.distinctive_df = distinctive_df

    # -- terms ------------------------------------------------------------

    def lexemes(self, text: str) -> list[str]:
        """The document's lexemes, stemmed and stop-word-stripped by Postgres.

        Asked of the database rather than reimplemented in Python: the stemming
        must match what is stored in the generated `search_original` column, and
        the only way to guarantee that is to use the same code path.
        """
        if not text.strip():
            return []
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT tsvector_to_array(to_tsvector('english', %s))", [text]
            )
            row = cursor.fetchone()
        return list(row[0]) if row and row[0] else []

    def document_frequencies(
        self, terms: Sequence[str], *, owner, exclude_node_id: int | None = None
    ) -> dict[str, int]:
        """How many of this person's *other* notes contain each term.

        `exclude_node_id` is normally the source note, so a count of 1 means
        "exactly one other note has this" regardless of whether the source is in
        the corpus yet.

        One query for all terms rather than one per term. Each lexeme is quoted and
        cast to `tsquery` rather than passed through `to_tsquery`: quoting survives
        lexemes containing apostrophes or operators, and these are *already*
        lexemes — re-stemming them risks producing a term that no longer matches
        what is stored.

        Archived notes are excluded here and in `corpus_size`, matching the
        candidate filter in `similar_to`. Counting a note that can never be
        returned would inflate every frequency and quietly push shared terms past
        the distinctive threshold.
        """
        if not terms:
            return {}
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT t.term,
                       (SELECT count(*) FROM mind_node n
                         WHERE n.owner_id = %(owner)s
                           AND n.deleted_at IS NULL
                           AND n.archived_at IS NULL
                           AND n.id IS DISTINCT FROM %(exclude)s
                           AND n.search_original @@ (quote_literal(t.term))::tsquery)
                  FROM unnest(%(terms)s::text[]) AS t(term)
                """,
                {"owner": owner.pk, "terms": list(terms), "exclude": exclude_node_id},
            )
            return {term: count for term, count in cursor.fetchall()}

    def corpus_size(self, *, owner, exclude_node_id: int | None = None) -> int:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT count(*) FROM mind_node WHERE owner_id = %(owner)s "
                "AND deleted_at IS NULL AND archived_at IS NULL "
                "AND id IS DISTINCT FROM %(exclude)s",
                {"owner": owner.pk, "exclude": exclude_node_id},
            )
            return cursor.fetchone()[0]

    def significant_terms(
        self, text: str, *, owner, exclude_node_id: int | None = None
    ) -> list[str]:
        """Lexemes worth querying with, rarest first.

        There is no IDF to lean on, so document frequency over the person's own
        notes stands in for it — and it is better than the obvious alternatives,
        because rarity is what makes a shared term mean something.

        Two filters:

        * **Cannot match.** A term no *other* note contains can never be shared.
          Dropping it shrinks the query without changing a single result.
        * **Too common.** A term in a quarter of someone's notes carries no
          discriminating power. Postgres' `english` configuration already strips
          true stop words before a lexeme reaches a tsvector; this removes the
          *personal* ones, which no dictionary knows about. Only this second filter
          needs a minimum corpus — a fraction of twelve notes is not a fraction of
          anything — and below that size it is skipped while real frequencies are
          still used for everything else.

        Rarest first with an alphabetical tiebreak. The tiebreak is not cosmetic:
        without it, selection at the `max_terms` boundary could vary between runs
        and the same note would yield different proposals.
        """
        terms = self.lexemes(text)
        if not terms:
            return []

        frequencies = self.document_frequencies(
            terms, owner=owner, exclude_node_id=exclude_node_id
        )
        matchable = [t for t in terms if frequencies.get(t, 0) >= 1]

        total = self.corpus_size(owner=owner, exclude_node_id=exclude_node_id)
        if total >= MIN_CORPUS_FOR_FREQUENCY_FILTER:
            ceiling = max(1, int(total * self.max_document_fraction))
            matchable = [t for t in matchable if frequencies[t] <= ceiling]

        matchable.sort(key=lambda t: (frequencies.get(t, 0), t))
        return matchable[: self.max_terms]

    # -- matching ---------------------------------------------------------

    def similar_to(
        self,
        text: str,
        *,
        owner,
        source_node_id: int | None = None,
        exclude_node_ids: Iterable[int] = (),
        limit: int = 20,
        min_shared_terms: int = 2,
        min_distinctive_terms: int = 0,
    ) -> list[Match]:
        """Candidates sharing at least `min_shared_terms` significant terms.

        `source_node_id` is the note the text came from, excluded from every
        frequency count so that "appears in one other note" means that whether or
        not the source has been saved.

        `min_distinctive_terms` is the gate that matters — see `Match`. Raising it
        trades recall for precision far more effectively than any score threshold,
        because it asks a different question: not "how similar" but "do these two
        notes share something that appears nowhere else".

        Two stages, deliberately. The `@@` predicate narrows using the GIN index;
        the overlap count then runs only over what survived. Counting overlap
        across the whole table would be correct and needlessly slow.
        """
        terms = self.significant_terms(text, owner=owner, exclude_node_id=source_node_id)
        if len(terms) < min_shared_terms:
            return []

        # Real document frequencies, always — never fabricated, whatever the corpus
        # size. Filling in `df = 1` below a threshold made every shared term count
        # as distinctive, so `reason()` would tell the person that eleven of eleven
        # shared terms appear in almost none of their other notes while one of them
        # appeared in nineteen notes out of nineteen. A wrong score is a bad
        # suggestion; a wrong *reason* breaks the promise that every proposal
        # explains itself, and it is checkable, so it will be caught by the person
        # rather than by a test.
        #
        # Absolute frequency is meaningful at any corpus size — "appears in at most
        # two notes" means the same thing with twelve notes as with twelve thousand.
        # Only the *fractional* ceiling needs a minimum corpus, and that is applied
        # in significant_terms, not here.
        total = self.corpus_size(owner=owner)
        frequencies = self.document_frequencies(
            terms, owner=owner, exclude_node_id=source_node_id
        )
        weights = {
            t: math.log(1 + max(total, 1) / max(1, frequencies.get(t, 0) + 1))
            for t in terms
        }
        total_weight = sum(weights.values())
        # The source is never its own candidate. Excluded here rather than left to
        # every caller: it is excluded from the frequency counts a line above, so a
        # caller reasonably assumes the same of the results, and a note returned as
        # similar to itself is never what anyone wanted.
        excluded = set(exclude_node_ids)
        if source_node_id is not None:
            excluded.add(source_node_id)
        excluded_ids = list(excluded) or [0]

        with connection.cursor() as cursor:
            cursor.execute(
                """
                WITH query AS (
                    SELECT string_agg(quote_literal(t), ' | ')::tsquery AS q
                      FROM unnest(%(terms)s::text[]) AS t
                )
                -- tsvector_to_array yields lexemes only: positions and weight
                -- labels are already discarded, so the set is weight-insensitive
                -- without needing strip().
                SELECT n.id,
                       ARRAY(
                           SELECT w FROM unnest(tsvector_to_array(n.search_original)) AS w
                            WHERE w = ANY(%(terms)s::text[])
                            ORDER BY w
                       ) AS shared,
                       coalesce(array_length(tsvector_to_array(n.search_original), 1), 0)
                  FROM mind_node n, query
                 WHERE n.owner_id = %(owner)s
                   AND n.deleted_at IS NULL
                   AND n.archived_at IS NULL
                   AND NOT (n.id = ANY(%(excluded)s::bigint[]))
                   AND n.search_original @@ query.q
                """,
                {
                    "terms": terms,
                    "owner": owner.pk,
                    "excluded": excluded_ids,
                },
            )
            rows = cursor.fetchall()

        matches = [
            Match(
                node_id=node_id,
                # Rarest first, so the reason a person reads leads with the term
                # that actually carried the match rather than an alphabetical
                # accident.
                shared_terms=tuple(
                    sorted(shared, key=lambda t: (-weights.get(t, 0.0), t))
                ),
                candidate_term_count=candidate_total,
                query_term_count=len(terms),
                weight=(
                    sum(weights.get(t, 0.0) for t in shared) / total_weight
                    if total_weight
                    else 0.0
                ),
                distinctive_terms=tuple(
                    sorted(
                        t
                        for t in shared
                        if frequencies.get(t, 99) <= self.distinctive_df
                    )
                ),
            )
            for node_id, shared, candidate_total in rows
            if len(shared) >= min_shared_terms
        ]
        matches = [
            m for m in matches if m.distinctive_count >= min_distinctive_terms
        ]
        # Distinctive count first — the gate that carries the signal — then the
        # weighted score, then Dice, then node id.
        #
        # Dice earns its place as a tiebreak specifically because the score is
        # normalised by the *query's* weight mass and so is blind to how long the
        # candidate is. Between two candidates sharing the same terms, the one
        # that is mostly those terms is the better match than the one that merely
        # contains them somewhere; only a symmetric measure can say so. The id
        # tiebreak makes the whole ordering assertable.
        matches.sort(
            key=lambda m: (-m.distinctive_count, -m.score, -m.dice, m.node_id)
        )
        return matches[:limit]


def default_index() -> PostgresFullTextIndex:
    return PostgresFullTextIndex()
