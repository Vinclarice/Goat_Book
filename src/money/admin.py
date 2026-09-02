"""The Money module's admin registrations.

Moved from `lists/admin.py` on September 2, 2026 with the models they register.
"""
from django.contrib import admin
from unfold.admin import ModelAdmin

from money.models import Bill, BillSeries


# ~~The only window onto two tables nothing else reads yet.~~ **Six surfaces
# read them now**, and this stays for the reason it was written: being able to
# look at rows a migration produced is the difference between verifying it and
# hoping. `0055` and `0057` were both verified this way.
#
# **Registered while their siblings are not**, still worth naming rather than
# hiding: Account, BalanceReading and MoneyCategory have no admin presence.
# That is arguably their gap rather than this one's excess, and moving apps is
# not the moment to decide it.
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
