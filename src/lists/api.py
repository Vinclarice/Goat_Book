import json
from datetime import date
from functools import wraps

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from accounts.auth import token_or_session_required
from accounts.models import SCOPE_AGENDA_WRITE
from lists import services
from lists.models import ChecklistStep, Item, List
from lists.serializers import serialize_checklist_step, serialize_item

# What a token-authenticated request may change through item_detail --
# android-full-client-plan.md slice 2 only ever sends status (complete/
# reopen) or due_date (snooze), never text/tags/recurrence/notes and never
# DELETE. See token-scopes-plan.md §7: this endpoint's own auth check can't
# express that boundary (it wraps the whole view), so the guard lives here,
# where the field-level knowledge already does.
_TOKEN_ALLOWED_FIELDS = {"status", "due_date"}


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


def _owned_checklist_step(request, step_id):
    # Charter rule 1 pays off here: a direct owner FK on ChecklistStep makes
    # this a one-hop lookup, the same shape as _owned_item, rather than a
    # join through task__list__owner.
    return ChecklistStep.objects.select_related("task", "task__list").filter(
        id=step_id,
        owner=request.user,
    ).first()


@token_or_session_required(SCOPE_AGENDA_WRITE)
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


@token_or_session_required(SCOPE_AGENDA_WRITE)
@require_http_methods(["PATCH", "DELETE"])
def item_detail(request, item_id):
    item = _owned_item(request, item_id)
    if item is None:
        return JsonResponse(
            {"errors": {"item": ["Task not found."]}},
            status=404,
        )

    if request.method == "DELETE":
        if getattr(request, "token_authenticated", False):
            return JsonResponse(
                {"errors": {"authentication": ["Not available to a connected phone yet."]}},
                status=403,
            )
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
        "text", "status", "due_date", "tags", "recurrence", "notes",
    }.intersection(payload)
    if len(changed_fields) != 1:
        return JsonResponse(
            {
                "errors": {
                    "body": [
                        "Change exactly one of text, status, due_date, tags, "
                        "recurrence, or notes per request."
                    ]
                }
            },
            status=400,
        )
    if getattr(request, "token_authenticated", False) and not changed_fields <= _TOKEN_ALLOWED_FIELDS:
        return JsonResponse(
            {"errors": {"authentication": ["Not available to a connected phone yet."]}},
            status=403,
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
        elif "notes" in changed_fields:
            notes = payload["notes"]
            if not isinstance(notes, str):
                return JsonResponse(
                    {"errors": {"notes": ["Send notes as text."]}},
                    status=400,
                )
            item = services.set_item_notes(item, notes)
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
        # The fresh checklist steps this same completion cloned onto the new
        # occurrence. Always present when `spawned` is, empty when nothing
        # recurred, so the client reads an array without branching.
        response["spawned_checklist_steps"] = [
            serialize_checklist_step(step)
            for step in spawned.checklist_steps.order_by("position", "id")
        ]
    return JsonResponse(response)


@api_login_required
@require_http_methods(["POST"])
def create_checklist_step(request, task_id):
    task = _owned_item(request, task_id)
    if task is None:
        return JsonResponse(
            {"errors": {"task": ["Task not found."]}},
            status=404,
        )

    payload, error_response = _read_json(request)
    if error_response:
        return error_response
    carries_forward = payload.get("carries_forward")
    if carries_forward is not None and not isinstance(carries_forward, bool):
        return JsonResponse(
            {"errors": {"carries_forward": ["Send true or false."]}},
            status=400,
        )
    try:
        step = services.add_checklist_step(
            task, payload.get("text"), carries_forward=carries_forward,
        )
    except services.TaskConflict as error:
        return JsonResponse({"errors": {"text": [str(error)]}}, status=400)
    except services.InvalidTaskTransition as error:
        return JsonResponse({"errors": {"status": [str(error)]}}, status=400)
    return JsonResponse({"data": serialize_checklist_step(step)}, status=201)


@api_login_required
@require_http_methods(["POST"])
def reorder_checklist_steps(request, task_id):
    task = _owned_item(request, task_id)
    if task is None:
        return JsonResponse(
            {"errors": {"task": ["Task not found."]}},
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
            {"errors": {"ordered_ids": ["Send a list of step ids."]}},
            status=400,
        )
    try:
        steps = services.reorder_checklist_steps(task, ordered_ids)
    except services.TaskConflict as error:
        return JsonResponse(
            {"errors": {"ordered_ids": [str(error)]}},
            status=409,
        )
    return JsonResponse(
        {"data": [serialize_checklist_step(step) for step in steps]},
    )


@api_login_required
@require_http_methods(["PATCH", "DELETE"])
def checklist_step_detail(request, step_id):
    step = _owned_checklist_step(request, step_id)
    if step is None:
        return JsonResponse(
            {"errors": {"step": ["Checklist step not found."]}},
            status=404,
        )

    if request.method == "DELETE":
        try:
            services.delete_checklist_step(step)
        except services.InvalidTaskTransition as error:
            return JsonResponse(
                {"errors": {"status": [str(error)]}},
                status=400,
            )
        return JsonResponse({"data": {"deleted": step_id}})

    payload, error_response = _read_json(request)
    if error_response:
        return error_response
    changed_fields = {"text", "is_done", "carries_forward"}.intersection(payload)
    if len(changed_fields) != 1:
        return JsonResponse(
            {
                "errors": {
                    "body": [
                        "Change exactly one of text, is_done, or "
                        "carries_forward per request."
                    ]
                }
            },
            status=400,
        )

    try:
        if "text" in changed_fields:
            step = services.edit_checklist_step_text(step, payload["text"])
        elif "is_done" in changed_fields:
            is_done = payload["is_done"]
            if not isinstance(is_done, bool):
                return JsonResponse(
                    {"errors": {"is_done": ["Send true or false."]}},
                    status=400,
                )
            step = services.set_checklist_step_done(step, is_done)
        else:
            carries_forward = payload["carries_forward"]
            if not isinstance(carries_forward, bool):
                return JsonResponse(
                    {"errors": {"carries_forward": ["Send true or false."]}},
                    status=400,
                )
            step = services.set_checklist_step_carries_forward(step, carries_forward)
    except services.TaskConflict as error:
        return JsonResponse({"errors": {"conflict": [str(error)]}}, status=409)
    except services.InvalidTaskTransition as error:
        return JsonResponse({"errors": {"status": [str(error)]}}, status=400)
    return JsonResponse({"data": serialize_checklist_step(step)})


@api_login_required
@require_http_methods(["POST"])
def promote_checklist_step(request, step_id):
    step = _owned_checklist_step(request, step_id)
    if step is None:
        return JsonResponse(
            {"errors": {"step": ["Checklist step not found."]}},
            status=404,
        )
    try:
        task = services.promote_checklist_step(step)
    except services.TaskConflict as error:
        return JsonResponse({"errors": {"conflict": [str(error)]}}, status=409)
    except services.InvalidTaskTransition as error:
        return JsonResponse({"errors": {"status": [str(error)]}}, status=400)
    task = Item.objects.select_related("list").get(pk=task.pk)
    return JsonResponse({"data": serialize_item(task)}, status=201)
