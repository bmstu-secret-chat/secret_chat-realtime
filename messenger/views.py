import uuid

import environ
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .utils import send_create_chat_notification

env = environ.Env()

INTERNAL_SECRET_KEY = env("INTERNAL_SECRET_KEY")


@api_view(["POST"])
def create_secret_chat_view(request):
    """
    Создание секретного чата.
    """
    secret_key = request.headers.get("X-Internal-Secret")

    if secret_key != INTERNAL_SECRET_KEY:
        return Response({"error": "Отсутствует секретный ключ"}, status=status.HTTP_403_FORBIDDEN)

    chat_id = request.data.get("chat_id")
    user_id = request.data.get("user_id")
    with_user_id = request.data.get("with_user_id")
    chat_type = request.data.get("chat_type")

    if not user_id or not with_user_id:
        return Response({"error": "user_id и with_user_id обязательны"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        uuid.UUID(user_id)
        uuid.UUID(with_user_id)
    except ValueError:
        return Response(
            {"error": "user_id и with_user_id должны быть в формате uuid"}, status=status.HTTP_400_BAD_REQUEST
        )

    send_create_chat_notification(user_id, with_user_id, chat_id, chat_type)
    send_create_chat_notification(with_user_id, user_id, chat_id, chat_type)

    return Response({"message": "Секретный чат создан"}, status=status.HTTP_201_CREATED)
