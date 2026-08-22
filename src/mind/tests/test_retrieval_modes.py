"""Knowing why it is being asked — Track B increments 7, 8 and 9.

Part 2's finding: Clarice has **several retrieval tricks and no retrieval
architecture**. Lexical search, `material_bearing_on`, `semantic_echo` and the
concept detectors are each defensible for their original job, and none of them
shares any understanding of *why somebody is asking*.

The consequence is measurable in constants. `detectors/dormant_thread.py`
carries `MIN_DORMANCY` 548 days and `MIN_LENGTH` 120 characters — correct for
Discovery, where noise is unrecoverable and a stream of poor proposals teaches
somebody to skim past the review surface for good. **They are catastrophic for
Lookup**, where the person knows what they wrote and wants it: under those
floors *"Mum's birthday, 14 March"* can never be returned.

So three increments, and they are one thing:

- **7 — modes named in code.** A surface declares which of the six kinds of
  remembering it is doing and what the present context is. The mode is the
  argument every rule below takes.
- **8 — candidate generators behind one contract.** The existing indexes stop
  being final judges. They propose; eligibility and ranking sit above them.
- **9 — every result explains why it appeared.** Not a nicety: it is the only
  thing that lets somebody argue with an eligibility rule instead of learning
  to distrust the surface.

**The principle it establishes** is the brief's own: *Clarice may contain
anything, but it should never retrieve without knowing why the person is
asking — or why the system is interrupting.*

**Wired to the search page in the same slice**, deliberately. `principles.md`
now says a slice is not closed while nothing calls it, and a retrieval
architecture with no caller would be the largest dark seam in the project.
"""

from datetime import datetime, timedelta, timezone as dt_timezone

import pytest

from mind import retrieval, services
from mind.models import ConceptType, InferenceOrigin, Node


WRITTEN = datetime(2026, 5, 4, 9, 0, tzinfo=dt_timezone.utc)


def later(**offset):
    return WRITTEN + timedelta(**offset)


@pytest.fixture
def signed_in(client, owner):
    client.force_login(owner)
    return client


def a_note(owner, content, *, when=WRITTEN):
    return services.capture(
        owner, content=content, captured_at=when, source=Node.Source.WEB, actor="vince"
    )


# ---------------------------------------------------------------------------
# 7 — the moment, named
# ---------------------------------------------------------------------------


def test_every_mode_in_the_brief_is_named_in_code(db):
    """Six modes, and the table in Part 2 is the specification. A mode missing
    here is a kind of remembering no surface can declare, which is how the
    single implicit contract happened in the first place."""
    assert {m.value for m in retrieval.Mode} == {
        "lookup",
        "recollection",
        "discovery",
        "planning",
        "reflection",
        "resurfacing",
    }


def test_a_moment_carries_the_mode_and_the_present(db, owner):
    """*What moment is this?* is the first step of the pipeline, and a mode on
    its own does not answer it -- Lookup with no query and Planning with no
    outcomes are both unanswerable."""
    moment = retrieval.Moment(owner=owner, mode=retrieval.Mode.LOOKUP, text="chicken")

    assert moment.mode is retrieval.Mode.LOOKUP
    assert moment.text == "chicken"


def test_a_moment_must_say_which_mode_it_is(db, owner):
    with pytest.raises(ValueError):
        retrieval.Moment(owner=owner, mode=None, text="chicken")


# ---------------------------------------------------------------------------
# 8 — the indexes propose; eligibility decides
# ---------------------------------------------------------------------------


def test_lookup_returns_a_short_note_the_discovery_floors_would_refuse(db, owner):
    """The concrete payoff the plan names: *Lookup loses the dormancy and
    length floors it should never have had.*

    `MIN_LENGTH` is 120 characters. "Mum's birthday, 14 March" is 24, and
    somebody searching for it knows exactly what they wrote.
    """
    a_note(owner, "Mum's birthday, 14 March")

    found = retrieval.retrieve(
        retrieval.Moment(owner=owner, mode=retrieval.Mode.LOOKUP, text="birthday")
    )

    assert [r.node.original_content for r in found] == ["Mum's birthday, 14 March"]


def test_discovery_keeps_the_floors(db, owner):
    """The other half, and the reason the floors are not simply deleted. In
    Discovery noise is unrecoverable -- a stream of poor proposals teaches
    somebody to skim past the review surface, and no later improvement recovers
    that."""
    a_note(owner, "Mum's birthday, 14 March")

    found = retrieval.retrieve(
        retrieval.Moment(owner=owner, mode=retrieval.Mode.DISCOVERY, text="birthday")
    )

    assert found == []


