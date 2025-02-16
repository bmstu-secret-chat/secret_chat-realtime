from django.urls import path

from messenger.consumers import MessengerConsumer

websocket_urlpatterns = [
    path("<str:user_id>/", MessengerConsumer.as_asgi()),
]
