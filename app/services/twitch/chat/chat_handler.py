import asyncio
import re
import time

import httpx

from twitchAPI.chat import Chat, ChatEvent, ChatMessage, EventData

import app.services.twitch.auth.auth as auth
from app.adapters.websocket_adapter import WebsocketAdapter
from app.core.runtime import get_active_user_id
from app.core.use_cases.chat_use_case import ChatUseCase
from app.core.use_cases.eventsub_use_case import EventSubUseCase
from app.services.client_settings import (
    extract_command_message,
    load_effective_settings,
    resolve_chat_command,
    resolve_chunk_size,
)
from app.services.gemini import response_sandy, should_delete_message, try_local_task
from app.services.moderator import check_banned_words

DEFAULT_BOTS = ["streamlabs", "streamelements", "nightbot"]

chat_use_case = ChatUseCase(WebsocketAdapter())
avatar_trigger_use_case = EventSubUseCase(WebsocketAdapter())


def _get_twitch_emotes(message: str, chat_message: ChatMessage) -> list[dict[str, str]]:
    """Return Twitch IRC emote ids and their source text for the avatar overlay."""
    raw = getattr(chat_message, "emotes", None)
    if not raw:
        return []

    emotes: list[dict[str, str]] = []
    message_utf16 = message.encode("utf-16-le")
    if isinstance(raw, dict):
        emote_groups = raw.items()
    elif isinstance(raw, str):
        emote_groups = []
        for group in raw.split("/"):
            emote_id, separator, positions = group.partition(":")
            if separator:
                emote_groups.append((emote_id, positions.split(",")))
    else:
        return []

    for emote_id, positions in emote_groups:
        if not isinstance(emote_id, str | int) or not str(emote_id):
            continue
        for position in positions:
            if isinstance(position, dict):
                start_text = position.get("start_position")
                end_text = position.get("end_position")
            elif isinstance(position, str):
                start_text, dash, end_text = position.partition("-")
                if not dash:
                    continue
            else:
                continue
            try:
                start, end = int(start_text), int(end_text)
            except (TypeError, ValueError):
                continue
            if start < 0 or end < start:
                continue
            name = message_utf16[start * 2 : (end + 1) * 2].decode("utf-16-le", errors="ignore")
            if name:
                emotes.append(
                    {
                        "id": str(emote_id),
                        "name": name,
                        "start": str(start),
                        "end": str(end),
                    }
                )
    return emotes


def _add_catalog_emote(
    catalog: dict[str, dict[str, str]], name: object, emote_id: object, image_url: object
) -> None:
    if not isinstance(name, str) or not name or not isinstance(emote_id, str | int):
        return
    if not isinstance(image_url, str) or not image_url:
        return
    if image_url.startswith("//"):
        image_url = f"https:{image_url}"
    catalog[name] = {"id": str(emote_id), "name": name, "imageUrl": image_url}


