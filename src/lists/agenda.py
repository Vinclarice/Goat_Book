"""Read-side logic for the agenda (the logged-in home page).

Everything here is query/derivation only -- mutations live in
lists.services. The bucketing rules are defined once and shared by the
HTML view, the React bootstrap payload, and the daily digest email, so
"overdue" always means the same thing in all three.
"""
from datetime import datetime, timedelta

from django.db.models import Count, F, Q
from django.utils import timezone

from lists.models import Item, List


OVERDUE = "overdue"
TODAY = "today"
WEEK = "week"
LATER = "later"
SOMEDAY = "someday"

# How far ahead "this week" reaches, counting from today.
WEEK_HORIZON_DAYS = 7

BUCKET_LABELS = {
    OVERDUE: "Overdue",
    TODAY: "Today",
    WEEK: "This week",
    LATER: "Later",
    SOMEDAY: "No due date",
}

# Ordered as they appear down the page.
BUCKET_ORDER = (OVERDUE, TODAY, WEEK, LATER, SOMEDAY)

# The far end of the agenda is reference material rather than a plan for
# the day, so it starts folded away.
COLLAPSED_BY_DEFAULT = frozenset({LATER, SOMEDAY})

# Buckets the daily digest email reports on.
DIGEST_BUCKETS = (OVERDUE, TODAY)


# Muted hues that read as labels rather than status against the dark
# surface. Assigned deterministically so a list keeps its colour.
LIST_COLORS = (
    "#8fc7d6", "#a8dba8", "#f4c98a", "#c9a8dc",
    "#f4a3a3", "#9ab6e0", "#e5a8c4", "#f1e394",
)


def color_for_list(list_id):
    return LIST_COLORS[list_id % len(LIST_COLORS)]


def annotate_for_display(items, today):
    """Attach template-friendly extras the ORM can't express.

    Django templates can't do date arithmetic or modulo, so the couple of
    derived values the markup needs are computed once here instead.
    """
    for item in items:
        item.list_color = color_for_list(item.list_id)
        item.days_overdue = (
            (today - item.due_date).days
            if item.due_date and item.due_date < today
            else 0
        )
    return items


def bucket_for(due_date, today):
    """Which agenda bucket a due date falls into, relative to ``today``."""
    if due_date is None:
        return SOMEDAY
    if due_date < today:
        return OVERDUE
    if due_date == today:
        return TODAY
    if due_date <= today + timedelta(days=WEEK_HORIZON_DAYS):
        return WEEK
    return LATER


def open_items_for(user):
    """Every task the user still has to do, across all of their lists."""
    return (
        Item.objects.filter(list__owner=user, status=Item.Status.ACTIVE)
        .select_related("list")
        .prefetch_related("tags")
        .order_by(F("due_date").asc(nulls_last=True), "position", "id")
    )


def completed_today_for(user, today=None):
    """Ticked-off-but-not-yet-archived tasks, so they can be undone."""
    today = today or timezone.localdate()
    # A range comparison (rather than the __date transform) lets Postgres
    # use a plain B-tree index on completed_at instead of requiring a
    # functional/expression index.
    start_of_day = timezone.make_aware(datetime.combine(today, datetime.min.time()))
    end_of_day = start_of_day + timedelta(days=1)
    return (
        Item.objects.filter(
            list__owner=user,
            status=Item.Status.COMPLETED,
            completed_at__gte=start_of_day,
            completed_at__lt=end_of_day,
        )
        .select_related("list")
        .prefetch_related("tags")
        .order_by("-completed_at", "-id")
    )


# Scope filters offered by the header numbers. "week" deliberately
# includes what's already late, matching summary_counts.
SCOPES = {
    OVERDUE: (OVERDUE,),
    TODAY: (TODAY,),
    WEEK: (OVERDUE, TODAY, WEEK),
}


def apply_filters(items, today, scope=None, list=None, tag=None):
    """Narrow an item sequence by scope, list id and tag name."""
    selected = items
    if scope in SCOPES:
        allowed = SCOPES[scope]
        selected = [
            item for item in selected
            if bucket_for(item.due_date, today) in allowed
        ]
    if list is not None:
        selected = [item for item in selected if item.list_id == list]
    if tag:
        selected = [
            item for item in selected
            if any(each.name == tag for each in item.tags.all())
        ]
    return selected


def bucketed(items, today):
    """Group an iterable of items into ``{bucket_key: [item, ...]}``."""
    groups = {key: [] for key in BUCKET_ORDER}
    for item in items:
        groups[bucket_for(item.due_date, today)].append(item)
    return groups


def list_summaries(user):
    """Each list with its open and overdue counts, for the sidebar."""
    today = timezone.localdate()
    summaries = list(
        List.objects.filter(owner=user)
        .annotate(
            open_count=Count(
                "item",
                filter=Q(item__status=Item.Status.ACTIVE),
                distinct=True,
            ),
            overdue_count=Count(
                "item",
                filter=Q(
                    item__status=Item.Status.ACTIVE,
                    item__due_date__lt=today,
                ),
                distinct=True,
            ),
        )
        .order_by("id")
    )
    for each in summaries:
        each.color = color_for_list(each.id)
    return summaries


def tag_summaries(items):
    """Tag names used by the given open items, with counts, A-Z.

    Derived from the already-prefetched items rather than a fresh query,
    so tags with nothing open left don't clutter the sidebar.
    """
    counts = {}
    for item in items:
        for tag in item.tags.all():
            counts[tag.name] = counts.get(tag.name, 0) + 1
    return [
        {"name": name, "count": counts[name]} for name in sorted(counts)
    ]


def summary_counts(groups):
    """Headline numbers shown in the agenda header."""
    overdue = len(groups[OVERDUE])
    today = len(groups[TODAY])
    return {
        "overdue": overdue,
        "today": today,
        # "This week" is everything with a deadline inside the horizon,
        # including what's already late -- it's a workload number.
        "week": overdue + today + len(groups[WEEK]),
        "open": sum(len(items) for items in groups.values()),
    }


def digest_items_for(user, today=None):
    """The tasks a daily reminder email should mention, in order."""
    today = today or timezone.localdate()
    groups = bucketed(open_items_for(user), today)
    return [item for key in DIGEST_BUCKETS for item in groups[key]]
