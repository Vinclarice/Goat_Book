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
from datetime import datetime, timedelta
from enum import Enum

from django.utils import timezone

from clarice.search import to_query, to_question_query

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
    #: What is being recollected. Recollection is the one mode whose question
    #: -- *restore the context around something* -- has a something in it, and
    #: a mode with no anchor is Lookup wearing a different name.
    anchor: Node | None = None
    #: Whether `text` is a question somebody typed rather than search terms.
    #: It decides how the words are read: a question's extra words are
    #: scaffolding and must not narrow, where a search's are the person being
    #: more specific. `clarice/search.py` owns both readings.
    text_is_a_question: bool = False
    #: The clock, injected like everywhere else in this app, so a dormancy
    #: floor is testable without waiting eighteen months.
    now: datetime | None = None

    def __post_init__(self):
        if not isinstance(self.mode, Mode):
            raise ValueError(f"{self.mode!r} is not a kind of remembering")
        if self.mode is Mode.RECOLLECTION and self.anchor is None:
            raise ValueError("recollection needs something to recollect")

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
    build = to_question_query if moment.text_is_a_question else to_query
    query = build(moment.text)
    if query is None:
        return []

    words = moment.text.split()
    found = []
    for node in queries.search_ranked(moment.owner, query):
        # **The words this note actually has**, not the whole query. A question
        # is ORed, so naming every term explains an answer with words that are
        # not in it -- and increment 9 exists so somebody can argue with an
        # answer rather than acquire one more thing to distrust.
        body = queries.current_body(node).lower()
        present = [w for w in words if w.lower() in body]
        # **Past tense when nothing survived the edit.** `original_content` is
        # never mutated, so a note can be reached through wording its author
        # took out -- and "it says" would then be true of the note's history
        # and false of the note, which is the wrong way round.
        why = (
            f"it says {' '.join(present)}"
            if present
            else f"it once said {' '.join(words)}"
        )
        found.append((node, "lexical", why))
    return found


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


def _written_around(moment):
    """Notes captured near one of the anchor's own moments.

    Track A's `context_of` decides what *near* means, including merging moments
    close enough to be one sitting -- D19's resolution, reused rather than
    re-derived, which is the reason that read exists.

    **Only in Recollection.** Under Lookup this would return everything
    written near some instant, which is a different question answered under
    the wrong heading -- the single implicit contract coming back.
    """
    from clarice import recall

    found = []
    for occasion in recall.context_of(
        moment.owner, moment.anchor, window=RECOLLECTION_WINDOW
    ).occasions:
        for neighbour in occasion.neighbours:
            if neighbour.node is not None:
                found.append(
                    (neighbour.node, "temporal", "you wrote it around the same time")
                )
    return found


def _shares_a_concept(moment):
    """Notes confirmed to be about something this one is also about.

    **Confirmed concepts, never similarity.** A person said these are about
    the same thing, which is a record; a close embedding is a guess, and D4's
    refusal applies here exactly as it does in `since()`.
    """
    found = []
    for label in queries.confirmed_concept_labels(moment.anchor):
        for concept in queries.confirmed_concepts(moment.owner).filter(
            label__iexact=label
        ):
            for node in queries.nodes_mentioning(moment.owner, concept):
                found.append(
                    (node, "concept", f"it is also about {concept.label}")
                )
    return found


#: How many previous years Resurfacing is cued by. `recall`'s own default, and
#: named here rather than reached for, because the trade is this mode's: the
#: cost of the sixth year is not a query, it is an interruption that reads as an
#: archive. See `Mode.RESURFACING`'s named failure.
RESURFACING_YEARS = 5

#: Generous per year, unlike the read's own default. Deduplication and the
#: eligibility floor happen *above* the generator, so a day with fifteen events
#: on it must not be truncated to ten before anything has decided which of them
#: is worth an interruption.
RESURFACING_PER_YEAR = 50

#: How a distance in years is said. Spelled out rather than formatted, because
#: "1 years ago today" is the kind of thing that makes a person stop believing
#: the rest of the sentence. Public, because the page and the `why` string say
#: the same thing and must not drift into saying it two ways.
_HOW_LONG_AGO = {
    1: "a year ago today",
    2: "two years ago today",
    3: "three years ago today",
    4: "four years ago today",
    5: "five years ago today",
}


def how_long_ago(years):
    return _HOW_LONG_AGO.get(years, f"{years} years ago today")


