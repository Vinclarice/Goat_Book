"""When the semantic index gets switched on — **D14, answered**.

> **D14. Does the semantic index get switched on, and how?** Part 2's pipeline
> names the semantic index among its candidate generators, but `semantic_echo`
> has **never run in production** — `sentence-transformers` is dev-only by
> deliberate, documented refusal, so the fifth detector and the HNSW index are
> dark. The options are a decision, not engineering: **accept the dependency,
> embed via an API** (a new processor, touching `/privacy/` the way D9 does), **or
> a smaller model.** If this is ML policy rather than deployment, it escalates to
> `design-concept.md`.

**Two of the three options were already closed, and finding that out is most of
the answer.**

**The API is refused by standing policy**, written in `mind/embeddings.py` and
not reopened here: *"Per the ML policy: self-hosted, deterministic for a given
model version, **no external call**, no per-use cost, nothing generative."*
Embedding every note through a third party is the largest change to this
product's privacy posture anyone has proposed, and it is ruled out by a sentence
that predates the question. D14 says this escalates if it is ML policy rather
than deployment — **it is ML policy, and the policy already says no.**

**A smaller model is not a third option, it is the same option cheaper.**
`all-MiniLM-L6-v2` is already the small one; what makes the dependency large is
torch, which every self-hosted sentence encoder pulls in.

**So the only live option is the dependency, and it was decided on August 18** —
D4 of `planning-assistant-plan.md`, quoted in `run_mind_maintenance.py`:
*"Installing it in test requirements makes the detector measured, which costs CI
time; installing it in the image makes it run, which costs deploy size on every
build and droplet disk across the four images kept for rollback. **The second
waits for a corpus large enough for the detector to have something to say.**"*

**What was actually still open is that the gate is not checkable**, and that is
what this fixes. *Large enough to have something to say* is a feeling. Nothing
measures it, nothing reports it, and the decision could only ever be revisited
by somebody happening to remember it — which is how `LIVE` sat five days behind
production and how three seams shipped switched off.

**And the readiness line was telling production to do something impossible.**
`detector_readiness` exists for exactly one purpose — *"the difference between
no connections found and no connections possible"* — and for this detector it
gave a third answer that is neither: **"run manage.py embed_nodes"**, a command
that cannot run in production because the dependency is deliberately absent. The
one line whose job is to say what you are waiting for was naming an action
nobody can take. Same shape as the nginx comment that claimed a cap it did not
enforce.
"""

import datetime

import pytest

from mind import instrumentation, services
from mind.models import Node


NOW = datetime.datetime(2026, 8, 22, 15, 0, tzinfo=datetime.timezone.utc)


def readiness_for(owner, detector):
    for entry in instrumentation.detector_readiness(owner, now=NOW):
        if entry.detector == detector:
            return entry
    raise AssertionError(f"{detector} is not reported at all")


def notes(owner, count):
    for n in range(count):
        services.capture(
            owner,
            content=f"Note number {n}, long enough to be a real one about the venue.",
            captured_at=NOW - datetime.timedelta(days=n + 1),
            source=Node.Source.WEB,
            actor="vince",
        )


def test_the_gate_is_a_number(db):
    """Not a feeling. `DEFAULT_MIN_DORMANCY` is 548 days and
    `DEFAULT_MIN_LENGTH` is 120 characters; both are picked, written down and
    revisable. This is the same kind of thing and was the one threshold in the
    system that existed only as a sentence in a docstring."""
    assert isinstance(instrumentation.SEMANTIC_INDEX_CORPUS_GATE, int)


def test_it_says_how_far_off_the_corpus_is(db, owner):
    """The `dormant_thread` line already does this — *"your oldest note is 12
    days old"* — and it is the difference between a gate and a shrug."""
    notes(owner, 3)

    blocked = readiness_for(owner, "semantic_echo").blocked_by

    assert str(instrumentation.SEMANTIC_INDEX_CORPUS_GATE) in blocked
    assert "3" in blocked


def test_it_no_longer_tells_you_to_run_a_command_that_cannot_run(db, owner):
    """**The live falsehood.** `embed_nodes` needs `sentence-transformers`,
    which is deliberately not in the production image, so the instruction was
    impossible exactly where somebody would read it."""
    notes(owner, 3)

    assert "embed_nodes" not in readiness_for(owner, "semantic_echo").blocked_by


def test_it_is_still_reported_rather_than_hidden(db, owner):
    """*Every detector is reported, including the ready ones and especially the
    blocked ones.* A gate that removed the row would restore the ambiguity the
    whole page exists to remove."""
    notes(owner, 3)

    assert readiness_for(owner, "semantic_echo").ready is False


def test_a_corpus_past_the_gate_says_the_decision_is_due(db, owner, settings):
    """**The point of making it checkable.** Past the gate, the thing blocking
    the detector is no longer the corpus — it is a deploy decision somebody has
    to take, and the page now says so instead of repeating a threshold that has
    been met."""
    instrumentation.SEMANTIC_INDEX_CORPUS_GATE = 5
    try:
        notes(owner, 6)

        blocked = readiness_for(owner, "semantic_echo").blocked_by

        assert "D14" in blocked
    finally:
        instrumentation.SEMANTIC_INDEX_CORPUS_GATE = (
            instrumentation.DEFAULT_SEMANTIC_INDEX_CORPUS_GATE
        )


def test_vectors_present_still_means_ready(db, owner):
    """Unchanged where it was right: in development, where the dependency is
    installed and vectors exist, the detector is ready and the gate is not
    consulted. The gate is about the production image, not about the code."""
    notes(owner, 3)
    from mind.models import SentenceEmbedding
    from mind import embeddings

    node = Node.objects.filter(owner=owner).first()
    SentenceEmbedding.objects.create(
        node=node,
        seq=0,
        span_start=0,
        span_end=10,
        index_version=embeddings.INDEX_VERSION,
        embedding=[0.0] * 384,
    )

    assert readiness_for(owner, "semantic_echo").ready is True
