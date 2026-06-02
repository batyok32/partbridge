from django.urls import path

from .views import (
    StartThreadView,
    ThreadDetailView,
    ThreadListView,
    ThreadMarkReadView,
    ThreadMessageListCreateView,
)

urlpatterns = [
    path("messages/threads/", ThreadListView.as_view(), name="message-thread-list"),
    path("messages/start/", StartThreadView.as_view(), name="message-thread-start"),
    path("messages/threads/<int:thread_id>/", ThreadDetailView.as_view(), name="message-thread-detail"),
    path("messages/threads/<int:thread_id>/messages/", ThreadMessageListCreateView.as_view(), name="message-thread-messages"),
    path("messages/threads/<int:thread_id>/mark-read/", ThreadMarkReadView.as_view(), name="message-thread-mark-read"),
]
