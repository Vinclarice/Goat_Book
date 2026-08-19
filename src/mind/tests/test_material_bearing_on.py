"""What have I already written that bears on this? — the retrieval behind a brief.

`planning-assistant-plan.md` increment 4. Anchored on a statement the person
wrote themselves, which is the whole of why this is allowed to exist at all.

**"Compute similarity, show related notes" is a named failure in this codebase**
(`detectors/__init__.py`): it produces a panel of vaguely on-topic material that
is technically correct and reliably ignored, because topical relatedness answers
no question anybody asked. Three things separate this from that failure, and all
three are pinned below.

* **It is anchored.** One end is a project's stated purpose — a decision a person
  made and wrote down — which is `precision.md`'s Tier 2, the tier the concept
  detector already works in. The anchor does the precision work.
* **It is asked for.** A brief is opened, never pushed. The Attention Policy
  permits a queue inside a ritual the person chose to start, and this is one.
* **The gate is rarity, not a score.** `min_distinctive_terms` is the mechanism
  that took the lexical detector from 11% to 67% precision, and reusing it here
  is the reason a project brief is not the ignored panel. Shared *common* words
  must not surface anything, and `test_common_words_alone_surface_nothing` is
  the test that would fail first if somebody swapped the gate for a threshold.

**No purpose, no material.** A project nobody has described anchors nothing, and
the honest answer is silence rather than the whole corpus ranked by coincidence.
"""

from datetime import datetime, timedelta, timezone as dt_timezone

import pytest

from mind import queries, services
from mind.models import ActivityEvent, NodeSource

pytestmark = pytest.mark.django_db

UTC = dt_timezone.utc
NOW = datetime(2026, 6, 1, 9, 0, tzinfo=UTC)

PURPOSE = (
    "Replace the enquiries inbox with a booking form so the venue stops "
    "losing bookings to email."
)


def _capture(owner, content, days_ago=30):
    return services.capture(
        owner,
        content=content,
        captured_at=NOW - timedelta(days=days_ago),
        source=NodeSource.WEB,
        actor="vince",
    )


def _nodes(results):
    return [result.node for result in results]


def test_a_note_sharing_distinctive_words_is_material(owner):
    relevant = _capture(
        owner,
        "The booking form should collect the venue and the enquiries contact "
        "in one step.",
    )
    _capture(owner, "Bought milk and walked to the park in the afternoon.")

    results = queries.material_bearing_on(owner, PURPOSE)

    assert _nodes(results) == [relevant]


def test_words_the_corpus_uses_everywhere_surface_nothing(owner):
    """The rare-term gate, which is the whole precision argument.

    A term is distinctive *to this person*, so the test has to make it
    unremarkable rather than pick words that sound ordinary. Once "form",
    "stop" and "lose" appear all over the corpus they stop carrying a match,
    and the note whose only overlap is those three drops out.

    This is the first thing that breaks if the gate is traded for a similarity
    threshold — the coincidental note would still score, and scoring is what
    measured at 11%.
    """
    for index in range(6):
        _capture(
            owner,
            f"Note {index}: a form to fill, a habit to stop, an hour to lose.",
            days_ago=200 + index,
        )
    coincidence = _capture(owner, "The form I keep meaning to stop losing time to.")
    genuine = _capture(
        owner,
        "The booking form should collect the venue and the enquiries contact.",
    )

    surfaced = _nodes(queries.material_bearing_on(owner, PURPOSE))

    # Both halves, or this passes by surfacing nothing at all.
    assert genuine in surfaced
    assert coincidence not in surfaced

    # And the gate is what excluded it, not some other filter: drop the gate
    # and the coincidence comes back. Without this the test above would still
    # pass if the note were being dropped for an unrelated reason, and the
    # precision argument would be resting on an accident.
    ungated = _nodes(
        queries.material_bearing_on(owner, PURPOSE, min_distinctive_terms=0)
    )
    assert coincidence in ungated


