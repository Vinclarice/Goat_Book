from django.urls import path

from lists import api


urlpatterns = [
    path(
        "lists/<int:list_id>/items/",
        api.create_item,
        name="api_create_item",
    ),
    path(
        "lists/<int:list_id>/items/reorder/",
        api.reorder_items,
        name="api_reorder_items",
    ),
    path(
        "items/<int:item_id>/",
        api.item_detail,
        name="api_item_detail",
    ),
]
