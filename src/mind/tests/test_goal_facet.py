"""A note that is a project's outcome — `FacetKind.GOAL`, wired at last.

v3's *Unify* asks for **`FacetKind.GOAL` wired to `Project.outcome`, as
`EPISTEMIC` was.** `GOAL` has been declared since the merger and nothing has
ever written one — it is in the August 21 inventory's
*declared-but-never-written vocabulary*, beside `THREAD_ARTICULATED` and three
`EdgeRelation` values.

**`EPISTEMIC` is the precedent and this follows it exactly.** That one was
declared and unwritten too, and `open_question.py` had settled for reading
question-shaped text *"because the lab has no facet table"* — a substitution to
revisit once one existed. This is the same revisit, for the other kind.

**What it buys is the direction that did not exist.** `Project.desired_outcome`
is a text field somebody types. A `GOAL` facet says *this note is that
outcome*, which means the sentence a person actually wrote — with its capture
time, its concepts and its own life — becomes the project's stated end, rather
than a paraphrase of it living in a second place free to drift.

**One live goal per node**, which is `facet_one_live_per_kind` doing what it
was built for: changing your mind is a change of goal, not a second opinion
beside the first.
"""

import datetime

import pytest

from lists.models import Project
from mind import services
from mind.models import EventType, Facet, FacetKind, InferenceOrigin, Node


NOW = datetime.datetime(2026, 5, 4, 9, 0, tzinfo=datetime.timezone.utc)


@pytest.fixture
def note(owner):
    return services.capture(
        owner,
        content="the wedding should feel small and unhurried",
        captured_at=NOW,
        source=Node.Source.WEB,
        actor="vince",
    )


@pytest.fixture
def project(owner):
    return Project.objects.create(owner=owner, title="The wedding")


def goal_of(node):
    return node.facets.filter(kind=FacetKind.GOAL, retired_at__isnull=True).first()


# ---------------------------------------------------------------------------
# Wiring it
# ---------------------------------------------------------------------------


def test_a_note_can_be_a_projects_outcome(db, note, project):
    services.make_it_the_goal(note, project, now=NOW, actor="vince")

    assert goal_of(note) is not None


def test_the_facet_names_the_project(db, note, project):
    services.make_it_the_goal(note, project, now=NOW, actor="vince")

    assert goal_of(note).data["project"] == project.pk


def test_the_project_takes_the_notes_own_words(db, note, project):
    """**The direction that did not exist.** `desired_outcome` is a text field
    somebody types; this makes the sentence they actually wrote the project's
    stated end, rather than a paraphrase living in a second place free to
    drift."""
    services.make_it_the_goal(note, project, now=NOW, actor="vince")

    project.refresh_from_db()
    assert project.desired_outcome == "the wedding should feel small and unhurried"


def test_it_is_a_persons_statement_not_a_guess(db, note, project):
    """`origin=EXPLICIT`, always -- the rule `_set_epistemic_status` states for
    the same reason: a decision nobody can tell from a guess is one nobody can
    argue with later."""
    services.make_it_the_goal(note, project, now=NOW, actor="vince")

    assert goal_of(note).origin == InferenceOrigin.EXPLICIT


def test_it_is_written_to_the_log(db, note, project):
    services.make_it_the_goal(note, project, now=NOW, actor="vince")

    assert note.events.filter(
        event_type=EventType.FACET_CONFIRMED
    ).exists()


# ---------------------------------------------------------------------------
# Changing your mind
# ---------------------------------------------------------------------------


def test_naming_a_second_goal_replaces_the_first(db, owner, note, project):
    """`facet_one_live_per_kind` doing what it was built for: one live goal per
    node, so changing your mind is a change rather than a second opinion."""
    other = Project.objects.create(owner=owner, title="The book")
    services.make_it_the_goal(note, project, now=NOW, actor="vince")

    services.make_it_the_goal(note, other, now=NOW, actor="vince")

    assert goal_of(note).data["project"] == other.pk
    assert Facet.objects.filter(node=note, kind=FacetKind.GOAL).count() == 1


def test_saying_the_same_thing_twice_is_not_two_decisions(db, note, project):
    """The emitter-contract instinct again, in a module that writes to a table
    which refuses DELETE."""
    services.make_it_the_goal(note, project, now=NOW, actor="vince")
    services.make_it_the_goal(note, project, now=NOW, actor="vince")

    assert note.events.filter(event_type=EventType.FACET_CONFIRMED).count() == 1


# ---------------------------------------------------------------------------
# Refusals
# ---------------------------------------------------------------------------


def test_a_project_of_somebody_elses_is_refused(db, note, other_owner):
    theirs = Project.objects.create(owner=other_owner, title="Theirs")

    with pytest.raises(services.NotYours):
        services.make_it_the_goal(note, theirs, now=NOW, actor="vince")


def test_a_deleted_note_cannot_be_a_goal(db, note, project):
    services.delete_node(note, now=NOW, actor="vince")

    with pytest.raises(services.Deleted):
        services.make_it_the_goal(note, project, now=NOW, actor="vince")


def test_goal_is_no_longer_declared_and_never_written(db, note, project):
    """The inventory's phrase, and the point of the increment. This is the
    assertion that would fail if the wiring were removed and the value left
    sitting in the enum."""
    services.make_it_the_goal(note, project, now=NOW, actor="vince")

    assert Facet.objects.filter(kind=FacetKind.GOAL).exists()
