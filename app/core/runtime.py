from contextvars import ContextVar


_active_user_id: ContextVar[str | None] = ContextVar("active_user_id", default=None)
_last_active_user_id: str | None = None


def set_active_user_id(user_id: str | None) -> None:
    global _last_active_user_id
    _active_user_id.set(user_id)
    _last_active_user_id = user_id


def get_active_user_id() -> str | None:
    return _active_user_id.get() or _last_active_user_id

