from django.urls import reverse


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
