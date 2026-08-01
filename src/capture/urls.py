from django.urls import path

from . import views

urlpatterns = [
    path("", views.inbox, name="capture_inbox"),
    path("new/", views.new_capture, name="new_capture"),
    path("<int:capture_id>/edit/", views.edit_capture, name="edit_capture"),
    # One route per outcome rather than one resolve route taking a
    # discriminator: they create different things, fail in different ways,
    # and a single endpoint switching on a POST field would hide that.
    path(
        "<int:capture_id>/task/",
        views.promote_capture_to_task,
        name="promote_capture_to_task",
    ),
    path(
        "<int:capture_id>/idea/",
        views.promote_capture_to_idea,
        name="promote_capture_to_idea",
    ),
    path("<int:capture_id>/discard/", views.discard_capture, name="discard_capture"),
    path("<int:capture_id>/undo/", views.undo_capture, name="undo_capture"),
    path("ideas/", views.ideas, name="ideas"),
    path("ideas/<int:idea_id>/edit/", views.edit_idea, name="edit_idea"),
    path("ideas/<int:idea_id>/task/", views.promote_idea, name="promote_idea"),
    path("ideas/<int:idea_id>/delete/", views.delete_idea, name="delete_idea"),
]
