import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.core.runtime import get_active_user_id
from app.services.client_settings import load_effective_settings


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _key(user_id: str | None) -> str:
    resolved = user_id or get_active_user_id()
    if not resolved:
        raise ValueError("No hay un usuario activo para controlar el ciclo de vida")
    return str(resolved)


@dataclass
class LifecycleState:
    armed: bool = False
    running: bool = False
    last_activity: datetime = field(default_factory=_utcnow)
    monitor_task: asyncio.Task | None = None
    last_known_live: bool | None = None


_states: dict[str, LifecycleState] = {}
_state_lock = asyncio.Lock()
_monitor_interval_seconds = 30


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


async def arm(user_id: str | None = None) -> None:
    state = await _get_state(user_id)
    state.armed = True
    await mark_activity(user_id)


async def disarm(user_id: str | None = None) -> None:
    state = await _get_state(user_id)
    state.armed = False
    await stop_monitor(user_id)


async def _stream_is_live(user_id: str | None = None) -> bool:
    from app.services.kick.auth import auth

    resolved = _key(user_id)
    session = auth.get_session(resolved, bot=False)
    if session is None:
        return False

    kick_client = session.client
    profile = session.profile
    broadcaster_id = profile.get("id") if isinstance(profile, dict) else None
    if not broadcaster_id:
        return False

    streams = await kick_client.get_livestreams(broadcaster_user_id=[str(broadcaster_id)])
    if isinstance(streams, dict) and "data" in streams:
        streams = streams["data"]
    return bool(streams)


async def start_services(user_id: str | None = None) -> None:
    from app.services.kick.auth import auth

    resolved = _key(user_id)
    if auth.get_session(resolved, bot=False) is None:
        raise RuntimeError("No hay instancia de Kick autenticada para iniciar servicios")

    state = await _get_state(resolved)
    state.running = True
    await mark_activity(resolved)
    await start_monitor(resolved)


async def stop_services(user_id: str | None = None) -> None:
    resolved = _key(user_id)
    state = await _get_state(resolved)
    print(f"[KICK LIFECYCLE] Deteniendo monitor para {resolved}")
    await stop_monitor(resolved)
    state.running = False


async def _tick(user_id: str) -> None:
    settings = await load_effective_settings(user_id)
    service_mode = str(settings.get("service_mode") or "manual").lower()
    auto_start_on_live = bool(settings.get("auto_start_on_live", False))
    auto_stop_on_offline = bool(settings.get("auto_stop_on_offline", True))
    idle_timeout_minutes = int(settings.get("idle_timeout_minutes") or 0)

    if service_mode != "hybrid":
        return

    state = await _get_state(user_id)
    live = await _stream_is_live(user_id)
    state.last_known_live = live

    if state.running and auto_stop_on_offline and not live:
        print(f"[LIFECYCLE] Stream offline, deteniendo servicios de {user_id}")
        await stop_services(user_id)
        return

    if state.running and idle_timeout_minutes > 0:
        elapsed = (_utcnow() - state.last_activity).total_seconds() / 60.0
        if elapsed >= idle_timeout_minutes:
            print(f"[LIFECYCLE] Inactividad detectada ({elapsed:.1f}m), deteniendo servicios de {user_id}")
            await stop_services(user_id)
            return

    if not state.running and state.armed and auto_start_on_live and live:
        print(f"[LIFECYCLE] Stream en vivo, arrancando servicios de {user_id}")
        await start_services(user_id)


async def _monitor_loop(user_id: str) -> None:
    try:
        while True:
            state = await _get_state(user_id)
            if not state.armed and not state.running:
                break
            settings = await load_effective_settings(user_id)
            service_mode = str(settings.get("service_mode") or "manual").lower()
            if service_mode != "hybrid":
                state.armed = False
                break
            try:
                await _tick(user_id)
            except Exception as exc:
                print(f"[LIFECYCLE] Error en monitor de {user_id}: {repr(exc)}")
            await asyncio.sleep(_monitor_interval_seconds)
    finally:
        state = await _get_state(user_id)
        state.monitor_task = None


async def start_monitor(user_id: str | None = None) -> None:
    resolved = _key(user_id)
    state = await _get_state(resolved)
    if state.monitor_task and not state.monitor_task.done():
        return
    settings = await load_effective_settings(resolved)
    service_mode = str(settings.get("service_mode") or "hybrid").lower()
    if service_mode != "hybrid":
        return
    state.armed = True
    state.monitor_task = asyncio.create_task(_monitor_loop(resolved))


async def stop_monitor(user_id: str | None = None) -> None:
    resolved = _key(user_id)
    state = await _get_state(resolved)
    task = state.monitor_task
    state.armed = False
    print(f"[KICK LIFECYCLE] Deteniendo monitor para {resolved}")
    if task and not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        except Exception:
            pass
    state.monitor_task = None


async def register_activity_and_monitor(user_id: str | None = None) -> None:
    await mark_activity(user_id)
    await start_monitor(user_id)


async def set_running(user_id: str | None = None, running: bool = True) -> None:
    state = await _get_state(user_id)
    state.running = running
    if running:
        await mark_activity(user_id)


async def get_service_status(user_id: str | None = None) -> dict[str, object]:
    resolved = _key(user_id)
    state = await _get_state(resolved)
    settings = await load_effective_settings(resolved)
    service_mode = str(settings.get("service_mode") or "manual").lower()
    auto_start_on_live = bool(settings.get("auto_start_on_live", False))
    auto_stop_on_offline = bool(settings.get("auto_stop_on_offline", True))
    idle_timeout_minutes = int(settings.get("idle_timeout_minutes") or 0)
    last_activity = state.last_activity.isoformat() if state.last_activity else None

    return {
        "user_id": resolved,
        "service_mode": service_mode,
        "running": state.running,
        "armed": state.armed,
        "monitor_active": bool(state.monitor_task and not state.monitor_task.done()),
        "last_known_live": state.last_known_live,
        "last_activity": last_activity,
        "auto_start_on_live": auto_start_on_live,
        "auto_stop_on_offline": auto_stop_on_offline,
        "idle_timeout_minutes": idle_timeout_minutes,
        "status": "active" if state.running else "inactive",
    }
