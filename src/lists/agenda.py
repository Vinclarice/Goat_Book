"""Read-side logic for the agenda (the logged-in home page).

Everything here is query/derivation only -- mutations live in
lists.services. The bucketing rules are defined once and shared by the
/api/v1/agenda payload and the daily digest email, so "overdue" always
means the same thing in both.
"""
from datetime import datetime, timedelta

from django.db.models import Case, Count, F, IntegerField, Q, Value, When
from django.urls import reverse
from django.utils import timezone

from lists import money
from lists.models import Item, List, Priority
from lists.serializers import project_ref_for, serialize_item


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


# A task standing on its own is not in any Area, so it must not be tinted like
# one -- borrowing a colour would say it belonged somewhere it does not, and
# borrowing index 0 would make it look like whichever Area happens to hold that
# slot. Grey is the absence of the signal rather than another value of it.
NO_LIST_COLOR = "#c9cdd2"


def color_for_list(list_id):
    if list_id is None:
        return NO_LIST_COLOR
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


def age_in_days(created_at, today):
    """How many of the owner's days something has been waiting.

    Measured between two *local* dates rather than from the raw timestamp,
    because that is the number a person means -- and computed here rather
    than in the browser, whose zone is not the account's. A phone in
    Makassar and a laptop in New York must agree about how long something
    has been open.

    Never negative: clock skew or a backdated import should read as "made
    today" rather than as the future.

    Lives in this module rather than on the Daily Page that first needed it
    (Crane 2 slice 5), because Crane 3's weekly review reports the same
    number about the same tasks, and two implementations of "how old is
    this" would drift the first time one of them was corrected. What has
    *not* moved is the contract decision: `age_in_days` stays off `TaskOut`,
    and only surfaces with a "today" to measure against serialise it.
    """
    return max(0, (today - timezone.localtime(created_at).date()).days)


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


