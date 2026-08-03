from django.urls import path

from lists import api


# The `areas/` segment is Release D slice 5's vocabulary rename; the `items/`
# one still awaits the Item -> "task" rename that /api/v1/tasks already made.
# Two vocabularies in one path is untidy, but finishing the second here would
# put two renames in one commit. The url *names* keep their Python spelling,
# which no client reads.
urlpatterns = [
    path(
        "areas/<int:list_id>/items/",
        api.create_item,
        name="api_create_item",
    ),
    path(
        "areas/<int:list_id>/items/reorder/",
        api.reorder_items,
        name="api_reorder_items",
    ),
    path(
        "items/<int:item_id>/",
        api.item_detail,
        name="api_item_detail",
    ),
    path(
        "tasks/<int:task_id>/checklist-steps/",
        api.create_checklist_step,
        name="api_create_checklist_step",
    ),
    path(
        "tasks/<int:task_id>/checklist-steps/reorder/",
        api.reorder_checklist_steps,
        name="api_reorder_checklist_steps",
    ),
    path(
        "checklist-steps/<int:step_id>/",
        api.checklist_step_detail,
        name="api_checklist_step_detail",
    ),
    path(
        "checklist-steps/<int:step_id>/promote/",
        api.promote_checklist_step,
        name="api_checklist_step_promote",
    ),
]
