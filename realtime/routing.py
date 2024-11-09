from django.urls import path

from message.consumers import MessengerConsumer

websocket_urlpatterns = [
    path('messenger/', MessengerConsumer.as_asgi()),
]
