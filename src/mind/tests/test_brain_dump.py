"""Emptying your head — Track D increment 14.

**The highest-bandwidth intake surface there is, and it costs a text box.**
Everything on your mind, no decisions about what any of it is.

**Safe only because increment 13 exists**, which is why the plan orders them
that way and calls the order *the whole safety of the feature*: without
session-aware budgeting, the first dump is the one that teaches somebody to
skim past the review surface, and that is not recoverable.

**A fragment is a submission, not a sentence.** Each *keep and continue* is one
fragment and one `Node`, and the person draws the boundaries. The brief is
blunt that an earlier draft implied otherwise: `services._SENTENCE` splits a
`DailyEntry` so the journal parser can cite the line that caused a proposal,
and **it has never created a `Node`**. A splitter exists; the splitting a dump
would need does not.

**A multiline paste is a product decision, not a parsing one.** If several
lines should become several memories, **show a preview and ask.** Never split a
submission silently — a dump is precisely the surface where a person is least
able to predict what the system did with what they typed.

**The ongoing ritual and orientation are the same surface** with different copy
and a different corpus behind them. What this ships is the ritual; increment 15
is the orientation flow and belongs to v3's *Usable* release.
"""

import pytest

from mind import services
from mind.models import CaptureSession, Facet, Node


@pytest.fixture
def signed_in(client, owner):
    client.force_login(owner)
    return client


def open_dump(client):
    return client.get("/mind/dump/")


def keep(client, text, **extra):
    return client.post("/mind/dump/", {"content": text, **extra})


def fragments(owner):
    return list(
        Node.objects.filter(owner=owner, session__isnull=False).order_by("captured_at")
    )


# ---------------------------------------------------------------------------
# One keep, one fragment, one node
# ---------------------------------------------------------------------------


def test_opening_the_page_starts_a_sitting(signed_in, owner):
    open_dump(signed_in)

    assert CaptureSession.objects.filter(owner=owner, processed_at=None).count() == 1


def test_reopening_does_not_start_a_second(signed_in, owner):
    """A refresh mid-dump is ordinary, and two sittings for one would split the
    budget the sitting was given."""
    open_dump(signed_in)
    open_dump(signed_in)

    assert CaptureSession.objects.filter(owner=owner).count() == 1


def test_each_keep_is_one_fragment(signed_in, owner):
    open_dump(signed_in)
    keep(signed_in, "the venue idea")
    keep(signed_in, "Mum's birthday is in March")

    assert [n.original_content for n in fragments(owner)] == [
        "the venue idea",
        "Mum's birthday is in March",
    ]


def test_a_fragment_belongs_to_the_sitting(signed_in, owner):
    open_dump(signed_in)
    keep(signed_in, "the venue idea")

    assert fragments(owner)[0].session is not None


def test_nothing_is_proposed_while_the_dump_is_open(signed_in, owner):
    """Rule 2 reaching the surface. Forty proposals mid-flow is the failure the
    whole ordering exists to prevent."""
    open_dump(signed_in)
    keep(signed_in, "call the dentist by Friday")

    assert not Facet.objects.exists()


def test_an_empty_keep_records_nothing(signed_in, owner):
    open_dump(signed_in)
    keep(signed_in, "   ")

    assert fragments(owner) == []


# ---------------------------------------------------------------------------
# Multiline paste — preview and ask, never a silent split
# ---------------------------------------------------------------------------


def test_a_multiline_paste_is_not_split_silently(signed_in, owner):
    """**The refusal, and the plan lists it among the non-negotiable ones.** A
    dump is where a person is least able to predict what the system did with
    what they typed."""
    open_dump(signed_in)
    keep(signed_in, "the venue idea\nMum's birthday\ncall the dentist")

    assert len(fragments(owner)) <= 1


def test_a_multiline_paste_is_offered_as_several(signed_in, owner):
    """Asked, not guessed. The preview is the product decision the brief says
    this is."""
    open_dump(signed_in)
    response = keep(signed_in, "the venue idea\nMum's birthday\ncall the dentist")
    body = response.content.decode()

    assert "three separate" in body.lower() or "3 separate" in body
    assert "the venue idea" in body


def test_saying_keep_them_separately_makes_several(signed_in, owner):
    open_dump(signed_in)
    keep(signed_in, "the venue idea\nMum's birthday\ncall the dentist", split="yes")

    assert len(fragments(owner)) == 3


def test_saying_keep_it_as_one_makes_one(signed_in, owner):
    open_dump(signed_in)
    keep(signed_in, "the venue idea\nMum's birthday", split="no")

    assert len(fragments(owner)) == 1
    assert "\n" in fragments(owner)[0].original_content


def test_a_single_line_is_never_asked_about(signed_in, owner):
    """The question is worth asking once in a while and unbearable every time."""
    open_dump(signed_in)
    response = keep(signed_in, "the venue idea")

    assert "separate" not in response.content.decode().lower()
    assert len(fragments(owner)) == 1


# ---------------------------------------------------------------------------
# Ending it is when anything comes back
# ---------------------------------------------------------------------------


def test_finishing_runs_the_producers_once(signed_in, owner):
    open_dump(signed_in)
    keep(signed_in, "call the dentist by Friday")
    signed_in.post("/mind/dump/done/")

    assert Facet.objects.exists()


def test_finishing_shows_at_most_the_attention_budget(signed_in, owner):
    open_dump(signed_in)
    for index in range(10):
        keep(signed_in, f"call the dentist by Friday about {index}")

    response = signed_in.post("/mind/dump/done/", follow=True)
    body = response.content.decode()

    assert body.count("call the dentist") <= services.SESSION_ATTENTION_BUDGET


def test_finishing_an_empty_sitting_says_so_rather_than_nothing(signed_in, owner):
    open_dump(signed_in)

    body = signed_in.post("/mind/dump/done/", follow=True).content.decode()

    assert "nothing" in body.lower()


def test_the_dump_is_in_the_navigation(signed_in, owner):
    body = signed_in.get("/mind/").content.decode()

    assert "/mind/dump/" in body


def test_dumping_requires_signing_in(client):
    response = client.get("/mind/dump/")

    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


def test_one_person_never_dumps_into_anothers_sitting(db, client, owner, other_owner):
    theirs = services.begin_capture_session(other_owner, now=None or __import__(
        "django.utils.timezone", fromlist=["timezone"]
    ).now())
    client.force_login(owner)
    open_dump(client)
    keep(client, "mine")

    assert not Node.objects.filter(session=theirs).exists()
