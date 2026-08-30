"""Ciclo de vida de los servicios de Twitch de un usuario.

Solo hay modo manual: los servicios arrancan y paran cuando el usuario lo pide.
El modo híbrido —que vigilaba el directo para arrancar y parar solo— se retiró
porque consumía tokens del cliente sin que él lo decidiera.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.core.runtime import get_active_user_id


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _key(user_id: str | None) -> str:
    resolved = user_id or get_active_user_id()
    if not resolved:
        raise ValueError("No hay un usuario activo para controlar el ciclo de vida")
    return str(resolved)


@dataclass
class LifecycleState:
    running: bool = False
    last_activity: datetime = field(default_factory=_utcnow)


_states: dict[str, LifecycleState] = {}
_state_lock = asyncio.Lock()


async def _get_state(user_id: str | None) -> LifecycleState:
    resolved = _key(user_id)
    async with _state_lock:
        state = _states.get(resolved)
        if state is None:
            state = LifecycleState()
            _states[resolved] = state
        return state


async def mark_activity(user_id: str | None = None) -> None:
    state = await _get_state(user_id)
    state.last_activity = _utcnow()


async def start_services(user_id: str | None = None) -> None:
    from app.services.twitch.twitch import auth, setup_chat_instance, setup_eventsub_instance

    resolved = _key(user_id)
    session = auth.get_session(resolved, bot=False)
    if session is None:
        try:
            _, _, _ = await auth.return_twitch_instance(False, resolved)
            session = auth.get_session(resolved, bot=False)
        except Exception:
            session = None

    if session is None:
        print(f"[TWITCH LIFECYCLE] Twitch no está autenticado para {resolved}; omitiendo.")
        state = await _get_state(resolved)
        state.running = True
        return

    twitch_client = session.client
    if session.profile is None:
        await auth.get_profile_users(bot=False, user_id=resolved)
    broadcaster_id = getattr(session.profile, "id", None)
    if not broadcaster_id:
        print(f"[TWITCH LIFECYCLE] No se pudo resolver broadcaster para {resolved}")
        state = await _get_state(resolved)
        state.running = True
        return

    try:
        await setup_chat_instance(twitch_client, user_id=resolved)
        await setup_eventsub_instance(twitch_client, resolved, broadcaster_id)
    except Exception as exc:
        print(f"[TWITCH LIFECYCLE] Error al iniciar chat o EventSub: {repr(exc)}")

    state = await _get_state(resolved)
    state.running = True
    await mark_activity(resolved)


async def stop_services(user_id: str | None = None) -> None:
    from app.services.twitch.twitch import close_chat_instance, close_eventsub

    resolved = _key(user_id)
    print(f"[TWITCH LIFECYCLE] Deteniendo chat y EventSub para {resolved}")
    await close_chat_instance(resolved)
    await close_eventsub(resolved)
    state = await _get_state(resolved)
    state.running = False


async def set_running(user_id: str | None = None, running: bool = True) -> None:
    state = await _get_state(user_id)
    state.running = running
    if running:
        await mark_activity(user_id)


def is_running(user_id: str | None = None) -> bool:
    """Sin efectos secundarios: sirve para decidir si hay algo que apagar."""
    state = _states.get(_key(user_id))
    return bool(state and state.running)


async def get_service_status(user_id: str | None = None) -> dict[str, object]:
    resolved = _key(user_id)
    state = await _get_state(resolved)

    twitch_connected = False
    kick_connected = False
    youtube_connected = False
    kick_running = False
    youtube_running = False

    try:
        from app.services.storage.supabase_store import get_twitch_tokens
        twitch_tokens = await get_twitch_tokens(resolved, False)
        twitch_connected = bool(twitch_tokens)
    except Exception:
        pass

    try:
        from app.services.storage.supabase_store import get_kick_tokens
        from app.services.kick.lifecycle import is_running as is_kick_running
        kick_tokens = await get_kick_tokens(resolved, False)
        kick_connected = bool(kick_tokens)
        kick_running = is_kick_running(resolved)
    except Exception:
        pass

    try:
        from app.services.youtube.auth.auth import get_tokens as get_youtube_tokens
        from app.services.youtube.youtube import _get_state as get_youtube_state
        yt_tokens = await get_youtube_tokens(resolved)
        youtube_connected = bool(yt_tokens)
        yt_state = await get_youtube_state(resolved)
        youtube_running = bool(yt_state.running)
    except Exception:
        pass

    return {
        "user_id": resolved,
        "service_mode": "manual",
        "running": state.running,
        "last_activity": state.last_activity.isoformat() if state.last_activity else None,
        "status": "active" if state.running else "inactive",
        "platforms": {
            "twitch": {
                "connected": twitch_connected,
                "running": bool(state.running and twitch_connected),
            },
            "kick": {
                "connected": kick_connected,
                "running": kick_running,
            },
            "youtube": {
                "connected": youtube_connected,
                "running": youtube_running,
            },
        },
    }
