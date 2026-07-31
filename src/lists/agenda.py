"""Read-side logic for the agenda (the logged-in home page).

Everything here is query/derivation only -- mutations live in
lists.services. The bucketing rules are defined once and shared by the
/api/v1/agenda payload and the daily digest email, so "overdue" always
means the same thing in both.
"""
from datetime import datetime, timedelta

from django.db.models import Count, F, Q
from django.urls import reverse
from django.utils import timezone

from lists.models import Item, List
from lists.serializers import serialize_item


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


SNOOZE_TOMORROW = "tomorrow"
SNOOZE_WEEKEND = "weekend"
SNOOZE_NEXT_WEEK = "next_week"
SNOOZE_CLEAR = "clear"

# date.weekday() indices for the two days the presets pivot on.
MONDAY = 0
SATURDAY = 5

# Kept in one place so frontend/src/agenda.ts can mirror the literal
# strings a user reads rather than a paraphrase of them.
SNOOZE_LABELS = {
    SNOOZE_TOMORROW: "Tomorrow",
    SNOOZE_WEEKEND: "This weekend",
    SNOOZE_NEXT_WEEK: "Next week",
    SNOOZE_CLEAR: "Clear",
}

# Ordered as they appear down the menu, soonest first.
SNOOZE_ORDER = (SNOOZE_TOMORROW, SNOOZE_WEEKEND, SNOOZE_NEXT_WEEK, SNOOZE_CLEAR)


# Muted hues that read as labels rather than status against the dark
# surface. Assigned deterministically so a list keeps its colour.
# Still used by the daily digest email, which hasn't migrated to the API.
# LIST_COLOR_KEYS is the semantic equivalent served over /api/v1/ (see
# the List-Color Contract in the UI overhaul plan); the two are indexed
# identically so a list reads as the same hue in both places.
LIST_COLORS = (
    "#8fc7d6", "#a8dba8", "#f4c98a", "#c9a8dc",
    "#f4a3a3", "#9ab6e0", "#e5a8c4", "#f1e394",
)

LIST_COLOR_KEYS = (
    "sky", "sage", "amber", "lilac",
    "coral", "azure", "blush", "straw",
)


def color_for_list(list_id):
    return LIST_COLORS[list_id % len(LIST_COLORS)]


def color_key_for_list(list_id):
    return LIST_COLOR_KEYS[list_id % len(LIST_COLOR_KEYS)]


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


def next_weekday(today, weekday):
    """The first date strictly after ``today`` falling on ``weekday``."""
    ahead = (weekday - today.weekday()) % 7
    return today + timedelta(days=ahead or 7)


def snooze_presets(today):
    """The due dates the snooze menu offers, relative to ``today``.

    Every dated option lands strictly in the future, so picking one is
    never a no-op. That decides the two ambiguous days: on a Saturday
    "this weekend" is the Sunday still to come, and on a Sunday the
    weekend is spent so it rolls on to the next Saturday. "Next week" is
    read the same way -- on a Monday it means the Monday after this one,
    not today.
    """
    weekend = (
        today + timedelta(days=1)
        if today.weekday() == SATURDAY
        else next_weekday(today, SATURDAY)
    )
    dates = {
        SNOOZE_TOMORROW: today + timedelta(days=1),
        SNOOZE_WEEKEND: weekend,
        SNOOZE_NEXT_WEEK: next_weekday(today, MONDAY),
        SNOOZE_CLEAR: None,
    }
    return [
        {"key": key, "label": SNOOZE_LABELS[key], "due_date": dates[key]}
        for key in SNOOZE_ORDER
    ]


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
        each.color_key = color_key_for_list(each.id)
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


def workspace_data_for(user, *, today, all_open, completed_today, lists, archived_count):
    """Shapes the agenda JSON payload served by /api/v1/agenda.

    Callers supply already-queried data rather than this function
    querying itself, since /api/v1/agenda needs the same rows for the
    archived-count query it runs alongside this one.
    """
    return {
        "today": today.isoformat(),
        "username": user.username,
        "archive_url": reverse("archive"),
        "archived_count": archived_count,
        "new_list_url": reverse("new_list"),
        "settings_url": reverse("account_settings"),
        "daily_digest": user.daily_digest,
        "buckets": [
            {
                "key": key,
                "label": BUCKET_LABELS[key],
                "collapsed": key in COLLAPSED_BY_DEFAULT,
            }
            for key in BUCKET_ORDER
        ],
        "items": [serialize_item(item) for item in all_open],
        "completed_today": [serialize_item(item) for item in completed_today],
        "lists": [
            {
                "id": each.id,
                "title": each.title,
                "url": each.get_absolute_url(),
                "create_item_url": reverse("api_create_item", args=(each.id,)),
                "open_count": each.open_count,
                "overdue_count": each.overdue_count,
                "color_key": each.color_key,
            }
            for each in lists
        ],
    }


def digest_items_for(user, today=None):
    """The tasks a daily reminder email should mention, in order."""
    today = today or timezone.localdate()
    groups = bucketed(open_items_for(user), today)
    return [item for key in DIGEST_BUCKETS for item in groups[key]]
