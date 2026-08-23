"""Read side for the Project domain -- charter rule 4.

Query and derivation code answers questions; `services.py` enforces
invariants and mutates. Its own module rather than a corner of `agenda.py`,
which is agenda-scoped and would have had to grow a second subject to hold
this.

Deliberately thin. Slice 7 is the model and the API; what the interface
actually needs to ask is slice 8's question, and inventing reads for it now
would be optimising an imagined workflow.
"""
from datetime import timedelta
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
    #: What earlier finished projects taught — **S12's fourth clause, delivered
    #: here rather than on the retrospective**, because *next time* is a
    #: different project from the one that learned it.
    learned_before: list = field(default_factory=list)
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
        # **S12's *kept for next time*.** A lesson only its own finished project
        # can show has been filed, not kept; the brief is what somebody opens
        # while a project is running, which is when it is still actionable.
        learned_before=_learned_before(owner, project),
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


# ---------------------------------------------------------------------------
# The retrospective -- S12.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WeekLookedBackOn:
    """One week of a project's life, judged at that week's end."""

    week_start: object
    met: int = 0
    unfinished: int = 0
    set_aside: int = 0

    @property
    def planned(self):
        """Met plus unfinished. **Set-aside is not in the denominator**, and
        that is the same honest-denominator rule `review/reads.py` keeps: a pin
        dropped on purpose was a decision, not a commitment that failed, and
        counting it against him would make deliberate pruning look like
        slippage."""
        return self.met + self.unfinished

    @property
    def has_anything(self):
        return bool(self.planned or self.set_aside)


@dataclass(frozen=True)
class Retrospective:
    """What a project came to, assembled rather than remembered — **S12**.

    > A project completes. Vince wants a retrospective he did not have to write
    > from memory.

    **Everything here except `learned` is derived from rows that already
    exist**, which is what makes it something he did not have to write. Part 1's
    *facts, not derivations* is satisfied because nothing is stored: the weeks
    are a fold over `DailyFocus`, the notes come along the merger's own
    provenance chain, and the decisions cite those notes.

    **`learned` is the exception and has to be**, because *what I would do
    differently* is the one thing no row can answer. A judgement a person makes
    is a fact.
    """

    project: object
    #: Chronological, every week between the first pin and the close --
    #: **including the quiet ones**. Dropping empty weeks would make a project
    #: that ran for a quarter look like a fortnight of work, which is the
    #: opposite of what a retrospective is for.
    weeks: list = field(default_factory=list)
    met: int = 0
    unfinished: int = 0
    set_aside: int = 0
    #: Notes that actually became work here, along `Node -> Facet -> Item ->
    #: List -> Project`. **Recorded provenance, not retrieval** -- see
    #: `retrospective_for`.
    notes: list = field(default_factory=list)
    decisions: list = field(default_factory=list)
    learned: str = ""
    #: Weeks between the last week that held anything and the close.
    #:
    #: **Counted rather than listed, and found in a browser.** The first version
    #: rendered every week up to the close, which put twenty-two empty rows
    #: under a three-week project that nobody had got round to marking done --
    #: and made it read as a six-month one. Silence *inside* the work is the
    #: finding and stays a row each; silence *after* it is one fact and gets one
    #: sentence. Not dropped, because that is the *no silent caps* rule.
    quiet_weeks_before_closing: int = 0

    @property
    def quiet_says(self):
        if not self.quiet_weeks_before_closing:
            return ""
        weeks = self.quiet_weeks_before_closing
        return (
            f"Then {weeks} weeks with nothing pinned to a day for it, "
            "before you marked it done"
        )

    @property
    def planned(self):
        return self.met + self.unfinished

    @property
    def has_anything(self):
        return bool(self.weeks or self.notes or self.decisions or self.learned)


