"""Reading the log in time -- `temporal-substrate-plan.md` Track A increment 4.

`clarice/life_log.py` is how the task core tells the log what happened. This is
the other half: how anything asks the log what was going on. It lives beside
that module and not in `mind/queries.py` for the same reason -- a read that
crosses both cores cannot belong to either, and `clarice/` is where the rules
that outrank one app already live (`clarice/search.py`, `scheduled_mail.py`).

**`around()` is adjacency in time.** Every one of `mind/queries.py`'s
twenty-one reads is adjacency in *meaning*: similarity, shared concepts,
mentions, threads. None of them can say what else you were doing that morning,
because until increment 1 the log had no vocabulary for a morning.

**`since()` is adjacency in provenance**, and increment 5 -- the one the brief
said might correctly never ship. **D4** asked what makes a later event *bear
on* an earlier note, and the wide answer is the one that cannot be given
honestly: "bears on" would be a similarity score wearing a causal word. The
narrow answer invents nothing, because the merger already records one true
development chain in columns -- `Node` to confirmed actionable `Facet` to
`Item` to that task's later life events. `since()` follows it and stops.

**The two share `PERSON_EVENTS` rather than copying it**, and share
`Neighbour`, the chronological-never-ranked rule and the counted-not-flagged
cap. A caller putting *what else was going on* beside *what came of it* should
not have to reconcile two vocabularies.

**Six findings in `code-review-2026-08-21.md` are answered in this file** --
R2, R4, R5, R6, R8, R9 -- and one is deliberately deferred: **R7**. The window
is fetched whole before the Python cap, so `limit_each_side` bounds the output
and not the cost. Two `LIMIT n+1` queries walking `event_timeline` in each
direction is the fix, and it waits until a surface actually calls this and can
say what windows it asks for. The cheap half of it is done: the two persisted
`tsvector` columns are deferred rather than hydrated.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from django.db.models import Q
from django.utils import timezone

from mind.models import ActivityEvent, EventType


#: Six hours either side. Wide enough that a morning holds together and a
#: completion at nine sits beside the note that prompted it at seven; narrow
#: enough that "nearby" still means something. Overridable per call, because
#: the right window is a property of the question and not of the log.
DEFAULT_WINDOW = timedelta(hours=6)

#: Per side, not in total -- a cap applied to the whole neighbourhood would
#: return twenty things from before and nothing after, which is a worse answer
#: than either half alone.
DEFAULT_LIMIT_EACH_SIDE = 20


#: What the machine did, rather than what the person did.
#:
#: The three proposals and `HYPOTHESIS_SURFACED` are written without anybody
#: deciding anything -- by the nightly pass, and on live paths where the system
#: is guessing at structure while somebody types. `MAINTENANCE_RAN` is the pass
#: itself.
#:
#: **The line is whose act it was, not which core it came from.** `IMPORTED`,
#: `CONCEPT_CONFIRMED` and `FACET_DISMISSED` are all knowledge-core events and
#: all belong on the other side, because a person performed each of them. A
#: confirmation is a decision; the proposal it answers is a suggestion.
#:
#: `MENTION_PROPOSED` is here and `MENTION_CONFIRMED` is not, which was only
#: true after R2 was fixed in `mind/services.py`: an `EXPLICIT` mention is
#: created with `confirmed_at` already stamped, and used to be logged as a
#: proposal anyway -- so tagging a note by hand vanished from its own morning.
MACHINE_EVENTS = frozenset(
    {
        EventType.CONCEPT_PROPOSED,
        EventType.FACET_PROPOSED,
        EventType.MENTION_PROPOSED,
        EventType.HYPOTHESIS_PROPOSED,
        EventType.HYPOTHESIS_SURFACED,
        EventType.MAINTENANCE_RAN,
    }
)

#: Everything else, written out rather than derived by subtraction.
#:
#: **R8: a denylist over an open enum admits the next value by default.**
#: Deriving this as `set(EventType.values) - MACHINE_EVENTS` would restate that
#: bug in the shape of a fix -- the new value would land here silently and be
#: treated as a person's act with nobody having decided that. Spelled out, and
#: with `test_every_event_type_is_classified_one_way_or_the_other` asserting
#: the partition, adding an `EventType` fails a test until somebody answers the
#: question. `life_log.py` solved the identical problem with an allowlist and a
#: raise.
PERSON_EVENTS = frozenset(
    {
        EventType.CAPTURED,
        EventType.REVISED,
        EventType.CONCEPT_CONFIRMED,
        EventType.CONCEPT_RETIRED,
        EventType.FACET_CONFIRMED,
        EventType.FACET_DISMISSED,
        EventType.ALIAS_MERGED,
        EventType.MENTION_CONFIRMED,
        EventType.EDGE_CREATED,
        EventType.EDGE_REMOVED,
        EventType.HYPOTHESIS_RESOLVED,
        EventType.THREAD_ARTICULATED,
        EventType.REVIEWED,
        EventType.IMPORTED,
        EventType.ARCHIVED,
        EventType.DELETED,
        EventType.PURGED,
        EventType.TASK_COMPLETED,
        EventType.TASK_REOPENED,
        EventType.TASK_ARCHIVED,
        EventType.COMMITMENT_CHANGED,
        EventType.COMMITMENT_ENDED,
        EventType.FOCUS_PINNED,
        EventType.FOCUS_RELEASED,
        EventType.WEEK_REVIEWED,
        EventType.INTENTION_SET,
        EventType.OUTCOME_CHOSEN,
    }
)


@dataclass(frozen=True)
class Neighbour:
    """One thing that was going on near the instant asked about.

    Subjects are resolved rather than left as ids: rendering a morning is the
    point of this read, and a surface that has to issue a query per row to name
    what happened will issue thirty of them.

    **Any subject may be None**, including on an event that plainly had one.
    Two reasons, and both are deliberate. The log outlives what it names -- a
    completed task can be deleted and the row survives it. And a note the
    person deleted or archived is withheld even though the row is still there,
    which is R5: the event stays, because capturing it was a real act, but
    handing back the content of something somebody erased would break
    `delete_node`'s own promise.
    """

    event_id: int
    event_type: str
    occurred_at: datetime
    #: `recorded` or `reconstructed` -- how the log knows, never whether it is
    #: true. Increment 3's whole point, carried through so a surface can say
    #: "recalled" where it cannot say "witnessed".
    origin: str
    actor: str
    node: object | None
    task: object | None
    entry_id: int | None
    payload: dict
    #: The event named a note this read will not hand back -- deleted,
    #: archived, or a row that no longer exists at all.
    #:
    #: **Without this a surface cannot tell "about a note you cannot see" from
    #: "never had a note",** and renders both as a bare verb. Eight rows
    #: reading `written` with nothing beside them is what that looks like, and
    #: it is what the note page rendered before this existed.
    #:
    #: `ActivityEvent.node` is `DO_NOTHING` with `db_constraint=False`, so a
    #: hard-deleted node leaves `node_id` set while `node` resolves to None --
    #: which is the log outliving what it names, working as designed, and the
    #: exact signal this reads.
    subject_withheld: bool = False


@dataclass(frozen=True)
class Around:
    """What else was in the log near an instant."""

    instant: datetime
    window: timedelta
    #: Both chronological. Never one merged ranking: an ordering over a task
    #: completion and a captured note is `SearchRank` across two document sets
    #: again -- a number that does not exist, presented as relevance, failing
    #: in silence. Time is the one ordering both sides genuinely share.
    before: list[Neighbour] = field(default_factory=list)
    after: list[Neighbour] = field(default_factory=list)
    #: How many the cap left out, per side. Counts rather than a flag, because
    #: "three more" and "three hundred more" are different mornings and a
    #: boolean makes them the same one.
    omitted_before: int = 0
    omitted_after: int = 0

    @property
    def has_anything(self):
        """Whether the neighbourhood held anything, not whether any survived
        the cap.

        R9: with `limit_each_side=0` this read False beside non-zero omitted
        counts -- "nothing is dropped in silence" inverted on the one flag
        callers branch on.
        """
        return bool(
            self.before or self.after or self.omitted_before or self.omitted_after
        )


def around(
    owner,
    instant,
    *,
    window=DEFAULT_WINDOW,
    limit_each_side=DEFAULT_LIMIT_EACH_SIDE,
    excluding=None,
):
    """What else this owner's log holds within ``window`` of ``instant``.

    ``excluding`` drops one event from its own neighbourhood, which is what
    "what was around this completion?" means -- an event is not nearby itself.
    Takes an ``ActivityEvent`` or its primary key, and refuses anything else:
    R6 found that accepting whatever had a ``pk`` meant another model's row
    silently excluded an unrelated event sharing its integer id.

    ``instant`` must be timezone-aware. `USE_TZ` is on, so a naive one is
    merely warned about by the ORM and then raises comparing against the aware
    values from the database -- but only when the window holds a row, so it
    would present as intermittent. The most natural day-scoped call,
    ``datetime.combine(entry.date, time(9))``, is exactly the naive one.

    Events exactly on either edge of the window are included, and an event
    exactly at ``instant`` counts as *after*: `accept_draft` pins a whole set
    inside one transaction, so simultaneous rows are ordinary here, and
    splitting them would depend on microseconds nobody chose.
    """
    if timezone.is_naive(instant):
        raise ValueError(
            "around() needs a timezone-aware instant; "
            "got a naive one, which the database would reinterpret silently"
        )
    if limit_each_side < 0:
        raise ValueError("limit_each_side cannot be negative")

    rows = (
        ActivityEvent.objects.filter(
            owner=owner,
            event_type__in=PERSON_EVENTS,
            occurred_at__gte=instant - window,
            occurred_at__lte=instant + window,
        )
        .select_related("node", "task")
        # The persisted `tsvector` columns, which nothing here reads and which
        # are the largest thing on either row. The same reasoning that keeps
        # `DailyEntry` off this join entirely -- see `entry_id` below.
        .defer("node__search_original", "task__search_document")
    )
    if excluding is not None:
        rows = rows.exclude(pk=_event_id(excluding))

    before, after = [], []
    for event in rows.order_by("occurred_at", "id"):
        (before if event.occurred_at < instant else after).append(event)

    # Truncated from the far end on each side, keeping what is closest to the
    # instant: the nearest neighbours are the ones that make a moment legible,
    # and the ones six hours out are what a person would drop first.
    omitted_before = max(0, len(before) - limit_each_side)
    omitted_after = max(0, len(after) - limit_each_side)

    return Around(
        instant=instant,
        window=window,
        before=[_neighbour(e) for e in before[omitted_before:]],
        after=[_neighbour(e) for e in after[: len(after) - omitted_after]],
        omitted_before=omitted_before,
        omitted_after=omitted_after,
    )


@dataclass(frozen=True)
class Since:
    """What developed out of one note, afterwards."""

    node_id: int
    from_moment: datetime
    #: Chronological, earliest first -- a development chain is read forward
    #: from a beginning, where a neighbourhood is read outward from an instant.
    developments: list[Neighbour] = field(default_factory=list)
    omitted: int = 0

    @property
    def has_anything(self):
        return bool(self.developments or self.omitted)


def since(owner, node, *, from_moment=None, limit=DEFAULT_LIMIT_EACH_SIDE):
    """What came of ``node`` after ``from_moment``, along recorded provenance.

    Track A increment 5, and the narrow answer to **D4**. The merger already
    records one true development chain, in columns::

        Node -> Facet (confirmed actionable) -> Item -> that task's life events

    Every hop is a row somebody wrote, with a date on it. This follows that and
    stops. **What it refuses is the point**: two notes about the same subject,
    a shared concept, a close embedding -- none of those is development, and
    presenting them as *"what came of this"* would be a similarity score
    wearing a causal word. The brief's *"stopping at four is the correct
    outcome"* was written for that wider version, and this is not it.

    ``from_moment`` defaults to when the node was captured, which is the honest
    default for *"what came of this"*. Passing a later one answers *"what
    changed since I last looked"*.

    **A deleted or archived node develops no further**, matching `around()` and
    `delete_node`'s promise.

    **Edges reach forward only.** An edge drawn *from* this note grew out of
    it; one drawn *toward* it is a development of the other note, and following
    it would make *"what developed from X"* and *"what has since mentioned X"*
    one question -- which is the slide D4 exists to stop. Nothing extra is
    needed to get this right: `EDGE_CREATED` is recorded against `from_node`.
    """
    if _visible(node) is None:
        return Since(node_id=node.pk, from_moment=from_moment or node.captured_at)

    from_moment = from_moment if from_moment is not None else node.captured_at
    if timezone.is_naive(from_moment):
        raise ValueError(
            "since() needs a timezone-aware moment; "
            "got a naive one, which the database would reinterpret silently"
        )
    if limit < 0:
        raise ValueError("limit cannot be negative")

    # The one hop out of the knowledge core. Imported here rather than at
    # module scope for the reason `confirm_actionable` gives going the other
    # way: the seam is one-directional and should be visible where it is used.
    from mind.models import Facet

    grew_into = set(
        Facet.objects.filter(node=node, task__isnull=False)
        .exclude(confirmed_at=None)
        .values_list("task_id", flat=True)
    )

    rows = (
        ActivityEvent.objects.filter(
            owner=owner,
            event_type__in=PERSON_EVENTS,
            occurred_at__gt=from_moment,
        )
        .filter(Q(node=node) | Q(task_id__in=grew_into))
        .select_related("node", "task")
        .defer("node__search_original", "task__search_document")
        .order_by("occurred_at", "id")
    )

    found = list(rows)
    # Truncated from the far end, which is the *later* end here -- the opposite
    # of `around()`, and deliberately: the first things that came of a thought
    # are the ones that explain it.
    omitted = max(0, len(found) - limit)
    return Since(
        node_id=node.pk,
        from_moment=from_moment,
        developments=[_neighbour(e) for e in found[: len(found) - omitted]],
        omitted=omitted,
    )


@dataclass(frozen=True)
class Occasion:
    """One stretch of a subject's life, and what else was going on around it.

    **The moments are the subject's own**; the neighbours are everything else.
    A merged occasion has no single timestamp, which is why `began` and `ended`
    exist and why this is a read rather than something each caller assembles.
    """

    moments: list[Neighbour] = field(default_factory=list)
    neighbours: list[Neighbour] = field(default_factory=list)
    omitted: int = 0

    @property
    def began(self):
        return self.moments[0].occurred_at

    @property
    def ended(self):
        return self.moments[-1].occurred_at


@dataclass(frozen=True)
class Context:
    """A subject's life, in occasions."""

    node_id: int
    occasions: list[Occasion] = field(default_factory=list)

    @property
    def has_anything(self):
        return bool(self.occasions)


