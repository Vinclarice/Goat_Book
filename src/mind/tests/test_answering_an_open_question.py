"""Answering a loose end — increment 1's two missing decisions.

`planning-assistant-plan.md` increment 1 shipped its read and stopped, because
its three actions each needed somewhere to write and two of them had nowhere:

* **"Mark answered" with nothing to point at.** The read excludes a question via
  an `answers` edge, which needs a node that answered it. Somebody who simply
  knows a thing is settled has no such node, and forcing them to name one would
  be asking for a citation they do not have.
* **"Not a question."** `looks_like_a_question` is a heuristic over three text
  signals; a rhetorical question is a false positive by construction. Saying so
  had no home at all.

**Both are epistemic facets — Vince, August 19, 2026.** `FacetKind.EPISTEMIC`
has existed since the merger and nothing has ever written one, and
`open_question.py`'s own docstring says its signal *should* have been a
`question` epistemic status, deferred because "the lab has no facet table".
Facets exist now. That revisit trigger fired and nobody noticed.

**The shape is deliberate: the heuristic stays at read time and the facet
records only the correction.** Materialising question-ness would mean a stored
field agreeing or disagreeing with a predicate that can change, which is two
answers to one question. A person's decision, on the other hand, is exactly the
thing that should outlive any predicate — so the facet is the override, and the
override is what makes "not a question" teach rather than merely hide.
"""

from datetime import datetime, timedelta, timezone as dt_timezone

import pytest

from mind import queries, services
from mind.models import Facet, FacetKind, InferenceOrigin, NodeSource

pytestmark = pytest.mark.django_db

UTC = dt_timezone.utc
NOW = datetime(2026, 6, 1, 9, 0, tzinfo=UTC)

QUESTION = "Which payment provider should we use for the launch?"


@pytest.fixture
def question(owner):
    return services.capture(
        owner,
        content=QUESTION,
        captured_at=NOW - timedelta(days=12),
        source=NodeSource.WEB,
        actor="v",
    )


def test_a_question_starts_unresolved(owner, question):
    assert list(queries.unresolved_questions(owner)) == [question]


# -- settled, with nothing to point at ------------------------------------


def test_marking_it_answered_settles_it(owner, question):
    services.resolve_question(question, now=NOW, actor="v")

    assert list(queries.unresolved_questions(owner)) == []


def test_settling_it_records_who_said_so_and_that_they_did(owner, question):
    """Explicit, not inferred, and that distinction is the whole record.

    A resolution nobody can tell from a guess is a resolution nobody can argue
    with later.
    """
    services.resolve_question(question, now=NOW, actor="v")

    facet = question.facets.get(kind=FacetKind.EPISTEMIC)
    assert facet.origin == InferenceOrigin.EXPLICIT
    assert facet.data["status"] == "resolved"


def test_settling_it_twice_is_not_an_error(owner, question):
    """Two taps, or a tap against a stale page. The caller's intent is already
    satisfied, and one live epistemic facet per node is the constraint."""
    services.resolve_question(question, now=NOW, actor="v")
    services.resolve_question(question, now=NOW, actor="v")

    assert question.facets.filter(kind=FacetKind.EPISTEMIC).count() == 1


# -- not a question at all -------------------------------------------------


def test_saying_it_is_not_a_question_removes_it(owner, question):
    services.dismiss_as_question(question, now=NOW, actor="v")

    assert list(queries.unresolved_questions(owner)) == []


def test_that_is_a_different_statement_from_answered(owner, question):
    """"I settled this" and "this was never a question" are different facts.

    Collapsing them would lose the only correction signal the heuristic will
    ever get -- the count of notes it read as questions and a person did not.
    """
    services.dismiss_as_question(question, now=NOW, actor="v")

    facet = question.facets.get(kind=FacetKind.EPISTEMIC)
    assert facet.data["status"] == "not_a_question"


def test_a_correction_survives_the_predicate_that_caused_it(owner, question):
    """The reason this is stored rather than recomputed.

    `looks_like_a_question` is three text signals and will change. A person's
    decision about their own note should outlive any of them, which is what a
    read-time heuristic plus a stored override buys and what a materialised
    question flag would not.
    """
    services.dismiss_as_question(question, now=NOW, actor="v")
    services.revise(question, body="Rewritten, still ending in a?", actor="v", now=NOW)

    assert list(queries.unresolved_questions(owner)) == []


# -- changing your mind ----------------------------------------------------


def test_a_settled_question_can_be_reopened(owner, question):
    """Nothing here is one-way.

    Retiring the facet rather than deleting it keeps "this was settled and then
    was not" as a fact, which is the same call `dismiss_facet` makes.
    """
    services.resolve_question(question, now=NOW, actor="v")

    services.reopen_question(question, now=NOW, actor="v")

    assert list(queries.unresolved_questions(owner)) == [question]
    assert question.facets.filter(kind=FacetKind.EPISTEMIC).count() == 1


def test_reopening_leaves_the_record_that_it_was_settled(owner, question):
    services.resolve_question(question, now=NOW, actor="v")
    services.reopen_question(question, now=NOW, actor="v")

    retired = question.facets.get(kind=FacetKind.EPISTEMIC)
    assert retired.retired_at is not None


# -- ownership -------------------------------------------------------------


def test_a_facet_on_one_person_s_note_does_not_settle_another_s(
    owner, other_owner
):
    theirs = services.capture(
        other_owner,
        content=QUESTION,
        captured_at=NOW - timedelta(days=12),
        source=NodeSource.WEB,
        actor="someone-else",
    )
    services.resolve_question(theirs, now=NOW, actor="someone-else")

    mine = services.capture(
        owner,
        content=QUESTION,
        captured_at=NOW - timedelta(days=12),
        source=NodeSource.WEB,
        actor="v",
    )

    assert list(queries.unresolved_questions(owner)) == [mine]


def test_an_answers_edge_still_settles_a_question(owner, question):
    """The other route, unchanged.

    Naming what answered it is better than saying it is settled, when there is
    something to name -- the edge carries the connection and the facet carries
    only the conclusion. Both close the loose end; this pins that adding the
    second did not break the first.
    """
    answer = services.capture(
        owner,
        content="Settled at the meeting.",
        captured_at=NOW,
        source=NodeSource.WEB,
        actor="v",
    )
    services.link(
        answer, question, relation="answers", origin="inferred", now=NOW, actor="v"
    )

    assert list(queries.unresolved_questions(owner)) == []
