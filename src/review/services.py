"""Write-side logic for the weekly review. Reads live in review.reads.

The module charter rule 4 asks for, arriving with the first record rather
than as an empty file three slices ago. Everything the review *displays* is
still a read; this is only what a person writes and the one thing the
product records on their behalf when they say the week is reviewed.
"""
from django.db import transaction
from django.utils import timezone

from review import reads
from review.models import WeeklyReview
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
