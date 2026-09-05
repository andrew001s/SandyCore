from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.core.runtime import get_active_user_id
from app.services.client_settings import load_effective_settings
from app.services.youtube.auth.auth import authenticate_youtube
from app.services.youtube.events.handler import YouTubeEventHandler
from app.services.youtube.monitor import LiveChatMonitor


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _resolve_user_id(user_id: str | None = None) -> str:
    resolved = user_id or get_active_user_id()
    if not resolved:
        raise Exception("No hay un usuario activo asociado a la configuración")
    return str(resolved)


@dataclass
class YouTubeLifecycleState:
    armed: bool = False
    running: bool = False
    last_activity: datetime = field(default_factory=_utcnow)
    monitor_task: asyncio.Task | None = None
    last_known_live: bool | None = None
    live_chat_id: str | None = None
    broadcast_id: str | None = None
    monitor: LiveChatMonitor | None = None


_states: dict[str, YouTubeLifecycleState] = {}
_state_lock = asyncio.Lock()


async def _get_state(user_id: str | None) -> YouTubeLifecycleState:
    resolved = _resolve_user_id(user_id)
    async with _state_lock:
        state = _states.get(resolved)
        if state is None:
            state = YouTubeLifecycleState()
            _states[resolved] = state
        return state


async def mark_activity(user_id: str | None = None) -> None:
    state = await _get_state(user_id)
    state.last_activity = _utcnow()


async def start_services(user_id: str | None = None) -> None:
    resolved = _resolve_user_id(user_id)
    state = await _get_state(resolved)

    # Verifica tokens válidos
    client = await authenticate_youtube(resolved)

    state.running = True
    state.armed = True
    await mark_activity(resolved)

    # Si ya hay una tarea de monitor activa, la conservamos
    if state.monitor_task and not state.monitor_task.done():
        return

    handler = YouTubeEventHandler(resolved, client)
    monitor = LiveChatMonitor(resolved, client, handler)
    state.monitor = monitor
    state.monitor_task = asyncio.create_task(monitor.run())
    print(f"[YOUTUBE LIFECYCLE] Tarea de monitor iniciada para {resolved}")


async def stop_services(user_id: str | None = None) -> None:
    resolved = _resolve_user_id(user_id)
    state = await _get_state(resolved)
    state.running = False
    state.armed = False
    task = state.monitor_task
    print(f"[YOUTUBE LIFECYCLE] Deteniendo monitor de YouTube para {resolved}")
    if task and not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        except Exception:
            pass
    state.monitor_task = None
    state.monitor = None


async def set_running(user_id: str | None = None, running: bool = True) -> None:
    resolved = _resolve_user_id(user_id)
    if running:
        await start_services(resolved)
    else:
        await stop_services(resolved)


def is_running(user_id: str | None = None) -> bool:
    try:
        resolved = _resolve_user_id(user_id)
    except Exception:
        return False
    state = _states.get(resolved)
    return bool(state and state.running)


async def get_service_status(user_id: str | None = None) -> dict[str, Any]:
    resolved = _resolve_user_id(user_id)
    state = await _get_state(resolved)
    settings = await load_effective_settings(resolved)
    last_activity = state.last_activity.isoformat() if state.last_activity else None
    return {
        "user_id": resolved,
        "running": state.running,
        "armed": state.armed,
        "monitor_active": bool(state.monitor_task and not state.monitor_task.done()),
        "last_known_live": state.last_known_live,
        "last_activity": last_activity,
        "youtube_channel_id": settings.get("youtube_channel_id"),
        "youtube_channel_title": settings.get("youtube_channel_title"),
        "youtube_broadcast_id": state.broadcast_id or settings.get("youtube_broadcast_id"),
        "youtube_live_chat_id": state.live_chat_id or settings.get("youtube_live_chat_id"),
        "status": "active" if state.running else "inactive",
    }
