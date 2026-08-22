"""Asking your memory a question — Track E increment 22, the last of the track.

**Declined on August 21 and built the same evening**, which is worth saying
plainly: the refusal was right when the pipeline beneath it did not exist, and
stopped being right once Track B's 7–9 and Recollection shipped. Built on
nothing, this box is `search_ranked` with a prompt in front of it — one blended
ordering, unable to say where an answer came from, **failing silently**. Built
on the pipeline it is three things the plan names:

**Extractive.** Answers are sentences the person wrote, lifted with their
offsets. **Nothing is generated, summarised or paraphrased.** A second mind
that writes new prose about your life is a second mind you have to fact-check,
and the whole value of the store is that it holds what you actually said.

**Cited.** Every answer names the note it came from and links to it. The same
discipline as the planning assistant quoting the passage behind each proposal:
without it a person cannot argue with an answer, only distrust it.

**Per-mode.** The question decides which kind of remembering this is, **by an
enumerable rule rather than a classifier** — *"Predicates before ranking"*, and
a rule can be argued with where a score cannot. A question about *when* or
*what else* is a Recollection anchored on the best Lookup hit; everything else
is a Lookup. The page says which it chose, so a wrong choice is visible rather
than mysterious.

**And it can say it does not know**, which is the failure mode a question box
invites: an answer assembled from nothing looks exactly like an answer.
"""

from datetime import datetime, timedelta, timezone as dt_timezone

import pytest

from mind import ask, services
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


def asking(client, question):
    return client.get("/mind/ask/", {"q": question})


# ---------------------------------------------------------------------------
# Extractive — the person's own words, never new ones
# ---------------------------------------------------------------------------


def test_it_answers_with_the_sentence_you_wrote(db, owner):
    a_note(
        owner,
        "The caterer is called Bellini. They need eight days notice. "
        "The venue closes at eleven.",
    )

    answer = ask.answer(owner, "caterer")

    assert answer.passages[0].text.strip() == "The caterer is called Bellini."


def test_it_does_not_return_the_whole_note(db, owner):
    """Extractive means the sentence, not the document. A note holding a
    paragraph answers a question with one line of it, and returning all of it
    is the search page again."""
    a_note(
        owner,
        "The caterer is called Bellini. They need eight days notice. "
        "The venue closes at eleven.",
    )

    answer = ask.answer(owner, "caterer")

    assert "venue closes" not in answer.passages[0].text


def test_it_invents_nothing(db, owner):
    """The property that matters most, asserted directly: every passage is a
    substring of something the person actually wrote.

    A second mind that writes new prose about your life is one you have to
    fact-check, and then the store's whole value is gone.
    """
    note = a_note(owner, "The caterer is called Bellini. They need eight days notice.")

    answer = ask.answer(owner, "caterer notice")

    for passage in answer.passages:
        assert passage.text in note.original_content


def test_a_question_with_no_answer_says_so(db, owner):
    """An answer assembled from nothing looks exactly like an answer, which is
    the failure a question box invites."""
    a_note(owner, "the venue closes at eleven")

    answer = ask.answer(owner, "aardvark")

    assert answer.passages == []
    assert not answer.found_anything


# ---------------------------------------------------------------------------
# Cited — where each answer came from
# ---------------------------------------------------------------------------


def test_every_passage_names_the_note_it_came_from(db, owner):
    note = a_note(owner, "The caterer is called Bellini.")

    answer = ask.answer(owner, "caterer")

    assert answer.passages[0].node.pk == note.pk


def test_every_passage_says_why_that_note_was_reached(db, owner):
    """Increment 9's explanation, carried through. A note reached by concept
    rather than by the typed word is baffling without it."""
    note = a_note(owner, "She is called Bellini.")
    concept = services.propose_concept(
        owner, label="caterer", concept_type=ConceptType.UNKNOWN, now=WRITTEN, actor="s"
    )
    services.confirm_concept(concept, now=WRITTEN, actor="vince")
    services.propose_mention(
        note,
        concept,
        index_version="manual",
        origin=InferenceOrigin.EXPLICIT,
        now=WRITTEN,
        actor="vince",
    )

    answer = ask.answer(owner, "caterer")

    assert "caterer" in answer.passages[0].why