def _merge_emote_catalogs(payloads: dict[str, object]) -> dict[str, dict[str, str]]:
    catalog: dict[str, dict[str, str]] = {}

    # Fill global emotes first; channel sets below replace matching names.
    bttv_global = payloads.get("bttv_global")
    if isinstance(bttv_global, list):
        for emote in bttv_global:
            if isinstance(emote, dict):
                _add_catalog_emote(
                    catalog,
                    emote.get("code"),
                    emote.get("id"),
                    f"https://cdn.betterttv.net/emote/{emote.get('id')}/2x",
                )

    seven_global = payloads.get("seven_global")
    if isinstance(seven_global, dict):
        for emote in seven_global.get("emotes", []):
            if isinstance(emote, dict):
                emote_id = emote.get("id")
                _add_catalog_emote(
                    catalog,
                    emote.get("name"),
                    emote_id,
                    f"https://cdn.7tv.app/emote/{emote_id}/2x.webp",
                )

    ffz_global = payloads.get("ffz_global")
    if isinstance(ffz_global, dict):
        default_sets = {str(set_id) for set_id in ffz_global.get("default_sets", [])}
        for set_id in default_sets:
            emote_set = ffz_global.get("sets", {}).get(set_id, {})
            for emote in emote_set.get("emoticons", []):
                if isinstance(emote, dict):
                    urls = emote.get("urls", {})
                    image_url = urls.get("2") or urls.get(2) or urls.get("1") or urls.get(1)
                    _add_catalog_emote(catalog, emote.get("name"), emote.get("id"), image_url)

    bttv_channel = payloads.get("bttv_channel")
    if isinstance(bttv_channel, dict):
        for key in ("channelEmotes", "sharedEmotes"):
            for emote in bttv_channel.get(key, []):
                if isinstance(emote, dict):
                    emote_id = emote.get("id")
                    _add_catalog_emote(
                        catalog,
                        emote.get("code"),
                        emote_id,
                        f"https://cdn.betterttv.net/emote/{emote_id}/2x",
                    )

    seven_channel = payloads.get("seven_channel")
    if isinstance(seven_channel, dict):
        emote_set = seven_channel.get("emote_set") or {}
        for emote in emote_set.get("emotes", []):
            if isinstance(emote, dict):
                emote_id = emote.get("id")
                _add_catalog_emote(
                    catalog,
                    emote.get("name"),
                    emote_id,
                    f"https://cdn.7tv.app/emote/{emote_id}/2x.webp",
                )

    ffz_channel = payloads.get("ffz_channel")
    if isinstance(ffz_channel, dict):
        for emote_set in ffz_channel.get("sets", {}).values():
            for emote in emote_set.get("emoticons", []):
                if isinstance(emote, dict):
                    urls = emote.get("urls", {})
                    image_url = urls.get("2") or urls.get(2) or urls.get("1") or urls.get(1)
                    _add_catalog_emote(catalog, emote.get("name"), emote.get("id"), image_url)

    return catalog


def _match_external_emotes(
    message: str,
    catalog: dict[str, dict[str, str]],
    twitch_emotes: list[dict[str, str]],
) -> list[dict[str, str]]:
    ranges = [
        (int(emote["start"]), int(emote["end"]))
        for emote in twitch_emotes
        if emote.get("start", "").isdigit() and emote.get("end", "").isdigit()
    ]
    matches: list[tuple[int, dict[str, str]]] = []
    for name, emote in catalog.items():
        pattern = re.compile(rf"(?<!\w){re.escape(name)}(?!\w)")
        for match in pattern.finditer(message):
            start = len(message[: match.start()].encode("utf-16-le")) // 2
            end = len(message[: match.end()].encode("utf-16-le")) // 2 - 1
            if any(start <= native_end and native_start <= end for native_start, native_end in ranges):
                continue
            entry = dict(emote)
            entry["start"] = str(start)
            entry["end"] = str(end)
            matches.append((start, entry))
            ranges.append((start, end))
    matches.sort(key=lambda item: item[0])
    return [emote for _, emote in matches]


