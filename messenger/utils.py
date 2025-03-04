import uuid

import environ
import httpx
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

channel_layer = get_channel_layer()

env = environ.Env()

INTERNAL_SECRET_KEY = env("INTERNAL_SECRET_KEY")

NGINX_URL = env("NGINX_URL")

BACKEND_PATH = "api/backend"


async def get_secret_chat_users(chat_id):
    """
    Получение списка пользователей секретного чата.
    """
    url = f"{NGINX_URL}/{BACKEND_PATH}/chats/{chat_id}/users/"
    headers = {"X-Internal-Secret": INTERNAL_SECRET_KEY}

    async with httpx.AsyncClient(verify=False) as client:
        response = await client.get(url, headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            response.raise_for_status()


async def get_user_secret_chats(user_id):
    """
    Получение списка секретных чатов конкретного пользователя.
    """
    url = f"{NGINX_URL}/{BACKEND_PATH}/users/{user_id}/secret-chats/"
    headers = {"X-Internal-Secret": INTERNAL_SECRET_KEY}

    async with httpx.AsyncClient(verify=False) as client:
        response = await client.get(url, headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            response.raise_for_status()


async def delete_secret_chat(chat_id):
    """
    Удаление секретного чата.
    """
    async with httpx.AsyncClient(verify=False) as client:
        await client.delete(
            f"{NGINX_URL}/{BACKEND_PATH}/chats/{chat_id}/",
            headers={"X-Internal-Secret": INTERNAL_SECRET_KEY}
        )


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


async def send_notifications_about_deleting_chats(user_id):
    """
    Отправка уведомлений об удалении чатов.
    """
    chat_ids = await get_user_secret_chats(user_id)

    for chat_id in chat_ids:
        payload = {"chat_id": chat_id}
        chat_users = await get_secret_chat_users(chat_id)

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
    chat_users = await get_secret_chat_users(chat_id)
    await delete_secret_chat(chat_id)

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
