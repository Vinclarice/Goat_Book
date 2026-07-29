from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from lists import services
from lists.forms import (
    ExistingListItemForm,
    ListTitleForm,
    NewListForm,
    TaskTextForm,
)
from lists.models import Item, List
from lists.serializers import serialize_item


def _lists_for(user):
    return user.lists.order_by("id")


def _dashboard_context(request, form=None):
    archived_tasks = list(
        Item.objects.filter(
            list__owner=request.user,
            status=Item.Status.ARCHIVED,
        ).select_related("list").order_by(
            "-archived_at",
            "-id",
        )
    )
    return {
        "form": form if form is not None else NewListForm(),
        "active_lists": _lists_for(request.user),
        "archived_tasks": archived_tasks,
        "archive_workspace_data": {
            "items": [serialize_item(item) for item in archived_tasks],
        },
    }


@login_required
def dashboard(request):
    return render(request, "dashboard.html", _dashboard_context(request))


def _list_context(our_list, form=None, title_form=None):
    items = list(
        our_list.item_set.exclude(
            status=Item.Status.ARCHIVED,
        ).select_related("list")
    )
    return {
        "list": our_list,
        "form": (
            form
            if form is not None
            else ExistingListItemForm(for_list=our_list)
        ),
        "title_form": (
            title_form
            if title_form is not None
            else ListTitleForm(instance=our_list)
        ),
        "items": items,
        "archived_task_count": our_list.item_set.filter(
            status=Item.Status.ARCHIVED,
        ).count(),
        "task_workspace_data": {
            "list": {
                "id": our_list.id,
                "title": our_list.title,
                "create_item_url": reverse(
                    "api_create_item",
                    args=(our_list.id,),
                ),
                "reorder_url": reverse(
                    "api_reorder_items",
                    args=(our_list.id,),
                ),
            },
            "items": [serialize_item(item) for item in items],
        },
    }


@login_required
def view_list(request, list_id):
    our_list = get_object_or_404(List, id=list_id, owner=request.user)
    form = ExistingListItemForm(for_list=our_list)

    if request.method == "POST":
        form = ExistingListItemForm(for_list=our_list, data=request.POST)
        if form.is_valid():
            form.save()
            return redirect(our_list)

    return render(request, "list.html", _list_context(our_list, form=form))


@login_required
@require_POST
def new_list(request):
    form = NewListForm(data=request.POST)
    if form.is_valid():
        new_list = form.save(owner=request.user)
        return redirect(new_list)

    return render(request, "dashboard.html", _dashboard_context(request, form))


@login_required
@require_POST
def rename_list(request, list_id):
    our_list = get_object_or_404(List, id=list_id, owner=request.user)
    title_form = ListTitleForm(data=request.POST, instance=our_list)
    if title_form.is_valid():
        title_form.save()
        messages.success(request, "List name updated.")
        return redirect(our_list)

    return render(
        request,
        "list.html",
        _list_context(our_list, title_form=title_form),
    )


@login_required
@require_POST
def complete_item(request, item_id):
    item = get_object_or_404(
        Item,
        id=item_id,
        list__owner=request.user,
        status__in=(Item.Status.ACTIVE, Item.Status.COMPLETED),
    )
    services.complete_item(item)
    return redirect(item.list)


@login_required
@require_POST
def reopen_item(request, item_id):
    item = get_object_or_404(
        Item,
        id=item_id,
        list__owner=request.user,
        status__in=(Item.Status.ACTIVE, Item.Status.COMPLETED),
    )
    services.reopen_item(item)
    return redirect(item.list)


@login_required
@require_POST
def archive_item(request, item_id):
    item = get_object_or_404(
        Item,
        id=item_id,
        list__owner=request.user,
        status__in=(Item.Status.ACTIVE, Item.Status.COMPLETED),
    )
    services.archive_item(item)
    messages.success(request, f'"{item.text}" moved to Done & archived.')
    return redirect(item.list)


@login_required
@require_POST
def restore_item(request, item_id):
    item = get_object_or_404(
        Item,
        id=item_id,
        list__owner=request.user,
        status=Item.Status.ARCHIVED,
    )
    try:
        services.restore_item(item)
    except services.TaskConflict as error:
        messages.error(request, str(error))
        return redirect("dashboard")

    messages.success(request, f'"{item.text}" restored to {item.list.title}.')
    return redirect("dashboard")


@login_required
@require_http_methods(["GET", "POST"])
def delete_archived_item(request, item_id):
    item = get_object_or_404(
        Item.objects.select_related("list"),
        id=item_id,
        list__owner=request.user,
        status=Item.Status.ARCHIVED,
    )
    if request.method == "POST":
        task_text = item.text
        services.delete_archived_item(item)
        messages.success(request, f'"{task_text}" was permanently deleted.')
        return redirect("dashboard")

    return render(request, "confirm_delete_item.html", {"item": item})


@login_required
@require_http_methods(["GET", "POST"])
def edit_item(request, item_id):
    item = get_object_or_404(
        Item.objects.select_related("list"),
        id=item_id,
        list__owner=request.user,
        status__in=(Item.Status.ACTIVE, Item.Status.COMPLETED),
    )
    form = TaskTextForm(
        for_item=item,
        data=request.POST if request.method == "POST" else None,
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Task updated.")
        return redirect(item.list)
    return render(request, "edit_item.html", {"item": item, "form": form})


@login_required
@require_http_methods(["GET", "POST"])
def delete_list(request, list_id):
    our_list = get_object_or_404(List, id=list_id, owner=request.user)
    if request.method == "POST":
        title = our_list.title
        services.delete_list(our_list)
        messages.success(request, f'"{title}" and its tasks were permanently deleted.')
        return redirect("dashboard")

    counts = {
        "open": our_list.item_set.filter(status=Item.Status.ACTIVE).count(),
        "completed": our_list.item_set.filter(
            status=Item.Status.COMPLETED,
        ).count(),
        "archived": our_list.item_set.filter(
            status=Item.Status.ARCHIVED,
        ).count(),
    }
    return render(
        request,
        "confirm_delete_list.html",
        {"list": our_list, "counts": counts},
    )
