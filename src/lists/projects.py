"""Read side for the Project domain -- charter rule 4.

Query and derivation code answers questions; `services.py` enforces
invariants and mutates. Its own module rather than a corner of `agenda.py`,
which is agenda-scoped and would have had to grow a second subject to hold
this.

Deliberately thin. Slice 7 is the model and the API; what the interface
actually needs to ask is slice 8's question, and inventing reads for it now
would be optimising an imagined workflow.
"""
from dataclasses import dataclass

from django.db.models import Count, Q

from lists.models import Item, Project
# The task core reading the knowledge core, which is the direction the
# dependency has to run: `mind.queries` is text-anchored and does not know what
# a Project is. `review/reads.py` already imports it the same way.
from mind import queries as mind_queries


def projects_for(owner):
    """This owner's projects, open first, each with its open-task count.

    The count is annotated rather than fetched per project: rendering a list
    of projects with their sizes is the one thing every caller so far wants,
    and doing it per row is the N+1 that `list_summaries` already avoids for
    areas.

    Two hops now -- project-workspace-plan.md 2: a project has no tasks of
    its own, only areas, which have tasks. `distinct=True` because the join
    fans out through two tables (areas, then their items) and would
    otherwise double-count a project with more than one area.
    """
    return (
        Project.objects.filter(owner=owner)
        .annotate(
            open_task_count=Count(
                "areas__item",
                filter=Q(areas__item__status=Item.Status.ACTIVE),
                distinct=True,
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


@dataclass(frozen=True)
class ProjectBrief:
    """What a project page can offer when somebody opens it, in three sections.

    Three because a piece of prior thinking, a loose end and a dated commitment
    are three different things to do something about, and a single ranked list
    would ask the reader to work out which is which.

    Nothing here is a proposal. Every item already exists and already belongs to
    the person, so there is no confirm gate: a brief assembles what is already
    theirs rather than claiming anything new about it. That is also why reading
    one records nothing -- contrast `services.open_review`, which stamps
    `first_surfaced_at` precisely because a *proposal* shown without starting
    its window makes silence meaningless.
    """

    project: Project
    material: list
    questions: list
    commitments: object


def brief_for(owner, project) -> ProjectBrief:
    """Assemble a project's brief -- planning-assistant-plan.md increment 4.

    **This is the half that knows what a Project is.** `mind.queries` stays
    text-anchored and answers only "what bears on this statement"; the caller
    supplies the statement. Keeping the dependency pointing this way is what
    lets the knowledge core remain ignorant of the task core, and it is the
    same direction `review/reads.py` already reads in.

    The first two sections **partition one retrieval** rather than running two.
    A note that is both an open question and topically relevant is a loose end
    first -- showing it in both would be one item counted twice, which is how a
    surface stops being trustworthy about its own contents.

    `material_bearing_on` returns nothing for a project with no anchor, so
    both retrieval sections are empty for one. That is deliberate and is not a
    special case here: an unanchored query is the ranked-by-coincidence panel
    the detector registry rejects.

    **Two anchors joined rather than two retrievals** — v2 increment 3. The
    purpose says why and the outcome says what done looks like, and the second
    supplies the concrete nouns the first usually does not: *"the booking form
    is live"* against *"stop enquiries going to email"*. Running them
    separately would mean merging and de-duplicating two ranked lists whose
    scores are not comparable, where one query over both simply has more terms
    to select on — and the rare-term gate is what stops the extra words
    widening this into a vaguely-on-topic panel.
    """
    anchor = "\n".join(
        part for part in (project.purpose, project.desired_outcome) if part
    )
    material = mind_queries.material_bearing_on(owner, anchor)
    open_question_ids = {
        node.pk for node in mind_queries.unresolved_questions(owner)
    }

    questions = [each for each in material if each.node.pk in open_question_ids]
    rest = [each for each in material if each.node.pk not in open_question_ids]

    return ProjectBrief(
        project=project,
        material=rest,
        questions=questions,
        commitments=commitments_for(owner, project),
    )


def commitments_for(owner, project):
    """This project's open tasks, those already dated for it soonest first.

    Two hops, like `projects_for`: a project has areas and areas have tasks.

    **A project with no due date is not a project with no commitments.**
    Filtering on `due_date__lte=None` would return nothing and read as "no work
    here", which is a different claim from "this has no deadline" -- so the
    horizon only applies when there is one.

    Undated tasks are left out when a horizon exists, which `due_date__lte`
    would do anyway by dropping NULLs. Stated rather than inherited, because a
    behaviour that is correct by accident survives a rewrite that makes it
    wrong.
    """
    tasks = Item.objects.filter(
        owner=owner, list__project=project, status=Item.Status.ACTIVE,
    )
    if project.due_date is not None:
        tasks = tasks.filter(due_date__isnull=False, due_date__lte=project.due_date)
    return tasks.order_by("due_date", "id")
