from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods, require_POST

from lists import agenda as agenda_reader
from lists import services
from lists.forms import (
    DueDateForm,
    ExistingListItemForm,
    ListTitleForm,
    NewListForm,
    QuickAddForm,
    TaskTextForm,
)
from lists.models import Item, List
from lists.serializers import serialize_item


def _lists_for(user):
    return user.lists.order_by("id")


def _safe_next(request, default):
    """Where to send the user after a POST.

    Only same-origin paths are honoured, so a crafted ``next`` can't be
    used to bounce someone off to another site after they click a button
    on a page we rendered.
    """
    candidate = request.POST.get("next") or request.GET.get("next")
    if candidate and url_has_allowed_host_and_scheme(
        candidate,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return candidate
    return default


def _agenda_filters(request, lists):
    """Read ?scope=/?list=/?tag= so the no-JS page can filter too.

    Unrecognised values are dropped rather than erroring -- a stale
    bookmark should show the whole agenda, not a 404.
    """
    scope = request.GET.get("scope")
    if scope not in agenda_reader.SCOPES:
        scope = None

    list_id = None
    raw_list = request.GET.get("list")
    if raw_list and raw_list.isdigit():
        list_id = next(
            (each.id for each in lists if each.id == int(raw_list)),
            None,
        )

    return {"scope": scope, "list": list_id, "tag": request.GET.get("tag")}


def _agenda_context(request, quick_add_form=None, new_list_form=None):
    today = timezone.localdate()
    all_open = agenda_reader.annotate_for_display(
        list(agenda_reader.open_items_for(request.user)), today
    )
    completed_today = agenda_reader.annotate_for_display(
        list(agenda_reader.completed_today_for(request.user, today)), today
    )
    lists = agenda_reader.list_summaries(request.user)
    filters = _agenda_filters(request, lists)

    # Headline counts describe the whole agenda; only the task rows below
    # them narrow, so the numbers stay a stable "how am I doing" signal.
    counts = agenda_reader.summary_counts(
        agenda_reader.bucketed(all_open, today)
    )
    groups = agenda_reader.bucketed(
        agenda_reader.apply_filters(all_open, today, **filters),
        today,
    )

    # Computed once and reused below -- the template context and the
    # workspace payload both need it, and it's the same query either way.
    archived_count = Item.objects.filter(
        list__owner=request.user,
        status=Item.Status.ARCHIVED,
    ).count()

    buckets = [
        {
            "key": key,
            "label": agenda_reader.BUCKET_LABELS[key],
            "items": groups[key],
            "collapsed": (
                key in agenda_reader.COLLAPSED_BY_DEFAULT
                and not any(filters.values())
            ),
        }
        for key in agenda_reader.BUCKET_ORDER
        if groups[key]
    ]

    return {
        "today": today,
        "tomorrow": today + timedelta(days=1),
        "buckets": buckets,
        "counts": counts,
        "filters": filters,
        "has_filters": any(value for value in filters.values()),
        "visible_count": sum(len(each["items"]) for each in buckets),
        "completed_today": completed_today,
        "agenda_lists": lists,
        "agenda_tags": agenda_reader.tag_summaries(all_open),
        "archived_count": archived_count,
        "quick_add_form": (
            quick_add_form
            if quick_add_form is not None
            else QuickAddForm(owner=request.user)
        ),
        "form": new_list_form if new_list_form is not None else NewListForm(),
        "agenda_workspace_data": agenda_reader.workspace_data_for(
            request.user,
            today=today,
            all_open=all_open,
            completed_today=completed_today,
            lists=lists,
            archived_count=archived_count,
        ),
    }


@login_required
def dashboard(request):
    return render(request, "agenda.html", _agenda_context(request))


@login_required
def archive(request):
    archived_tasks = list(
        Item.objects.filter(
            list__owner=request.user,
            status=Item.Status.ARCHIVED,
        ).select_related("list").prefetch_related("tags").order_by(
            "-archived_at",
            "-id",
        )
    )
    return render(
        request,
        "archive.html",
        {
            "archived_tasks": archived_tasks,
            "archive_workspace_data": {
                "items": [serialize_item(item) for item in archived_tasks],
                # Task JSON only carries list_id; the frontend joins
                # against this to show a list's title and link.
                "lists": [
                    {
                        "id": each.id,
                        "title": each.title,
                        "url": each.get_absolute_url(),
                    }
                    for each in List.objects.filter(owner=request.user)
                ],
            },
        },
    )


@login_required
@require_POST
def quick_add(request):
    form = QuickAddForm(owner=request.user, data=request.POST)
    if form.is_valid():
        item = form.save()
        messages.success(request, f'Added "{item.text}" to {item.list.title}.')
        return redirect(_safe_next(request, reverse("dashboard")))

    return render(
        request,
        "agenda.html",
        _agenda_context(request, quick_add_form=form),
    )


@login_required
@require_POST
def set_item_due_date(request, item_id):
    item = get_object_or_404(
        Item.objects.select_related("list"),
        id=item_id,
        list__owner=request.user,
        status__in=(Item.Status.ACTIVE, Item.Status.COMPLETED),
    )
    form = DueDateForm(data=request.POST)
    if form.is_valid():
        services.set_due_date(item, form.cleaned_data["due_date"])
        messages.success(request, form.confirmation_for(item))
    else:
        messages.error(request, "Use a valid date (YYYY-MM-DD).")

    return redirect(_safe_next(request, reverse("dashboard")))


def _list_context(our_list, form=None, title_form=None):
    items = list(
        our_list.item_set.exclude(
            status=Item.Status.ARCHIVED,
        ).select_related("list").prefetch_related("tags")
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

    return render(
        request,
        "agenda.html",
        _agenda_context(request, new_list_form=form),
    )


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
    return redirect(_safe_next(request, item.list.get_absolute_url()))


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
    return redirect(_safe_next(request, item.list.get_absolute_url()))


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
    messages.success(request, f'"{item.text}" moved to the archive.')
    return redirect(_safe_next(request, item.list.get_absolute_url()))


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
        return redirect("archive")

    messages.success(request, f'"{item.text}" restored to {item.list.title}.')
    return redirect("archive")


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
        return redirect("archive")

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
