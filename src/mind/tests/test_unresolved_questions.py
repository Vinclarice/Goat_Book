"""Questions that are still open: "you asked this and nothing has answered it."

The inverse of the `open_question` detector, and deliberately not a detector.
That one fires when an *answer* arrives, so it is silent about everything still
hanging -- which is the thing a person actually wants to be asked about. This
reads the corpus and says what is unresolved.

**It is a view, not a claim.** No `ConnectionHypothesis`, no fingerprint, no
review window, no confirm gate. "You asked this and nothing has answered it" is
a fact about the graph rather than a proposal about it, so it needs none of the
machinery that exists to make a guess accountable. That distinction is what
keeps it off the attention budget: nothing here can be wrong in the way a
proposal can be wrong, only stale.

**Question-shape is a heuristic and stays one here.** `looks_like_a_question`
is the same predicate the detector uses, and `planning-assistant-plan.md`
increment 1 keeps it evaluated on read rather than materialised as an epistemic
facet -- the corpus is small, and the swap is one function body when something
else needs to query epistemic status. The predicate's own cost is unchanged and
already named in `test_open_question.py`.

**What "answered" means is the typed relation, not a guess.** `confirm_hypothesis`
links answer --answers--> question, so a question is resolved exactly when it is
the *target* of an `answers` edge. Reading it the other way round would report
every answer as an unanswered question, which is the failure the typed relation
exists to prevent.
"""

from datetime import datetime, timedelta, timezone as dt_timezone

import pytest

from mind import queries, services
from mind.models import EdgeRelation, InferenceOrigin, NodeSource

pytestmark = pytest.mark.django_db

UTC = dt_timezone.utc
NOW = datetime(2026, 6, 1, 9, 0, tzinfo=UTC)

QUESTION = "Which payment provider should we use for the launch?"
STATEMENT = "Signed the venue contract for the launch this morning."
ANSWER = "We settled on Stripe for the launch, mostly for the invoicing."


def _capture(owner, content, days_ago, **kwargs):
    return services.capture(
        owner,
        content=content,
        captured_at=NOW - timedelta(days=days_ago),
        source=NodeSource.WEB,
        actor="vince",
        **kwargs,
    )


def test_a_question_nobody_answered_is_unresolved(owner):
    question = _capture(owner, QUESTION, days_ago=12)

    assert list(queries.unresolved_questions(owner)) == [question]


def test_a_statement_is_not_a_question(owner):
    _capture(owner, STATEMENT, days_ago=12)

    assert list(queries.unresolved_questions(owner)) == []


def test_a_question_with_an_answers_edge_is_resolved(owner):
    """The edge points answer -> question, so the question is the target.

    Written with the arguments in the order `confirm_hypothesis` passes them,
    rather than constructing the Edge directly, so that a change to that
    direction fails here instead of silently inverting this read.
    """
    question = _capture(owner, QUESTION, days_ago=12)
    answer = _capture(owner, ANSWER, days_ago=2)
    services.link(
        answer,
        question,
        relation=EdgeRelation.ANSWERS,
        origin=InferenceOrigin.INFERRED,
        now=NOW,
        actor="vince",
    )

    assert list(queries.unresolved_questions(owner)) == []


def test_an_answer_is_not_itself_reported_as_unresolved(owner):
    """The other half of the direction test, and the one that would pass by luck.

    `ANSWER` is not question-shaped, so a read that inverted the edge would still
    exclude it here for the wrong reason. The pairing with the test above is what
    makes the direction actually pinned: that one must exclude the question, this
    one must not report the answer.
    """
    question = _capture(owner, QUESTION, days_ago=12)
    answer = _capture(owner, ANSWER, days_ago=2)
    services.link(
        answer,
        question,
        relation=EdgeRelation.ANSWERS,
        origin=InferenceOrigin.INFERRED,
        now=NOW,
        actor="vince",
    )

    assert answer not in list(queries.unresolved_questions(owner))


def test_a_question_already_proposed_against_is_not_repeated(owner):
    """One item, one place in one ritual.

    A pending `open_question` hypothesis already puts this question on the review
    surface, carrying a candidate answer and a confirm gate. Listing it again as
    "still unanswered" two sections higher is the same loose end counted twice,
    which is how a review stops being trustworthy about its own numbers.
    """
    question = _capture(owner, QUESTION, days_ago=12)
    answer = _capture(owner, ANSWER, days_ago=2)
    services.propose_hypothesis(
        owner,
        detector="open_question",
        citations=[
            services.Citation(node=answer, reason="the note just captured"),
            services.Citation(node=question, reason="asked launch, payment"),
        ],
        confidence=0.5,
        label=QUESTION,
        index_version="fts-v1",
        relation=EdgeRelation.ANSWERS,
        now=NOW,
        actor="vince",
    )

    assert list(queries.unresolved_questions(owner)) == []