def context_of(
    owner, node, *, window=DEFAULT_WINDOW, limit_each_side=DEFAULT_LIMIT_EACH_SIDE
):
    """What was going on around this note, across the whole of its life.

    **D19, answered: both, and the subject read is built on the instant one.**
    `around()` takes one timestamp and a thing does not have one -- a note has
    its writing, its confirmation as a commitment, the completion of the task it
    became. Anchoring on `captured_at` alone answers about the morning it was
    written and drops the rest, which is what the note page did because that was
    the one timestamp to hand.

    **The subject's moments** are its own log events plus those of any task it
    grew into, which is `since()`'s provenance chain reaching back to include
    the capture itself. Coincidence is not provenance here any more than there.

    **Moments within ``window`` of each other are one occasion.** Two moments
    twenty minutes apart otherwise produce two nearly identical neighbourhoods,
    and a caller unioning them naively either shows everything twice or loses
    which moment each thing belonged to -- both silent. The decision's own
    words: *without it every caller re-derives that resolution ad hoc.*

    **An event near two occasions is reported once, in the earlier.** Later is
    the tempting choice and it is wrong: the first time something appeared
    beside this subject is the fact worth keeping.
    """
    if window is None or limit_each_side is None:
        raise ValueError("context_of needs a window and a per-side limit")
    if _visible(node) is None:
        return Context(node_id=node.pk)

    moments = list(_moments_of(owner, node))
    if not moments:
        return Context(node_id=node.pk)

    own_life = {event.pk for event in moments}
    already_seen = set()
    occasions = []
    for cluster in _clustered(moments, window):
        neighbours, omitted = _around_the_cluster(
            owner, cluster, window, limit_each_side, own_life, already_seen
        )
        occasions.append(
            Occasion(
                moments=[_neighbour(e) for e in cluster],
                neighbours=neighbours,
                omitted=omitted,
            )
        )
    return Context(node_id=node.pk, occasions=occasions)


