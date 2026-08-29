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
        raise RuntimeError("No hay instancia de Twitch autenticada para iniciar servicios")

    twitch_client = session.client
    if session.profile is None:
        await auth.get_profile_users(bot=False, user_id=resolved)
    broadcaster_id = getattr(session.profile, "id", None)
    if not broadcaster_id:
        raise RuntimeError("No se pudo resolver el broadcaster para iniciar servicios")

    try:
        await setup_chat_instance(twitch_client, user_id=resolved)
        await setup_eventsub_instance(twitch_client, resolved, broadcaster_id)
    except Exception:
        from app.services.twitch.twitch import close_chat_instance, close_eventsub

        await close_chat_instance(resolved)
        await close_eventsub(resolved)
        raise

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
    return {
        "user_id": resolved,
        "service_mode": "manual",
        "running": state.running,
        "last_activity": state.last_activity.isoformat() if state.last_activity else None,
        "status": "active" if state.running else "inactive",
    }
