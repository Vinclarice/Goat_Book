"""Moving the Inbox into the graph.

Step 3 of `design/one-capture-surface-plan.md`, and the step whose value is not
the one it looks like. Draining 8 untriaged captures is the obvious reason. The
better one is the other 26.

**The corpus is the binding constraint on this entire core.** Three of the five
detectors rest on argument rather than evidence purely because there is no
material; the gravity gate cannot see recurrence across four notes. Production
holds 34 captures with real timestamps spread over months, inside a model that
is being deleted. Moving them is not cleanup that happens to preserve data — it
is the step that gives the detectors something to work on, and it should run
before anybody judges whether they are any good.

Two rules govern the mapping, and both come from what a detector needs:

**Original timestamps, never now.** `captured_at` is when the thought happened.
Stamping an import with the moment it ran collapses months of history onto one
afternoon and makes every temporal detector wrong on exactly the material most
likely to trigger one — which `services.capture` already says in its own
docstring, and which this is the largest test of.

**Provenance survives.** A capture promoted to a task keeps that link, as a
confirmed actionable facet pointing at the Item that already exists. The graph
gains a node; the task does not gain a duplicate.
"""

from datetime import datetime, timedelta, timezone as dt_timezone

import pytest
from django.core.management import call_command

from capture.models import Capture, Idea
from lists.models import Item, List
from mind.models import (
    ConceptCandidate,
    Edge,
    EdgeRelation,
    Facet,
    FacetKind,
    Node,
    NodeSource,
)

pytestmark = pytest.mark.django_db

UTC = dt_timezone.utc
LONG_AGO = datetime(2026, 3, 2, 11, 0, tzinfo=UTC)
LATER = datetime(2026, 5, 19, 8, 0, tzinfo=UTC)


@pytest.fixture
def area(owner):
    return List.objects.create(owner=owner, title="Home")


def a_capture(owner, text, *, when=LONG_AGO, tags=(), resolution=None, task=None,
              idea=None):
    capture = Capture.objects.create(
        owner=owner, text=text, resolution=resolution or "",
        promoted_task=task, promoted_idea=idea,
        resolved_at=when if resolution else None,
    )
    # created_at is auto_now_add, so the real capture date has to be written
    # afterwards -- which is the whole point of the test below.
    Capture.objects.filter(pk=capture.pk).update(created_at=when)
    if tags:
        from lists.services import resolve_tags
        capture.tags.set(resolve_tags(owner, list(tags)))
    capture.refresh_from_db()
    return capture


# ---------------------------------------------------------------------------
# The material
# ---------------------------------------------------------------------------


def test_every_capture_becomes_a_node(owner):
    a_capture(owner, "the boiler is making that noise")
    a_capture(owner, "look up the Indonesian phrase", when=LATER)

    call_command("migrate_inbox")

    assert Node.objects.count() == 2


def test_a_node_keeps_the_day_the_thought_happened(owner):
    """The rule the whole step turns on. Dormancy is measured *between* notes,
    so an import stamped with today would destroy the temporal spread on
    precisely the material that spread makes valuable."""
    a_capture(owner, "the boiler again", when=LONG_AGO)

    call_command("migrate_inbox")

    assert Node.objects.get().captured_at == LONG_AGO


def test_the_source_says_it_was_imported(owner):
    a_capture(owner, "the boiler again")

    call_command("migrate_inbox")

    assert Node.objects.get().source == NodeSource.IMPORT


def test_a_captures_tags_arrive_as_confirmed_concepts(owner):
    """Step 1's rule applied to history: these are labels a person typed, so
    they are decisions rather than guesses and skip the gravity gate."""
    a_capture(owner, "the boiler again", tags=["house", "repairs"])

    call_command("migrate_inbox")

    labels = set(
        ConceptCandidate.objects.filter(confirmed_at__isnull=False)
        .values_list("label", flat=True)
    )
    assert labels == {"house", "repairs"}


