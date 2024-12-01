import asyncio
import json
from uuid import uuid4

import environ
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from channels.generic.websocket import AsyncWebsocketConsumer

env = environ.Env()


class MessengerConsumer(AsyncWebsocketConsumer):
    """
    Класс для обработки сообщений с использованием Kafka.
    """
    async def connect(self):
        """
        Выполняется при подключении нового клиента к WebSocket.
        """
        self.group_name = "messenger_group"
        self.topic_name = "messenger_topic"
        self.kafka_group_id = f"{self.group_name}_{str(uuid4())}"

        # Инициализация Kafka Producer
        self.producer = AIOKafkaProducer(
            bootstrap_servers=env("KAFKA_BROKER_URL"),
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        )
        await self.producer.start()

        # Инициализация Kafka Consumer
        self.consumer = AIOKafkaConsumer(
            self.topic_name,
            bootstrap_servers=env("KAFKA_BROKER_URL"),
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

    async def receive(self, text_data):
        """
        Обрабатывает входящие сообщения от клиента.
        """
        # Попытка распарсить JSON
        try:
            data = json.loads(text_data)

            user_id = data.get("user_id")
            message_content = data.get("message", {}).get("content")
            message_time = data.get("message", {}).get("time")

            # Обработка неправильной структуры данных
            if not user_id or not message_content or not message_time:
                await self.send(text_data=json.dumps({
                    "status": "error",
                    "time": message_time if message_time is not None else None,
                }))
                print("Invalid JSON structure")
                return

            # Отправка сообщения в Kafka
            await self.producer.send_and_wait(
                self.topic_name,
                {
                    "group_name": self.group_name,
                    "user_id": user_id,
                    "content": message_content,
                    "time": message_time,
                    "sender_channel": self.channel_name,
                },
            )

            # Отправка подтверждения клиенту
            await self.send(text_data=json.dumps({
                "status": "ok",
                "time": message_time,
            }))

        # Обработка неправильного формата данных
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                "status": "error",
                "time": None,
            }))
            print("Invalid JSON format")

    async def listen_to_kafka(self):
        """Асинхронное прослушивание сообщений из Kafka."""
        try:
            async for message in self.consumer:
                # Обработка полученного сообщения
                await self.send_message(message.value)
        except asyncio.CancelledError:
            pass

    async def send_message(self, data):
        """
        Отправка сообщения WebSocket-клиенту.
        """
        sender_channel = data.get("sender_channel")
        user_id = data.get("user_id")
        content = data.get("content")
        time = data.get("time")

        if data.get("group_name") == self.group_name and sender_channel != self.channel_name:
            # Отправляем сообщение
            await self.send(text_data=json.dumps({
                "user_id": user_id,
                "message": {
                    "content": content,
                    "time": time,
                },
            }, ensure_ascii=False))
