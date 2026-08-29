import asyncio

import twitchAPI.object.eventsub as eventsub
from twitchAPI.eventsub.websocket import EventSubWebsocket
from twitchAPI.object.eventsub import ChannelPointsCustomRewardRedemptionAddEvent

from app.adapters.websocket_adapter import WebsocketAdapter
from app.core.runtime import get_active_user_id
from app.core.use_cases.eventsub_use_case import EventSubUseCase
from app.services.client_settings import load_effective_settings
from app.services.gemini import stream_gemini_events, stream_gemini_rewards

eventsubUseCase = EventSubUseCase(WebsocketAdapter())

ALLOWED_REDEMPTIONS = {
    "Te mando un saludo",
    "Sound Alert: Screamer",
    "Me gusta el directo",
}


class EventSubSession:
    """EventSub de UN usuario.

    `user_id` es el id de la aplicación (Clerk) y manda para configuración e IA;
    `broadcaster_id` es el id numérico de Twitch y solo se usa para suscribirse.
    Confundirlos hacía que se cargara la configuración de un id inexistente.
    """

    def __init__(self, user_id: str, broadcaster_id: str):
        self.user_id = str(user_id)
        self.broadcaster_id = str(broadcaster_id)
        self.instance: EventSubWebsocket | None = None

    async def start(self, twitch) -> bool:
        settings = await load_effective_settings(self.user_id)
        feature_flags = settings.get("feature_flags") or {}
        rewards_enabled = bool(feature_flags.get("rewards", True))
        events_enabled = bool(feature_flags.get("events", True))

        if not events_enabled and not rewards_enabled:
            print(f"[EVENTSUB] Desactivado por configuración de {self.user_id}")
            return False

        await self.stop()

        self.instance = EventSubWebsocket(twitch)
        self.instance.start()

        broadcaster = self.broadcaster_id
        if rewards_enabled:
            await self.instance.listen_channel_points_custom_reward_redemption_add(
                broadcaster_user_id=broadcaster, callback=self.chanel_points
            )
        if events_enabled:
            await self.instance.listen_channel_follow_v2(
                broadcaster, broadcaster, self.on_follow
            )
            await self.instance.listen_channel_subscribe(broadcaster, self.on_subscribe)
            await self.instance.listen_channel_subscription_message(
                broadcaster, self.on_subscribe_message
            )
            await self.instance.listen_channel_subscription_gift(
                broadcaster, self.on_sub_gift
            )
            await self.instance.listen_channel_cheer(broadcaster, self.on_cheer)
            await self.instance.listen_channel_raid(
                to_broadcaster_user_id=broadcaster, callback=self.on_raid
            )
        return True

    async def stop(self) -> None:
        if self.instance is None:
            return
        try:
            await self.instance.stop()
        except Exception as exc:
            print(f"[EVENTSUB] Error al detener el de {self.user_id}: {repr(exc)}")
        finally:
            self.instance = None

    async def _emitir(self, tipo: str, message: str, flujo) -> None:
        """Publica un evento de avatar por cada frase que produce la IA.

        El frontend sintetiza voz por evento recibido, así que trocear aquí es lo
        que hace que la reacción empiece a sonar antes de estar completa.
        """
        try:
            async for piece in flujo:
                await eventsubUseCase.handle_events(
                    tipo, message, piece, user_id=self.user_id
                )
        except Exception as exc:
            print(f"[EVENTSUB] No se pudo generar la reacción de {self.user_id}: {repr(exc)}")

    async def chanel_points(self, msg: ChannelPointsCustomRewardRedemptionAddEvent):
        redemtion = msg.event.reward.title
        if redemtion not in ALLOWED_REDEMPTIONS:
            return
        user = msg.event.user_name
        message = f"Redemption: {redemtion} from {user}"
        redemtion_obj = '{"user": "' + user + '", "reward": "' + redemtion + '"}'
        await self._emitir(
            "reaction", message, stream_gemini_rewards(redemtion_obj, self.user_id)
        )

    async def on_follow(self, data: eventsub.ChannelFollowEvent):
        user = data.event.user_name
        message = f"Follow nombre_usuario: {user}"
        await self._emitir(
            "reaction", message, stream_gemini_events(f"{message}", self.user_id)
        )

    async def on_subscribe(self, data: eventsub.ChannelSubscribeEvent):
        user = data.event.user_name
        sub = f"Subscribe user: {user}"
        await self._emitir(
            "reaction", sub, stream_gemini_events(f"{sub}", self.user_id)
        )

    async def on_subscribe_message(self, data: eventsub.ChannelSubscriptionMessageEvent):
        user = data.event.user_name
        sub = f"Suscribe user: {user} message: {data.event.message}"
        await self._emitir(
            "speech", sub, stream_gemini_events(f"{sub}", self.user_id)
        )

    async def on_sub_gift(self, data: eventsub.ChannelSubscriptionGiftEvent):
        user = data.event.user_name
        gift = f"gift_Sub user: {user}"
        await self._emitir(
            "reaction", gift, stream_gemini_events(f"{gift}", self.user_id)
        )

    async def on_cheer(self, data: eventsub.ChannelCheerEvent):
        user = data.event.user_name
        cheer = data.event.message
        cheer_amount = data.event.bits
        cheer = f"cheer user: {user} bits_amount: {cheer_amount} message: {cheer}"
        await self._emitir(
            "reaction", cheer, stream_gemini_events(f"{cheer}", self.user_id)
        )

    async def on_raid(self, data: eventsub.ChannelRaidEvent):
        user = data.event.from_broadcaster_user_name
        raid = f"Raid: user que raideo: {user}"
        await self._emitir(
            "reaction", raid, stream_gemini_events(f"{raid}", self.user_id)
        )


# Una sesión de EventSub por usuario. Nunca una instancia global compartida.
_sessions: dict[str, EventSubSession] = {}
_locks: dict[str, asyncio.Lock] = {}


def _resolve_user_id(user_id: str | None = None) -> str:
    owner_id = user_id or get_active_user_id()
    if not owner_id:
        raise Exception("No hay un usuario activo para operar EventSub")
    return str(owner_id)


def _lock_for(owner_id: str) -> asyncio.Lock:
    lock = _locks.get(owner_id)
    if lock is None:
        lock = asyncio.Lock()
        _locks[owner_id] = lock
    return lock


def get_eventsub_session(user_id: str | None = None) -> EventSubSession | None:
    owner_id = _resolve_user_id(user_id)
    return _sessions.get(owner_id)


async def setup_eventsub(twitch, user_id, broadcaster_id=None):
    owner_id = _resolve_user_id(user_id)
    resolved_broadcaster = str(broadcaster_id or user_id)
    async with _lock_for(owner_id):
        session = EventSubSession(owner_id, resolved_broadcaster)
        previous = _sessions.pop(owner_id, None)
        if previous is not None:
            await previous.stop()
        started = await session.start(twitch)
        if started:
            _sessions[owner_id] = session
        return started


async def close_eventsub(user_id: str | None = None):
    owner_id = _resolve_user_id(user_id)
    async with _lock_for(owner_id):
        session = _sessions.pop(owner_id, None)
        if session is not None:
            await session.stop()


async def close_all_eventsub():
    """Solo para el apagado del proceso."""
    for owner_id in list(_sessions.keys()):
        session = _sessions.pop(owner_id, None)
        if session is not None:
            await session.stop()
