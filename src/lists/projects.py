"""Read side for the Project domain -- charter rule 4.

Query and derivation code answers questions; `services.py` enforces
invariants and mutates. Its own module rather than a corner of `agenda.py`,
which is agenda-scoped and would have had to grow a second subject to hold
this.

Deliberately thin. Slice 7 is the model and the API; what the interface
actually needs to ask is slice 8's question, and inventing reads for it now
would be optimising an imagined workflow.
"""
from django.db.models import Count, Q

from lists.models import Item, Project


def projects_for(owner):
    """This owner's projects, open first, each with its open-task count.

    The count is annotated rather than fetched per project: rendering a list
    of projects with their sizes is the one thing every caller so far wants,
    and doing it per row is the N+1 that `list_summaries` already avoids for
    areas.
    """
    return (
        Project.objects.filter(owner=owner)
        .annotate(
            open_task_count=Count(
                "tasks", filter=Q(tasks__status=Item.Status.ACTIVE),
            ),
        )
        # Repeats Project.Meta.ordering rather than inheriting it, because
        # annotating an aggregate drops the default ordering from the
        # generated SQL entirely -- the query came back with no ORDER BY at
        # all and the completed project sorted first. Found by the test, not
        # by reading the query.
        .order_by("is_completed", "-created_at", "id")
    )


def project_for(owner, project_id):
    """One owned project, or None.

    Owner-scoped in the query rather than fetched and then checked, so a
    caller cannot forget the second half. `principles.md`: guards fail
    closed.
    """
    return projects_for(owner).filter(id=project_id).first()