def test_a_note_reached_by_concept_still_yields_a_passage(db, owner):
    """The word is not in the note at all, so a passage picker that needed a
    keyword match would return the note with nothing to show for it."""
    a_note(owner, "She is called Bellini and needs eight days notice.")
    concept = services.propose_concept(
        owner, label="caterer", concept_type=ConceptType.UNKNOWN, now=WRITTEN, actor="s"
    )
    services.confirm_concept(concept, now=WRITTEN, actor="vince")
    services.propose_mention(
        Node.objects.get(original_content__startswith="She is called"),
        concept,
        index_version="manual",
        origin=InferenceOrigin.EXPLICIT,
        now=WRITTEN,
        actor="vince",
    )

    answer = ask.answer(owner, "caterer")

    assert answer.passages
    assert answer.passages[0].text.strip()


# ---------------------------------------------------------------------------
# Per-mode — and the rule is arguable
# ---------------------------------------------------------------------------


def test_an_ordinary_question_is_a_lookup(db, owner):
    a_note(owner, "The caterer is called Bellini.")

    answer = ask.answer(owner, "what is the caterer called")

    assert answer.mode.value == "lookup"


def test_a_question_about_when_is_a_recollection(db, owner):
    """*What else was going on* is a different kind of remembering, and
    answering it in Lookup would return the note and nothing around it."""
    a_note(owner, "The caterer is called Bellini.")
    a_note(owner, "the venue closes at eleven", when=later(minutes=20))

    answer = ask.answer(owner, "what else was going on when I wrote about the caterer")

    assert answer.mode.value == "recollection"


def test_a_recollection_answers_from_around_the_anchor(db, owner):
    a_note(owner, "The caterer is called Bellini.")
    a_note(owner, "the venue closes at eleven", when=later(minutes=20))

    answer = ask.answer(owner, "what else was going on when I wrote about the caterer")

    assert "venue closes at eleven" in " ".join(p.text for p in answer.passages)


def test_a_recollection_with_nothing_to_anchor_on_falls_back_and_says_so(db, owner):
    """The honest half of the rule. *When did I write about aardvarks* is a
    Recollection question with no note to recollect around, and silently
    answering something else is how a surface teaches somebody to distrust it.
    """
    answer = ask.answer(owner, "what else was going on when I wrote about aardvarks")

    assert not answer.found_anything
    assert "nothing to anchor" in answer.why_this_mode.lower()


def test_the_page_says_which_kind_of_remembering_it_did(signed_in, owner):
    """A rule can be argued with where a score cannot -- but only if the page
    says which rule fired."""
    a_note(owner, "The caterer is called Bellini.")

    body = asking(signed_in, "what is the caterer called").content.decode()

    assert "looked it up" in body.lower() or "lookup" in body.lower()


# ---------------------------------------------------------------------------
# The surface
# ---------------------------------------------------------------------------


def test_the_page_answers_and_cites(signed_in, owner):
    note = a_note(owner, "The caterer is called Bellini. They need eight days notice.")

    body = asking(signed_in, "caterer").content.decode()

    assert "The caterer is called Bellini." in body
    assert f"/mind/notes/{note.public_id}/" in body


def test_the_page_with_no_question_asks_one(signed_in, owner):
    body = signed_in.get("/mind/ask/").content.decode()

    assert "<form" in body


def test_the_page_says_when_it_does_not_know(signed_in, owner):
    a_note(owner, "the venue closes at eleven")

    body = asking(signed_in, "aardvark").content.decode()

    assert "nothing" in body.lower()


def test_asking_requires_signing_in(client):
    response = client.get("/mind/ask/", {"q": "caterer"})

    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


