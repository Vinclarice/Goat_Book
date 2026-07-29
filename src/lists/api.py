import json
from datetime import date
from functools import wraps

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from lists import services
from lists.models import Item, List
from lists.serializers import serialize_item


class _InvalidDueDate(Exception):
    pass


def _parse_due_date(value):
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise _InvalidDueDate from None


def api_login_required(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse(
                {"errors": {"authentication": ["Login required."]}},
                status=401,
            )
        return view(request, *args, **kwargs)

    return wrapped


def _read_json(request):
    try:
        payload = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None, JsonResponse(
            {"errors": {"body": ["Send a valid JSON object."]}},
            status=400,
        )
    if not isinstance(payload, dict):
        return None, JsonResponse(
            {"errors": {"body": ["Send a JSON object."]}},
            status=400,
        )
    return payload, None


def _owned_item(request, item_id):
    return Item.objects.select_related("list").filter(
        id=item_id,
        list__owner=request.user,
    ).first()


@api_login_required
@require_http_methods(["POST"])
def create_item(request, list_id):
    our_list = List.objects.filter(id=list_id, owner=request.user).first()
    if our_list is None:
        return JsonResponse(
            {"errors": {"item": ["Task not found."]}},
            status=404,
        )

    payload, error_response = _read_json(request)
    if error_response:
        return error_response
    try:
        due_date = _parse_due_date(payload.get("due_date"))
    except _InvalidDueDate:
        return JsonResponse(
            {"errors": {"due_date": ["Use a valid date (YYYY-MM-DD)."]}},
            status=400,
        )
    tags = payload.get("tags")
    if tags is not None and (
        not isinstance(tags, list) or not all(isinstance(t, str) for t in tags)
    ):
        return JsonResponse(
            {"errors": {"tags": ["Send a list of tag names."]}},
            status=400,
        )
    recurrence = payload.get("recurrence")
    if recurrence is not None and recurrence not in Item.Recurrence.values:
        return JsonResponse(
            {"errors": {"recurrence": ["Choose a valid recurrence."]}},
            status=400,
        )
    try:
        item = services.create_item(
            our_list,
            payload.get("text"),
            due_date=due_date,
            tags=tags,
            recurrence=recurrence,
        )
    except services.TaskConflict as error:
        return JsonResponse(
            {"errors": {"text": [str(error)]}},
            status=400,
        )
    item = Item.objects.select_related("list").get(pk=item.pk)
    return JsonResponse({"data": serialize_item(item)}, status=201)


@api_login_required
@require_http_methods(["POST"])
def reorder_items(request, list_id):
    our_list = List.objects.filter(id=list_id, owner=request.user).first()
    if our_list is None:
        return JsonResponse(
            {"errors": {"list": ["List not found."]}},
            status=404,
        )

    payload, error_response = _read_json(request)
    if error_response:
        return error_response
    ordered_ids = payload.get("ordered_ids")
    if not isinstance(ordered_ids, list) or not all(
        isinstance(value, int) for value in ordered_ids
    ):
        return JsonResponse(
            {"errors": {"ordered_ids": ["Send a list of item ids."]}},
            status=400,
        )

    try:
        services.reorder_items(our_list, ordered_ids)
    except services.TaskConflict as error:
        return JsonResponse(
            {"errors": {"ordered_ids": [str(error)]}},
            status=409,
        )

    items = Item.objects.filter(id__in=ordered_ids).select_related("list")
    by_id = {item.id: item for item in items}
    return JsonResponse(
        {"data": [serialize_item(by_id[item_id]) for item_id in ordered_ids]},
    )


@api_login_required
@require_http_methods(["PATCH", "DELETE"])
def item_detail(request, item_id):
    item = _owned_item(request, item_id)
    if item is None:
        return JsonResponse(
            {"errors": {"item": ["Task not found."]}},
            status=404,
        )

    if request.method == "DELETE":
        try:
            services.delete_archived_item(item)
        except services.InvalidTaskTransition as error:
            return JsonResponse(
                {"errors": {"status": [str(error)]}},
                status=400,
            )
        return JsonResponse({"data": {"deleted": item_id}})

    payload, error_response = _read_json(request)
    if error_response:
        return error_response
    changed_fields = {
        "text", "status", "due_date", "tags", "recurrence",
    }.intersection(payload)
    if len(changed_fields) != 1:
        return JsonResponse(
            {
                "errors": {
                    "body": [
                        "Change exactly one of text, status, due_date, tags, "
                        "or recurrence per request."
                    ]
                }
            },
            status=400,
        )

    spawned = None
    try:
        if "text" in changed_fields:
            item = services.edit_item(item, payload["text"])
        elif "due_date" in changed_fields:
            try:
                due_date = _parse_due_date(payload["due_date"])
            except _InvalidDueDate:
                return JsonResponse(
                    {"errors": {"due_date": ["Use a valid date (YYYY-MM-DD)."]}},
                    status=400,
                )
            item = services.set_due_date(item, due_date)
        elif "tags" in changed_fields:
            tags = payload["tags"]
            if not isinstance(tags, list) or not all(
                isinstance(t, str) for t in tags
            ):
                return JsonResponse(
                    {"errors": {"tags": ["Send a list of tag names."]}},
                    status=400,
                )
            item = services.set_item_tags(item, tags)
        elif "recurrence" in changed_fields:
            item = services.set_recurrence(item, payload["recurrence"])
        else:
            requested_status = payload["status"]
            if requested_status == Item.Status.ACTIVE:
                item = services.reopen_item(item)
            elif requested_status == Item.Status.COMPLETED:
                if item.status == Item.Status.ARCHIVED:
                    item = services.restore_item(item)
                else:
                    item = services.complete_item(item)
                    spawned = getattr(item, "_spawned", None)
            elif requested_status == Item.Status.ARCHIVED:
                item = services.archive_item(item)
            else:
                return JsonResponse(
                    {"errors": {"status": ["Choose a valid task status."]}},
                    status=400,
                )
    except services.TaskConflict as error:
        return JsonResponse(
            {"errors": {"conflict": [str(error)]}},
            status=409,
        )
    except services.InvalidTaskTransition as error:
        return JsonResponse(
            {"errors": {"status": [str(error)]}},
            status=400,
        )

    item = Item.objects.select_related("list").get(pk=item.pk)
    response = {"data": serialize_item(item)}
    if spawned is not None:
        spawned = Item.objects.select_related("list").get(pk=spawned.pk)
        response["spawned"] = serialize_item(spawned)
    return JsonResponse(response)
