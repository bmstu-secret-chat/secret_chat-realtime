import asyncio
import json
import logging
import uuid

import environ
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from channels.exceptions import StopConsumer
from channels.generic.websocket import AsyncWebsocketConsumer

from .utils import get_secret_chat_users, remove_secret_chat, remove_secret_chats_of_user, update_user_status

logger = logging.getLogger(__name__)

env = environ.Env()

KAFKA_BROKER_URL = env("KAFKA_BROKER_URL")

MESSENGER_TOPIC = "messenger_topic"

ACTIONS_TOPIC = "actions_topic"


class MessengerConsumer(AsyncWebsocketConsumer):
    """
    Класс для обработки сообщений с использованием Kafka.
    """
    async def connect(self):
        """
        Выполняется при подключении нового клиента к WebSocket.
        """
        self.user_id = self.scope["user_id"]

        try:
            uuid.UUID(self.user_id)
        except ValueError:
            logger.error("Некорректный user_id: %s. Ожидался формат UUID.", self.user_id)
            raise StopConsumer

        await update_user_status(self.user_id, True)

        self.group_name = f"user_{self.user_id}"
        self.kafka_group_id = f"user_{self.user_id}"

        self.websocket_producer = AIOKafkaProducer(
            bootstrap_servers=KAFKA_BROKER_URL,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        )
        self.disconnect_producer = AIOKafkaProducer(
            bootstrap_servers=KAFKA_BROKER_URL,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        )
        self.backend_producer = AIOKafkaProducer(
            bootstrap_servers=KAFKA_BROKER_URL,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        )

        await asyncio.gather(
            self.websocket_producer.start(),
            self.disconnect_producer.start(),
            self.backend_producer.start()
        )

        self.messenger_consumer = AIOKafkaConsumer(
            MESSENGER_TOPIC,
            bootstrap_servers=KAFKA_BROKER_URL,
            group_id=self.kafka_group_id,
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            auto_offset_reset="latest",
        )
        self.actions_consumer = AIOKafkaConsumer(
            ACTIONS_TOPIC,
            bootstrap_servers=KAFKA_BROKER_URL,
            group_id=f"{self.kafka_group_id}_actions",
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            auto_offset_reset="latest",
        )

        await asyncio.gather(
            self.messenger_consumer.start(),
            self.actions_consumer.start()
        )

        self.messenger_task = asyncio.create_task(self.listen_to_messenger())
        self.actions_task = asyncio.create_task(self.listen_to_actions())

        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name,
        )
        await self.accept()

    async def disconnect(self, close_code):
        """
        Выполняется при отключении клиента от WebSocket.
        """
        await update_user_status(self.user_id, False)

        if hasattr(self, "messenger_task") and not self.messenger_task.done():
            self.messenger_task.cancel()
        if hasattr(self, "actions_task") and not self.actions_task.done():
            self.actions_task.cancel()

        if hasattr(self, "messenger_consumer"):
            await self.messenger_consumer.stop()
        if hasattr(self, "actions_consumer"):
            await self.actions_consumer.stop()

        if hasattr(self, "websocket_producer"):
            await self.websocket_producer.stop()
        if hasattr(self, "disconnect_producer"):
            await self.disconnect_producer.stop()
        if hasattr(self, "backend_producer"):
            await self.backend_producer.stop()

        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

        await remove_secret_chats_of_user(self.user_id)

    async def receive(self, text_data):
        """
        Обрабатывает входящие сообщения от клиента.
        """
        try:
            data = json.loads(text_data)
            type = data.get("type")

            match type:
                case "send_message":
                    await self.websocket_producer.send_and_wait(MESSENGER_TOPIC, text_data)

                case "delete_chat":
                    await self.websocket_producer.send_and_wait(ACTIONS_TOPIC, text_data)

        except json.JSONDecodeError:
            logger.error("Ошибка декодирования JSON в receive: %s", text_data)
        except KeyError as e:
            logger.error("Отсутствует ключ %s в JSON в receive: %s", e, text_data)

    async def send_chat_notification(self, event):
        """
        Отправка уведомлений о чате в Kafka.
        """
        type = event["notification_type"]
        message = {
            "id": event["id"],
            "type": type,
            "payload": event["payload"],
        }

        match type:
            case "create_chat":
                await self.backend_producer.send_and_wait(ACTIONS_TOPIC, json.dumps(message))

            case "delete_chat":
                await self.disconnect_producer.send_and_wait(ACTIONS_TOPIC, json.dumps(message))

    async def delete_chat_notification(self, event):
        """
        Отправка уведомлений об удалении чата.
        """
        await self.send(text_data=json.dumps({
            "id": event["id"],
            "type": event["notification_type"],
            "payload": event["payload"],
        }))

    async def process_kafka_message(self, text_data):
        """
        Обрабатывает сообщение из Kafka и отправляет его WebSocket-клиенту.
        """
        try:
            data = json.loads(text_data)

            id = data.get("id")
            chat_id = data["payload"]["chat_id"]
            sender_id = data.get("payload", {}).get("user_id", self.user_id)

            chat_users = get_secret_chat_users(chat_id)

            if sender_id not in chat_users or self.user_id not in chat_users:
                return

            if self.user_id != sender_id:
                await self.send(text_data=json.dumps(data, ensure_ascii=False))
            else:
                message = {
                    "id": id,
                    "type": "send_message_response",
                    "payload": {
                        "chat_id": chat_id,
                        "status": "ok"
                    }
                }
                await self.send(text_data=json.dumps(message))

        except json.JSONDecodeError:
            logger.error("Ошибка декодирования JSON в process_kafka_message: %s", text_data)
        except KeyError as e:
            logger.error("Отсутствует ключ %s в JSON в process_kafka_message: %s", e, text_data)

    async def process_kafka_action(self, text_data):
        """
        Обрабатывает действия из Kafka и отправляет его WebSocket-клиенту.
        """
        try:
            data = json.loads(text_data)

            type = data.get("type")
            chat_id = data["payload"]["chat_id"]

            match type:
                case "delete_chat":
                    id = data.get("id")
                    await remove_secret_chat(id, chat_id)

                case "create_chat":
                    with_user_id = data["payload"]["with_user_id"]

                    chat_users = get_secret_chat_users(chat_id)

                    if self.user_id in chat_users and self.user_id != with_user_id:
                        await self.send(text_data=json.dumps(data, ensure_ascii=False))

        except json.JSONDecodeError:
            logger.error("Ошибка декодирования JSON в process_kafka_action: %s", text_data)
        except KeyError as e:
            logger.error("Отсутствует ключ %s в JSON в process_kafka_action: %s", e, text_data)

    async def listen_to_messenger(self):
        """
        Асинхронное прослушивание сообщений из Kafka.
        """
        try:
            async for message in self.messenger_consumer:
                await self.process_kafka_message(message.value)
        except asyncio.CancelledError:
            pass

    async def listen_to_actions(self):
        """
        Асинхронное прослушивание действий из Kafka.
        """
        try:
            async for message in self.actions_consumer:
                await self.process_kafka_action(message.value)
        except asyncio.CancelledError:
            pass
