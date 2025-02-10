import uuid

import environ
import redis
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .utils import send_create_chat_notification

env = environ.Env()

INTERNAL_SECRET_KEY = env("INTERNAL_SECRET_KEY")

redis_client = redis.StrictRedis(host=env("REDIS_HOST"), port=env("REDIS_PORT"), db=0)


@api_view(["POST"])
def create_secret_chat_view(request):
    """
    Создание секретного чата.
    """
    secret_key = request.headers.get("X-Internal-Secret")

    if secret_key != INTERNAL_SECRET_KEY:
        return Response({"error": "Отсутствует секретный ключ"}, status=status.HTTP_403_FORBIDDEN)

    user_id = request.data.get("user_id")
    with_user_id = request.data.get("with_user_id")

    if not user_id or not with_user_id:
        return Response({"error": "user_id и with_user_id обязательны"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        uuid.UUID(user_id)
        uuid.UUID(with_user_id)
    except ValueError:
        return Response(
            {"error": "user_id и with_user_id должны быть в формате uuid"}, status=status.HTTP_400_BAD_REQUEST
        )

    chat_id = str(uuid.uuid4())
    chat_type = "secret"

    redis_client.sadd(f"secret_chat:{chat_id}:users", user_id, with_user_id)
    redis_client.sadd(f"user:{user_id}:secret_chats", chat_id)
    redis_client.sadd(f"user:{with_user_id}:secret_chats", chat_id)

    send_create_chat_notification(user_id, with_user_id, chat_id, chat_type)
    send_create_chat_notification(with_user_id, user_id, chat_id, chat_type)

    return Response({"message": "Секретный чат создан"}, status=status.HTTP_201_CREATED)
