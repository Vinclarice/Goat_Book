"""Saying how one note relates to another, by hand, on the note page.

**The manual act `EdgeRelation` was built for and never given.** That enum's own
docstring says its last three values *"exist because recording evolving thought
is a manual act -- which is the actual argument for typed relations rather than
one untyped link"*, and until now there was no manual act: `CONTRADICTS`,
`SUPERSEDES` and `DEVELOPED_FROM` had never been written, and `unlink` had no
caller. Declared dark on August 24, 2026, all four naming this surface as the
trigger.

**One missing surface, counted again.** `roadmap-history.md` records the same
finding at a larger size -- twelve dark services in `src/mind/`, eleven of them
the undo half of a live pair, and *"it was never twelve pieces of dead code: it
was one missing surface, listed eleven times."* Track E gave the note page its
reading half and said so explicitly: *"read-only on purpose... nine dark
services are waiting on this page and they stay dark."* This is some of the
other half.

**Candidates come from what the page already surfaced, then from recent notes**
-- rather than from a picker or a search box. Deciding which notes bear on this
one is retrieval's job and the page has just done it, so a search field beside
that answer would be a second opinion on the same question.

**Retrieval orders the list and does not bound it, and a test found the
difference.** The first version let retrieval decide membership outright, and
`test_the_three_manual_relations_are_all_offered` failed on a note whose
neighbours it did not surface: the form disappeared entirely, on exactly the
notes somebody is most likely to be reconciling. Recency fills the rest, which
is predictable where relevance is not -- *the one I wrote just before this* is a
real way to find a note.

**`unlink` is the undo, and it is why this can ship without a confirmation.**
`principles.md`: *undo has to exist, not merely be conceivable* -- where there
is none the act needs a confirmation whatever it looks like in principle. Here
there is one, it is on the same card, and it is the dark service this closes.
"""

from datetime import datetime, timezone as dt_timezone

import pytest

from mind import services
from mind.models import Edge, EdgeRelation, EventType, InferenceOrigin, NodeSource

pytestmark = pytest.mark.django_db

NOW = datetime(2026, 6, 10, 9, 0, tzinfo=dt_timezone.utc)
LATER = datetime(2026, 8, 1, 9, 0, tzinfo=dt_timezone.utc)


@pytest.fixture
def signed_in(client, owner):
    client.force_login(owner)
    return client


@pytest.fixture
def earlier_note(owner):
    return services.capture(
        owner,
        content="the shop should open at seven",
        captured_at=NOW,
        source=NodeSource.WEB,
        actor="vince",
    )


@pytest.fixture
def later_note(owner):
    return services.capture(
        owner,
        content="seven is too early, eight is the right opening time",
        captured_at=LATER,
        source=NodeSource.WEB,
        actor="vince",
    )


def relate(client, node, other, relation):
    return client.post(
        f"/mind/notes/{node.public_id}/relate/",
        {"other": str(other.public_id), "relation": relation},
    )


