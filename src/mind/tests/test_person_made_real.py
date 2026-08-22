"""Saying what kind of thing something is — Track E increment 20.

`ConceptType` has seven values and **production holds eleven concepts, every
one of them `unknown`**. The field has existed since the first slice; nothing
has ever set anything else, because no surface could. The August 21 inventory
listed it under *declared-but-never-written vocabulary*, beside
`THREAD_ARTICULATED` and three `EdgeRelation` values.

**A person is the type worth making real first**, and the plan says so: *"the
person page built from the concept page plus the facet and temporal joins."*
A name recurring across a year of notes is the thing a second mind is supposed
to be good at, and until the type exists every concept is one undifferentiated
list of mentions.

**No new event, and that is a decision rather than an oversight.** A type is
corrigible by design — the substrate brief refuses *asking what a thing is at
capture* and says roles are proposed and correctable. Increment 1's scope
sentence draws the same line for the log: *a log recording every keystroke of a
task's text is a log nobody can read.* Recording each correction of a
corrigible property would be that, in a table that cannot be corrected.
`ConceptCandidate.confirmed_at` already records the decision that matters —
that this is a thing at all.

**What the person page adds beyond the concept page** is the two joins the
plan names: the commitments that came out of notes mentioning them, and when
they appear across time. Neither is reachable from a list of mentions.
"""

from datetime import datetime, timedelta, timezone as dt_timezone

import pytest

from mind import services
from mind.models import ConceptType, FacetKind, InferenceOrigin, Node


WRITTEN = datetime(2026, 5, 4, 9, 0, tzinfo=dt_timezone.utc)


def later(**offset):
    return WRITTEN + timedelta(**offset)


@pytest.fixture
def signed_in(client, owner):
    client.force_login(owner)
    return client


@pytest.fixture
def maya(owner):
    concept = services.propose_concept(
        owner,
        label="Maya",
        concept_type=ConceptType.UNKNOWN,
        now=WRITTEN,
        actor="system",
    )
    return services.confirm_concept(concept, now=WRITTEN, actor="vince")


def a_note_mentioning(owner, concept, content, *, when=WRITTEN):
    node = services.capture(
        owner,
        content=content,
        captured_at=when,
        source=Node.Source.WEB,
        actor="vince",
    )
    services.propose_mention(
        node,
        concept,
        index_version="manual",
        origin=InferenceOrigin.EXPLICIT,
        now=when,
        actor="vince",
    )
    return node


def say_it_is(client, concept, kind):
    return client.post(
        f"/mind/concepts/{concept.public_id}/kind/", {"concept_type": kind}
    )


def concept_page(client, concept):
    return client.get(f"/mind/concepts/{concept.public_id}/")


# ---------------------------------------------------------------------------
# Saying what kind of thing it is
# ---------------------------------------------------------------------------


def test_a_concept_can_be_told_what_it_is(signed_in, maya):
    say_it_is(signed_in, maya, ConceptType.PERSON)

    maya.refresh_from_db()
    assert maya.concept_type == ConceptType.PERSON


def test_the_concept_page_offers_the_kinds(signed_in, maya):
    """Every value, not a curated few. The set is small and closed, and
    offering four of seven would make the other three unreachable in exactly
    the way the field has been unreachable until now."""
    body = concept_page(signed_in, maya).content.decode()

    for kind in ConceptType.values:
        assert kind in body


def test_it_can_be_corrected(signed_in, maya):
    """Corrigible by design: the substrate brief refuses asking what a thing is
    at capture precisely because the answer arrives later and changes."""
    say_it_is(signed_in, maya, ConceptType.PERSON)
    say_it_is(signed_in, maya, ConceptType.PROJECT)

    maya.refresh_from_db()
    assert maya.concept_type == ConceptType.PROJECT


def test_a_kind_nobody_offers_is_refused(signed_in, maya):
    say_it_is(signed_in, maya, "deity")

    maya.refresh_from_db()
    assert maya.concept_type == ConceptType.UNKNOWN


def test_saying_what_it_is_needs_a_post(signed_in, maya):
    response = signed_in.get(f"/mind/concepts/{maya.public_id}/kind/")

    assert response.status_code == 405


