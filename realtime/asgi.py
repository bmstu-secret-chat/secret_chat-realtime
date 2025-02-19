import os

from django.core.asgi import get_asgi_application
from django.urls import path

from channels.routing import ProtocolTypeRouter, URLRouter

from .middleware import TokenAuthenticationMiddlewareStack
from .routing import websocket_urlpatterns

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'realtime.settings')

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": TokenAuthenticationMiddlewareStack(
        URLRouter(
            [path("api/realtime/", URLRouter(websocket_urlpatterns))]
        )
    ),
})
