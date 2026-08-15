"""Move the Inbox into the graph.

Step 3 of `design/one-capture-surface-plan.md`, and the step whose value is not
the one it looks like. Draining untriaged captures is the obvious reason; the
resolved ones are the better one.

**The corpus is the binding constraint on this whole core.** Three of the five
detectors rest on argument rather than evidence purely because there is no
material, and the gravity gate cannot see recurrence across four notes.
Production holds 34 captures with real timestamps spread over months, sitting
inside a model that is being deleted. This is not cleanup that preserves data —
it is the step that gives the detectors something to work on, and it should run
before anybody judges whether they are any good.

**Original timestamps, never now.** A node's `captured_at` is when the thought
happened. Stamping an import with the moment it ran collapses months onto one
afternoon and makes every temporal detector wrong on exactly the material most
likely to trigger one. `services.capture` says this in its own docstring; this
command is the largest test of it.

**Idempotent on `import_key`**, the same mechanism `services.capture` already
uses for re-run imports — so a partial run is recovered by running it again
rather than by cleaning up after it.

Nothing is deleted here. The `Capture` and `Idea` rows stay exactly as they are;
retiring them is step 4, deliberately separate, so that this step can be run and
inspected before anything becomes irreversible.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from capture.models import Capture, Idea
from mind import services
from mind.models import EdgeRelation, FacetKind, InferenceOrigin, Node, NodeSource


def _key(prefix, pk):
    """Stable across runs, and namespaced so a Capture and an Idea sharing an
    id cannot collide."""
    return f"inbox:{prefix}:{pk}"


class Command(BaseCommand):
    help = "Move Capture and Idea rows into the knowledge graph as nodes."

    def add_arguments(self, parser):
        parser.add_argument("--owner", help="Just this person. Omit for everybody.")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would move without writing anything.",
        )

    def handle(self, *args, **options):
        captures = Capture.objects.prefetch_related("tags").order_by("created_at")
        ideas = Idea.objects.prefetch_related("tags", "related_ideas").order_by("created_at")

        if options["owner"]:
            try:
                owner = get_user_model().objects.get(username=options["owner"])
            except get_user_model().DoesNotExist:
                raise CommandError(f"no user named {options['owner']!r}")
            captures = captures.filter(owner=owner)
            ideas = ideas.filter(owner=owner)

        captures, ideas = list(captures), list(ideas)
        unresolved = sum(1 for c in captures if not c.resolution)
        self.stdout.write(
            f"{len(captures)} capture(s), {unresolved} untriaged · {len(ideas)} idea(s)"
        )

        if options["dry_run"]:
            for capture in captures:
                state = capture.resolution or "untriaged"
                self.stdout.write(
                    f"  {capture.created_at:%Y-%m-%d}  {state:<9}  "
                    f"{capture.text[:52]}"
                )
            self.stdout.write("Dry run: nothing written.")
            return

        archived = 0
        with transaction.atomic():
            for capture in captures:
                self._move_capture(capture)
                if capture.resolution == Capture.Resolution.DISCARDED:
                    archived += 1
            nodes_by_idea = {idea.pk: self._move_idea(idea) for idea in ideas}
            self._link_ideas(ideas, nodes_by_idea)

        live = Node.objects.filter(
            deleted_at__isnull=True, archived_at__isnull=True
        ).count()
        self.stdout.write(
            self.style.SUCCESS(f"{Node.objects.count()} node(s) in the graph")
        )
        if archived:
            # Said out loud rather than done quietly. Detectors read the live
            # set, so an archived capture is material the graph holds and the
            # detectors cannot see -- which is right for something somebody
            # said no to, and a real cost when the corpus is this small.
            self.stdout.write(
                f"  {archived} discarded capture(s) archived; "
                f"{live} node(s) visible to the detectors"
            )

    # -- captures ----------------------------------------------------------

    def _move_capture(self, capture):
        node = services.capture(
            capture.owner,
            content=capture.text,
            # The thought's own time, which is the entire point.
            captured_at=capture.created_at,
            source=NodeSource.IMPORT,
            import_key=_key("capture", capture.pk),
            actor="migration",
        )
        self._carry_tags(node, capture, when=capture.created_at)

        if capture.resolution == Capture.Resolution.DISCARDED:
            # Kept, because it is still material, but not put back in front of
            # somebody who already said no to it once.
            services.archive_node(
                node, now=capture.resolved_at or capture.created_at, actor="migration"
            )
        elif capture.promoted_task_id:
            self._carry_task(node, capture.promoted_task, when=capture.resolved_at)
        return node

    # -- ideas -------------------------------------------------------------

    def _move_idea(self, idea):
        node = services.capture(
            idea.owner,
            content=idea.text,
            captured_at=idea.created_at,
            source=NodeSource.IMPORT,
            import_key=_key("idea", idea.pk),
            actor="migration",
        )
        self._carry_tags(node, idea, when=idea.created_at)

        if idea.notes:
            # Notes are thinking done *after* the thought, which is what a
            # revision is. The original text stays what was first said.
            services.revise(
                node, body=idea.notes, now=idea.created_at, actor="migration"
            )
        if idea.promoted_task_id:
            self._carry_task(node, idea.promoted_task, when=idea.created_at)
        return node

    def _link_ideas(self, ideas, nodes_by_idea):
        """`related_ideas` is a person's own undirected link, which is exactly
        what a confirmed `relates_to` edge is. `link` is idempotent and covers
        the reverse direction, so a symmetric pair is asserted once."""
        for idea in ideas:
            for other in idea.related_ideas.all():
                if other.pk in nodes_by_idea:
                    services.link(
                        nodes_by_idea[idea.pk],
                        nodes_by_idea[other.pk],
                        relation=EdgeRelation.RELATES_TO,
                        now=idea.created_at,
                        actor="migration",
                        origin=InferenceOrigin.EXPLICIT,
                    )

    # -- shared ------------------------------------------------------------

    def _carry_tags(self, node, source, *, when):
        labels = [tag.name for tag in source.tags.all()]
        if labels:
            services.record_typed_tags(node, labels, now=when, actor="migration")

    def _carry_task(self, node, task, *, when):
        """Provenance, as a confirmed actionable facet pointing at the task that
        already exists. The graph gains a node; the agenda gains nothing.

        `propose_facet` refuses an explicit actionable facet on purpose -- only
        a person may attach one -- and a person did, when they promoted this.
        So it is proposed and then confirmed against the existing task rather
        than created outright, which is the same two-step every accepted
        commitment goes through.
        """
        now = when or node.captured_at
        facet = services.propose_facet(
            node,
            kind=FacetKind.ACTIONABLE,
            data={"due_date": task.due_date.isoformat() if task.due_date else None},
            now=now,
            actor="migration",
            reason="promoted from the Inbox before the crossover",
        )
        if facet.task_id is None:
            facet.task = task
            facet.confirmed_at = now
            facet.save(update_fields=["task", "confirmed_at"])