def test_discovery_admits_something_long_and_dormant(db, owner):
    a_note(
        owner,
        "A long dormant thought about the venue, " * 5,
        when=WRITTEN - timedelta(days=600),
    )

    found = retrieval.retrieve(
        retrieval.Moment(
            owner=owner,
            mode=retrieval.Mode.DISCOVERY,
            text="venue",
            now=WRITTEN,
        )
    )

    assert len(found) == 1


def test_a_candidate_names_which_index_proposed_it(db, owner):
    a_note(owner, "the lemon chicken recipe")

    found = retrieval.retrieve(
        retrieval.Moment(owner=owner, mode=retrieval.Mode.LOOKUP, text="chicken")
    )

    assert found[0].found_by == "lexical"


def test_the_concept_index_proposes_too(db, owner):
    """An index rather than the index. A note that never uses the word but is
    confirmed to be about the thing is exactly what a second mind should
    return, and lexical search alone cannot."""
    concept = services.propose_concept(
        owner, label="Maya", concept_type=ConceptType.UNKNOWN, now=WRITTEN, actor="s"
    )
    services.confirm_concept(concept, now=WRITTEN, actor="vince")
    node = a_note(owner, "she knows about the venue")
    services.propose_mention(
        node,
        concept,
        index_version="manual",
        origin=InferenceOrigin.EXPLICIT,
        now=WRITTEN,
        actor="vince",
    )

    found = retrieval.retrieve(
        retrieval.Moment(owner=owner, mode=retrieval.Mode.LOOKUP, text="Maya")
    )

    assert "she knows about the venue" in [r.node.original_content for r in found]


def test_one_note_found_by_two_indexes_is_returned_once(db, owner):
    """Deduplicated above the generators, which is the point of them being
    generators. Two tricks returning one note twice is what a merged list of
    independent mechanisms does today."""
    concept = services.propose_concept(
        owner, label="chicken", concept_type=ConceptType.UNKNOWN, now=WRITTEN, actor="s"
    )
    services.confirm_concept(concept, now=WRITTEN, actor="vince")
    node = a_note(owner, "the lemon chicken recipe")
    services.propose_mention(
        node,
        concept,
        index_version="manual",
        origin=InferenceOrigin.EXPLICIT,
        now=WRITTEN,
        actor="vince",
    )

    found = retrieval.retrieve(
        retrieval.Moment(owner=owner, mode=retrieval.Mode.LOOKUP, text="chicken")
    )

    assert len(found) == 1


def test_a_deleted_note_is_never_a_candidate(db, owner):
    node = a_note(owner, "something regretted about chicken")
    services.delete_node(node, now=later(days=1), actor="vince")

    found = retrieval.retrieve(
        retrieval.Moment(owner=owner, mode=retrieval.Mode.LOOKUP, text="chicken")
    )

    assert found == []


def test_it_does_not_reach_into_another_persons_memory(db, owner, other_owner):
    a_note(other_owner, "their chicken recipe")

    found = retrieval.retrieve(
        retrieval.Moment(owner=owner, mode=retrieval.Mode.LOOKUP, text="chicken")
    )

    assert found == []


def test_the_semantic_index_declares_that_it_cannot_run(db, owner):
    """**Said rather than silently absent.** `semantic_echo` has never run in
    production -- `sentence-transformers` is dev-only by documented refusal --
    so a pipeline that listed it among its generators and quietly returned
    nothing would be claiming a capability it does not have. D14 owns the
    decision; this owns not lying about it in the meantime.
    """
    assert "semantic" in retrieval.GENERATORS_NOT_RUNNING


# ---------------------------------------------------------------------------
# 9 — every result explains why it appeared
# ---------------------------------------------------------------------------


def test_every_result_says_why_it_appeared(db, owner):
    """Not a nicety. It is the only thing that lets somebody argue with an
    eligibility rule instead of learning to distrust the surface -- the same
    discipline as the planning assistant citing the passage behind each
    proposal."""
    a_note(owner, "the lemon chicken recipe")

    found = retrieval.retrieve(
        retrieval.Moment(owner=owner, mode=retrieval.Mode.LOOKUP, text="chicken")
    )

    assert found[0].why == "it says chicken"


