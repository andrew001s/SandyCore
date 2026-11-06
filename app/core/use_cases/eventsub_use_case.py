from datetime import datetime, timezone
from uuid import uuid4

from app.core.ports.websocket_port import WebsocketPort
from app.domain.automatic_reactions import filter_reaction_decision
from app.services.client_settings import load_effective_settings
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
        payload = payload_builder(
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
        )
        if event_kind != "action":
            settings = await load_effective_settings(user_id)
            allowed, _ = filter_reaction_decision(True, payload.get("emotion"), settings)
            if not allowed:
                payload.update(
                    reaction=False,
                    emotion=None,
                    expression=None,
                    gesture=None,
                    speechStyle=None,
                    intensity=0,
                )
                payload["mouth"]["smile"] = 0
        await self.websocket_port.broadcast_message(payload, user_id)

    async def publish_avatar_trigger(
        self, event_name: str, data: dict, *, user_id: str
    ) -> None:
        """Forward the original provider event to the avatar trigger graph."""
        await self.websocket_port.broadcast_message(
            {
                "id": f"trigger_{uuid4().hex}",
                "type": "avatar_trigger",
                "trigger": event_name,
                "source": "twitch",
                "data": data,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            user_id,
        )