# DARK: no production caller. **Not dead -- the server half of a mirrored
# rule.** `frontend/src/agenda.ts:71` says so at its own copy: *"Mirrors
# lists.agenda.snooze_presets -- see there for the edge cases."* The SPA
# computes the menu, and this is the reference the edge cases are reasoned and
# tested against.
# Decision registered: `mirrored-rules-brief.md` owns whether the mirror
# collapses to one side. Deleting this half would leave the TypeScript as the
# only statement of the two ambiguous days, which is the divergence that brief
# was written about.
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
    """Every task the user still has to do, across all of their lists.

    **No bills, and no filter for them either.** For one day this took an
    `include_bills` flag, while some callers wanted the task-backed bills and
    others did not; increment 4 of `bill-as-a-model-plan.md` settled it by
    making a bill something other than an `Item`, so there is nothing here to
    include or exclude. Every surface that shows bills has a `Bill` source of
    its own — `open_bill_rows_for` for the agenda and the day,
    `money.open_bills_for` and `money.coming_bills_for` for the digest and the
    calendar.

    **Income is not one of them.** A salary is money moving toward you on a
    date, which the money module tracks and can call late -- but it is not
    something you *do*, and "Salary" sitting on the day page every month is a
    line nobody can act on. Vince's call, August 27, 2026: money in belongs to
    Money only.

    **Bills stay**, deliberately and by the same reasoning. Paying one is a real
    thing to do on the day it is due, and the agenda is where you would notice
    it is late.

    Filtered here rather than in each caller because this is the single
    selection point the day and the agenda both use -- which is why the
    exclusion costs one clause instead of an audit.
    """
    return (
        Item.objects.filter(owner=user, status=Item.Status.ACTIVE)
        .select_related("list")
        .prefetch_related("tags")
        .annotate(
            # Explicit rather than alphabetical: the values sort "high, low,
            # none" as text, and what is wanted is high, then unmarked, then
            # low. `Priority.NONE` sits in the middle because it *is* the
            # middle -- an unmarked task is ordinary, not lowest.
            priority_rank=Case(
                When(priority=Priority.HIGH, then=Value(0)),
                When(priority=Priority.LOW, then=Value(2)),
                default=Value(1),
                output_field=IntegerField(),
            )
        )
        # **After the due date, never before it.** Sorting emphasis above a
        # date would bury something overdue under something starred, which is
        # worse than having no priority at all. It orders *within* a day.
        #
        # Server-side only, unlike `bucket_for` and `WEEK_HORIZON_DAYS`: no
        # client mirrors this ordering, so it is not a fourth copy of anything.
        .order_by(
            F("due_date").asc(nulls_last=True), "priority_rank", "position", "id"
        )
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
            owner=user,
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


# DARK: no production caller. The same shape as `snooze_presets` above:
# `frontend/src/agenda.ts:182` exports its own `tagSummaries`, which is what
# `AgendaWorkspace.tsx` renders. This half stopped being called when the
# sidebar moved into the SPA and nothing said so.
# Decision registered: `mirrored-rules-brief.md`, as above. The counting rule
# -- open items only, so a tag with nothing left does not clutter the sidebar
# -- is the part worth keeping stated in both languages or in neither.
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


def open_bill_rows_for(user):
    """The bills the agenda and the day carry, in the shape `_agenda_bill_out`
    reads.

    **One query, two surfaces**, for the reason `open_items_for` is one query:
    the agenda and the day disagreeing about which bills exist is a defect
    nobody would find by reading either. Money coming in is excluded here
    exactly as `open_items_for` excludes it -- a salary is not a thing to do
    on a day.

    **Sourced from tasks with a sidecar until the flip.** After it, this is
    where `Bill.objects` arrives and neither caller changes --
    `bill-as-a-model-plan.md` increment 5.
    """
    return money.open_bills_for(user)


def _agenda_bill_out(bill):
    """One bill, as the agenda and the day carry it.

    **Not `serialize_item`.** A bill row on these screens needs what a bill is
    -- payee, what it comes to, whether it is settled -- and none of what a
    task is. Sending a `TaskOut` would mean synthesising a dozen fields a bill
    has not got, and the SPA would offer to file it in an area.

    **`task_id`, not an id of its own**, until the flip: pay and delete are
    keyed on it. The name survives the switch even though what it points at
    changes, which is the one piece of this that will read oddly for a while
    and is cheaper than a rename on both sides.
    """
    series = bill.series
    return {
        "task_id": bill.id,
        "payee": bill.payee,
        "due_date": bill.due_date.isoformat(),
        "amount": str(bill.amount) if bill.amount is not None else None,
        "currency": bill.currency,
        "direction": bill.direction,
        "repeats": series is not None and series.ended_at is None,
    }


def workspace_data_for(
    user, *, today, all_open, completed_today, lists, archived_count, projects,
    open_bills=(),
):
    """Shapes the agenda JSON payload served by /api/v1/agenda.

    Callers supply already-queried data rather than this function
    querying itself, since /api/v1/agenda needs the same rows for the
    archived-count query it runs alongside this one.

    `open_bills` defaults to empty so the many tests that build a payload
    without them keep working; the endpoint passes the real ones.
    """
    return {
        "today": today.isoformat(),
        "username": user.username,
        "archive_url": reverse("archive"),
        "archived_count": archived_count,
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
        # **Decision 4, kept while the model splits.** Bills are on this screen
        # because paying is a real thing to do on a day -- and a bill that is
        # no longer an `Item` cannot arrive in `items`, so it arrives here.
        #
        # **Sourced from the task-backed rows today**, and keyed on `task_id`
        # for the same reason `/money/bills/:id` is: the pay and delete
        # endpoints take that key, so a `Bill`-sourced row could not be acted
        # on until they move. The array lands now and its source changes at the
        # flip, which is the sequencing the detail page already used.
        "bills": [_agenda_bill_out(item) for item in open_bills],
        "completed_today": [serialize_item(item) for item in completed_today],
        "areas": [
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
        # ui-second-pass-plan.md F2: a task carries a project_id but nothing
        # in the payload said what that project was, so the Agenda row had
        # no title to show.
        "projects": [project_ref_for(each) for each in projects],
    }


def coming_up_for(user, today=None):
    """Open tasks inside their own lead time, soonest first.

    Advance notice, and deliberately a *separate* list from what is due: a task
    with a lead time is not overdue early and is not due early, it is mentioned
    early. `bucket_for` is untouched, which is also what keeps this out of the
    three languages that mirror it.

    Strictly after today, so nothing appears here and in the digest's own list
    at once -- saying a thing twice in one email is how a reminder starts being
    skimmed. Zero lead time is off rather than "the day itself", or every dated
    task in the product would join in.
    """
    today = today or timezone.localdate()
    # Filtered here rather than in SQL, which reads like the lazier choice and
    # is the cheaper one: `digest_items_for` below already materialises this
    # exact queryset to bucket it, so a database-side version would be a
    # second full scan of rows already in memory. The comparison is per-row
    # against that row's own `lead_days`, which is also why it cannot be a
    # plain `due_date__lte` bound.
    return sorted(
        (
            item
            for item in open_items_for(user)
            if item.lead_days
            and item.due_date is not None
            and today < item.due_date <= today + timedelta(days=item.lead_days)
        ),
        key=lambda item: (item.due_date, item.id),
    )


def digest_items_for(user, today=None):
    """The tasks a daily reminder email should mention, in order."""
    today = today or timezone.localdate()
    groups = bucketed(open_items_for(user), today)
    return [item for key in DIGEST_BUCKETS for item in groups[key]]
