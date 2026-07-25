from django.urls import path

from lists import api


urlpatterns = [
    path(
        "lists/<int:list_id>/items/",
        api.create_item,
        name="api_create_item",
    ),
    path(
        "items/<int:item_id>/",
        api.item_detail,
        name="api_item_detail",
    ),
]