def retrospective_for(owner, project):
    """What a project came to, week by week — **S12**.

    Returns None when the project is not this owner's, which is
    `project_for`'s rule: guards fail closed rather than relying on the caller
    to remember the second half.

    **Planned versus met comes from `DailyFocus`, not from `WeeklyOutcome`.**
    An outcome records what was chosen and never what became of it -- there is
    no met state on that model -- so a retrospective built on outcomes would
    have had to invent the judgement. Pins already carry it.

    **And the judgement is `review.reads.what_became_of`, extracted rather than
    copied.** One function, two callers: the weekly review and this. A second
    copy would have drifted the first time either changed, silently, because
    both would have gone on returning plausible numbers.

    **Judged at each week's end, which is the rule the whole read hangs on.** A
    task finished the following Tuesday was unfinished when the week closed. A
    retrospective that judged at read time would quietly rewrite every past week
    into a success, and the number would move every time somebody opened it.

    **Notes and decisions come from recorded provenance, and this is the line
    between a brief and a retrospective.** `brief_for` asks *what bears on
    this?* and answers topically, because a running project wants prompting and
    a plausible prompt costs little. A retrospective is a **record**: every item
    in it is a row somebody wrote, because a retrospective that was partly
    guessed is one he would have to check, and checking it is the work he wanted
    not to do.
    """
    from daily.models import DailyFocus
    from review.reads import what_became_of
    from review.weeks import week_end_for, week_start_for

    if project.owner_id != owner.pk:
        return None

    pins = list(
        DailyFocus.objects.filter(
            owner=owner,
            # A pin whose task has been permanently deleted cannot be attributed
            # to a project at all -- `DailyFocus.task` is SET_NULL and the
            # `task_text` snapshot names the task, never its area. So it is
            # absent here rather than miscounted, which is the honest failure.
            task__list__project=project,
        )
        .select_related("task", "entry")
        .order_by("entry__date", "position", "id")
    )

    counted = {}
    for focus in pins:
        start = week_start_for(focus.entry.date)
        became = what_became_of(focus, week_end_for(focus.entry.date))
        tally = counted.setdefault(start, {"met": 0, "unfinished": 0, "set_aside": 0})
        tally[became] += 1

    weeks = [
        WeekLookedBackOn(week_start=start, **counted.get(start, {}))
        for start in _every_week_between(counted)
    ]

    notes = _notes_that_became_work_in(project)
    return Retrospective(
        project=project,
        weeks=weeks,
        quiet_weeks_before_closing=_quiet_weeks_before_closing(project, counted),
        met=sum(week.met for week in weeks),
        unfinished=sum(week.unfinished for week in weeks),
        set_aside=sum(week.set_aside for week in weeks),
        notes=notes,
        decisions=_decisions_on(notes),
        learned=project.learned,
    )


def _every_week_between(counted):
    """Every Monday from the first week that held something to the last.

    **Including the quiet ones in between**, which is why this is a range rather
    than the keys of `counted`: a fortnight of silence in the middle of a
    quarter is the most legible thing a retrospective can show, and a list of
    only the busy weeks hides exactly that.

    **It stops at the last week that held something**, and does not run on to
    the close. See `Retrospective.quiet_weeks_before_closing` for what happens
    to the gap after, and why rendering it as rows was wrong.
    """
    from review.weeks import DAYS_IN_WEEK

    if not counted:
        return []

    weeks, day, last = [], min(counted), max(counted)
    while day <= last:
        weeks.append(day)
        day += timedelta(days=DAYS_IN_WEEK)
    return weeks


def _quiet_weeks_before_closing(project, counted):
    """How long the project sat with nothing pinned before it was closed.

    A real signal and a different one from a stalled week: this is the distance
    between *the work stopped* and *somebody said so*.
    """
    from clarice import clocks
    from review.weeks import DAYS_IN_WEEK, week_start_for

    if not counted or project.completed_at is None:
        return 0
    closed = week_start_for(clocks.day_for(project.owner, project.completed_at))
    return max(0, (closed - max(counted)).days // DAYS_IN_WEEK)


def _notes_that_became_work_in(project):
    """Notes that became a task in this project, oldest first.

    The merger's own chain, in columns: a confirmed actionable `Facet` points at
    an `Item`, an `Item` sits in a `List`, and a `List` belongs to a `Project`.
    Every hop is a row somebody wrote.
    """
    from mind.models import Facet

    facets = (
        Facet.objects.filter(task__list__project=project)
        .exclude(confirmed_at=None)
        .exclude(node=None)
        .select_related("node")
        .order_by("node__captured_at", "id")
    )
    seen, notes = set(), []
    for facet in facets:
        if facet.node_id in seen:
            continue
        seen.add(facet.node_id)
        notes.append(facet.node)
    return notes


def _decisions_on(notes):
    """Decisions citing any of those notes, oldest first.

    Chronological because a run of decisions on one subject reads forward, and
    superseded ones stay: what he chose and then changed is the part of a
    retrospective worth having.
    """
    from mind.models import Decision

    if not notes:
        return []
    return list(
        Decision.objects.filter(
            cited_node_id__in=[node.pk for node in notes]
        ).order_by("decided_at", "id")
    )


@dataclass(frozen=True)
class LearnedBefore:
    """One lesson a finished project left behind — **S12's *kept for next
    time***.

    A learning stored where only its own finished project can show it has been
    filed rather than kept, and the moment it would matter is the next project.
    So the brief carries it: the brief is what somebody opens while a project is
    running, which is when *what I would do differently* is still actionable.

    **Named with its project**, because a lesson with no source is an aphorism.
    Knowing which project taught it is what lets him decide whether it applies.
    """

    project: object
    learned: str


def _learned_before(owner, project):
    """What earlier finished projects taught, newest first.

    **Completed projects only.** A learning recorded mid-flight is a note to
    self about work still in progress, and offering it as a lesson would be the
    project advising itself. Its own project is excluded for the same reason.

    Not retrieved and not ranked: there are few finished projects, every lesson
    was written deliberately, and a relevance score over a handful of sentences
    somebody wrote by hand would be inventing a judgement nobody asked for.
    """
    return [
        LearnedBefore(project=each, learned=each.learned)
        for each in Project.objects.filter(owner=owner, is_completed=True)
        .exclude(pk=project.pk)
        .exclude(learned="")
        .order_by("-completed_at", "-id")
    ]
