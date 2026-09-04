from calendar import monthrange
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.db.models import Max
from django.utils import timezone

from clarice import life_log
from clarice.errors import Conflict
from clarice.recurrence import advance_due_date, nth_occurrence_after

from lists.models import (
    CadenceMode,
    ChecklistStep,
    Item,
    List,
    Priority,
    Project,
    RecurringCommitment,
    Tag,
)

# ~~The one seam the extraction leaves open.~~ **Closed September 2, 2026**:
# `create_account`, `record_balance` and the four category functions were
# money's writes sitting in the task core's service module while their models
# had already left. They are `money/services.py`'s now, and this module no
# longer imports a money model at all.


EMPTY_ITEM_ERROR = "You can't have an empty list item"
DUPLICATE_ITEM_ERROR = "You've already got this in your list"
ARCHIVED_DELETE_ERROR = "Only archived tasks can be permanently deleted"
CHECKLIST_STEP_ARCHIVED_ERROR = "Restore this task before editing its checklist"


class TaskServiceError(Exception):
    pass


class TaskConflict(TaskServiceError, Conflict):
    """A task write refused because the domain says no.

    **Also a `clarice.errors.Conflict` since September 2, 2026**, so a boundary
    that handles refusals alike can catch the base and get a bill's as well.
    Every handler naming this one keeps working and keeps meaning tasks.
    """


class InvalidTaskTransition(TaskServiceError):
    pass


def normalize_task_text(text):
    normalized = (text or "").strip()
    if not normalized:
        raise TaskConflict(EMPTY_ITEM_ERROR)
    return normalized


def _duplicate_exists(for_list, text, excluding=None, owner=None):
    # An unfiled task is deduplicated against its owner's other unfiled tasks,
    # which reverses what this said an hour earlier. The argument then was that
    # unfiled tasks are not a list, so two thoughts sharing wording should both
    # be allowed through. What changed it is the retry: a phone re-sending a
    # share is the common case and a second identical commitment is the common
    # cost, while the thought itself is never at stake -- the node stays in the
    # knowledge core either way, and only the duplicate task is refused.
    if for_list is None:
        if owner is None:
            return False
        duplicates = Item.objects.filter(
            owner=owner, list__isnull=True, text=text
        ).exclude(status=Item.Status.ARCHIVED)
    else:
        duplicates = for_list.item_set.exclude(status=Item.Status.ARCHIVED).filter(
            text=text,
        )
    if excluding is not None:
        duplicates = duplicates.exclude(pk=excluding.pk)
    return duplicates.exists()


@transaction.atomic
def create_list_with_item(owner, title, text):
    normalized_text = normalize_task_text(text)
    normalized_title = (title or "").strip() or normalized_text[:100]
    new_list = List.objects.create(owner=owner, title=normalized_title)
    Item.objects.create(list=new_list, text=normalized_text)
    return new_list


def create_area(owner, title, project=None):
    """An Area with no task in it -- Vince's call, August 10, 2026.

    create_list_with_item's first-task requirement was never a domain rule;
    it was the only creation path that existed before a Project needed its
    own way to grow an Area from nothing. The Agenda sidebar's "+ New area"
    form is unchanged and still asks for a first task -- this is a second,
    additive path, not a replacement.
    """
    normalized_title = (title or "").strip() or "Untitled list"
    if project is not None and project.owner_id != owner.id:
        raise TaskConflict(FOREIGN_PROJECT_ERROR)
    return List.objects.create(owner=owner, title=normalized_title, project=project)


def _next_position(for_list, owner=None):
    # Position orders a task within its Area. An unfiled task is ordered by the
    # agenda's own rules instead, so any value is unused -- but they still get
    # distinct ones, because a column full of zeroes makes a stable sort
    # impossible the day something does want to arrange them.
    if for_list is None:
        if owner is None:
            return 0
        highest = (
            Item.objects.filter(owner=owner, list__isnull=True)
            .exclude(status=Item.Status.ARCHIVED)
            .aggregate(Max("position"))["position__max"]
        )
        return 0 if highest is None else highest + 1
    highest = for_list.item_set.exclude(
        status=Item.Status.ARCHIVED,
    ).aggregate(Max("position"))["position__max"]
    return 0 if highest is None else highest + 1


