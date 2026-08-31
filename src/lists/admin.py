from django.contrib import admin

from unfold.admin import ModelAdmin, TabularInline

from .models import Bill, BillSeries, Item, List, Tag


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


# **The only window onto two tables nothing else reads yet** -- increment 1 of
# design/bill-as-a-model-plan.md. They are deliberately dark until that plan's
# increment 3, and increment 2 migrates real rows into them, so being able to
# look is the difference between verifying that migration and hoping.
#
# **Registered while their siblings are not**, which is an inconsistency worth
# naming rather than hiding: MoneyLine, Account, BalanceReading and
# MoneyCategory have no admin presence at all. That is arguably their gap
# rather than this one's excess, and it is not fixed here.
@admin.register(BillSeries)
class BillSeriesAdmin(ModelAdmin):
    list_display = ("payee", "owner", "cadence", "amount", "currency", "ended_at")
    list_filter = ("owner", "cadence", "direction")
    search_fields = ("payee", "owner__username", "owner__email")


@admin.register(Bill)
class BillAdmin(ModelAdmin):
    list_display = ("payee", "owner", "due_date", "amount", "paid_amount", "paid_at")
    list_filter = ("owner", "direction")
    search_fields = ("payee", "owner__username", "owner__email")
    date_hierarchy = "due_date"