def test_the_explanation_names_the_concept_when_that_is_the_reason(db, owner):
    """A note returned because it is confirmed to be about Maya, without the
    word in it, is unarguable-with unless the page says so."""
    concept = services.propose_concept(
        owner, label="Maya", concept_type=ConceptType.UNKNOWN, now=WRITTEN, actor="s"
    )
    services.confirm_concept(concept, now=WRITTEN, actor="vince")
    node = a_note(owner, "she knows about the venue")
    services.propose_mention(
        node,
        concept,
        index_version="manual",
        origin=InferenceOrigin.EXPLICIT,
        now=WRITTEN,
        actor="vince",
    )

    found = retrieval.retrieve(
        retrieval.Moment(owner=owner, mode=retrieval.Mode.LOOKUP, text="Maya")
    )
    reason = [r.why for r in found if r.node.pk == node.pk][0]

    assert "Maya" in reason


def test_a_mode_ranks_within_itself_and_never_across_modes(db, owner):
    """*These modes must not share one final ranking.* Asserted as a property
    of the return rather than described: what comes back is one mode's
    ordering, and there is no number on it that could be compared with
    another's."""
    a_note(owner, "chicken one")
    a_note(owner, "chicken two")

    found = retrieval.retrieve(
        retrieval.Moment(owner=owner, mode=retrieval.Mode.LOOKUP, text="chicken")
    )

    assert all(r.mode is retrieval.Mode.LOOKUP for r in found)


# ---------------------------------------------------------------------------
# It has a caller, which is the whole point of shipping it now
# ---------------------------------------------------------------------------


def test_the_search_page_declares_itself_a_lookup(signed_in, owner):
    """`principles.md`: a slice is not closed while nothing calls it. A
    retrieval architecture with no caller would be the largest dark seam in
    the project."""
    a_note(owner, "Mum's birthday, 14 March")

    body = signed_in.get("/mind/search/", {"q": "birthday"}).content.decode()

    # Asserted without the apostrophe, which renders escaped. The note is
    # twenty-four characters against a MIN_LENGTH of 120, so Lookup returning
    # it at all is the increment.
    assert "birthday, 14 March" in body


def test_the_search_page_says_why_each_note_appeared(signed_in, owner):
    a_note(owner, "the lemon chicken recipe")

    body = signed_in.get("/mind/search/", {"q": "chicken"}).content.decode()

    assert "matched" in body.lower()


# ---------------------------------------------------------------------------
# Recollection — the fourth mode, and the one increment 22 actually needs
# ---------------------------------------------------------------------------


def test_recollection_needs_something_to_recollect(db, owner):
    """A mode with no anchor is Lookup with a different name. *Restore the
    context around something* has a something in it."""
    with pytest.raises(ValueError):
        retrieval.Moment(owner=owner, mode=retrieval.Mode.RECOLLECTION)


def test_it_returns_what_was_written_around_the_same_time(db, owner):
    """The failure that matters here is **context too thin to resume**, which
    is the opposite of Discovery's. So the temporal index proposes, and
    nothing about length or dormancy is asked."""
    anchor = a_note(owner, "ask Maya about the venue")
    a_note(owner, "the caterer called back", when=later(minutes=20))

    found = retrieval.retrieve(
        retrieval.Moment(
            owner=owner, mode=retrieval.Mode.RECOLLECTION, anchor=anchor, now=WRITTEN
        )
    )

    assert "the caterer called back" in [r.node.original_content for r in found]


def test_a_short_note_nearby_is_still_context(db, owner):
    """Twenty-four characters is a fact about a note, not about whether it
    helps somebody resume. Discovery's floors would drop it and Discovery is
    right to; here they would produce the exact failure the mode names."""
    anchor = a_note(owner, "ask Maya about the venue")
    a_note(owner, "14 March", when=later(minutes=5))

    found = retrieval.retrieve(
        retrieval.Moment(
            owner=owner, mode=retrieval.Mode.RECOLLECTION, anchor=anchor, now=WRITTEN
        )
    )

    assert "14 March" in [r.node.original_content for r in found]


