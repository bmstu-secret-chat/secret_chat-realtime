from django.urls import path

from .views import create_chat_view

app_name = "messenger"

urlpatterns = [
    path("chat/create/", create_chat_view, name="create-chat"),
]