def test_a_note_sharing_only_stopwords_surfaces_nothing(owner):
    """The cheap half of the same argument.

    Postgres strips these before a term ever reaches the gate, so this is a
    statement about the text search configuration rather than about rarity —
    kept separate from the test above for exactly that reason.
    """
    _capture(owner, "The and so the with the to it of a for.")

    assert queries.material_bearing_on(owner, PURPOSE) == []


def test_every_result_carries_the_terms_that_selected_it(owner):
    """Evidence, not a score.

    "These share three words that appear in none of your other notes" is
    checkable; a confidence number is something the person has to trust. The
    brief shows the reason, so the reason has to exist here.
    """
    _capture(
        owner,
        "The booking form should collect the venue and the enquiries contact "
        "in one step.",
    )

    result = queries.material_bearing_on(owner, PURPOSE)[0]

    assert result.distinctive_terms
    assert result.reason
    for term in result.distinctive_terms:
        assert term in result.reason


def test_a_project_with_no_purpose_gets_nothing(owner):
    """Silence over a ranked corpus.

    An unanchored query is `precision.md`'s Tier 3, where every measured
    failure lives. A brief that answered an empty purpose with "here is
    everything, sorted by coincidence" would teach somebody to stop opening it.
    """
    _capture(owner, "The booking form should collect the venue and enquiries.")

    assert queries.material_bearing_on(owner, "") == []
    assert queries.material_bearing_on(owner, "   \n ") == []


def test_deleted_and_archived_material_is_not_offered(owner):
    deleted = _capture(
        owner, "The booking form collects the venue and enquiries contact."
    )
    archived = _capture(
        owner, "Enquiries about the venue should reach the booking form."
    )
    services.delete_node(deleted, now=NOW, actor="vince")
    services.archive_node(archived, now=NOW, actor="vince")

    assert queries.material_bearing_on(owner, PURPOSE) == []


def test_another_person_s_notes_are_never_material(owner, other_owner):
    """Adversarial: theirs is the only corpus with a match in it."""
    services.capture(
        other_owner,
        content="The booking form should collect the venue and enquiries.",
        captured_at=NOW - timedelta(days=30),
        source=NodeSource.WEB,
        actor="someone-else",
    )

    assert queries.material_bearing_on(owner, PURPOSE) == []


def test_the_strongest_match_comes_first(owner):
    """Ordered by share of the purpose's distinctive vocabulary.

    A brief is read from the top and its tail is skimmed, so the ordering is
    the part that decides whether the first thing seen was worth opening it for.
    """
    weaker = _capture(owner, "Enquiries keep arriving about the venue.")
    stronger = _capture(
        owner,
        "The booking form should collect the venue and the enquiries contact, "
        "so we stop losing bookings.",
    )

    results = queries.material_bearing_on(owner, PURPOSE)

    assert _nodes(results)[0] == stronger
    assert weaker in _nodes(results) or len(results) == 1


def test_the_limit_is_honoured(owner):
    """A brief is a briefing, not a search result page."""
    for index in range(6):
        _capture(
            owner,
            f"Booking form note {index}: the venue enquiries contact goes here.",
        )

    assert len(queries.material_bearing_on(owner, PURPOSE, limit=3)) <= 3


def test_reading_a_brief_writes_nothing(owner):
    """A read module that must stay one.

    The same statement `review/reads.py` makes about a week: a page view that
    recorded having been rendered would be history invented by looking. It
    matters more here than there, because the neighbouring mechanic does the
    opposite on purpose — loading `/mind/review/` stamps `first_surfaced_at`,
    since a proposal shown without starting its window makes silence
    meaningless. A brief proposes nothing, so it starts no window and records
    no surfacing, and the two behaviours must not be confused for each other.
    """
    _capture(owner, "The booking form should collect the venue and enquiries.")
    before = ActivityEvent.objects.count()

    queries.material_bearing_on(owner, PURPOSE)

    assert ActivityEvent.objects.count() == before
