from contextvars import ContextVar


# El usuario activo vive SOLO en el contexto de la petición/tarea actual.
# Nunca debe existir un fallback a nivel de proceso: con varios clientes
# concurrentes, ese fallback resolvería el "último usuario que tocó el
# servidor" y devolvería datos de otra cuenta.
_active_user_id: ContextVar[str | None] = ContextVar("active_user_id", default=None)


def set_active_user_id(user_id: str | None) -> None:
    _active_user_id.set(user_id)


def get_active_user_id() -> str | None:
    return _active_user_id.get()