class TwitchChatSession:
    """Chat de Twitch de UN usuario.

    Todo el estado (canal, flags, buffer, instancia de Chat) vive en la sesión,
    nunca en el módulo: varios usuarios pueden tener su bot corriendo a la vez
    sin pisarse la conexión ni los mensajes.
    """

    def __init__(self, user_id: str):
        self.user_id = str(user_id)
        self.chat: Chat | None = None
        self.twitch = None
        self.twitch_bot = None
        self.target_channel: str | None = None
        self.bot_channel: str | None = None
        self.feature_flags: dict = {}
        self.bots: list[str] = list(DEFAULT_BOTS)
        self.chunk_message: list[str] = []
        self.channel_emotes: dict[str, dict[str, str]] = {}
        self.channel_emotes_loaded_at = 0.0
        self.channel_emote_refresh_task: asyncio.Task | None = None

    async def start(self, twitch_instance, twitch_bot=None) -> bool:
        self.twitch = twitch_instance
        self.twitch_bot = twitch_bot if twitch_bot else twitch_instance

        settings = await load_effective_settings(self.user_id)
        self.feature_flags = settings.get("feature_flags") or {}
        self.target_channel = settings.get("twitch_channel")
        self.bot_channel = settings.get("twitch_bot_account")
        self.bots = list(DEFAULT_BOTS)
        if self.bot_channel:
            self.bots.append(self.bot_channel)

        if not self.feature_flags.get("chat_replies", True) and not self.feature_flags.get(
            "moderation", True
        ):
            print(f"[TWITCH CHAT] Chat desactivado por configuración de {self.user_id}")
            return False

        if not self.target_channel:
            raise Exception(
                "Falta twitch_channel en la configuración. "
                "Primero guarda la configuración o vuelve a autenticar Twitch."
            )

        await self.stop()

        self.chat = await Chat(self.twitch)
        self.chat.register_event(ChatEvent.READY, self.on_ready)
        self.chat.register_event(ChatEvent.MESSAGE, self.on_message)
        self.chat.start()
        return True

    async def stop(self) -> None:
        if self.chat is None:
            return
        try:
            self.chat.stop()
        except Exception as exc:
            print(f"[TWITCH CHAT] Error al detener el chat de {self.user_id}: {repr(exc)}")
        finally:
            self.chat = None

    async def on_ready(self, ready_event: EventData) -> None:
        print(f"[TWITCH CHAT] Bot listo para {self.user_id}, uniendo canales")
        if not self.target_channel:
            raise Exception("No hay canal configurado para unir el chat")
        await ready_event.chat.join_room(self.target_channel)
        self._schedule_channel_emote_refresh()
        await chat_use_case.notify_chat_connected(self.target_channel, self.user_id)

    def _schedule_channel_emote_refresh(self, room_id: str | None = None) -> None:
        if time.monotonic() - self.channel_emotes_loaded_at < 3600:
            return
        if self.channel_emote_refresh_task and not self.channel_emote_refresh_task.done():
            return
        self.channel_emotes_loaded_at = time.monotonic()
        self.channel_emote_refresh_task = asyncio.create_task(
            self._refresh_channel_emotes(room_id)
        )

    async def _refresh_channel_emotes(self, room_id: str | None = None) -> None:
        if not room_id:
            try:
                room_id = str(await self._broadcaster_id())
            except Exception as exc:
                print(f"[TWITCH EMOTES] No se pudo resolver el canal: {exc!r}")
                self.channel_emotes_loaded_at = time.monotonic() - 3300
                return
        if not room_id.isdigit():
            self.channel_emotes_loaded_at = time.monotonic() - 3300
            return

        base_urls = {
            "bttv_channel": f"https://api.betterttv.net/3/cached/users/twitch/{room_id}",
            "bttv_global": "https://api.betterttv.net/3/cached/emotes/global",
            "seven_channel": f"https://7tv.io/v3/users/twitch/{room_id}",
            "seven_global": "https://7tv.io/v3/emote-sets/global",
            "ffz_channel": f"https://api.frankerfacez.com/v1/room/id/{room_id}",
            "ffz_global": "https://api.frankerfacez.com/v1/set/global",
        }

        async def fetch_json(client: httpx.AsyncClient, url: str) -> object:
            try:
                response = await client.get(url)
                if response.is_success:
                    return response.json()
            except (httpx.HTTPError, ValueError):
                return None
            return None

        try:
            async with httpx.AsyncClient(timeout=4.0, follow_redirects=True) as client:
                names = list(base_urls)
                results = await asyncio.gather(
                    *(fetch_json(client, base_urls[name]) for name in names)
                )
            payloads = dict(zip(names, results, strict=True))
            catalog = _merge_emote_catalogs(payloads)
            if catalog:
                self.channel_emotes = catalog
            elif not any(payloads.values()):
                self.channel_emotes_loaded_at = time.monotonic() - 3300
        except (httpx.HTTPError, ValueError) as exc:
            print(f"[TWITCH EMOTES] No se pudo cargar el catálogo del canal: {exc!r}")
            self.channel_emotes_loaded_at = time.monotonic() - 3300

    async def _broadcaster_id(self):
        broadcaster = auth.get_broadcaster(self.user_id, bot=False)
        broadcaster_id = getattr(broadcaster, "id", None)
        if broadcaster_id:
            return broadcaster_id
        broadcaster = await auth.get_profile_users(bot=False, user_id=self.user_id)
        return broadcaster.id

    async def _reply(
        self, msg: ChatMessage, response: str, batch: list[str]
    ) -> None:
        voice_enabled = bool(self.feature_flags.get("voice_replies", True))
        if not voice_enabled:
            await self.chat.send_message(msg.room.name, response)
            return
        await chat_use_case.process_chunk(
            response,
            messages=batch,
            user_id=self.user_id,
            voice_enabled=voice_enabled,
        )

    async def on_message(self, msg: ChatMessage) -> None:
        print(f"[{self.user_id}] {msg.user.name}: {msg.text}")
        if msg.user.name in self.bots:
            # Cuenta del bot o de un bot de terceros: ni se modera ni se responde.
            print(f"[MODERACION] {msg.user.name} está en la lista de bots; se ignora")
            return

        settings = await load_effective_settings(self.user_id)
        self.feature_flags = settings.get("feature_flags") or {}

        # Traza de la moderación: sin ella, un mensaje que no se borra puede ser
        # el diccionario que no lo vio, el usuario que es mod o la IA que lo
        # permitió, y desde fuera los tres casos parecen lo mismo.
        if bool(self.feature_flags.get("moderation", True)):
            sospechoso = await check_banned_words(msg.text, self.user_id)
            if not sospechoso:
                print(f"[MODERACION] Sin coincidencias en el diccionario: {msg.text!r}")
            elif msg.user.mod:
                print(f"[MODERACION] {msg.user.name} es moderador; no se le modera")
        else:
            sospechoso = False
            print("[MODERACION] Desactivada en la configuración")

        if sospechoso and msg.user.mod is False:
            print(f"[MODERACION] Sospechoso de {msg.user.name}: {msg.text!r}")
            # El diccionario solo levanta la sospecha; quien decide es la IA. Con
            # modelo local la consulta va y vuelve por el canal del navegador, y
            # si algo falla `should_delete_message` deja pasar el mensaje en vez
            # de tumbar el chat.
            if await should_delete_message(msg.text, self.user_id):
                try:
                    twitch_instance = self.twitch_bot if self.twitch_bot else self.twitch
                    broadcaster_id = await self._broadcaster_id()
                    await twitch_instance.delete_chat_message(
                        broadcaster_id, broadcaster_id, msg.id
                    )
                    await self.chat.send_message(
                        msg.room.name,
                        f"HEY! {msg.user.name} tu mensaje no es permitido, por favor no lo vuelvas a enviar elshan1Nojao ",
                    )
                except Exception as exc:
                    print(f"[MODERACION] No se pudo borrar el mensaje: {repr(exc)}")
                msg.text = "Mensaje no permitido"
                return

        room_id = getattr(msg.room, "room_id", None)
        self._schedule_channel_emote_refresh(str(room_id) if room_id else None)
        twitch_emotes = _get_twitch_emotes(msg.text, msg)
        channel_emotes = _match_external_emotes(msg.text, self.channel_emotes, twitch_emotes)
        await avatar_trigger_use_case.publish_avatar_trigger(
            "chat_message",
            {
                "user": msg.user.name,
                "message": msg.text,
                "emotes": twitch_emotes + channel_emotes,
            },
            user_id=self.user_id,
        )

        if not self.feature_flags.get("chat_replies", True):
            print(f"[TWITCH CHAT] chat_replies desactivado para {self.user_id}")
            return

        command = resolve_chat_command(settings)
        if command is not None:
            # Modo comando: sin lote. Solo cuenta el mensaje que invoca al bot y
            # se procesa únicamente lo que va detrás del comando. Se vacía el
            # lote por si quedaron mensajes de cuando estaba en modo lote.
            self.chunk_message.clear()
            texto = extract_command_message(msg.text, command)
            if texto is None:
                return
            batch = [f"{msg.user.name}: {texto}"]
        else:
            self.chunk_message.append(f"{msg.user.name}: {msg.text}")
            chunk_size = resolve_chunk_size(settings)
            if len(self.chunk_message) < chunk_size:
                return

            # El lote se vacía ANTES de llamar a la IA: si la llamada falla o llegan
            # mensajes mientras está en vuelo, no se mezclan con el lote actual ni
            # se quedan atascados esperando al siguiente.
            batch = list(self.chunk_message)
            self.chunk_message.clear()

        entrada = "\n".join(batch)

        # Con modelo local, el navegador resuelve la tarea entera: llama a su
        # modelo y encadena la voz directamente, igual que hace el micrófono.
        # Así el audio arranca con la primera frase sin dar la vuelta por aquí.
        if await try_local_task("chat", entrada, "vtuber", self.user_id):
            return

        try:
            response = await response_sandy(entrada, self.user_id)
        except Exception as exc:
            print(f"[CHAT ERROR] No se pudo generar respuesta: {repr(exc)}")
            response = "No pude responder en este momento."
        await self._reply(msg, response, batch)

    async def send(self, message: str) -> bool:
        if self.chat is None:
            print(f"[TWITCH CHAT] No hay chat activo de {self.user_id}")
            return False

        settings = await load_effective_settings(self.user_id)
        target_channel = settings.get("twitch_channel") or self.target_channel
        if not target_channel:
            print(f"[TWITCH CHAT] No hay canal objetivo para {self.user_id}")
            return False

        await self.chat.send_message(target_channel, message)
        return True


