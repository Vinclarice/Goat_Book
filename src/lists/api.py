import json
from functools import wraps

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from lists import services
from lists.models import Item, List
from lists.serializers import serialize_item


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
        item = services.create_item(our_list, payload.get("text"))
    except services.TaskConflict as error:
        return JsonResponse(
            {"errors": {"text": [str(error)]}},
            status=400,
        )
    item = Item.objects.select_related("list").get(pk=item.pk)
    return JsonResponse({"data": serialize_item(item)}, status=201)


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
    changed_fields = {"text", "status"}.intersection(payload)
    if len(changed_fields) != 1:
        return JsonResponse(
            {
                "errors": {
                    "body": ["Change exactly one of text or status per request."]
                }
            },
            status=400,
        )

    try:
        if "text" in changed_fields:
            item = services.edit_item(item, payload["text"])
        else:
            requested_status = payload["status"]
            if requested_status == Item.Status.ACTIVE:
                item = services.reopen_item(item)
            elif requested_status == Item.Status.COMPLETED:
                if item.status == Item.Status.ARCHIVED:
                    item = services.restore_item(item)
                else:
                    item = services.complete_item(item)
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
    return JsonResponse({"data": serialize_item(item)})