def _on_this_day(moment):
    """Notes from this calendar day in previous years — **D17's cyclic cue**.

    **The present this mode was waiting for turns out to be the date.** Track B
    increment 8 left Resurfacing raising `NotImplementedError` because it
    *"needs context this module does not yet take — outcomes, a period, a
    present"*, and the cheapest honest present is the one every person already
    has. *This time last year* is a recorded fact rather than a similarity
    score, which is why this mode could ship while D14 is still open.

    **`recall.this_time_before` rather than a query here**, for the reason
    `_written_around` defers to `context_of`: the hard part is which calendar
    day, in whose clock, and that is D16's answer and belongs beside it. The
    log is the right index either way — `capture` records `CAPTURED` with
    `occurred_at=captured_at`, so an imported note carries the thought's own
    time and not the import's.
    """
    from clarice import recall
    from clarice import clocks

    found = []
    before = recall.this_time_before(
        moment.owner,
        on=clocks.day_for(moment.owner, moment.when),
        years=RESURFACING_YEARS,
        per_year=RESURFACING_PER_YEAR,
    )
    for anniversary in before.years:
        for neighbour in anniversary.neighbours:
            # `None` where the note was deleted or archived: `_neighbour`
            # withholds it, which is R5's rule and exactly right here. A note
            # somebody erased must not be the thing that interrupts them.
            if neighbour.node is not None:
                found.append(
                    (
                        neighbour.node,
                        "anniversary",
                        f"you wrote this {how_long_ago(anniversary.years_ago)}",
                    )
                )
    return found


#: How far *around the same time* reaches when restoring context. Wider than
#: `recall.DEFAULT_WINDOW`, and deliberately: the failure that matters here is
#: **context too thin to resume**, so the cost of one extra note is far below
#: the cost of a missing one. The opposite trade from Discovery.
RECOLLECTION_WINDOW = timedelta(hours=12)


#: Which indexes each mode consults, in the order they are asked. Order decides
#: only which explanation survives deduplication, never rank.
#:
#: **Per mode rather than one pool**, which is increment 8's actual content: the
#: temporal index answering a Lookup would return everything written near some
#: instant, and that is Recollection's question under the wrong heading.
GENERATORS = {
    Mode.LOOKUP: (_lexical, _concept),
    Mode.DISCOVERY: (_lexical, _concept),
    Mode.RECOLLECTION: (_written_around, _shares_a_concept),
    Mode.RESURFACING: (_on_this_day,),
}


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


def _eligible_for_recollection(node, moment):
    """Everything reached, except the thing being recollected.

    **No floors, and for the opposite reason to Lookup's.** There the failure
    is a miss; here it is *context too thin to resume*, so the cost of one
    extra note sits far below the cost of a missing one. A twenty-four
    character note is not less useful for being short — *"14 March"* beside a
    venue question is exactly the fragment that lets somebody pick the thread
    up.

    **The narrowing has already happened**, which is why this rule is one line.
    Recollection's generators reach only along recorded adjacency and confirmed
    concepts, so a note about nothing in common was never a candidate. Doing it
    with an eligibility rule instead would have meant admitting everything and
    then arguing it back down.
    """
    return node.pk != moment.anchor.pk


def _eligible_for_resurfacing(node, moment):
    """Long enough to be worth an interruption. **Nobody asked for this one.**

    The opposite trade from Lookup, where the person knows what they wrote and
    every floor is a way to produce a miss. Here the named failure is
    *interrupting for nothing*, and something arriving unbidden has to earn it —
    so Discovery's length floor applies, for Discovery's reason.

    **No dormancy floor, because the generator is one.** A note reaches this
    mode only by being a year old on today's date, which is a stronger and more
    honest signal than 548 days of silence: the anniversary is a fact about the
    calendar rather than a threshold somebody picked.
    """
    return len(queries.current_body(node)) >= DEFAULT_MIN_LENGTH


#: Per mode, and the missing ones are missing on purpose: Planning and
#: Reflection each need context this module does not yet take — outcomes, and a
#: period. Falling back to Lookup's "admit everything" would be three modes
#: quietly sharing one contract, which is the state Part 2 exists to end. They
#: raise instead.
#:
#: **Resurfacing was the third of these and is answered — D17, August 22,
#: 2026.** The present it was waiting for is the date, which every person
#: already has, and `_on_this_day` is the whole of it.
ELIGIBILITY = {
    Mode.LOOKUP: _eligible_for_lookup,
    Mode.DISCOVERY: _eligible_for_discovery,
    Mode.RECOLLECTION: _eligible_for_recollection,
    Mode.RESURFACING: _eligible_for_resurfacing,
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
    Mode.RECOLLECTION: _rank_for_lookup,
    Mode.RESURFACING: _rank_for_lookup,
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
    for generator in GENERATORS[mode]:
        for node, found_by, why in generator(moment):
            if node.pk in seen or not admit(node, moment):
                continue
            seen[node.pk] = Result(node=node, mode=mode, found_by=found_by, why=why)

    return RANKING[mode](list(seen.values()), moment)[:limit]