def test_running_it_twice_imports_nothing_the_second_time(owner):
    """Idempotent on `import_key`, the same mechanism `services.capture`
    already uses -- so a partial run is recovered by running it again."""
    a_capture(owner, "the boiler again")
    call_command("migrate_inbox")

    call_command("migrate_inbox")

    assert Node.objects.count() == 1


# ---------------------------------------------------------------------------
# What each resolution meant
# ---------------------------------------------------------------------------


def test_an_unresolved_capture_arrives_live(owner):
    """The 8 that matter first: untriaged thoughts, which stop needing triage."""
    a_capture(owner, "should I move the desk")

    call_command("migrate_inbox")

    node = Node.objects.get()
    assert node.archived_at is None
    assert node.deleted_at is None


def test_a_discarded_capture_arrives_archived(owner):
    """Kept, because it is still material, but not put back in front of
    somebody who already said no to it once."""
    a_capture(owner, "buy that gadget", resolution=Capture.Resolution.DISCARDED)

    call_command("migrate_inbox")

    assert Node.objects.get().archived_at is not None


def test_a_capture_that_became_a_task_keeps_the_link(owner, area):
    """Provenance, as a confirmed actionable facet pointing at the Item that
    already exists. The graph gains a node; the agenda gains nothing."""
    task = Item.objects.create(list=area, owner=owner, text="Ring the plumber")
    a_capture(owner, "ring the plumber", resolution=Capture.Resolution.TASK, task=task)

    call_command("migrate_inbox")

    facet = Facet.objects.get(kind=FacetKind.ACTIONABLE)
    assert facet.task == task
    assert facet.confirmed_at is not None
    assert Item.objects.count() == 1


# ---------------------------------------------------------------------------
# Ideas
# ---------------------------------------------------------------------------


def test_an_idea_becomes_a_node_too(owner):
    Idea.objects.create(owner=owner, text="a second mind that grows itself")

    call_command("migrate_inbox")

    assert Node.objects.filter(original_content__contains="second mind").exists()


def test_an_ideas_notes_arrive_as_a_revision(owner):
    """Notes are thinking done *after* the thought, which is what a revision
    is. The original text stays what was first said."""
    Idea.objects.create(
        owner=owner, text="a second mind", notes="the graph is the point",
    )

    call_command("migrate_inbox")

    node = Node.objects.get()
    assert node.original_content == "a second mind"
    assert "graph is the point" in node.revisions.get().body


def test_linked_ideas_become_a_confirmed_edge(owner):
    """`related_ideas` is a person's own undirected link -- exactly what a
    confirmed `relates_to` edge is, so it survives as one rather than being
    dropped."""
    first = Idea.objects.create(owner=owner, text="a second mind")
    second = Idea.objects.create(owner=owner, text="a world you can explore")
    first.related_ideas.add(second)

    call_command("migrate_inbox")

    assert Edge.objects.filter(relation=EdgeRelation.RELATES_TO).exists()


def test_a_promoted_idea_keeps_its_task(owner, area):
    task = Item.objects.create(list=area, owner=owner, text="Write the plan")
    Idea.objects.create(
        owner=owner, text="write the plan", status=Idea.Status.PROMOTED,
        promoted_task=task,
    )

    call_command("migrate_inbox")

    assert Facet.objects.get(kind=FacetKind.ACTIONABLE).task == task


# ---------------------------------------------------------------------------
# Care
# ---------------------------------------------------------------------------


def test_it_reports_without_writing_when_asked(owner):
    a_capture(owner, "the boiler again")

    call_command("migrate_inbox", "--dry-run")

    assert Node.objects.count() == 0


def test_one_persons_inbox_does_not_reach_another(owner, other_owner):
    a_capture(owner, "mine")
    a_capture(other_owner, "theirs")

    call_command("migrate_inbox", owner=owner.get_username())

    assert Node.objects.count() == 1
    assert Node.objects.get().owner == owner
