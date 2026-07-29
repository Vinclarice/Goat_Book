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
        "list": {
            "id": item.list_id,
            "title": item.list.title,
            "url": item.list.get_absolute_url(),
        },
        "update_url": reverse("api_item_detail", args=(item.id,)),
        "delete_url": reverse("api_item_detail", args=(item.id,)),
    }
