import json
from channels.generic.websocket import AsyncWebsocketConsumer


class MessengerConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()

    async def disconnect(self, close_code):
        pass

    async def receive(self, text_data):
        data = json.loads(text_data)
        message = data.get("message", "")
        response = {
            "status": "ok",
            "message": message
        }
        await self.send(text_data=json.dumps(response))
