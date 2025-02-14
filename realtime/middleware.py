from urllib.parse import parse_qs

import environ
import requests
from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware

env = environ.Env()

INTERNAL_SECRET_KEY = env("INTERNAL_SECRET_KEY")

NGINX_URL = env("NGINX_URL")

AUTH_PATH = "/api/auth"


class TokenAuthenticationMiddleware(BaseMiddleware):
    """
    Middleware для проверки авторизации пользователя при подключении к WebSocket.
    """
    async def __call__(self, scope, receive, send):
        query_string = parse_qs(scope["query_string"].decode())

        access_token = query_string.get("access_token", [None])[0]

        if not access_token:
            await send({"type": "websocket.close"})
            return

        url = f"{NGINX_URL}{AUTH_PATH}/check/"
        cookies = {"access": access_token}
        response = await self.fetch_auth(url, cookies)

        if response and response.status_code == 200:
            data = response.json()
            scope["user_id"] = data.get("id")
            return await super().__call__(scope, receive, send)
        else:
            await send({"type": "websocket.close"})
            return

    @database_sync_to_async
    def fetch_auth(self, url, cookies):
        """
        Запрос в API для проверки токена.
        """
        return requests.get(url, cookies=cookies, verify=False)


def TokenAuthenticationMiddlewareStack(inner):
    return TokenAuthenticationMiddleware(inner)
