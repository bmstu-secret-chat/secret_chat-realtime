import uuid

import environ
import httpx
import redis
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

channel_layer = get_channel_layer()

env = environ.Env()

redis_client = redis.StrictRedis(host=env("REDIS_HOST"), port=env("REDIS_PORT"), db=0, decode_responses=True)

INTERNAL_SECRET_KEY = env("INTERNAL_SECRET_KEY")

NGINX_URL = env("NGINX_URL")

BACKEND_PATH = "api/backend"


def get_secret_chat_users(chat_id):
    """
    Получение списка пользователей секретного чата из Redis.
    """
    return redis_client.smembers(f"secret_chat:{chat_id}:users")


async def update_user_status(user_id, status):
    """
    Обновление статуса пользователя.
    """
    async with httpx.AsyncClient(verify=False) as client:
        await client.patch(
            f"{NGINX_URL}/{BACKEND_PATH}/users/status/",
            headers={"X-Internal-Secret": INTERNAL_SECRET_KEY},
            json={"user_id": user_id, "is_online": status}
        )


def send_create_chat_notification(user_id, with_user_id, chat_id, chat_type):
    """
    Отправка уведомления о создании чата.
    """
    payload = {
        "chat_id": chat_id,
        "with_user_id": with_user_id,
        "chat_type": chat_type,
    }

    async_to_sync(channel_layer.group_send)(
        f"user_{user_id}",
        {
            "type": "send_chat_notification",
            "id": str(uuid.uuid4()),
            "notification_type": "create_chat",
            "payload": payload,
        },
    )


async def remove_secret_chats_of_user(user_id):
    """
    Удаление секретных чатов пользователя.
    """
    chat_ids = redis_client.smembers(f"user:{user_id}:secret_chats")

    for chat_id in chat_ids:
        payload = {"chat_id": chat_id}
        chat_users = get_secret_chat_users(chat_id)

        for chat_user_id in chat_users:
            redis_client.srem(f"user:{chat_user_id}:secret_chats", chat_id)

        redis_client.delete(f"secret_chat:{chat_id}:users")
        redis_client.delete(f"secret_chat:{chat_id}")

        for chat_user_id in chat_users:
            if chat_user_id != user_id:
                await channel_layer.group_send(
                    f"user_{chat_user_id}",
                    {
                        "type": "send_chat_notification",
                        "id": str(uuid.uuid4()),
                        "notification_type": "delete_chat",
                        "payload": payload,
                    },
                )


async def remove_secret_chat(id, chat_id):
    """
    Удаление секретного чата.
    """
    payload = {"chat_id": chat_id}
    chat_users = get_secret_chat_users(chat_id)

    for chat_user_id in chat_users:
        redis_client.srem(f"user:{chat_user_id}:secret_chats", chat_id)

    redis_client.delete(f"secret_chat:{chat_id}:users")
    redis_client.delete(f"secret_chat:{chat_id}")

    for chat_user_id in chat_users:
        await channel_layer.group_send(
            f"user_{chat_user_id}",
            {
                "type": "delete_chat_notification",
                "id": id,
                "notification_type": "delete_chat",
                "payload": payload,
            },
        )