def test_nobody_types_another_persons_concept(client, other_owner, maya):
    client.force_login(other_owner)
    say_it_is(client, maya, ConceptType.PERSON)

    maya.refresh_from_db()
    assert maya.concept_type == ConceptType.UNKNOWN


def test_typing_requires_signing_in(client, maya):
    say_it_is(client, maya, ConceptType.PERSON)

    maya.refresh_from_db()
    assert maya.concept_type == ConceptType.UNKNOWN


# ---------------------------------------------------------------------------
# The person page
# ---------------------------------------------------------------------------


def person_page(client, concept):
    return client.get(f"/mind/people/{concept.public_id}/")


def test_a_person_has_a_page(signed_in, owner, maya):
    say_it_is(signed_in, maya, ConceptType.PERSON)
    a_note_mentioning(owner, maya, "ask Maya about the venue")

    response = person_page(signed_in, maya)

    assert response.status_code == 200
    assert "ask Maya about the venue" in response.content.decode()


def test_something_that_is_not_a_person_has_no_person_page(signed_in, maya):
    """A page called *people* that renders a motif is a page that means
    nothing. Redirected to the concept page rather than 404, because the
    concept is real and there is somewhere right to be."""
    say_it_is(signed_in, maya, ConceptType.MOTIF)

    response = person_page(signed_in, maya)

    assert response.status_code == 302
    assert f"/mind/concepts/{maya.public_id}/" in response["Location"]


def test_it_says_what_you_committed_to_that_involves_them(signed_in, owner, maya):
    """The first join the plan names, and the one a list of mentions cannot
    give: notes about somebody become tasks, and the tasks are the part with
    consequences."""
    from lists.models import List

    say_it_is(signed_in, maya, ConceptType.PERSON)
    node = a_note_mentioning(owner, maya, "ask Maya about the venue")
    area = List.objects.create(owner=owner, title="Home")
    facet = services.propose_facet(
        node,
        kind=FacetKind.ACTIONABLE,
        data={},
        now=later(hours=1),
        actor="vince",
        reason="looks like a commitment",
    )
    services.confirm_actionable(facet, area=area, now=later(hours=1), actor="vince")

    body = person_page(signed_in, maya).content.decode()

    assert "ask Maya about the venue" in body


def test_it_says_when_they_have_come_up(signed_in, owner, maya):
    """The second join: a name across time is the thing a second mind should be
    good at, and a flat list of mentions does not show it."""
    say_it_is(signed_in, maya, ConceptType.PERSON)
    a_note_mentioning(owner, maya, "met Maya at the thing", when=WRITTEN)
    a_note_mentioning(owner, maya, "Maya again about the venue", when=later(days=200))

    body = person_page(signed_in, maya).content.decode()

    assert "May 2026" in body
    assert "Nov 2026" in body


def test_a_person_nobody_has_written_about_says_so(signed_in, maya):
    """A page that renders three empty headings is indistinguishable from one
    that is broken -- the failure this project shipped twice in a week."""
    say_it_is(signed_in, maya, ConceptType.PERSON)

    body = person_page(signed_in, maya).content.decode()

    assert "Nothing" in body or "nothing" in body


def test_a_deleted_note_is_not_on_the_person_page(signed_in, owner, maya):
    """`live_nodes` is the one visibility rule, and a page that reached round
    it would hand back what somebody erased."""
    say_it_is(signed_in, maya, ConceptType.PERSON)
    node = a_note_mentioning(owner, maya, "something regretted")
    services.delete_node(node, now=later(days=1), actor="vince")

    assert "something regretted" not in person_page(signed_in, maya).content.decode()


def test_one_person_cannot_open_anothers_person_page(client, other_owner, maya):
    client.force_login(other_owner)

    assert person_page(client, maya).status_code in (302, 404)


def test_the_concept_page_links_to_the_person_page(signed_in, maya):
    """Findability, which is the failure this sequence has now shipped twice --
    the calendar, and bills. A page reachable only by typing its URL is the
    un-switched-on seam under a nicer name."""
    say_it_is(signed_in, maya, ConceptType.PERSON)

    body = concept_page(signed_in, maya).content.decode()

    assert f"/mind/people/{maya.public_id}/" in body