def _clean_tag_names(tag_names):
    cleaned = []
    seen = set()
    for raw in tag_names or []:
        name = (raw or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        cleaned.append(name)
    return cleaned


def resolve_tags(owner, tag_names):
    """Public: capture.services reuses this rather than a second
    definition of what a tag is, per lists.Tag being the one owner-scoped
    tag vocabulary in the app.
    """
    return [
        Tag.objects.get_or_create(owner=owner, name=name)[0]
        for name in _clean_tag_names(tag_names)
    ]


def _anchor_commitment(item):
    """Give a repeating task the series identity it belongs to.

    Called on every path that can leave a root task repeating. Reuses an
    existing commitment rather than starting a second series, so a task that
    was paused and resumed stays one commitment with a gap in it.

    Always returns a commitment. It used to return None when the list had
    no owner, for anonymous-era rows; release D slice 6 made `List.owner`
    required and deleted those rows, so that branch became unreachable and
    went with them, exactly as this docstring used to promise it would.
    """
    if item.commitment_id is not None:
        commitment = item.commitment
        if commitment.ended_at is not None:
            commitment.ended_at = None
            commitment.save(update_fields=["ended_at"])
        return commitment
    # Seeded from the item at birth, not left empty. A commitment adopted at
    # completion (the legacy path, for rows predating this key) would
    # otherwise reach its first spawn with a blank template and produce a
    # blank task.
    commitment = RecurringCommitment.objects.create(
        owner=item.owner,
        text=item.text,
        list=item.list,
        cadence=item.recurrence,
        notes=item.notes,
    )
    item.commitment = commitment
    commitment.tags.set(item.tags.all())
    return commitment


def _end_commitment(item):
    """Stop a series accepting new occurrences, without disowning the old ones."""
    if item.commitment_id is None:
        return
    commitment = item.commitment
    if commitment.ended_at is None:
        commitment.ended_at = timezone.now()
        commitment.save(update_fields=["ended_at"])


def _write_through_to_commitment(item, **fields):
    """Editing an occurrence edits its commitment -- "this and future".

    Decided August 3, 2026; see recurring-commitment-vocabulary-plan.md 4.
    Renaming a recurring task means renaming the commitment, so the next
    occurrence carries the new name. Occurrences already completed keep their
    own text, notes and tags -- they are the snapshot of what actually ran,
    and nothing here touches them.

    A no-op for the ordinary one-off task, which has no commitment. That is
    the load-bearing part: inventing one here would turn every edited task
    into a series.
    """
    if item.commitment_id is None:
        return
    commitment = item.commitment
    tags = fields.pop("tags", None)
    if fields:
        for name, value in fields.items():
            setattr(commitment, name, value)
        commitment.save(update_fields=tuple(fields))
    if tags is not None:
        commitment.tags.set(tags)


@transaction.atomic
def create_item(for_list, text, due_date=None, tags=None, recurrence=None, owner=None):
    """A task, in an Area or standing on its own.

    `owner` is only needed when `for_list` is None; with an Area, the Area's
    owner is the answer and passing a different one would be inventing a second
    opinion. Callers that already pass an Area are unchanged, which is what
    makes this a widening rather than a migration of every call site.
    """
    if for_list is None and owner is None:
        raise TaskConflict("A task with no Area still has to belong to somebody")
    owner = for_list.owner if for_list is not None else owner

    normalized = normalize_task_text(text)
    if _duplicate_exists(for_list, normalized, owner=owner):
        raise TaskConflict(DUPLICATE_ITEM_ERROR)
    if recurrence and recurrence not in Item.Recurrence.values:
        raise TaskConflict("Choose a valid recurrence.")
    try:
        item = Item.objects.create(
            list=for_list,
            owner=owner,
            text=normalized,
            due_date=due_date,
            position=_next_position(for_list, owner=owner),
            recurrence=recurrence or Item.Recurrence.NONE,
        )
    except IntegrityError as error:
        raise TaskConflict(DUPLICATE_ITEM_ERROR) from error
    if item.recurrence != Item.Recurrence.NONE:
        _anchor_commitment(item)
        item.save(update_fields=["commitment"])
    if tags:
        item.tags.set(resolve_tags(owner, tags))
    return item


@transaction.atomic
def edit_item(item, text):
    item = Item.objects.select_for_update(of=("self",)).select_related("list").get(pk=item.pk)
    if item.status == Item.Status.ARCHIVED:
        raise InvalidTaskTransition("Restore this task before editing it")

    normalized = normalize_task_text(text)
    if _duplicate_exists(item.list, normalized, excluding=item):
        raise TaskConflict(DUPLICATE_ITEM_ERROR)

    item.text = normalized
    try:
        item.save()
    except IntegrityError as error:
        raise TaskConflict(DUPLICATE_ITEM_ERROR) from error
    _write_through_to_commitment(item, text=normalized)
    return item


@transaction.atomic
def reorder_items(for_list, ordered_ids):
    # Set equality against the list's open tasks is what stops an id
    # belonging to another list from being smuggled in.
    items = list(
        Item.objects.select_for_update()
        .filter(list=for_list)
        .exclude(status=Item.Status.ARCHIVED)
    )
    by_id = {item.id: item for item in items}
    if set(ordered_ids) != set(by_id):
        raise TaskConflict(
            "This list changed since you last loaded it. Refresh and try again."
        )
    for position, item_id in enumerate(ordered_ids):
        item = by_id[item_id]
        if item.position != position:
            item.position = position
            item.save(update_fields=["position"])
    return [by_id[item_id] for item_id in ordered_ids]


@transaction.atomic
def set_item_tags(item, tag_names):
    item = Item.objects.select_for_update(of=("self",)).select_related("list").get(pk=item.pk)
    if item.status == Item.Status.ARCHIVED:
        raise InvalidTaskTransition("Restore this task before editing it")
    resolved = resolve_tags(item.owner, tag_names)
    item.tags.set(resolved)
    _write_through_to_commitment(item, tags=resolved)
    return item


@transaction.atomic
def set_due_date(item, due_date):
    item = Item.objects.select_for_update().get(pk=item.pk)
    if item.status == Item.Status.ARCHIVED:
        raise InvalidTaskTransition("Restore this task before editing it")
    item.due_date = due_date or None
    item.save()
    return item


@transaction.atomic
def set_priority(item, priority):
    """Mark a commitment as more or less pressing than the rest.

    Writes through to the series for the same reason renaming does -- "this and
    future". A priority set on "pay rent" that came back unmarked next month
    would be the one attribute of a commitment that did not carry.
    """
    item = Item.objects.select_for_update().get(pk=item.pk)
    if item.status == Item.Status.ARCHIVED:
        raise InvalidTaskTransition("Restore this task before editing it")
    if priority not in Priority.values:
        raise TaskConflict("Choose a valid priority.")
    item.priority = priority
    item.save(update_fields=["priority"])
    _write_through_to_commitment(item, priority=priority)
    return item


@transaction.atomic
def set_lead_days(item, days):
    """How many days before its due date this should be mentioned.

    Written through to the series, like priority: a lead time on "pay rent"
    that came back zero next month would be the one attribute somebody had to
    set again forever.
    """
    item = Item.objects.select_for_update().get(pk=item.pk)
    if item.status == Item.Status.ARCHIVED:
        raise InvalidTaskTransition("Restore this task before editing it")
    if days < 0:
        raise TaskConflict("A lead time cannot be negative.")
    item.lead_days = days
    item.save(update_fields=["lead_days"])
    _write_through_to_commitment(item, lead_days=days)
    return item




@transaction.atomic
def move_item(item, to_list):
    """File a task into a different Area, or out of every Area.

    `commercial-blueprint.md` Part 3 named the absence: `item_detail` PATCH
    took six fields and `list` was not one, so a misfiled task stayed
    misfiled.

    **Moving between Areas moves between Projects as a consequence, not as a
    second decision.** A `Project` hangs off `List`, so a task's project is
    whatever its area's is -- there is nothing here to keep consistent.

    **`position` is recomputed rather than carried.** It orders a task *within*
    its Area, so the number it held in the old one means nothing in the new
    one; appending is the only answer that does not interleave it silently
    into an order somebody arranged.

    **`to_list=None` is a destination, not a missing argument.** `Item.list`
    has been nullable since August 14 and `Item.owner` is what keeps an
    unfiled task a real one -- and `_derive_owner` only fires when there *is*
    an area, so unfiling leaves the owner where it was rather than stranding
    the row.
    """
    item = Item.objects.select_for_update().get(pk=item.pk)
    if item.status == Item.Status.ARCHIVED:
        raise InvalidTaskTransition("Restore this task before editing it")
    item.list = to_list
    item.position = _next_position(to_list, owner=item.owner)
    item.save()
    # **Write through, or a series quietly stays where it was.** Spawning
    # reads `commitment.list`, not the occurrence's -- see `list=commitment.list`
    # in the spawn below -- so moving only the task would file this occurrence
    # in the new Area and its successor back in the old one. Same "this and
    # future" rule renaming already follows.
    _write_through_to_commitment(item, list=to_list)
    return item


@transaction.atomic
def set_recurrence(item, recurrence, cadence_mode=None):
    """Set how often this repeats, and optionally whether it is anchored.

    `cadence_mode=None` means "leave it as it is", not "reset to the default".
    Editing a cadence must not silently undo a mode somebody chose -- that is
    how a setting gets quietly reverted by an unrelated edit.
    """
    item = Item.objects.select_for_update().get(pk=item.pk)
    if item.status == Item.Status.ARCHIVED:
        raise InvalidTaskTransition("Restore this task before editing it")
    if recurrence not in Item.Recurrence.values:
        raise TaskConflict("Choose a valid recurrence.")
    if cadence_mode is not None and cadence_mode not in CadenceMode.values:
        raise TaskConflict("Choose a valid schedule mode.")
    # Read before the write, so the log can tell a change from a re-save.
    # **Only the cadence.** `cadence_mode` is deliberately not a life event in
    # slice 1: it decides where the *next* occurrence lands rather than whether
    # there is a series at all, and under-recording is recoverable where a
    # keystroke log is not.
    cadence_changed = item.recurrence != recurrence
    item.recurrence = recurrence
    if recurrence == Item.Recurrence.NONE:
        # The link stays. This task really was an occurrence of that series,
        # and clearing the key would rewrite history to say it never was --
        # only the series stops accepting new ones.
        _end_commitment(item)
    else:
        _anchor_commitment(item)
    item.save()
    # The cadence is the commitment's rule; `item.recurrence` above is this
    # occurrence's snapshot of it. Writing both keeps an *active* occurrence
    # in step with its series, which is why the API can keep reading the
    # item's own value -- see the plan file, slice 3.
    #
    # Deliberately also written when the cadence is NONE: a commitment that
    # was stopped should say so rather than keep advertising the rule it no
    # longer follows.
    _write_through_to_commitment(item, cadence=recurrence)
    if cadence_mode is not None:
        _write_through_to_commitment(item, cadence_mode=cadence_mode)
    if cadence_changed:
        life_log.record(
            item.owner,
            life_log.COMMITMENT_ENDED
            if recurrence == Item.Recurrence.NONE
            else life_log.COMMITMENT_CHANGED,
            task=item,
        )
    return item


@transaction.atomic
def set_item_notes(item, notes):
    item = Item.objects.select_for_update().get(pk=item.pk)
    if item.status == Item.Status.ARCHIVED:
        raise InvalidTaskTransition("Restore this task before editing it")
    # Normalised to "" rather than None so callers never have to handle both;
    # clearing notes and never having written any are the same state.
    item.notes = (notes or "").strip()
    item.save()
    _write_through_to_commitment(item, notes=item.notes)
    return item


def _next_step_position(task):
    highest = task.checklist_steps.aggregate(Max("position"))["position__max"]
    return 0 if highest is None else highest + 1


def _duplicate_step_exists(task, text, excluding=None):
    # Mirrors unique_open_checklist_step_text: open-scoped, not task-wide, so
    # a done step's text is free to reuse -- see design/release-d-plan.md 2.
    duplicates = task.checklist_steps.filter(is_done=False, text=text)
    if excluding is not None:
        duplicates = duplicates.exclude(pk=excluding.pk)
    return duplicates.exists()


@transaction.atomic
def add_checklist_step(task, text, carries_forward=None):
    task = Item.objects.select_for_update(of=("self",)).select_related("list").get(pk=task.pk)
    if task.status == Item.Status.ARCHIVED:
        raise InvalidTaskTransition(CHECKLIST_STEP_ARCHIVED_ERROR)
    normalized = normalize_task_text(text)
    if _duplicate_step_exists(task, normalized):
        raise TaskConflict(DUPLICATE_ITEM_ERROR)
    try:
        step = ChecklistStep.objects.create(
            owner=task.owner,
            task=task,
            text=normalized,
            position=_next_step_position(task),
            carries_forward=True if carries_forward is None else carries_forward,
        )
    except IntegrityError as error:
        raise TaskConflict(DUPLICATE_ITEM_ERROR) from error
    return step


@transaction.atomic
def set_checklist_step_done(step, is_done):
    step = ChecklistStep.objects.select_for_update().select_related("task").get(pk=step.pk)
    if step.task.status == Item.Status.ARCHIVED:
        raise InvalidTaskTransition(CHECKLIST_STEP_ARCHIVED_ERROR)
    step.is_done = bool(is_done)
    step.completed_at = timezone.now() if step.is_done else None
    step.save()
    return step


@transaction.atomic
def set_checklist_step_carries_forward(step, value):
    step = ChecklistStep.objects.select_for_update().select_related("task").get(pk=step.pk)
    if step.task.status == Item.Status.ARCHIVED:
        raise InvalidTaskTransition(CHECKLIST_STEP_ARCHIVED_ERROR)
    step.carries_forward = bool(value)
    step.save()
    return step


@transaction.atomic
def edit_checklist_step_text(step, text):
    step = ChecklistStep.objects.select_for_update().select_related("task").get(pk=step.pk)
    if step.task.status == Item.Status.ARCHIVED:
        raise InvalidTaskTransition(CHECKLIST_STEP_ARCHIVED_ERROR)
    normalized = normalize_task_text(text)
    if _duplicate_step_exists(step.task, normalized, excluding=step):
        raise TaskConflict(DUPLICATE_ITEM_ERROR)
    step.text = normalized
    try:
        step.save()
    except IntegrityError as error:
        raise TaskConflict(DUPLICATE_ITEM_ERROR) from error
    return step


@transaction.atomic
def delete_checklist_step(step):
    step = ChecklistStep.objects.select_for_update().select_related("task").get(pk=step.pk)
    if step.task.status == Item.Status.ARCHIVED:
        raise InvalidTaskTransition(CHECKLIST_STEP_ARCHIVED_ERROR)
    step.delete()


@transaction.atomic
def reorder_checklist_steps(task, ordered_ids):
    steps = list(ChecklistStep.objects.select_for_update().filter(task=task))
    by_id = {step.id: step for step in steps}
    if set(ordered_ids) != set(by_id):
        raise TaskConflict(
            "This checklist changed since you last loaded it. Refresh and try again."
        )
    for position, step_id in enumerate(ordered_ids):
        step = by_id[step_id]
        if step.position != position:
            step.position = position
            step.save(update_fields=["position"])
    return [by_id[step_id] for step_id in ordered_ids]


@transaction.atomic
def promote_checklist_step(step):
    """Turn a Checklist Step into its own Task -- design/release-d-plan.md 2.

    A state transition, not a copy: the step ceases to exist, so there is
    exactly one live record of the work either way. No due date, no tags, no
    recurrence -- the owner does whatever they were going to do with a new
    task next. Demotion (the reverse) is deliberately not built; see that
    document for why.
    """
    step = (
        ChecklistStep.objects.select_for_update(of=("self",))
        .select_related("task", "task__list")
        .get(pk=step.pk)
    )
    if step.task.status == Item.Status.ARCHIVED:
        raise InvalidTaskTransition(CHECKLIST_STEP_ARCHIVED_ERROR)
    task_list = step.task.list
    # From the task, not from its Area, which may not exist -- the same
    # correction as in _spawn_next_occurrence, and the same mistake: relying on
    # save() to derive an owner works for every filed task and leaves an
    # unfiled one violating NOT NULL. Passing it here also restores the
    # duplicate check, which followed the Area and so did nothing without one.
    owner = step.task.owner
    if _duplicate_exists(task_list, step.text, owner=owner):
        raise TaskConflict(DUPLICATE_ITEM_ERROR)
    try:
        promoted = Item.objects.create(
            list=task_list,
            owner=owner,
            text=step.text,
            position=_next_position(task_list, owner=owner),
        )
    except IntegrityError as error:
        raise TaskConflict(DUPLICATE_ITEM_ERROR) from error
    step.delete()
    return promoted


#: **Re-exported, not defined here, since September 2, 2026.**
#: `clarice.recurrence` owns the calendar arithmetic; both cores depend on it
#: and neither owns it. The private spellings stay because this module says them
#: in a dozen places and each reads correctly there — they are the same
#: functions, not copies.
#:
#: `bills.py` used to import `_advance_due_date` from here, which is a private
#: name money had no claim on. That is what step 2 of the app extraction
#: removed; see `clarice/recurrence.py` for the argument.
_nth_occurrence_after = nth_occurrence_after
_advance_due_date = advance_due_date


def _spawn_next_occurrence(completed_item, carry_forward_steps=(), today=None):
    # Anchored here as well as on the paths that set a cadence, because rows
    # predating this key reach completion without one. Their earlier
    # occurrences can't be recovered -- that history is gone -- but adopting
    # the pair here means no path leaves the series unlinked from now on.
    was_linked = completed_item.commitment_id is not None
    commitment = _anchor_commitment(completed_item)
    if not was_linked:
        completed_item.save(update_fields=["commitment"])
    # Built from the template, not copied from the occurrence that just
    # finished. That is the whole point of the pair: the commitment says what
    # the next one starts as, and the completed row keeps what *it* was, so
    # renaming a commitment in September leaves June reading "Pay rent".
    #
    # `due_date` is the exception and always was -- computed per occurrence by
    # _advance_due_date rather than seeded, because it advances from the one
    # that just finished rather than being a property of the series.
    #
    # The template is the sole source now. It carried `or` fallbacks to the
    # completed occurrence through one deploy, as the compatibility window
    # for 0031's backfill; that window closed on August 3, 2026 when the
    # migration reported empty=0 against production -- every commitment has a
    # template, so there is nothing left for a fallback to cover.
    #
    # The cadence is not merely a label: it decides how far the next due date
    # moves, so reading the wrong one schedules the next occurrence on the
    # wrong day rather than just describing it wrongly.
    next_item = Item.objects.create(
        list=commitment.list,
        # From the series, not from the Area. `Item.save()` derives owner from
        # `list`, which works for every filed task and leaves an unfiled one
        # with nothing to derive from -- so this insert violated NOT NULL and
        # completing the task raised. The commitment is the durable identity
        # here and it knows whose it is, whether or not it has a place.
        owner=commitment.owner,
        text=commitment.text,
        # `today` rather than `timezone.localdate()` inline, so a caller can
        # say which day it is. Passing None means the real clock, which is
        # every production path -- `_advance_due_date` does the defaulting, so
        # there is still exactly one place that reads the system date.
        #
        # It was inline until August 28, 2026, and that made the boundary
        # untestable without mocking: a fortnightly item due the 14th whose
        # successor falls on the 28th produced a *different* successor once the
        # real date reached the 28th, because the schedule must clear today.
        # `test_the_next_one_lands_two_weeks_later` hard-coded the 28th and so
        # passed for fourteen days and then failed for good -- red on `main`,
        # not a flake. See `principles.md`, *inject the clock; do not freeze
        # it*: the sibling test two functions down had been doing this all
        # along, via `landing_for(..., today=AUGUST)`.
        due_date=_advance_due_date(
            completed_item.due_date,
            commitment.cadence,
            today=today,
            mode=commitment.cadence_mode,
        ),
        recurrence=commitment.cadence,
        position=_next_position(commitment.list, owner=commitment.owner),
        commitment=commitment,
        notes=commitment.notes,
        priority=commitment.priority,
        lead_days=commitment.lead_days,
    )
    next_item.tags.set(commitment.tags.all())

    # **There is no money relation to carry any more.** A bill is a `Bill`, it
    # is not spawned by completing a task, and `bills.spawn_next` is where its
    # successor comes from. The sidecar this paragraph used to name was deleted
    # on September 1, 2026, so the guard in
    # `tests/test_a_spawn_accounts_for_everything_on_a_task.py` no longer asks
    # about it.
    #
    # The paragraph is kept rather than deleted because of what it used to
    # say. Between bills shipping and August 27, 2026 nothing here touched the
    # sidecar, so paying rent produced a plain *task* for next month and rent
    # silently stopped appearing on the page that exists to show bills --
    # recurrence was built for tasks, the sidecar was added beside it, and
    # nobody joined them. The two-record shape is what made that possible, and
    # this is the shape that replaced it.
    #
    # **NOT CARRIED: Facet.** A facet records that a particular thought became
    # a particular task -- `mind.Facet.task`, whose invariant is that a
    # confirmed actionable facet has a live task. It is provenance about *one*
    # occurrence. Copying it would claim the same thought also became next
    # month's task, and the month after that, which is false and gets less true
    # every cycle. The original keeps its facet; completing a task does not
    # delete it, so nothing is orphaned.
    #
    # **NOT CARRIED: ActivityEvent.** The life log of what happened to *this*
    # occurrence. Copying rows forward would fabricate history -- events dated
    # before the task existed -- and the table is append-only by database
    # trigger, so it is not a thing to write casually in either direction.
    #
    # All three declared rather than left silent, and
    # `tests/test_a_spawn_accounts_for_everything_on_a_task.py` is why: the
    # sidecar was correctly not mentioned here either, right up until it turned
    # out to be a defect that had been live since bills shipped.

    # Fresh copies, not carried state: a step that was already ticked off
    # this cycle starts the next one unchecked, the same way the parent
    # itself starts active rather than completed.
    for step in carry_forward_steps:
        ChecklistStep.objects.create(
            owner=step.owner,
            task=next_item,
            text=step.text,
            position=step.position,
            carries_forward=step.carries_forward,
        )
    return next_item


def _checklist_steps_to_carry_forward(item):
    """Every checklist step flagged carries_forward -- what clones onto the
    next occurrence. A step has no independent archived state to exclude: it
    dies with its task (release-d-plan.md 2) rather than being separately
    removed, so there's nothing else to filter here.
    """
    return list(
        item.checklist_steps.filter(carries_forward=True).order_by("position", "id")
    )


@transaction.atomic
# `of=("self",)` on every lock that also selects the Area.
#
# Item.list became nullable on August 14, 2026, which turned select_related("list")
# from an inner join into an outer one -- and Postgres refuses "FOR UPDATE cannot
# be applied to the nullable side of an outer join". Locking only the base row is
# what was meant anyway: nothing here mutates the Area, and locking it would take
# a lock on every task in it.
#
# Found by the suite rather than by reading: 95 errors from one column changing
# nullability, none of them in code that mentions the column.


# `transaction.atomic` here rather than nowhere, which is what it was.
# `temporal-substrate-plan.md` increment 2 records a completion to the
# append-only log, and Vince's answer to how that may fail is **both or
# neither** -- so the completion and its event have to be one transaction or
# the log becomes a sample with a silent hole in it. This function already did
# two saves and a spawn in autocommit, each committing alone; the log is what
# made that worth fixing rather than merely noting.
@transaction.atomic
def complete_item(item, *, today=None):
    item = Item.objects.select_for_update(of=("self",)).select_related("list").get(pk=item.pk)
    if item.status == Item.Status.ARCHIVED:
        raise InvalidTaskTransition("Archived tasks must be restored first")
    if item.status != Item.Status.COMPLETED:
        now = timezone.now()
        is_recurring = item.recurrence != Item.Recurrence.NONE
        # Read before the item moves: a recurring task archives itself below,
        # and reading this after would see its own steps as belonging to an
        # already-archived task rather than change what they answer.
        carry_forward_steps = (
            _checklist_steps_to_carry_forward(item) if is_recurring else []
        )
        item.status = Item.Status.COMPLETED
        item.completed_at = now
        item.archived_at = None
        if is_recurring:
            # Recurring tasks skip the "completed" resting state: archive
            # immediately (freeing up its text for the next occurrence,
            # which would otherwise collide with the unique-active-text
            # constraint) and spawn the next one right away.
            item.status = Item.Status.ARCHIVED
            item.archived_at = now
        item.save()
        if is_recurring:
            item._spawned = _spawn_next_occurrence(
                item, carry_forward_steps=carry_forward_steps, today=today,
            )
        # The completion, and not the archive above it. A recurring task is
        # archived immediately to free its text for the next occurrence --
        # mechanism, not a decision -- and logging that would put a retirement
        # in the record of a habit somebody is keeping.
        #
        # `now` rather than a fresh clock read: the log has to agree with
        # `completed_at`, or a reading joining the two sees one task finished
        # twice a millisecond apart.
        life_log.record(
            item.owner, life_log.TASK_COMPLETED, task=item, occurred_at=now
        )
        _draw_todays_line_if_this_was_chosen(item, now)
    return item


def _draw_todays_line_if_this_was_chosen(item, now):
    """Rule 3: the first act of execution draws the line under today's list.

    **A tick on a *chosen* task, and rule 3 enumerates rather than describes.**
    A Note, a Pool capture, an appointment passing and every derived event
    leave the list open, because writing down something overheard at breakfast
    is not the start of the day's work -- the plan's D7, answered the day it
    was asked. A task nobody chose is not on either of rule 3's lists, so it
    does not draw the line either; that reading is narrow on purpose and is the
    one worth revisiting first if the line turns out to be drawn too rarely.
    The composer's Did and Today lines join this site at increment 4.

    **Today, never the pinned day.** The line records when *this* day's work
    began, so completing something chosen for yesterday draws nothing --
    yesterday closed unclosed and rule 11 keeps it that way.

    `day_for` rather than `localdate`, because which day an instant fell on is
    a property of the record and must answer the same to a request, a
    management command and the phone -- `clarice/clocks.py` owns that split.

    Imported inside the function: `daily` reads `lists`, and a module-level
    import back would make the two packages import-order dependent for no gain.
    The same shape `daily.reads.typical_day_for` uses for `review.reads`.
    """
    from clarice.clocks import day_for
    from daily import services as daily_services
    from daily.models import DailyFocus

    today = day_for(item.owner, now)
    chosen = DailyFocus.objects.filter(
        owner=item.owner,
        entry__date=today,
        task=item,
        released_at__isnull=True,
    ).exists()
    if chosen:
        daily_services.draw_the_line(item.owner, today, now=now)


@transaction.atomic
def keep(item):
    """"Yes, still want this" -- `superlists-2.0-plan.md` rule 8's other answer.

    Writes nothing but the clock. The line is unchanged in every way a reader
    can see; what changed is that the pool has been told not to ask again for
    another `agenda.STALE_AFTER_DAYS`.

    **No life event.** The log records what happened to a life, and *I was
    asked whether I still wanted something and said yes* is housekeeping about
    a prompt -- the same call `recall.NOT_A_DEVELOPMENT` makes about a review
    row. Letting go is the half that is a real decision, and that one is
    recorded.
    """
    item = Item.objects.select_for_update().get(pk=item.pk)
    item.kept_at = timezone.now()
    item.save(update_fields=["kept_at", "updated_at"])
    return item


@transaction.atomic
def reopen_item(item):
    item = Item.objects.select_for_update().get(pk=item.pk)
    if item.status == Item.Status.ARCHIVED:
        raise InvalidTaskTransition("Archived tasks must be restored first")
    if item.status != Item.Status.ACTIVE:
        item.status = Item.Status.ACTIVE
        item.completed_at = None
        item.archived_at = None
        item.save()
        # Without this the log asserts a completion it can never retract, and
        # any projection folded over it drifts the first time somebody ticks
        # the wrong row.
        life_log.record(item.owner, life_log.TASK_REOPENED, task=item)
    return item


@transaction.atomic
def archive_item(item):
    item = Item.objects.select_for_update().get(pk=item.pk)
    if item.status != Item.Status.ARCHIVED:
        item.status = Item.Status.ARCHIVED
        item.archived_at = timezone.now()
        item.save()
        life_log.record(
            item.owner,
            life_log.TASK_ARCHIVED,
            task=item,
            occurred_at=item.archived_at,
        )
    return item


def _restore_status_for(item):
    # A null completed_at means the task was active when it was archived, so
    # that is where it goes back to; anything else was genuinely completed.
    if item.completed_at is None:
        return Item.Status.ACTIVE
    return Item.Status.COMPLETED


@transaction.atomic
def restore_item(item):
    item = Item.objects.select_for_update(of=("self",)).select_related("list").get(pk=item.pk)
    if item.status != Item.Status.ARCHIVED:
        raise InvalidTaskTransition("Only archived tasks can be restored")
    if _duplicate_exists(item.list, item.text, excluding=item):
        raise TaskConflict(
            "That task already exists in its original list, so it was not restored."
        )

    item.status = _restore_status_for(item)
    item.archived_at = None
    try:
        item.save()
    except IntegrityError as error:
        raise TaskConflict(
            "That task already exists in its original list, so it was not restored."
        ) from error
    return item


@transaction.atomic
def delete_archived_item(item):
    item = Item.objects.select_for_update().get(pk=item.pk)
    if item.status != Item.Status.ARCHIVED:
        raise InvalidTaskTransition(ARCHIVED_DELETE_ERROR)
    item.delete()


@transaction.atomic
def delete_list(list_):
    list_ = List.objects.select_for_update().get(pk=list_.pk)
    list_.delete()


EMPTY_PROJECT_TITLE_ERROR = "Give the project a name"
FOREIGN_PROJECT_ERROR = "That project isn't yours"


@transaction.atomic
def set_desired_outcome(project, text):
    """What done looks like.

    A service rather than a line in the API handler, which is where this field
    has been written since August 20. **Not a refactor for its own sake**: it
    is `abandon_if`'s twin, that one needs a service for `brief_for` to read
    against, and one of a pair living in the API while the other lives here is
    how two fields that must stay distinguishable start drifting apart.
    """
    project.desired_outcome = (text or "").strip()
    project.save(update_fields=["desired_outcome"])
    return project


def set_abandonment_condition(project, text):
    """What would tell him it went wrong -- S10, and D4's answer.

    Separate from `desired_outcome` because **a tripwire you cannot tell from
    an ambition can never be checked**. See `Project.abandon_if`.
    """
    project.abandon_if = (text or "").strip()
    project.save(update_fields=["abandon_if"])
    return project


def set_project_notes(project, text):
    """Working notes on a project. Optional, like everything else here."""
    project.notes = (text or "").strip()
    project.save(update_fields=["notes"])
    return project


def create_project(owner, title, due_date=None, purpose=""):
    """A new, standalone project -- project-workspace-plan.md 2.

    Owner is passed directly rather than derived: a Project has no parent
    record left to borrow it from, the same shape create_list_with_item
    already uses.

    `purpose` is stripped like the title and, unlike it, may end up empty --
    it is optional by design (see the field). Whitespace-only collapses to
    "" so that "the person typed spaces" and "the person wrote nothing"
    are one state rather than two, which is the same reason the field is
    blank rather than null.
    """
    normalized = (title or "").strip()
    if not normalized:
        raise TaskConflict(EMPTY_PROJECT_TITLE_ERROR)
    return Project.objects.create(
        owner=owner,
        title=normalized,
        due_date=due_date,
        purpose=(purpose or "").strip(),
    )


def record_what_was_learned(project, text):
    """What he would do differently — **S12's fourth clause**.

    Its own verb rather than a field on the completion call, because the two
    happen at different moments: a project is marked done when the work stops,
    and the lesson arrives while looking at what the retrospective shows. Making
    one write both would mean closing a project demanded a sentence nobody has
    thought of yet, which is the toll `confirm_actionable` refuses to charge for
    filing.

    **Editable and never cleared by anything else.** A learning lost at the next
    state change is worse than none, because he would stop writing them.

    **No `@transaction.atomic`**, matching `set_abandonment_condition` and unlike
    `set_desired_outcome`: one `save()` is already atomic. It briefly had one --
    `complete_project`'s, taken by accident when this was inserted above it --
    and keeping a decorator acquired that way would be making a decision out of
    a slip.
    """
    project.learned = (text or "").strip()
    project.save(update_fields=["learned"])
    return project


@transaction.atomic
def complete_project(project):
    """Mark a project done, without touching a single one of its tasks.

    **The decorator went missing for four hours on August 23, 2026, and it was
    stolen rather than forgotten.** S12 inserted `record_what_was_learned`
    immediately above this function by anchoring a text replacement on
    `def complete_project(project):` -- which put the new function *between this
    decorator and its def*, so `record_what_was_learned` silently acquired it
    and this lost it. `select_for_update()` below needs a transaction, so
    `PATCH /api/v1/projects/{id}` with `is_completed` began returning a 500.

    **Anchoring an insertion on a `def` line is unsafe whenever a decorator can
    sit above it**, and nothing about the edit looked wrong afterwards: both
    functions read correctly in isolation and the diff showed an addition, not a
    move.

    **Every unit test covering it still passed**, because Django's `TestCase`
    wraps each test in a transaction and so supplied exactly the thing the code
    had lost. A test that provides the conditions production code depends on
    cannot discover that it depends on them. CI's browser job caught it within
    the hour; `tests/test_completing_a_project_outside_a_transaction.py` now
    holds it in a second rather than the minute that suite costs.

    Charter rule 5 -- a project references its tasks, it does not own their
    status. Someone finishing a project has said the *grouping* is done; if
    tasks are still open underneath, that is information worth seeing rather
    than something to tidy away silently. principles.md: automations propose,
    people decide.

    Completing an already-completed project keeps the original stamp, so a
    double-click cannot rewrite when the work actually finished.
    """
    project = Project.objects.select_for_update().get(pk=project.pk)
    if project.is_completed:
        return project
    project.is_completed = True
    project.completed_at = timezone.now()
    # Finishing a paused project is finishing it. Clearing the pause here is
    # what keeps "completed wins" a property of the data rather than a rule
    # every reader has to remember -- no row is ever both.
    project.paused_at = None
    project.save(update_fields=("is_completed", "completed_at", "paused_at"))
    return project


@transaction.atomic
def reopen_project(project):
    """Un-finish it. It comes back open, never paused.

    Reopening says the work is not done; it does not say it was parked. A
    project that should be parked is paused explicitly, which keeps that a
    decision somebody made rather than one this function guessed at.
    """
    project = Project.objects.select_for_update().get(pk=project.pk)
    project.is_completed = False
    project.completed_at = None
    project.save(update_fields=("is_completed", "completed_at"))
    return project


@transaction.atomic
def pause_project(project):
    """Park it: not finished, and not being worked on either.

    **Idempotent, and the date is why.** How long something has been sitting is
    the only thing this timestamp is for, so a second pause must not re-stamp
    it -- the same call `complete_project` makes above for the same reason.

    Touches no task. A decision about a container is not a decision about the
    work inside it, and a pause that quietly unpinned or re-dated things would
    be a destructive action wearing a soft word.
    """
    project = Project.objects.select_for_update().get(pk=project.pk)
    if project.paused_at is not None:
        return project
    project.paused_at = timezone.now()
    project.save(update_fields=("paused_at",))
    return project


@transaction.atomic
def resume_project(project):
    """Pick it back up. Clears the pause and nothing else."""
    project = Project.objects.select_for_update().get(pk=project.pk)
    project.paused_at = None
    project.save(update_fields=("paused_at",))
    return project


@transaction.atomic
def add_area_to_project(area, project):
    """Put an Area into a Project, or move it from one Project to another.

    project-workspace-plan.md 2. The guard below is a cross-row check a
    plain ForeignKey can't express on its own -- same "two owned records,
    guard they share an owner" shape as capture.services.link_ideas.
    Checked here rather than only at the API, so the invariant holds
    regardless of caller. principles.md: guards fail closed.
    """
    area = List.objects.select_for_update().get(pk=area.pk)
    if project.owner_id != area.owner_id:
        raise TaskConflict(FOREIGN_PROJECT_ERROR)
    area.project = project
    area.save(update_fields=("project",))
    return area


@transaction.atomic
def remove_area_from_project(area):
    """Take an Area out of its Project. A no-op if it has none."""
    area = List.objects.select_for_update().get(pk=area.pk)
    area.project = None
    area.save(update_fields=("project",))
    return area


def delete_project(project):
    """Hard delete -- charter rule 6, stated in the model too.

    Its areas survive: `List.project` is SET_NULL, so deleting a project
    says the grouping was wrong, not that the work is gone. No tombstone,
    because rule 2 does not apply -- nothing creates or holds a Project
    offline.
    """
    project.delete()
