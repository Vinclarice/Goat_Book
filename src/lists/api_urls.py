from django.urls import path

from lists import api


# **The Android compatibility surface, and nothing else.**
#
# coherence-audit-2026-08-30.md F2 moved every web task write to
# `/api/v1/`. These two remain because the shipped Android build reads `url`
# off each task in the agenda payload and `create_item_url` off each area, and
# calls them -- so deleting them would break the phone's agenda, not merely its
# writes. It cannot be updated first: `android-release-signing-plan.md`'s
# keystore does not exist, so no signed release can ship.
#
# **What retires this file**: a signed Android release running the client that
# addresses `/api/v1/` by id. `android/` is already written against it; what is
# missing is the ability to build it.
#
# ~~The `items/` segment awaits the Item -> "task" rename that /api/v1/tasks
# already made.~~ **It no longer does.** These two paths are frozen by a
# shipped binary, so renaming them is exactly the thing that would break it,
# and F5's rename belongs to the endpoints that replaced them.
urlpatterns = [
    path(
        "areas/<int:list_id>/items/",
        api.create_item,
        name="api_create_item",
    ),
    path(
        "items/<int:item_id>/",
        api.item_detail,
        name="api_item_detail",
    ),
]