def test_a_dismissed_proposal_leaves_the_question_open(owner):
    """Dismissing a candidate answer says *that* was not it, not that it is settled.

    The pending-proposal filter above must read pending, never "has ever been
    proposed against" -- otherwise one wrong guess buries a question permanently,
    and the detector's own dedupe guarantees it will never be proposed again.
    """
    question = _capture(owner, QUESTION, days_ago=12)
    answer = _capture(owner, ANSWER, days_ago=2)
    hypothesis = services.propose_hypothesis(
        owner,
        detector="open_question",
        citations=[
            services.Citation(node=answer, reason="the note just captured"),
            services.Citation(node=question, reason="asked launch, payment"),
        ],
        confidence=0.5,
        label=QUESTION,
        index_version="fts-v1",
        relation=EdgeRelation.ANSWERS,
        now=NOW,
        actor="vince",
    )
    services.dismiss_hypothesis(hypothesis, now=NOW, actor="vince")

    assert list(queries.unresolved_questions(owner)) == [question]


def test_the_oldest_question_comes_first(owner):
    """Oldest first, which is the opposite of `live_nodes`.

    A loose end gets worse with age, so this read inverts the corpus default
    rather than inheriting it -- stated as a test because inheriting the default
    would look correct and read backwards.
    """
    recent = _capture(owner, "Should we run a second beta?", days_ago=3)
    oldest = _capture(owner, QUESTION, days_ago=40)

    assert list(queries.unresolved_questions(owner)) == [oldest, recent]


def test_a_deleted_question_is_not_a_loose_end(owner):
    question = _capture(owner, QUESTION, days_ago=12)
    services.delete_node(question, now=NOW, actor="vince")

    assert list(queries.unresolved_questions(owner)) == []


def test_an_archived_question_is_not_a_loose_end(owner):
    question = _capture(owner, QUESTION, days_ago=12)
    services.archive_node(question, now=NOW, actor="vince")

    assert list(queries.unresolved_questions(owner)) == []


def test_a_revision_decides_whether_it_still_reads_as_a_question(owner):
    """`current_body`, never `original_content`.

    A note captured as a question and since rewritten into a decision is not a
    loose end, and the corpus already has one definition of what a node currently
    says. Reading the original capture would keep answering with a sentence the
    person has replaced.
    """
    question = _capture(owner, QUESTION, days_ago=12)
    services.revise(
        question,
        body="We are using Stripe for the launch.",
        actor="vince",
        now=NOW,
    )

    assert list(queries.unresolved_questions(owner)) == []


def test_another_person_s_questions_are_invisible(owner, other_owner):
    """Adversarial rather than incidental: the other corpus is the only one with
    anything in it, so a read that forgot to filter returns their question."""
    theirs = services.capture(
        other_owner,
        content=QUESTION,
        captured_at=NOW - timedelta(days=12),
        source=NodeSource.WEB,
        actor="someone-else",
    )

    assert list(queries.unresolved_questions(owner)) == []
    assert theirs.owner == other_owner


# ---------------------------------------------------------------------------
# The duplicated definition, guarded.
#
# These two pass on their first run and are meant to. `current_body_expression`
# is deliberately a second statement of `current_body` -- one in SQL because
# this read scans the corpus, one in Python because everything else resolves a
# single node -- and `principles.md` allows that only with a guard against the
# two drifting. This is the guard, not a test of new behaviour.
# ---------------------------------------------------------------------------


def test_the_sql_body_agrees_with_current_body_when_unrevised(owner):
    node = _capture(owner, QUESTION, days_ago=12)

    annotated = (
        queries.live_nodes(owner)
        .annotate(body=queries.current_body_expression())
        .get(pk=node.pk)
    )
    assert annotated.body == queries.current_body(node) == QUESTION


def test_the_sql_body_agrees_with_current_body_when_revised(owner):
    node = _capture(owner, QUESTION, days_ago=12)
    services.revise(node, body="Second thoughts.", actor="vince", now=NOW)
    services.revise(node, body="Third thoughts.", actor="vince", now=NOW)

    annotated = (
        queries.live_nodes(owner)
        .annotate(body=queries.current_body_expression())
        .get(pk=node.pk)
    )
    assert annotated.body == queries.current_body(node) == "Third thoughts."
