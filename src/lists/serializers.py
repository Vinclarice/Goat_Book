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
        # Just the id -- callers already have (or can fetch) the area's
        # title/url from the top-level `areas` array in the page payload,
        # so it doesn't need repeating on every single task.
        # `item.list_id` is the ORM's column; `area_id` is what the boundary
        # calls it, the same split Item/"task" already lives with.
        "area_id": item.list_id,
        # Null for most tasks. A task belongs to an Area always and to a
        # Project optionally -- release-d-plan.md 3's additive shape.
        "project_id": item.project_id,
        # update and delete hit the same endpoint, just with different
        # HTTP methods, so one url covers both.
        "url": reverse("api_item_detail", args=(item.id,)),
        "edit_url": reverse("edit_item", args=(item.id,)),
    }


def area_ref_for(our_list):
    return {
        "id": our_list.id,
        "title": our_list.title,
        # Still `create_item_url`/`api_create_item`: that spelling belongs to
        # the unfinished Item -> "task" rename, not to this one. Renaming it
        # here would make one commit answer for two vocabularies.
        "create_item_url": reverse("api_create_item", args=(our_list.id,)),
        "reorder_url": reverse("api_reorder_items", args=(our_list.id,)),
    }


def area_workspace_data_for(our_list, items):
    """Shapes the area-detail JSON shared by the Django-rendered area page's
    React bootstrap data and the /api/v1/areas/{id} endpoint, so the two
    can't drift apart -- same reasoning as agenda.workspace_data_for().
    """
    return {
        "area": area_ref_for(our_list),
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
        "area": {
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
        # Task JSON only carries area_id; the frontend joins against this
        # to show an area's title and link.
        "areas": [
            {
                "id": each.id,
                "title": each.title,
                "url": each.get_absolute_url(),
            }
            for each in List.objects.filter(owner=user)
        ],
    }