def test_it_does_not_answer_from_another_persons_memory(db, owner, other_owner):
    a_note(other_owner, "The caterer is called Bellini.")

    answer = ask.answer(owner, "caterer")

    assert answer.passages == []


def test_a_deleted_note_answers_nothing(db, owner):
    note = a_note(owner, "The caterer is called Bellini.")
    services.delete_node(note, now=later(days=1), actor="vince")

    answer = ask.answer(owner, "caterer")

    assert answer.passages == []


# ---------------------------------------------------------------------------
# The rule that decides what to anchor on, which is load-bearing
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "question,subject",
    [
        ("what else was going on when I wrote about the caterer", "the caterer"),
        ("what was going on around the time of the venue visit", "venue visit"),
        ("what else was going on that morning", ""),
    ],
)
def test_it_works_out_what_to_anchor_on(question, subject):
    """The first version returned the whole tail of the question -- *"was going
    on when I wrote about the caterer"* -- which ANDs into a query matching
    nothing, so every recollection answered empty while looking like it had
    tried.

    Two rules in order and both readable: everything after the last *about*,
    or the words left once cue and filler are removed.
    """
    assert ask._subject_of(question) == subject


def test_the_ask_page_is_in_the_navigation(signed_in, owner):
    """The failure this sequence has shipped twice -- the calendar and the
    bills month, both reachable only from one link nobody found."""
    body = signed_in.get("/mind/").content.decode()

    assert "/mind/ask/" in body


def test_a_question_asked_in_words_still_finds_the_answer(db, owner):
    """The defect the browser found, and the one this box invites most.

    *"What did I say about the venue"* went to the full-text index verbatim,
    which ANDs its terms -- so no note contained *what* and *did* and *say*,
    and the page replied that nothing answered it while the answer sat two
    lines away. **A question box that only works when you type keywords is a
    search box with a longer placeholder.**

    Fixed with the rule already written for anchoring, applied to both modes:
    the scaffolding of a question is not part of what is being asked.
    """
    a_note(owner, "The venue closes at eleven.")

    answer = ask.answer(owner, "what did I say about the venue")

    assert answer.found_anything
    assert "venue closes at eleven" in answer.passages[0].text


def test_a_question_of_only_scaffolding_finds_nothing_and_says_so(db, owner):
    """The other end of the same rule: strip everything and there is no
    question left, which is not the same as an answer being absent."""
    a_note(owner, "The venue closes at eleven.")

    answer = ask.answer(owner, "what did I say")

    assert not answer.found_anything


def test_the_explanation_names_the_words_that_actually_matched(db, owner):
    """It read *"it says say venue"* -- the stripped query, including a word
    the note does not contain. Increment 9 exists so somebody can argue with
    an answer, and an explanation naming words that are not there is one more
    thing to distrust."""
    a_note(owner, "The venue closes at eleven.")

    answer = ask.answer(owner, "what did I say about the venue")

    assert answer.passages[0].why == "it says venue"


def test_an_answer_from_wording_since_corrected_says_so(db, owner):
    """The search page labels this and the question box did not: a note found
    through text its author edited away answers with a passage that does not
    contain the word asked about, which is baffling rather than wrong.

    `original_content` is kept on purpose, so finding it is the design working
    -- and saying which version matched is what makes that legible.
    """
    note = a_note(owner, "The venue closes at eleven.")
    services.revise(note, body="Sorted, nothing outstanding.", now=later(days=1), actor="vince")

    answer = ask.answer(owner, "venue")

    assert answer.passages[0].from_earlier_wording


def test_a_note_that_only_once_said_it_says_that_instead(db, owner):
    """The fallback claimed the whole query when nothing survived the edit --
    *"it says say venue"* on a note that now says neither word. True of the
    note's history and false of the note, which is the wrong way round for a
    sentence beginning *it says*."""
    note = a_note(owner, "The venue closes at eleven.")
    services.revise(note, body="Sorted, nothing outstanding.", now=later(days=1), actor="vince")

    answer = ask.answer(owner, "venue")

    assert answer.passages[0].why.startswith("it once said")
