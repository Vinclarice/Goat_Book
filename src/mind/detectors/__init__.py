"""Detectors: each asks one specific question and carries its own evidence.

Similarity is a retrieval primitive, not a mechanic. "Compute similarity, show
related notes" is a known failure — it produces a panel of vaguely on-topic
material that is technically correct and reliably ignored, because topical
relatedness answers no question the person was asking. So the unit here is a
*detector*: a named question, a concrete signal, and a reason a person can read.

Shipped:

* **concept_assignment** — "this looks like it is about Indonesian." The only one
  here that answers *what is this about* rather than *what did you forget*, which
  is why it is the only one that can say anything from a cold start: it needs a
  confirmed concept and no accumulated history at all. Anchored rather than
  pairwise — one end is a decision a person made — so it matches a note against a
  profile aggregated from confirmed material instead of against another note,
  which is the failure mode whole-document embeddings measured at 0%. Proposes an
  unconfirmed mention, never an edge.
* **dormant_thread** — "you wrote about this before and have probably forgotten."
  Lexical, so its precision comes from a threshold and its ceiling is real: it
  cannot see a connection stated in different words. Measured at 67% precision and
  2 of 6 known connections (`docs/detector-evaluation.md`).
* **shared_referent** — "these describe the same thing, named differently." A
  resolution finding rather than a similarity one, so its evidence is *exact*: a
  confirmed alias is not a guess with a score. Precision comes from the
  architecture, at the cost of depending on the person having confirmed something.
* **semantic_echo** — "you have said this before, in other words." Scores a pair by
  its best-matching *sentence* pair, and cites both sentences. Recovers a connection
  the lexical detector provably cannot reach; needs the optional embedding
  dependency, and reports itself unavailable without it.

All three are complementary by design, and each was built because the previous ones'
misses were measured rather than guessed at. Whole-document embeddings, for contrast,
scored 0% precision — so `semantic_echo` is emphatically not "the same thing with
vectors" (`docs/embedding-shadow-evaluation.md`).

* **open_question** — "you asked this in April; this looks like an answer." The
  second detector that works from a cold start, and the cheapest evidence
  available in week one: a dump is mostly unresolved questions and ordinary
  capture supplies the answers. Its stated signal was a `question` epistemic
  status and the lab has no facet table, so it reads question-*shaped* text
  instead — deterministic, and a substitution to revisit the moment facets
  exist rather than a final answer. Its relation is `answers` rather than
  `relates_to`, because the direction is the whole content of the finding.

Adding a detector is additive: each attributes its proposals to itself, so
accept rates are per-detector. That is deliberate — the useful question is
*which* detectors work, and a single blended score cannot answer it.
"""

from .concept_assignment import (
    DETECTOR as CONCEPT_ASSIGNMENT,
    find_concept_assignments,
    propose_concept_assignments,
)
from .open_question import (
    DETECTOR as OPEN_QUESTION,
    find_open_questions,
    looks_like_a_question,
    propose_open_questions,
)
from .dormant_thread import (
    DETECTOR as DORMANT_THREAD,
    Finding,
    find_dormant_threads,
    propose_dormant_threads,
)
from .semantic_echo import (
    DETECTOR as SEMANTIC_ECHO,
    find_semantic_echoes,
    propose_semantic_echoes,
)
from .shared_referent import (
    DETECTOR as SHARED_REFERENT,
    find_shared_referents,
    propose_shared_referents,
)

__all__ = [
    "CONCEPT_ASSIGNMENT",
    "DORMANT_THREAD",
    "OPEN_QUESTION",
    "SEMANTIC_ECHO",
    "SHARED_REFERENT",
    "Finding",
    "find_concept_assignments",
    "find_dormant_threads",
    "find_open_questions",
    "find_semantic_echoes",
    "find_shared_referents",
    "propose_concept_assignments",
    "looks_like_a_question",
    "propose_dormant_threads",
    "propose_open_questions",
    "propose_semantic_echoes",
    "propose_shared_referents",
]
