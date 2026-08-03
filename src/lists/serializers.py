from django.urls import reverse

from lists.models import List


def serialize_checklist_step(step):
    return {
        "id": step.id,
        "text": step.text,
        "position": step.position,
        "is_done": step.is_done,
        "completed_at": (
            step.completed_at.isoformat() if step.completed_at else None
        ),
        "carries_forward": step.carries_forward,
        "task_id": step.task_id,
        # update and delete hit the same endpoint, same shape as Task's url.
        "url": reverse("api_checklist_step_detail", args=(step.id,)),
        "promote_url": reverse("api_checklist_step_promote", args=(step.id,)),
    }


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
        "checklist_steps": [
            serialize_checklist_step(step)
            for step in item.checklist_steps.order_by("position", "id")
        ],
        "create_checklist_step_url": reverse(
            "api_create_checklist_step", args=(item.id,)
        ),
        "reorder_checklist_steps_url": reverse(
            "api_reorder_checklist_steps", args=(item.id,)
        ),
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
