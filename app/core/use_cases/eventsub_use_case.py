from app.core.ports.websocket_port import WebsocketPort
from app.services.avatar_events import (
    build_action_event,
    build_reaction_event,
    build_speech_event,
)


class EventSubUseCase:
    def __init__(self, websocket_port: WebsocketPort):
        self.websocket_port = websocket_port

    async def handle_events(
        self,
        event_kind: str,
        message: str,
        response: str,
        *,
        user_id: str,
        voice_enabled: bool = True,
    ) -> None:
        if event_kind == "speech":
            payload_builder = build_speech_event
        elif event_kind == "action":
            payload_builder = build_action_event
        else:
            payload_builder = build_reaction_event
        await self.websocket_port.broadcast_message(
            payload_builder(
                response,
                priority=6 if event_kind == "speech" else 8,
                interrupt=False if event_kind == "speech" else True,
                scene="chat" if event_kind == "speech" else "reaction",
                metadata={
                    "source": "eventsub",
                    "user_id": user_id,
                    "eventKind": event_kind,
                    "message": message,
                    "response": response,
                    "voice_enabled": voice_enabled,
                },
            ),
            user_id,
        )
