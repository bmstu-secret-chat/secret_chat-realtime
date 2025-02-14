import asyncio
import json
import logging
import uuid

import environ
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from channels.exceptions import StopConsumer
from channels.generic.websocket import AsyncWebsocketConsumer

from .utils import get_secret_chat_users, remove_secret_chats, update_user_status

logger = logging.getLogger(__name__)

env = environ.Env()

KAFKA_BROKER_URL = env("KAFKA_BROKER_URL")


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
        self.topic_name = "messenger_topic"
        self.kafka_group_id = f"{self.group_name}_{str(uuid.uuid4())}"

        # Инициализация Kafka Producer
        self.producer = AIOKafkaProducer(
            bootstrap_servers=KAFKA_BROKER_URL,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        )
        await self.producer.start()

        # Инициализация Kafka Consumer
        self.consumer = AIOKafkaConsumer(
            self.topic_name,
            bootstrap_servers=KAFKA_BROKER_URL,
            group_id=self.kafka_group_id,
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            auto_offset_reset="latest",
        )
        await self.consumer.start()

        # Запуск задачи для прослушивания сообщений из Kafka
        self.consumer_task = asyncio.create_task(self.listen_to_kafka())

        # Добавление клиента в группу WebSocket-каналов
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name,
        )

        # Подтверждение соединения с клиентом
        await self.accept()

    async def disconnect(self, close_code):
        """
        Выполняется при отключении клиента от WebSocket.
        """
        await update_user_status(self.user_id, False)

        # Завершение задачи Kafka Consumer, если она ещё работает
        if hasattr(self, "consumer_task") and not self.consumer_task.done():
            self.consumer_task.cancel()

        # Остановка Kafka Consumer
        if hasattr(self, "consumer"):
            await self.consumer.stop()

        # Остановка Kafka Producer
        if hasattr(self, "producer"):
            await self.producer.stop()

        # Удаление клиента из группы WebSocket-каналов
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

        await remove_secret_chats(self.user_id)

    async def receive(self, text_data):
        """
        Обрабатывает входящие сообщения от клиента.
        """
        try:
            data = json.loads(text_data)

            id = data.get("id")
            type = data.get("type")
            chat_id = data["payload"]["chat_id"]

            if type == "delete_chat":
                await remove_secret_chats(self.user_id)
                return

            # Отправка сообщения в Kafka
            await self.producer.send_and_wait(self.topic_name, text_data)

            # Отправка подтверждения клиенту
            payload = {"chat_id": chat_id, "status": "ok"}
            await self.send_notification(id, "send_message_response", payload)

        except json.JSONDecodeError:
            logger.error("Ошибка декодирования JSON в receive: %s", text_data)
        except KeyError as e:
            logger.error("Отсутствует ключ %s в JSON в receive: %s", e, text_data)

    async def send_chat_notification(self, event):
        """
        Отправка уведомлений о чате.
        """
        await self.send_notification(event["id"], event["notification_type"], event["payload"])

    async def send_notification(self, id, type, payload):
        """
        Отправка уведомлений.
        """
        await self.send(text_data=json.dumps({
            "id": id,
            "type": type,
            "payload": payload,
        }))

    async def process_kafka_message(self, text_data):
        """
        Обрабатывает сообщение из Kafka и отправляет его WebSocket-клиенту.
        """
        try:
            data = json.loads(text_data)

            chat_id = data["payload"]["chat_id"]
            sender_id = data.get("payload", {}).get("user_id", self.user_id)

            chat_users = get_secret_chat_users(chat_id)

            if sender_id not in chat_users or self.user_id not in chat_users:
                return

            if self.user_id != sender_id:
                await self.send(text_data=json.dumps(data, ensure_ascii=False))

        except json.JSONDecodeError:
            logger.error("Ошибка декодирования JSON в process_kafka_message: %s", text_data)
        except KeyError as e:
            logger.error("Отсутствует ключ %s в JSON в process_kafka_message: %s", e, text_data)

    async def listen_to_kafka(self):
        """
        Асинхронное прослушивание сообщений из Kafka.
        """
        try:
            async for message in self.consumer:
                # Обработка полученного сообщения
                await self.process_kafka_message(message.value)
        except asyncio.CancelledError:
            pass
