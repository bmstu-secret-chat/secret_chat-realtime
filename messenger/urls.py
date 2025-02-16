from django.urls import path

from .views import create_secret_chat_view

app_name = "messenger"

urlpatterns = [
    path("secret-chat/create/", create_secret_chat_view, name="create-secret-chat"),
]