def _moments_of(owner, node):
    """Every event that is part of this subject's own life, in order.

    `since()`'s chain, reaching back far enough to include the capture -- that
    read answers *what came after* and this one needs the whole life.
    """
    from mind.models import Facet

    grew_into = set(
        Facet.objects.filter(node=node, task__isnull=False)
        .exclude(confirmed_at=None)
        .values_list("task_id", flat=True)
    )
    return (
        ActivityEvent.objects.filter(owner=owner, event_type__in=PERSON_EVENTS)
        .filter(Q(node=node) | Q(task_id__in=grew_into))
        .select_related("node", "task")
        .defer("node__search_original", "task__search_document")
        .order_by("occurred_at", "id")
    )


def _clustered(moments, window):
    """Moments within ``window`` of each other, grouped.

    The gap is measured against the previous moment rather than the cluster's
    start, so a long working session stays one occasion instead of splitting
    every time it outgrows a fixed span.
    """
    clusters = [[moments[0]]]
    for moment in moments[1:]:
        if moment.occurred_at - clusters[-1][-1].occurred_at <= window:
            clusters[-1].append(moment)
        else:
            clusters.append([moment])
    return clusters


def _around_the_cluster(owner, cluster, window, limit_each_side, own_life, already_seen):
    """The union of each moment's neighbourhood, minus the subject's own life.

    ``own_life`` is every one of the subject's moments and not merely this
    cluster's -- a completion three months later is still the subject, and
    without the whole set it reappears as a bystander at an earlier occasion.

    ``already_seen`` carries across occasions, which is what makes an event
    near two of them appear in the earlier one only. Earlier rather than later
    is deliberate: the first time something turned up beside this subject is
    the fact worth keeping.
    """
    found = {}
    for event in cluster:
        neighbourhood = around(
            owner,
            event.occurred_at,
            window=window,
            limit_each_side=limit_each_side,
        )
        for neighbour in neighbourhood.before + neighbourhood.after:
            if neighbour.event_id in own_life or neighbour.event_id in already_seen:
                continue
            found[neighbour.event_id] = neighbour

    already_seen.update(found)
    ordered = sorted(found.values(), key=lambda n: (n.occurred_at, n.event_id))
    omitted = max(0, len(ordered) - limit_each_side)
    return ordered[: len(ordered) - omitted], omitted


