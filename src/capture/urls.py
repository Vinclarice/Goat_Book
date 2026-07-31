from django.urls import path

from . import views

urlpatterns = [
    path("", views.inbox, name="capture_inbox"),
    path("new/", views.new_capture, name="new_capture"),
    path("<int:capture_id>/resolve/", views.resolve_capture, name="resolve_capture"),
]
