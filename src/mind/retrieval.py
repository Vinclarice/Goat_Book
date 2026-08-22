"""Retrieval that knows why it is being asked — Track B increments 7, 8 and 9.

**The finding this answers**, from `temporal-substrate-plan.md` Part 2: Clarice
has *several retrieval tricks and no retrieval architecture*. Lexical search,
`material_bearing_on`, `semantic_echo` and the concept detectors are each
defensible for their original job, and not one of them knows why somebody is
asking.

The cost is measurable in constants. `detectors/dormant_thread.py` carries
`MIN_DORMANCY` of 548 days and `MIN_LENGTH` of 120 characters, and the
detector's own reasoning for them is sound — in **Discovery**, noise is
unrecoverable, because a stream of poor proposals teaches somebody to skim past
the review surface and no later improvement recovers that. **The same floors
are catastrophic in Lookup**, where the person knows what they wrote: under
them *"Mum's birthday, 14 March"* can never be returned. One set of settings,
two modes, and only one of them served.

So the shape here is the brief's pipeline, and nothing more clever::

    What moment is this?
            v
    Gather candidates from the lexical, concept and temporal indexes
            v
    Apply eligibility rules for this moment
            v
    Rank within the eligible set
            v
    Explain why each result appeared

**The indexes are unchanged and stay where they are.** They stop being final
judges and become generators, which is a change to who decides rather than to
how anything is found.

**The principle:** *Clarice may contain anything, but it should never retrieve
without knowing why the person is asking — or why the system is interrupting.*

**This module proposes; `design-concept.md` decides.** `principles.md` §Scope
is explicit that the knowledge core's design authority is Second Mind's own
docs, and Part 2 is a proposal to that document. What is here is the mechanism
with the evidence attached, not a settlement of the Attention Policy.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from django.utils import timezone

from clarice.search import to_query

from . import queries
from .detectors.dormant_thread import DEFAULT_MIN_DORMANCY, DEFAULT_MIN_LENGTH
from .models import Node


class Mode(Enum):
    """What kind of remembering is happening now — Part 2's second axis.

    Six, and the table in the brief is the specification. **Not a
    `models.TextChoices`**: no row stores one. A mode is a property of the
    *moment*, which lasts one request.

    Each names the failure that matters, because that is what the eligibility
    rules below trade against:

    ==============  =====================================  ========================
    Mode            The question                           Failure that matters
    ==============  =====================================  ========================
    LOOKUP          find what I asked for                  a miss
    RECOLLECTION    restore the context around something   context too thin
    DISCOVERY       show meaningful connections            noise, unrecoverable
    PLANNING        evidence for active outcomes           irrelevance at a decision
    REFLECTION      compare experience across a period     not like for like
    RESURFACING     bring this back, the present cues it   interrupting for nothing
    ==============  =====================================  ========================
    """

    LOOKUP = "lookup"
    RECOLLECTION = "recollection"
    DISCOVERY = "discovery"
    PLANNING = "planning"
    REFLECTION = "reflection"
    RESURFACING = "resurfacing"


#: Generators named in Part 2's pipeline that **cannot run in production**, and
#: are declared rather than silently absent.
#:
#: `semantic_echo` is complete and tested, and `sentence-transformers` is
#: dev-only by documented refusal in `run_mind_maintenance.py` — so the HNSW
#: index and the fifth detector have never run against real material. A
#: pipeline that listed the semantic index among its generators and quietly
#: returned nothing from it would be claiming a capability the deployment does
#: not have. **D14 owns the decision**; this owns not lying about it meanwhile.
GENERATORS_NOT_RUNNING = frozenset({"semantic"})


@dataclass(frozen=True)
class Moment:
    """Why somebody is asking, or why the system is interrupting.

    *What moment is this?* is the first step of the pipeline, and a mode alone
    does not answer it — Lookup with no query and Planning with no outcomes are
    both unanswerable. So the present context travels with the mode.
    """

    owner: object
    mode: Mode
    text: str = ""
    #: The clock, injected like everywhere else in this app, so a dormancy
    #: floor is testable without waiting eighteen months.
    now: datetime | None = None

    def __post_init__(self):
        if not isinstance(self.mode, Mode):
            raise ValueError(f"{self.mode!r} is not a kind of remembering")

    @property
    def when(self):
        return self.now if self.now is not None else timezone.now()


@dataclass(frozen=True)
class Result:
    """One thing found, and why.

    **`why` is increment 9 and is not decoration.** It is the only thing that
    lets a person argue with an eligibility rule rather than learning to
    distrust the surface — the same discipline as the planning assistant citing
    the passage behind each proposal.

    **`mode` rides along** because these modes must not share one final
    ranking. A `Result` is one mode's answer and carries no number that could
    be compared against another's.
    """

    node: Node
    mode: Mode
    found_by: str
    why: str
    #: Only ever compared within one mode's result set.
    score: float = 0.0


# ---------------------------------------------------------------------------
# The generators. Existing indexes, unchanged, no longer deciding.
# ---------------------------------------------------------------------------


def _lexical(moment):
    """PostgreSQL full-text, which is right for *find that chicken recipe*."""
    query = to_query(moment.text)
    if query is None:
        return []
    return [
        (node, "lexical", f"it says {moment.text}")
        for node in queries.search_ranked(moment.owner, query)
    ]


def _concept(moment):
    """Notes confirmed to be about a named thing.

    The index lexical search cannot stand in for: a note that never uses the
    word but is confirmed to be about it is exactly what a second mind should
    return.
    """
    label = moment.text.strip()
    if not label:
        return []
    found = []
    for concept in queries.confirmed_concepts(moment.owner).filter(
        label__iexact=label
    ):
        for node in queries.nodes_mentioning(moment.owner, concept):
            found.append(
                (node, "concept", f"you confirmed this is about {concept.label}")
            )
    return found


#: The generators that run, in the order they are consulted. Order decides only
#: which explanation survives deduplication, never rank.
GENERATORS = (_lexical, _concept)


# ---------------------------------------------------------------------------
# Eligibility. One set of rules per mode, which is the whole point.
# ---------------------------------------------------------------------------


def _eligible_for_lookup(node, moment):
    """Everything. **No dormancy floor, no length floor, no narrowing.**

    The brief's worked example: *searching "lemon chicken recipe" searches
    everything and returns the recipe directly.* The person knows what they
    wrote; the failure that matters is a miss, and every floor is a way to
    produce one.
    """
    return True


def _eligible_for_discovery(node, moment):
    """The dormant-thread floors, kept and applied where they belong.

    Noise is unrecoverable here: a stream of poor proposals teaches somebody to
    skim past the review surface, and no later improvement recovers that. The
    detector's own reasoning, now attached to the mode rather than to the
    index, so Lookup stops paying for it.
    """
    if len(queries.current_body(node)) < DEFAULT_MIN_LENGTH:
        return False
    return moment.when - node.captured_at >= DEFAULT_MIN_DORMANCY


#: Per mode, and the missing ones are missing on purpose: Recollection,
#: Planning, Reflection and Resurfacing each need context this module does not
#: yet take — outcomes, a period, a present. Falling back to Lookup's "admit
#: everything" would be four modes quietly sharing one contract, which is the
#: state Part 2 exists to end. They raise instead.
ELIGIBILITY = {
    Mode.LOOKUP: _eligible_for_lookup,
    Mode.DISCOVERY: _eligible_for_discovery,
}


def _rank_for_lookup(results, moment):
    """Lexical rank, then recency, which is what the search page already did.

    Unchanged deliberately: increment 8 moves *who decides eligibility*, and
    changing the ordering in the same slice would make a regression here
    impossible to attribute.
    """
    return results


RANKING = {
    Mode.LOOKUP: _rank_for_lookup,
    Mode.DISCOVERY: _rank_for_lookup,
}


def retrieve(moment, *, limit=30):
    """Candidates, filtered by this moment's rules, each saying why it is here.

    Deduplicated above the generators, which is the point of them being
    generators: two tricks returning one note twice is what a merged list of
    independent mechanisms does today. The first generator to find a note owns
    the explanation, which is why `GENERATORS` is ordered.
    """
    mode = moment.mode
    if mode not in ELIGIBILITY:
        raise NotImplementedError(
            f"{mode.value} has no eligibility rules yet; it needs context this "
            "module does not take, and falling back to lookup's would be four "
            "modes sharing one contract again"
        )

    admit = ELIGIBILITY[mode]
    seen = {}
    for generator in GENERATORS:
        for node, found_by, why in generator(moment):
            if node.pk in seen or not admit(node, moment):
                continue
            seen[node.pk] = Result(node=node, mode=mode, found_by=found_by, why=why)

    return RANKING[mode](list(seen.values()), moment)[:limit]
