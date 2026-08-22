"""Read side for the Project domain -- charter rule 4.

Query and derivation code answers questions; `services.py` enforces
invariants and mutates. Its own module rather than a corner of `agenda.py`,
which is agenda-scoped and would have had to grow a second subject to hold
this.

Deliberately thin. Slice 7 is the model and the API; what the interface
actually needs to ask is slice 8's question, and inventing reads for it now
would be optimising an imagined workflow.
"""
from dataclasses import dataclass, field

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
class RelevantSource:
    """One thing the person read that this project's material came out of.

    **Reached through `Node.came_from`, never through the source's own text.**
    A source is here because a note the brief already surfaced came out of it —
    a column somebody wrote — so the reason is a fact rather than a score, and
    nothing new has to be indexed or thresholded.

    **What that refuses** is a source whose *title* resembles the purpose. That
    is `since()`'s refusal in another model: presenting it as *what bears on
    this* would be a similarity score wearing a causal word.
    """

    source: object
    #: The surfaced notes that came out of it. Plural because one source
    #: produces many, and the count is what makes the reason worth reading.
    through: tuple = ()

    @property
    def reason(self) -> str:
        first = self.through[0]
        if len(self.through) == 1:
            return f"you read this, and a note here came out of it: {_short(first)}"
        return (
            f"you read this, and {len(self.through)} notes here came out of it, "
            f"including: {_short(first)}"
        )


@dataclass(frozen=True)
class RelevantDecision:
    """One choice the person made while looking at this project's material.

    **Reached through `Decision.cited_node`**, for the same reason and with the
    same refusal as `RelevantSource`. A decision that cites nothing has no
    recorded path here, and inferring one from its wording is the thing this
    design has twice declined to build.

    **Superseded decisions come too.** *What he learned last time* includes the
    answer he later changed; showing only the surviving one would hide the part
    that makes keeping the record worth anything.
    """

    decision: object
    through: object = None

    @property
    def reason(self) -> str:
        return f"you decided this while looking at: {_short(self.through)}"


def _short(node, limit=70):
    text = node.original_content.strip().replace("\n", " ")
    return text if len(text) <= limit else text[: limit - 1] + "\u2026"


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
    #: **S16's other two nouns**, unblocked on August 22, 2026 when `Source` and
    #: `Decision` shipped hours apart. The story's done-means is *notes,
    #: decisions and sources*, and this had reached one of three since `kestrel`.
    sources: list = field(default_factory=list)
    decisions: list = field(default_factory=list)
    #: Whether anything the brief reached records where it came from. Empty
    #: sections cannot distinguish *nothing bears on this* from *nothing records
    #: its provenance*, and today the second is the true one -- both columns got
    #: their first writing surface the day before this. D5's discipline, one
    #: axis over.
    notes_carrying_provenance: int = 0
    #: What would tell him it went wrong -- S10's done-means asks for it to be
    #: *"still there when he is deciding whether to continue"*, and the brief is
    #: what a project page offers when somebody opens it. A field nobody sees
    #: at the moment of deciding is a field that may as well not exist.
    #:
    #: **Which is what it was**, from the day it was added until August 22,
    #: 2026: `ProjectBriefOut` never carried it, so the brief set it and no
    #: surface ever read it. The object warning against the bug had the bug.
    abandon_if: str = ""

    @property
    def provenance_says(self) -> str:
        """Why the two new sections are empty, when they are.

        Only when they are: a brief that explained an absence beside a full
        section would be answering a question nobody asked.
        """
        if self.sources or self.decisions:
            return ""
        if not (self.material or self.questions):
            return ""
        if self.notes_carrying_provenance:
            return ""
        return (
            "none of the notes here record where they came from or what you "
            "decided from them, so nothing can be reached that way yet"
        )


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

    reached = [each.node for each in material]
    return ProjectBrief(
        project=project,
        material=rest,
        questions=questions,
        commitments=commitments_for(owner, project),
        sources=_sources_behind(reached),
        decisions=_decisions_from(reached),
        notes_carrying_provenance=sum(
            1 for node in reached if node.came_from_id is not None
        ),
        # Carried, never retrieved against. The anchor above is *purpose and
        # outcome* -- what the project is for and what done looks like -- and
        # adding what going wrong looks like would pull material toward the
        # failure rather than the work.
        abandon_if=project.abandon_if,
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



def _sources_behind(nodes):
    """The sources the surfaced notes came out of, each with its notes — S16.

    **The narrowing has already happened**, which is why this is a group-by
    rather than a query with a threshold: `material_bearing_on` decided what
    bears on the project, and this follows one column out of the result. The
    same shape as `retrieval._written_around` deferring to `context_of` — the
    hard part is upstream and is not re-derived here.

    Ordered by how much of the brief each source accounts for, then by title, so
    the thing the person read most out of leads. Not a score: a count of rows.
    """
    if not nodes:
        return []

    behind = {}
    for node in nodes:
        if node.came_from_id is not None:
            behind.setdefault(node.came_from_id, []).append(node)

    from mind.models import Source

    sources = {
        source.pk: source
        for source in Source.objects.filter(pk__in=list(behind))
    }
    found = [
        RelevantSource(source=sources[pk], through=tuple(through))
        for pk, through in behind.items()
        if pk in sources
    ]
    return sorted(found, key=lambda each: (-len(each.through), each.source.title))


def _decisions_from(nodes):
    """The decisions taken while looking at the surfaced notes — S16.

    Chronological, earliest first: a sequence of decisions on one subject reads
    forward, and *what he learned last time* is the shape of the whole run
    rather than only its last entry. **Superseded ones are included**, which is
    the same reasoning that made `record_decision` stamp rather than delete.
    """
    if not nodes:
        return []

    from mind.models import Decision

    by_node = {node.pk: node for node in nodes}
    return [
        RelevantDecision(decision=decision, through=by_node[decision.cited_node_id])
        for decision in Decision.objects.filter(
            cited_node_id__in=list(by_node)
        ).order_by("decided_at", "id")
    ]
