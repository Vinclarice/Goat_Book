"""The Android compatibility surface — hand-rolled, frozen, and on its way out.

**This module used to be where every task write lived.** The SPA talked to it
through a hand-written client, so create, rename, due date, priority, move,
tags, recurrence, cadence mode, notes, lead days, bill, status, delete, reorder
and all six checklist operations sat outside the generated contract while
`tsc --noEmit` checked every Money call. coherence-audit-2026-08-30.md F2 moved
all of it to `lists/api_v1.py`, and this shrank from 543 lines to under 200.

**What is left is not dead code and must not be deleted on that reading.** The
shipped Android build reads `url` off each task in the agenda payload and
`create_item_url` off each area, and calls them. Removing them would break the
phone's agenda *screen*, not merely its writes: `taskEntryFrom` reads `url`
with `getString`, which throws. And the phone cannot be moved first —
`android-release-signing-plan.md`'s keystore does not exist, so no signed
release can ship.

**Its retirement trigger is that keystore.** `android/` is already written
against `/api/v1/`; the day a signed release carrying it is on the phone, this
file, `lists/api_urls.py`, the `/api/` mount in `clarice/urls.py` and `url` on
`TaskOut` all go together.

Two views, two fields, no DELETE. Anything a person can do to a task that is
not *complete it* or *move it to tomorrow* belongs on the typed router.
"""
import json
from datetime import date

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from accounts.auth import token_or_session_required
from accounts.models import SCOPE_AGENDA_WRITE
from lists import services
from lists.models import Item, List
from lists.serializers import serialize_checklist_step, serialize_item

# What a token-authenticated request may change through item_detail --
# android-full-client-plan.md slice 2 only ever sends status (complete/
# reopen) or due_date (snooze), never text/tags/recurrence/notes and never
# DELETE. See token-scopes-plan.md §7: this endpoint's own auth check can't
# express that boundary (it wraps the whole view), so the guard lives here,
# where the field-level knowledge already does.
#: The whole of this module's surface now, not a restriction within a
#: larger one -- see item_detail.
_PHONE_FIELDS = {"status", "due_date"}


class _InvalidDueDate(Exception):
    pass


def _parse_due_date(value):
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise _InvalidDueDate from None


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


@token_or_session_required(SCOPE_AGENDA_WRITE)
@require_http_methods(["PATCH"])
def item_detail(request, item_id):
    """Complete a task, or move its due date. Nothing else, and no DELETE.

    **Trimmed to the phone's surface on August 30, 2026** --
    coherence-audit-2026-08-30.md F2. This took eleven fields and a delete;
    the other ten and the delete were the web's, and the web is on
    `/api/v1/tasks/{item_id}` now. What is left is exactly what
    `_TOKEN_ALLOWED_FIELDS` already restricted a bearer token to, which is
    what the shipped Android build sends.

    The refusal for an unlisted field is a 400 rather than the 403 it used to
    be, and that is the honest status: those fields are not part of this
    endpoint any more, rather than being withheld from this caller.
    """
    item = _owned_item(request, item_id)
    if item is None:
        return JsonResponse({"errors": {"item": ["Task not found."]}}, status=404)

    payload, error_response = _read_json(request)
    if error_response:
        return error_response
    changed_fields = _PHONE_FIELDS.intersection(payload)
    if len(changed_fields) != 1:
        return JsonResponse(
            {"errors": {"body": ["Change exactly one of status or due_date."]}},
            status=400,
        )

    spawned = None
    try:
        if "due_date" in changed_fields:
            try:
                due_date = _parse_due_date(payload["due_date"])
            except _InvalidDueDate:
                return JsonResponse(
                    {"errors": {"due_date": ["Use a valid date (YYYY-MM-DD)."]}},
                    status=400,
                )
            item = services.set_due_date(item, due_date)
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
        return JsonResponse({"errors": {"conflict": [str(error)]}}, status=409)
    except services.InvalidTaskTransition as error:
        return JsonResponse({"errors": {"status": [str(error)]}}, status=400)

    item = Item.objects.select_related("list").get(pk=item.pk)
    response = {"data": serialize_item(item)}
    if spawned is not None:
        spawned = Item.objects.select_related("list").get(pk=spawned.pk)
        response["spawned"] = serialize_item(spawned)
        response["spawned_checklist_steps"] = [
            serialize_checklist_step(step)
            for step in spawned.checklist_steps.order_by("position", "id")
        ]
    return JsonResponse(response)