class TestSayingHowTwoNotesRelate:
    def test_a_person_can_record_that_one_note_supersedes_another(
        self, signed_in, later_note, earlier_note
    ):
        """The whole point of the typed relation: *I changed my mind, and this
        is where.*"""
        response = relate(signed_in, later_note, earlier_note, EdgeRelation.SUPERSEDES)

        assert response.status_code == 302
        edge = Edge.objects.get(from_node=later_note, to_node=earlier_note)
        assert edge.relation == EdgeRelation.SUPERSEDES

    def test_a_hand_made_link_is_explicit_rather_than_inferred(
        self, signed_in, later_note, earlier_note
    ):
        """`InferenceOrigin` is how a person's assertion is told apart from a
        detector's guess, and everything downstream that weighs confidence
        depends on the difference being recorded at the moment it is known."""
        relate(signed_in, later_note, earlier_note, EdgeRelation.CONTRADICTS)

        edge = Edge.objects.get(from_node=later_note, to_node=earlier_note)
        assert edge.origin == InferenceOrigin.EXPLICIT

    def test_the_three_manual_relations_are_all_offered(
        self, signed_in, later_note, earlier_note
    ):
        """The reason those three values exist. A form offering only
        `relates_to` would leave them exactly as dark as they were.

        `earlier_note` is here because there has to be something to link *to*:
        with one note the form correctly does not render, which is what the
        first version of this test failed on.
        """
        page = signed_in.get(f"/mind/notes/{later_note.public_id}/")

        rendered = page.content.decode()
        for relation in (
            EdgeRelation.CONTRADICTS,
            EdgeRelation.SUPERSEDES,
            EdgeRelation.DEVELOPED_FROM,
        ):
            assert relation.value in rendered

    def test_the_link_is_recorded_in_the_log(
        self, signed_in, later_note, earlier_note
    ):
        """A person's assertion about their own material is one of the acts the
        life log is for."""
        relate(signed_in, later_note, earlier_note, EdgeRelation.DEVELOPED_FROM)

        assert later_note.owner.events.filter(
            event_type=EventType.EDGE_CREATED
        ).exists()

    def test_the_new_connection_is_shown_on_the_page(
        self, signed_in, later_note, earlier_note
    ):
        """*Failure is recoverable and visible* has a positive form too: an act
        whose result the page does not show leaves somebody pressing it twice."""
        relate(signed_in, later_note, earlier_note, EdgeRelation.SUPERSEDES)

        page = signed_in.get(f"/mind/notes/{later_note.public_id}/")
        assert "supersedes" in page.content.decode()

    def test_a_note_cannot_be_related_to_itself(self, signed_in, later_note):
        """The service refuses it; the view must not turn that refusal into a
        500. *Guards fail closed.*"""
        response = relate(signed_in, later_note, later_note, EdgeRelation.SUPERSEDES)

        assert response.status_code == 302
        assert not Edge.objects.filter(from_node=later_note).exists()

    def test_another_persons_note_cannot_be_related_to(
        self, signed_in, later_note, other_owner
    ):
        """The isolation test `principles.md` requires of every owner-scoped,
        ID-taking surface -- and this one takes two ids, so it is the more
        interesting case: the target is the one that could leak."""
        theirs = services.capture(
            other_owner,
            content="not yours",
            captured_at=NOW,
            source=NodeSource.WEB,
            actor="them",
        )

        response = relate(signed_in, later_note, theirs, EdgeRelation.RELATES_TO)

        assert response.status_code == 302
        assert not Edge.objects.filter(to_node=theirs).exists()


class TestTakingItBack:
    def test_a_person_can_remove_a_connection_they_made(
        self, signed_in, later_note, earlier_note
    ):
        """`unlink`'s door. The undo half of the pair, and the reason the form
        above needs no confirmation."""
        relate(signed_in, later_note, earlier_note, EdgeRelation.SUPERSEDES)
        edge = Edge.objects.get(from_node=later_note, to_node=earlier_note)

        response = signed_in.post(
            f"/mind/notes/{later_note.public_id}/unrelate/", {"edge": str(edge.pk)}
        )

        assert response.status_code == 302
        assert not Edge.objects.filter(pk=edge.pk).exists()

    def test_removing_a_connection_is_recorded(
        self, signed_in, later_note, earlier_note
    ):
        """The edge goes and the fact that it was there does not. *Preserve
        durable records and meaningful history* -- an assertion having been made
        and withdrawn is two things that happened, not zero."""
        relate(signed_in, later_note, earlier_note, EdgeRelation.SUPERSEDES)
        edge = Edge.objects.get(from_node=later_note, to_node=earlier_note)

        signed_in.post(
            f"/mind/notes/{later_note.public_id}/unrelate/", {"edge": str(edge.pk)}
        )

        assert later_note.owner.events.filter(
            event_type=EventType.EDGE_REMOVED
        ).exists()

    def test_another_persons_edge_cannot_be_removed(
        self, signed_in, later_note, other_owner
    ):
        """The same isolation question on the undo half, where it is easier to
        forget: the id being posted is an edge's, not a note's."""
        theirs_from = services.capture(
            other_owner, content="a", captured_at=NOW,
            source=NodeSource.WEB, actor="them",
        )
        theirs_to = services.capture(
            other_owner, content="b", captured_at=NOW,
            source=NodeSource.WEB, actor="them",
        )
        theirs = services.link(
            theirs_from, theirs_to,
            relation=EdgeRelation.RELATES_TO, now=NOW, actor="them",
        )

        response = signed_in.post(
            f"/mind/notes/{later_note.public_id}/unrelate/", {"edge": str(theirs.pk)}
        )

        assert response.status_code == 302
        assert Edge.objects.filter(pk=theirs.pk).exists()
