from channels.generic.websocket import AsyncJsonWebsocketConsumer

class NotificationConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        print("WS CONNECT SCOPE keys:", list(self.scope.keys()))
        print("WS CONNECT user:", repr(self.user))
        if self.user.is_anonymous:
            print("WS CONNECTION REJECTED: ANONYMOUS USER")
            await self.close()
            return
        print("WS CONNECTION ACCEPTED FOR USER:", self.user.id)
        self.group_name = f"user_{self.user.id}"

        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    async def job_notification(self, event):
        # event["payload"] sent from backend
        print("WS JOB NOTIFICATION EVENT:", event)
        await self.send_json(event)