def test_it_returns_what_is_about_the_same_things(db, owner):
    """Confirmed concepts, not similarity. A person said these are about the
    same thing, which is provenance -- and D4's refusal applies here as much
    as in `since()`: a close embedding is not a connection anybody made."""
    concept = services.propose_concept(
        owner, label="Maya", concept_type=ConceptType.UNKNOWN, now=WRITTEN, actor="s"
    )
    services.confirm_concept(concept, now=WRITTEN, actor="vince")
    anchor = a_note(owner, "ask about the venue")
    distant = a_note(owner, "she prefers the small room", when=later(days=400))
    for node in (anchor, distant):
        services.propose_mention(
            node,
            concept,
            index_version="manual",
            origin=InferenceOrigin.EXPLICIT,
            now=node.captured_at,
            actor="vince",
        )

    found = retrieval.retrieve(
        retrieval.Moment(
            owner=owner, mode=retrieval.Mode.RECOLLECTION, anchor=anchor, now=WRITTEN
        )
    )

    assert "she prefers the small room" in [r.node.original_content for r in found]


def test_a_note_about_nothing_in_common_is_not_context(db, owner):
    """The refusal that keeps this from being *everything you ever wrote*.
    Written a year away, sharing no confirmed concept, connected by nothing
    anybody recorded."""
    anchor = a_note(owner, "ask Maya about the venue")
    a_note(owner, "the car needs a service", when=later(days=400))

    found = retrieval.retrieve(
        retrieval.Moment(
            owner=owner, mode=retrieval.Mode.RECOLLECTION, anchor=anchor, now=WRITTEN
        )
    )

    assert "the car needs a service" not in [r.node.original_content for r in found]


def test_the_thing_being_recollected_is_not_its_own_context(db, owner):
    anchor = a_note(owner, "ask Maya about the venue")

    found = retrieval.retrieve(
        retrieval.Moment(
            owner=owner, mode=retrieval.Mode.RECOLLECTION, anchor=anchor, now=WRITTEN
        )
    )

    assert anchor.pk not in [r.node.pk for r in found]


def test_recollection_says_why_too(db, owner):
    anchor = a_note(owner, "ask Maya about the venue")
    a_note(owner, "the caterer called back", when=later(minutes=20))

    found = retrieval.retrieve(
        retrieval.Moment(
            owner=owner, mode=retrieval.Mode.RECOLLECTION, anchor=anchor, now=WRITTEN
        )
    )

    assert "around the same time" in found[0].why


def test_a_deleted_note_is_not_context_either(db, owner):
    anchor = a_note(owner, "ask Maya about the venue")
    gone = a_note(owner, "something regretted", when=later(minutes=20))
    services.delete_node(gone, now=later(days=1), actor="vince")

    found = retrieval.retrieve(
        retrieval.Moment(
            owner=owner, mode=retrieval.Mode.RECOLLECTION, anchor=anchor, now=WRITTEN
        )
    )

    assert "something regretted" not in [r.node.original_content for r in found]


def test_lookup_does_not_use_the_temporal_index(db, owner):
    """Generators are per mode, not one pool. Searching for *chicken* must not
    return everything written near some instant -- that is Recollection's
    question, and answering it under Lookup is the single implicit contract
    coming back."""
    anchor = a_note(owner, "the lemon chicken recipe")
    a_note(owner, "unrelated thing nearby", when=later(minutes=5))

    found = retrieval.retrieve(
        retrieval.Moment(owner=owner, mode=retrieval.Mode.LOOKUP, text="chicken")
    )

    assert [r.node.pk for r in found] == [anchor.pk]


def test_the_note_page_declares_itself_a_recollection(signed_in, owner):
    """The surface was already doing recollection ad hoc -- the fragment, what
    was nearby, what came of it -- without naming it. Increment 7's whole point
    is that a surface says which kind of remembering it is doing.

    **Asserted on something only the mode can produce.** The first version of
    this test looked for a note written twenty minutes later, which
    `context_of` already put on the page as an *event*: it passed without the
    wiring existing. A note a year away sharing a confirmed concept is
    reachable by no other section.
    """
    concept = services.propose_concept(
        owner, label="Maya", concept_type=ConceptType.UNKNOWN, now=WRITTEN, actor="s"
    )
    services.confirm_concept(concept, now=WRITTEN, actor="vince")
    anchor = a_note(owner, "ask about the venue")
    distant = a_note(owner, "she prefers the small room", when=later(days=400))
    for node in (anchor, distant):
        services.propose_mention(
            node,
            concept,
            index_version="manual",
            origin=InferenceOrigin.EXPLICIT,
            now=node.captured_at,
            actor="vince",
        )

    body = signed_in.get(f"/mind/notes/{anchor.public_id}/").content.decode()

    assert "she prefers the small room" in body
    assert "it is also about Maya" in body
