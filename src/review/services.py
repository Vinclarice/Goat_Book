"""Write-side logic for the weekly review. Reads live in review.reads.

The module charter rule 4 asks for, arriving with the first record rather
than as an empty file three slices ago. Everything the review *displays* is
still a read; this is only what a person writes and the one thing the
product records on their behalf when they say the week is reviewed.
"""
from django.db import transaction
from django.utils import timezone

from review import reads
from review.models import (
    PlanningSession,
    WeeklyIntention,
    WeeklyOutcome,
    WeeklyReview,
)
from review.weeks import week_start_for


# "Not mentioned" as distinct from "cleared to empty", the same sentinel
# daily.services uses and for the same reason: a page saving one section
# must not blank one it never displayed.
_UNSET = object()


@transaction.atomic
def write_review(owner, day, *, reflections=_UNSET, plan=_UNSET):
    """Create or update this owner's review of the week ``day`` falls in.

    The week is snapped here rather than trusted from the caller, so a
    link to Wednesday and a link to Monday cannot produce two records for
    one week. `get_or_create` under the unique constraint makes concurrent
    first-writes safe.

    There is no separate create and update, because somebody writing about
    their week neither knows nor cares whether a row exists yet.
    """
    review, _ = WeeklyReview.objects.get_or_create(
        owner=owner, week_start=week_start_for(day)
    )
    updated = []
    for field, value in (("reflections", reflections), ("plan", plan)):
        if value is _UNSET:
            continue
        setattr(review, field, value or "")
        updated.append(field)
    if updated:
        review.save(update_fields=[*updated, "updated_at"])
    return review


@transaction.atomic
def complete_review(owner, day):
    """Mark the week reviewed, recording the figure it reported.

    Completing an already-completed review keeps the first answer. It
    records when the week was reviewed, not when somebody last pressed the
    button -- the same rule `pause_routine` follows for the same reason.

    This service reads in order to write, which is not the split charter
    rule 4 forbids: what that rule forbids is read-side code mutating. The
    figure has to come from `reads.planned_in_week` rather than from the
    request, because a caller passing its own numbers would let two clients
    stamp two different conclusions on one week.
    """
    week_start = week_start_for(day)
    review, _ = WeeklyReview.objects.get_or_create(
        owner=owner, week_start=week_start
    )
    if review.completed_at is not None:
        return review
    planned = reads.planned_in_week(
        owner, week_start, reads.week_bounds(day)[1]
    )
    review.completed_at = timezone.now()
    review.recorded_planned_total = planned.total
    review.recorded_planned_met = len(planned.met)
    review.save(
        update_fields=[
            "completed_at",
            "recorded_planned_total",
            "recorded_planned_met",
            "updated_at",
        ]
    )
    return review


@transaction.atomic
def reopen_review(owner, day):
    """Un-finish a review, dropping the figure it recorded.

    A one-way door on a mis-tap is not a recoverable failure, and
    `principles.md` asks that failure be recoverable. The recorded counts
    go with it rather than lingering: a review that is open again has
    concluded nothing, and a stale figure beside live lists would be the
    two-sources-of-truth problem the stamp exists to solve, pointed the
    wrong way.

    Nothing is written for a week that was never completed.
    """
    review = WeeklyReview.objects.filter(
        owner=owner, week_start=week_start_for(day)
    ).first()
    if review is None or review.completed_at is None:
        return review
    review.completed_at = None
    review.recorded_planned_total = None
    review.recorded_planned_met = None
    review.save(
        update_fields=[
            "completed_at",
            "recorded_planned_total",
            "recorded_planned_met",
            "updated_at",
        ]
    )
    return review


@transaction.atomic
def set_intention(owner, day, text):
    """Say what the week containing ``day`` is for -- S9.

    ``day`` is any day of the week, normalised through `week_start_for`, which
    is what lets Wednesday rewrite what Sunday decided without making a second
    row. Two definitions of "this week" is the drift `crane-plan.md` §6 names,
    so this borrows the one that exists rather than taking a Monday from the
    caller.

    Blank is a value, not a delete. An intention cleared to empty stays as a
    row, because "I set none this week" and "I never opened it" are different
    facts and only one of them says the practice lapsed -- the same call
    `DailyEntry` and `WeeklyReview` both make.
    """
    intention, _ = WeeklyIntention.objects.get_or_create(
        owner=owner, week_start=week_start_for(day)
    )
    intention.text = text or ""
    intention.save(update_fields=["text", "updated_at"])
    return intention


@transaction.atomic
def open_planning_session(owner, day):
    """Record that somebody sat down to plan the week containing ``day``.

    **Idempotent, and `created_at` is why.** When the ritual was first opened
    is the fact this row exists to hold; a second open that re-stamped it would
    rewrite that for no gain -- the same call `complete_project` and
    `pause_project` both make.

    Takes any day and normalises, like every week-keyed write here, so opening
    the planner from a Wednesday cannot make a second row for the same week.
    """
    session, _ = PlanningSession.objects.get_or_create(
        owner=owner, week_start=week_start_for(day),
    )
    return session


@transaction.atomic
def set_week_unusual(owner, day, unusual):
    """Say this week is not a typical one — or take that back.

    **Opens a session if none is open.** Correcting what the system believed
    *is* planning, so requiring a separate open first would let a correction be
    recorded against a week nobody sat down with -- and would mean the ritual's
    denominator missed everybody who only corrected something.

    Stores a direction and never a number. `typical_week_for` stays the
    authority on what a week holds; nothing multiplies the two together,
    because a declared figure beside a derived one is two authorities for one
    rule.
    """
    session = open_planning_session(owner, day)
    session.unusual = unusual
    session.save(update_fields=["unusual", "updated_at"])
    return session


@transaction.atomic
def choose_outcome(owner, day, *, text, project=None):
    """Commit to something being true by the end of this week — increment 5.

    **Snapshots the project's title at the moment of choosing**, charter rule
    3. The FK stays as a live reference for reaching the project; the copy is
    what stops a rename rewriting what somebody committed to. A project deleted
    later leaves the outcome standing, readable from the copy.

    `position` is the order chosen and never a ranking. Which outcome matters
    more is the person's to say, and a number the system sorted by would
    quietly become one.
    """
    week_start = week_start_for(day)
    taken = WeeklyOutcome.objects.filter(
        owner=owner, week_start=week_start
    ).count()
    return WeeklyOutcome.objects.create(
        owner=owner,
        week_start=week_start,
        text=text,
        project=project,
        project_title=project.title if project else "",
        position=taken,
    )


@transaction.atomic
def reword_outcome(owner, outcome_id, text):
    """Say it differently. Owner-scoped in the lookup rather than checked
    afterwards, so there is no comparison to forget."""
    outcome = WeeklyOutcome.objects.get(pk=outcome_id, owner=owner)
    outcome.text = text
    outcome.save(update_fields=["text", "updated_at"])
    return outcome


@transaction.atomic
def drop_outcome(owner, outcome_id):
    """Take it off the week.

    A hard delete, which every other week-keyed record here refuses. Their
    rows exist because their *presence* answers "did this practice happen",
    and `PlanningSession` already answers that for planning -- so an outcome
    is free to be what it looks like, a chosen thing that can be un-chosen.
    """
    WeeklyOutcome.objects.get(pk=outcome_id, owner=owner).delete()