def _event_id(excluding):
    if isinstance(excluding, ActivityEvent):
        return excluding.pk
    if isinstance(excluding, int):
        return excluding
    raise TypeError(
        f"excluding takes an ActivityEvent or its id, not {type(excluding).__name__}"
    )


def _visible(node):
    """A node the person has not put away.

    `queries.live_nodes` is the codebase's one node-visibility rule and this
    agrees with it rather than restating it -- but it applies the rule to an
    already-loaded row instead of to a queryset, because the event is kept
    either way and only its subject is withheld.
    """
    if node is None or node.deleted_at is not None or node.archived_at is not None:
        return None
    return node


def _neighbour(event):
    visible = _visible(event.node)
    return Neighbour(
        event_id=event.pk,
        event_type=event.event_type,
        occurred_at=event.occurred_at,
        origin=event.origin,
        actor=event.actor,
        node=visible,
        subject_withheld=event.node_id is not None and visible is None,
        # **An archived task is not withheld, unlike an archived node**, and
        # the asymmetry is the two cores' rules rather than an oversight. The
        # task core has an archive somebody browses -- an archived task is
        # finished, not hidden -- while `queries.live_nodes` excludes archived
        # nodes from everything, and `archive_node` has no surface at all. A
        # `TASK_ARCHIVED` event that withheld its own task would also be the
        # one event in the log that can never name its subject.
        task=event.task,
        # The id rather than the row: nothing that renders a neighbourhood
        # needs the day's prose, and `DailyEntry` carries three text fields
        # plus a generated `tsvector`.
        entry_id=event.entry_id,
        payload=event.payload,
    )
