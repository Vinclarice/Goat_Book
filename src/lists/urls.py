"""
URL configuration for clarice project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.urls import path
from lists import views


urlpatterns = [
    path("new", views.new_list, name="new_list"),
    path("add", views.quick_add, name="quick_add"),
    path(
        "items/<int:item_id>/due",
        views.set_item_due_date,
        name="set_item_due_date",
    ),
    path(
        "items/<int:item_id>/complete",
        views.complete_item,
        name="complete_item",
    ),
    path(
        "items/<int:item_id>/reopen",
        views.reopen_item,
        name="reopen_item",
    ),
    path(
        "items/<int:item_id>/archive",
        views.archive_item,
        name="archive_item",
    ),
    path(
        "items/<int:item_id>/restore",
        views.restore_item,
        name="restore_item",
    ),
    path(
        "items/<int:item_id>/delete",
        views.delete_archived_item,
        name="delete_archived_item",
    ),
    path(
        "items/<int:item_id>/edit",
        views.edit_item,
        name="edit_item",
    ),
    path("<int:list_id>/", views.view_list, name="view_list"),
    path("<int:list_id>/rename", views.rename_list, name="rename_list"),
    path("<int:list_id>/delete", views.delete_list, name="delete_list"),
]
