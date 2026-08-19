"""How long a question has been open, and whether it came back — increment 1.

The card Vince sketched reads *"Still unanswered: Which payment provider should
we use? First asked 12 days ago. Mentioned again in two later entries."*
`unresolved_questions` returns bare nodes and computes neither half.

**"Mentioned again" reuses the rare-term gate rather than inventing a second
idea of relatedness.** A later note counts when it shares vocabulary appearing
in almost none of the person's other notes — the same signal at 67% precision
that the project brief anchors on, and the same reason: a count built on
topical similarity would be the vaguely-on-topic panel `detectors/__init__`
rejects, wearing a number.

**Later only.** "Mentioned again" is a claim about what happened *after* the
asking. A note written before the question is not a recurrence, and counting it
would make the number mean "related at all", which is a different and much less
interesting fact.

**A separate read from `unresolved_questions`, deliberately.** This costs one
retrieval per question, and the weekly review's loose-ends list wants none of
that — it needs the questions cheaply and says nothing about recurrence. Two
readers, two costs, one definition of "bears on" underneath both.
"""

from datetime import datetime, timedelta, timezone as dt_timezone

import pytest

from mind import queries, services
from mind.models import NodeSource

pytestmark = pytest.mark.django_db

UTC = dt_timezone.utc
NOW = datetime(2026, 6, 20, 9, 0, tzinfo=UTC)

QUESTION = "Which payment provider should we use for the booking form?"


def _capture(owner, content, days_ago):
    return services.capture(
        owner,
        content=content,
        captured_at=NOW - timedelta(days=days_ago),
        source=NodeSource.WEB,
        actor="v",
    )


@pytest.fixture
def corpus(owner):
    """Unrelated notes, so "distinctive" has something to be distinctive against.

    `significant_terms` drops a term appearing in a large *fraction* of the
    corpus, so in a two-note corpus everything shared is common by definition
    and nothing matches anything. That is a property of rarity, not a quirk to
    write around — a term is distinctive *to this person*, and with two notes
    there is no "this person" to speak of yet.
    """
    for index in range(8):
        _capture(owner, f"Note {index}: the garden, the weather, a walk.", days_ago=40 + index)


@pytest.fixture
def question(owner, corpus):
    return _capture(owner, QUESTION, days_ago=12)


def _only(owner):
    found = queries.unresolved_questions_in_context(owner, now=NOW)
    assert len(found) == 1
    return found[0]


def test_it_says_how_long_the_question_has_been_open(owner, question):
    assert _only(owner).days_open == 12


def test_a_question_nobody_returned_to_has_no_mentions(owner, question):
    _capture(owner, "Bought milk and walked to the park.", days_ago=3)

    assert _only(owner).mentions == []


def test_a_later_note_sharing_distinctive_words_is_a_mention(owner, question):
    later = _capture(
        owner,
        "Still undecided on the payment provider for the booking form.",
        days_ago=4,
    )

    assert [m.node for m in _only(owner).mentions] == [later]


def test_an_earlier_note_is_not_a_recurrence(owner, question):
    """The claim is about what happened after the asking.

    Counting earlier notes would turn "mentioned again" into "related at all",
    which is a different and much duller fact — and one the brief already
    answers elsewhere.
    """
    _capture(
        owner,
        "Comparing every payment provider for the booking form today.",
        days_ago=30,
    )

    assert _only(owner).mentions == []


def test_the_question_is_not_its_own_mention(owner, question):
    """It matches its own text perfectly, so this is not hypothetical.

    `material_bearing_on` takes a statement rather than a node and so has no
    source to exclude by default — the caller has to say.
    """
    assert question not in [m.node for m in _only(owner).mentions]


def test_a_mention_carries_the_terms_that_matched(owner, question):
    """A number nobody can check is what `precision.md` exists to refuse.

    "Mentioned again twice" is a claim; the words it rests on are what let
    somebody disagree with it.
    """
    _capture(
        owner,
        "Still undecided on the payment provider for the booking form.",
        days_ago=4,
    )

    assert _only(owner).mentions[0].reason


def test_questions_still_come_oldest_first(owner, question):
    _capture(owner, "Should we run a second beta?", days_ago=3)

    found = queries.unresolved_questions_in_context(owner, now=NOW)

    assert [each.days_open for each in found] == [12, 3]


def test_a_settled_question_is_not_in_context_either(owner, question):
    """This wraps the same read, so every exclusion it makes holds here."""
    services.resolve_question(question, now=NOW, actor="v")

    assert queries.unresolved_questions_in_context(owner, now=NOW) == []


def test_another_person_s_notes_are_never_mentions(owner, other_owner, question):
    services.capture(
        other_owner,
        content="Still undecided on the payment provider for the booking form.",
        captured_at=NOW - timedelta(days=4),
        source=NodeSource.WEB,
        actor="someone-else",
    )

    assert _only(owner).mentions == []