# Una sesión de chat por usuario. Nunca una instancia global compartida.
_sessions: dict[str, TwitchChatSession] = {}
_locks: dict[str, asyncio.Lock] = {}


def _resolve_user_id(user_id: str | None = None) -> str:
    owner_id = user_id or get_active_user_id()
    if not owner_id:
        raise Exception("No hay un usuario activo para operar el chat de Twitch")
    return str(owner_id)


def _lock_for(owner_id: str) -> asyncio.Lock:
    lock = _locks.get(owner_id)
    if lock is None:
        lock = asyncio.Lock()
        _locks[owner_id] = lock
    return lock


def get_chat_session(user_id: str | None = None) -> TwitchChatSession | None:
    """Sesión de chat de este usuario, o None si no tiene ninguna activa."""
    owner_id = _resolve_user_id(user_id)
    return _sessions.get(owner_id)


def get_chat(user_id: str | None = None):
    session = get_chat_session(user_id)
    return session.chat if session else None


async def setup_chat(twitch_instance, twitch_bot=None, user_id=None):
    owner_id = _resolve_user_id(user_id)
    async with _lock_for(owner_id):
        session = _sessions.get(owner_id)
        if session is None:
            session = TwitchChatSession(owner_id)
            _sessions[owner_id] = session
        started = await session.start(twitch_instance, twitch_bot)
        if not started:
            _sessions.pop(owner_id, None)
        return started


async def close_chat(user_id: str | None = None):
    owner_id = _resolve_user_id(user_id)
    async with _lock_for(owner_id):
        session = _sessions.pop(owner_id, None)
        if session is not None:
            await session.stop()


async def close_all_chats():
    """Solo para el apagado del proceso."""
    for owner_id in list(_sessions.keys()):
        session = _sessions.pop(owner_id, None)
        if session is not None:
            await session.stop()


async def send_twitch_message(message: str, user_id: str | None = None) -> bool:
    session = get_chat_session(user_id)
    if session is None:
        print("[TWITCH CHAT] No hay chat activo para enviar el mensaje")
        return False
    return await session.send(message)
