from django.db.models import Count, Q
from django.urls import reverse

from lists.models import Item, List


def annotate_subtask_counts(queryset):
    """Adds subtask_total/subtask_done so serialize_item doesn't fall back to
    a per-row count. Apply it at query sites that serialise many items.
    """
    return queryset.annotate(
        subtask_total=Count(
            "subtasks",
            filter=~Q(subtasks__status=Item.Status.ARCHIVED),
            distinct=True,
        ),
        subtask_done=Count(
            "subtasks",
            filter=Q(subtasks__status=Item.Status.COMPLETED),
            distinct=True,
        ),
    )


def subtask_counts_for(item):
    """Open-and-completed counts for a task's children.

    Prefers the annotations added by annotate_subtask_counts() and falls back
    to counting in Python, which uses a prefetch when one is in play. The
    fallback exists so a caller that forgets to annotate gets a slow answer
    rather than a silently wrong "0/0" -- a subtask count that reads zero when
    five subtasks exist is worse than an extra query at this scale.
    """
    total = getattr(item, "subtask_total", None)
    done = getattr(item, "subtask_done", None)
    if total is None or done is None:
        children = [
            child
            for child in item.subtasks.all()
            if child.status != "archived"
        ]
        total = len(children)
        done = sum(1 for child in children if child.status == "completed")
    return {"total": total, "done": done}


def serialize_item(item):
    return {
        "id": item.id,
        "text": item.text,
        "status": item.status,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
        "completed_at": (
            item.completed_at.isoformat() if item.completed_at else None
        ),
        "archived_at": item.archived_at.isoformat() if item.archived_at else None,
        "due_date": item.due_date.isoformat() if item.due_date else None,
        "position": item.position,
        "tags": [tag.name for tag in item.tags.all()],
        "recurrence": item.recurrence,
        "notes": item.notes,
        # id + text, because the agenda shows a breadcrumb beside subtask rows
        # and would otherwise need a second lookup per row to render it.
        "parent": (
            {"id": item.parent_id, "text": item.parent.text}
            if item.parent_id
            else None
        ),
        # Counts rather than nested children: the list page fetches the whole
        # list anyway and nests client-side, while the agenda only needs "2/5".
        "subtask_counts": subtask_counts_for(item),
        # Just the id -- callers already have (or can fetch) the list's
        # title/url from the top-level `lists` array in the page payload,
        # so it doesn't need repeating on every single task.
        "list_id": item.list_id,
        # update and delete hit the same endpoint, just with different
        # HTTP methods, so one url covers both.
        "url": reverse("api_item_detail", args=(item.id,)),
        "edit_url": reverse("edit_item", args=(item.id,)),
    }


def list_ref_for(our_list):
    return {
        "id": our_list.id,
        "title": our_list.title,
        "create_item_url": reverse("api_create_item", args=(our_list.id,)),
        "reorder_url": reverse("api_reorder_items", args=(our_list.id,)),
    }


def list_workspace_data_for(our_list, items):
    """Shapes the list-detail JSON shared by the Django-rendered list page's
    React bootstrap data and the /api/v1/lists/{id} endpoint, so the two
    can't drift apart -- same reasoning as agenda.workspace_data_for().
    """
    return {
        "list": list_ref_for(our_list),
        "items": [serialize_item(item) for item in items],
    }


def task_detail_data_for(item):
    """Shapes the single-task JSON for /api/v1/tasks/{id} -- there's no
    Django-rendered equivalent to share a contract with (edit_item.html
    is HTML-only), so this is genuinely new rather than extracted from
    an existing view.
    """
    return {
        "task": serialize_item(item),
        "list": {
            "id": item.list.id,
            "title": item.list.title,
            "url": item.list.get_absolute_url(),
        },
        # The detail view is where subtasks are managed, so it gets the
        # children themselves rather than just the counts every other
        # serialised task carries. Archived children stay in the archive.
        "subtasks": [
            serialize_item(child)
            for child in annotate_subtask_counts(
                item.subtasks.exclude(status=Item.Status.ARCHIVED)
            )
            .select_related("list", "parent")
            .prefetch_related("tags")
            .order_by("position", "id")
        ],
    }


def archive_workspace_data_for(user, archived_items):
    """Shapes the archive JSON shared by the Django-rendered archive page's
    React bootstrap data and the /api/v1/archive endpoint.
    """
    return {
        "items": [serialize_item(item) for item in archived_items],
        # Task JSON only carries list_id; the frontend joins against this
        # to show a list's title and link.
        "lists": [
            {
                "id": each.id,
                "title": each.title,
                "url": each.get_absolute_url(),
            }
            for each in List.objects.filter(owner=user)
        ],
    }
