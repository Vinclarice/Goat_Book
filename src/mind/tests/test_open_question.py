"""Open question answered: "you asked this in April; this looks like an answer."

Two things about this detector are decisions rather than implementation, and
both are pinned here.

**It reads question-shaped text, not a facet.** The design document's signal is a
node's `question` epistemic status, and the lab has no facet table. Rather than
wait for one, the shape of the sentence stands in — rule-based and deterministic,
the same side of the line extraction sits on. The cost is real and worth naming:
a question phrased as a statement ("no idea whether the tutor takes evenings") is
invisible, and a rhetorical question is a false positive. A facet would be exact
where this is a heuristic, and this is a substitution to revisit rather than a
final answer.

**Direction is the finding.** An answer arrives *after* its question, and a
detector indifferent to that would propose the question as an answer to itself
half the time. `answers` is a typed relation for exactly this reason: it carries
which way round the pair goes, where `relates_to` would throw that away.
"""

from datetime import datetime, timedelta, timezone as dt_timezone

import pytest

from mind import services
from mind.detectors import find_open_questions, propose_open_questions
from mind.detectors.open_question import DETECTOR, looks_like_a_question
from mind.models import ConnectionHypothesis, EdgeRelation, NodeSource

pytestmark = pytest.mark.django_db

UTC = dt_timezone.utc
NOW = datetime(2026, 6, 1, 9, 0, tzinfo=UTC)

QUESTION = "Should I ask the tutor about evening lessons for Indonesian vocabulary?"
ANSWER = (
    "The tutor said evening lessons are fine, and we can focus on Indonesian "
    "vocabulary."
)


def _capture(owner, content, days_ago):
    return services.capture(
        owner,
        content=content,
        captured_at=NOW - timedelta(days=days_ago),
        source=NodeSource.WEB,
        actor="vince",
    )


# ---------------------------------------------------------------------------
# What counts as a question
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "Should I ask the tutor about evening lessons?",
        "why does the scanner keep jamming",
        "How long does a furnace filter actually last?",
        "wondering whether the recital is worth the trip",
    ],
)
def test_these_read_as_questions(text):
    assert looks_like_a_question(text)


@pytest.mark.parametrize(
    "text",
    [
        "The tutor said evening lessons are fine.",
        "Changed the furnace filter today.",
        # The trap the punctuation rule alone would fall for: a question mark
        # inside a note that is plainly not asking anything.
        "Bought the book called Why Nations Fail? and started it.",
    ],
)
def test_these_do_not(text):
    assert not looks_like_a_question(text)


# ---------------------------------------------------------------------------
# The finding
# ---------------------------------------------------------------------------


def test_a_later_note_that_resolves_an_earlier_question_is_surfaced(owner):
    asked = _capture(owner, QUESTION, days_ago=20)
    _capture(owner, "Unrelated note about the furnace filter.", days_ago=10)
    answered = _capture(owner, ANSWER, days_ago=1)

    findings = find_open_questions(answered, now=NOW)

    assert [f.question for f in findings] == [asked]


def test_a_question_is_never_answered_by_something_earlier(owner):
    """The direction *is* the finding. Without this the detector would happily
    propose a question as the answer to a question asked after it."""
    answered = _capture(owner, ANSWER, days_ago=20)
    _capture(owner, QUESTION, days_ago=1)

    assert find_open_questions(answered, now=NOW) == []


def test_two_questions_are_not_an_answer(owner):
    """Asking the same thing twice is a recurrence, which is a different
    detector's finding and a different thing to say about it."""
    _capture(owner, QUESTION, days_ago=20)
    asked_again = _capture(
        owner, "Should I ask the tutor about Indonesian vocabulary lessons?", days_ago=1
    )

    assert find_open_questions(asked_again, now=NOW) == []


def test_the_same_sitting_is_not_a_discovery(owner):
    """A question asked and answered in one sitting is one thought. Unlike
    dormancy's eighteen months this only has to clear the sitting, which is what
    keeps the detector usable in week one -- the whole reason it is built before
    the corpus-dependent ones."""
    _capture(owner, QUESTION, days_ago=1)
    answered = _capture(owner, ANSWER, days_ago=1)

    assert find_open_questions(answered, now=NOW) == []


def test_an_unrelated_later_note_answers_nothing(owner):
    _capture(owner, QUESTION, days_ago=20)
    unrelated = _capture(
        owner, "Changed the furnace filter and swept the basement.", days_ago=1
    )

    assert find_open_questions(unrelated, now=NOW) == []


def test_an_already_connected_pair_is_not_proposed(owner):
    asked = _capture(owner, QUESTION, days_ago=20)
    answered = _capture(owner, ANSWER, days_ago=1)
    services.link(
        answered, asked, relation=EdgeRelation.ANSWERS, now=NOW, actor="vince"
    )

    assert find_open_questions(answered, now=NOW) == []


