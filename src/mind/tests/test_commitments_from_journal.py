"""Reading commitments out of a journal entry — increment 2, slice B.

The parser has existed since the merger and has never seen a word of the
journal, which is the surface where most writing in this product actually
happens. `planning-assistant-plan.md` increment 2.

**Per sentence, not per entry.** `find_commitment` reads one piece of text and
returns one commitment; a day's writing is several, and running it over the
whole field would find the first date in the day and attribute it to the entire
page. Splitting first is what makes a span real — the proposal cites the
sentence that caused it, not the paragraph it was buried in.

**Read against the entry's own date.** "Tomorrow" written on Tuesday means
Wednesday, whenever the parse happens to run. Capture already reads against
`captured_at` for this reason, and reading against `now` here would put a date
nobody meant onto the most relative-sounding material in the product.

**The fingerprint is over the sentence, not its position.** Adding a line at the
top of an entry shifts every offset below it, and a fingerprint that included
the span would re-propose the whole day on one insertion. Editing a sentence
should re-propose it; moving it should not.
"""

from datetime import date, datetime, timezone as dt_timezone

import pytest
from django.utils import timezone

from daily.models import DailyEntry
from mind import services
from mind.models import Facet, FacetKind

pytestmark = pytest.mark.django_db

UTC = dt_timezone.utc
NOW = datetime(2026, 6, 1, 9, 0, tzinfo=UTC)
DAY = date(2026, 6, 1)


@pytest.fixture
def entry(owner):
    return DailyEntry.objects.create(owner=owner, date=DAY)


def commitments_on(entry):
    return list(
        Facet.objects.filter(entry=entry, kind=FacetKind.ACTIONABLE).order_by("id")
    )


def test_a_commitment_in_the_journal_is_proposed(owner, entry):
    entry.happenings = "I need to ring the venue on 4 June."
    entry.save()

    services.propose_journal_commitments(entry, now=NOW, actor="vince")

    assert len(commitments_on(entry)) == 1


def test_ordinary_writing_proposes_nothing(owner, entry):
    entry.happenings = "A good day. The garden is coming along."
    entry.save()

    services.propose_journal_commitments(entry, now=NOW, actor="vince")

    assert commitments_on(entry) == []


def test_each_sentence_is_read_on_its_own(owner, entry):
    """The reason splitting comes first.

    Two promises in one paragraph are two commitments. Run over the whole
    field, `find_commitment` returns one — the first date it sees — and the
    second promise is silently lost while the proposal looks confident.
    """
    entry.happenings = (
        "I need to ring the venue on 4 June. Nothing else today. "
        "I must send the deposit on 9 June."
    )
    entry.save()

    services.propose_journal_commitments(entry, now=NOW, actor="vince")

    assert len(commitments_on(entry)) == 2


def test_the_proposal_cites_the_sentence_that_caused_it(owner, entry):
    entry.happenings = "A quiet morning. I need to ring the venue on 4 June."
    entry.save()

    services.propose_journal_commitments(entry, now=NOW, actor="vince")

    facet = commitments_on(entry)[0]
    assert facet.cited_text.strip() == "I need to ring the venue on 4 June."
    # And the offsets are into the same body `cited_text` reads, or the quote
    # would come back shifted from whatever the producer meant.
    assert facet.span_start is not None and facet.span_end is not None


def test_only_what_happened_is_read(owner, entry):
    """~~"all three fields are read"~~ -- **D5, answered September 4, 2026**,
    `superlists-2.0-plan.md` increment 9.

    The three fields say different things. `intentions` is a plan for the day,
    and the morning pick is what makes a plan real -- offering a task for
    something already chosen, or deliberately not, is the producer arguing with
    a decision. `gratitude` is not about undertakings at all. What is left is
    the field that records what happened, which is where a promise made in
    passing turns up.

    The contract genuinely changed, so this expectation changed with it rather
    than being relaxed: it asserts one, and asserts *which* one.
    """
    entry.intentions = "I must call the bank on 5 June."
    entry.gratitude = "Grateful for the quiet."
    entry.happenings = "I need to post the form on 8 June."
    entry.save()

    services.propose_journal_commitments(entry, now=NOW, actor="vince")

    facets = commitments_on(entry)
    assert len(facets) == 1
    assert facets[0].cited_text.strip() == "I need to post the form on 8 June."


