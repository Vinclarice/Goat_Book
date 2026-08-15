from django.contrib import admin

from unfold.admin import ModelAdmin, TabularInline

from .models import Item, List, Tag


class ItemInline(TabularInline):
    """Shown on a List's admin page so you can see/add its items inline
    instead of hunting for them in the separate Item list."""

    model = Item
    extra = 0
    fields = ("text", "status", "due_date", "recurrence", "position")
    readonly_fields = ("status",)
    show_change_link = True
    tab = True


@admin.register(List)
class ListAdmin(ModelAdmin):
    list_display = ("title", "owner", "updated_at")
    list_filter = ("owner",)
    search_fields = ("title", "owner__username", "owner__email")
    inlines = [ItemInline]


@admin.register(Item)
class ItemAdmin(ModelAdmin):
    list_display = ("text", "list", "status", "due_date", "recurrence", "updated_at")
    list_filter = ("status", "recurrence")
    search_fields = ("text", "list__title", "owner__username")
    autocomplete_fields = ("list",)
    filter_horizontal = ("tags",)
    # status/completed_at/archived_at are managed together by
    # lists.services (see the valid_item_status_timestamps constraint on
    # Item) -- editing status directly here without also setting the
    # matching timestamps would trip that constraint, so they're read-only.
    readonly_fields = (
        "status",
        "created_at",
        "updated_at",
        "completed_at",
        "archived_at",
    )


@admin.register(Tag)
class TagAdmin(ModelAdmin):
    list_display = ("name", "owner")
    list_filter = ("owner",)
    search_fields = ("name", "owner__username")