def test_another_persons_questions_are_never_candidates(owner, other_owner):
    services.capture(
        other_owner,
        content=QUESTION,
        captured_at=NOW - timedelta(days=20),
        source=NodeSource.WEB,
        actor="them",
    )
    answered = _capture(owner, ANSWER, days_ago=1)

    assert find_open_questions(answered, now=NOW) == []


def test_finding_writes_nothing(owner):
    _capture(owner, QUESTION, days_ago=20)
    answered = _capture(owner, ANSWER, days_ago=1)

    find_open_questions(answered, now=NOW)

    assert ConnectionHypothesis.objects.count() == 0


# ---------------------------------------------------------------------------
# The proposal
# ---------------------------------------------------------------------------


def test_the_proposal_says_which_way_round_the_pair_goes(owner):
    """`answers` rather than `relates_to`, because the direction is the whole
    content of the finding and a symmetric relation would discard it."""
    _capture(owner, QUESTION, days_ago=20)
    answered = _capture(owner, ANSWER, days_ago=1)

    proposal = propose_open_questions(answered, now=NOW)[0]

    assert proposal.detector == DETECTOR
    assert proposal.relation == EdgeRelation.ANSWERS


def test_the_proposal_quotes_the_question(owner):
    """Checkable evidence, per "every proposal explains itself" -- the reader
    should be able to disagree without opening anything."""
    _capture(owner, QUESTION, days_ago=20)
    answered = _capture(owner, ANSWER, days_ago=1)

    proposal = propose_open_questions(answered, now=NOW)[0]

    quotes = [m.node.original_content for m in proposal.members.all()]
    assert QUESTION in quotes


def test_rerunning_proposes_nothing_new(owner):
    """Runs after every batch of captures, so a second pass must not re-propose
    what the fingerprint already covers."""
    _capture(owner, QUESTION, days_ago=20)
    answered = _capture(owner, ANSWER, days_ago=1)

    propose_open_questions(answered, now=NOW)
    propose_open_questions(answered, now=NOW)

    assert ConnectionHypothesis.objects.filter(detector=DETECTOR).count() == 1


def test_a_dismissed_proposal_is_not_offered_again(owner):
    """The sibling test every other detector has, and the one this detector was
    missing.

    `_previously_proposed_ids` was imported from `dormant_thread`, and Python
    binds a function's globals to its *defining* module -- so the filter queried
    `detector="dormant_thread"` and found nothing of this detector's. A dismissed
    answer was therefore re-derived every night, forever, crowding a genuinely
    new finding out of the top three.

    `test_rerunning_proposes_nothing_new` above cannot catch this: it asserts a
    row count, which the fingerprint constraint guarantees on its own. The
    dismissal is what separates the two -- `propose_hypothesis` returns the
    *existing* row rather than raising, so a caller trying to surface it hits
    `AlreadyResolved`.
    """
    _capture(owner, QUESTION, days_ago=20)
    answered = _capture(owner, ANSWER, days_ago=1)

    [hypothesis] = propose_open_questions(answered, now=NOW)
    services.dismiss_hypothesis(hypothesis, now=NOW, actor="vince")

    assert propose_open_questions(answered, now=NOW) == []
    assert ConnectionHypothesis.objects.filter(detector=DETECTOR).count() == 1


def test_a_pair_another_detector_proposed_is_still_a_candidate_here(owner):
    """The same defect from the other side, and the more damaging half.

    Borrowing `dormant_thread`'s filter meant every pair *that* detector had
    already proposed was permanently invisible to this one -- so the directional
    "answers" finding, which the module docstring calls the whole content of the
    detector, was unreachable for exactly the pairs most likely to have it. Two
    notes far enough apart to be a dormant thread are two notes far enough apart
    for a question to have been forgotten.
    """
    question = _capture(owner, QUESTION, days_ago=20)
    answered = _capture(owner, ANSWER, days_ago=1)

    services.propose_hypothesis(
        owner,
        detector="dormant_thread",
        citations=[
            services.Citation(node=answered, reason="the note just captured"),
            services.Citation(node=question, reason="an older thread"),
        ],
        confidence=0.5,
        label="an unrelated dormant-thread proposal",
        index_version="fts-v1",
        relation=EdgeRelation.RELATES_TO,
        now=NOW,
        actor="system",
    )

    [proposal] = propose_open_questions(answered, now=NOW)

    assert proposal.relation == EdgeRelation.ANSWERS


def test_a_proposal_starts_unsurfaced(owner):
    """Silence is not consent: the review window cannot start before somebody
    has actually been shown it."""
    _capture(owner, QUESTION, days_ago=20)
    answered = _capture(owner, ANSWER, days_ago=1)

    proposal = propose_open_questions(answered, now=NOW)[0]

    assert proposal.first_surfaced_at is None
    assert proposal.review_window_expires_at is None