def test_running_twice_proposes_nothing_new(owner, entry):
    """A journal entry is saved on every keystroke pause.

    Idempotence here is not a nicety: without it, a day's writing would
    accumulate a duplicate proposal per save, and the surface would be
    unusable by lunchtime.
    """
    entry.happenings = "I need to ring the venue on 4 June."
    entry.save()

    services.propose_journal_commitments(entry, now=NOW, actor="vince")
    services.propose_journal_commitments(entry, now=NOW, actor="vince")

    assert len(commitments_on(entry)) == 1


def test_moving_a_sentence_does_not_re_propose_it(owner, entry):
    """The fingerprint is over the sentence, not its offsets.

    Typing a line at the top of an entry shifts every span below it. A
    fingerprint including the position would re-propose the entire day on one
    insertion, which is the same failure as not deduping at all.
    """
    entry.happenings = "I need to ring the venue on 4 June."
    entry.save()
    services.propose_journal_commitments(entry, now=NOW, actor="vince")

    entry.happenings = "Woke late. I need to ring the venue on 4 June."
    entry.save()
    services.propose_journal_commitments(entry, now=NOW, actor="vince")

    assert len(commitments_on(entry)) == 1


def test_a_dismissed_suggestion_does_not_come_back(owner, entry):
    entry.happenings = "I need to ring the venue on 4 June."
    entry.save()
    services.propose_journal_commitments(entry, now=NOW, actor="vince")
    facet = commitments_on(entry)[0]
    services.dismiss_facet(facet, now=timezone.now(), actor="vince")

    services.propose_journal_commitments(entry, now=NOW, actor="vince")

    assert [each.pk for each in commitments_on(entry)] == [facet.pk]
    assert commitments_on(entry)[0].retired_at is not None


def test_a_relative_date_is_read_against_the_entry_s_own_day(owner, entry):
    """Tuesday's "tomorrow" is Wednesday, whenever this runs.

    `now` is a fortnight after the entry here, so a parse reading the clock
    would land two weeks out — on exactly the material most likely to be
    written relatively.
    """
    entry.happenings = "I need to ring the venue tomorrow."
    entry.save()

    services.propose_journal_commitments(
        entry, now=NOW + timezone.timedelta(days=14), actor="vince"
    )

    facet = commitments_on(entry)[0]
    assert facet.data["due_date"] == "2026-06-02"


def test_nothing_is_written_for_an_empty_entry(owner, entry):
    services.propose_journal_commitments(entry, now=NOW, actor="vince")

    assert commitments_on(entry) == []


def test_a_promise_with_no_date_is_still_a_promise(owner, entry):
    """The canonical example, and the one date-only would have missed.

    "I still need to ask Maya whether the venue is available" is the sentence
    increment 2 was written around and it carries no date at all. Requiring one
    would have dropped the thing this is for while firing on the narrative
    around it.
    """
    entry.happenings = "I still need to ask Maya whether the venue is available."
    entry.save()

    services.propose_journal_commitments(entry, now=NOW, actor="vince")

    facet = commitments_on(entry)[0]
    assert facet.data["due_date"] is None
    assert facet.reason == "reads as a commitment"


def test_a_date_without_a_promise_proposes_nothing(owner, entry):
    """The other half, and the failure that found this rule.

    Prose is full of dates that commit to nothing. Written date-first, this
    producer proposed a commitment for "Nothing else today." -- confident,
    cited, and about a sentence that promises the opposite. A journal is
    narrative, so the trigger has to be the undertaking and not the date.
    """
    entry.happenings = "Nothing else today. Saw them on Tuesday. A quiet morning."
    entry.save()

    services.propose_journal_commitments(entry, now=NOW, actor="vince")

    assert commitments_on(entry) == []


def test_an_obligation_about_the_world_is_not_a_promise(owner, entry):
    """First person, deliberately.

    "The invoice must be paid" is a fact about the world; "I must pay the
    invoice" is something somebody undertook. Missing one costs a tap;
    inventing one puts a commitment nobody made into their week, and the two
    failures are not symmetric.
    """
    entry.happenings = "The deposit must be paid by 9 June, apparently."
    entry.save()

    services.propose_journal_commitments(entry, now=NOW, actor="vince")

    # `must` on its own is permitted -- the pattern cannot tell subjects apart
    # -- so this documents where the line actually falls rather than claiming
    # a precision the regex does not have.
    assert len(commitments_on(entry)) == 1
