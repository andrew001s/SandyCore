"""Errores de aplicación con códigos estables para el cliente.

Todos los endpoints responden un fallo con la misma forma:

    {"error": {"code", "message", "provider", "model", "retryable"}}

El cliente decide el texto que ve el usuario a partir del `code`. Los mensajes
crudos de Twitch, Kick, YouTube o el proveedor de IA cambian sin aviso y no
sirven como contrato.
"""

from __future__ import annotations

import re
from typing import Any

# --- códigos ---------------------------------------------------------------
# Proveedor de IA
RATE_LIMIT = "error.rate-limit"
INSUFFICIENT_CREDITS = "error.insufficient-credits"
INVALID_API_KEY = "error.invalid-api-key"
FORBIDDEN = "error.forbidden"
MODEL_NOT_FOUND = "error.model-not-found"
CONTENT_BLOCKED = "error.content-blocked"
EMPTY_RESPONSE = "error.empty-response"

# Integraciones de plataforma y configuración
NOT_CONNECTED = "error.not-connected"
REAUTH_REQUIRED = "error.reauth-required"
NO_ACTIVE_USER = "error.no-active-user"
MISSING_CONFIG = "error.missing-config"
CHANNEL_NOT_CONFIGURED = "error.channel-not-configured"
NO_BROADCAST = "error.no-broadcast"
SERVICE_NOT_RUNNING = "error.service-not-running"
STORAGE_UNAVAILABLE = "error.storage-unavailable"
LOCAL_PROVIDER_UNREACHABLE = "error.local-provider-unreachable"
ORDER_FAILED = "error.order-failed"
CATEGORY_NOT_FOUND = "error.category-not-found"

# Genéricos
NOT_FOUND = "error.not-found"
INVALID_REQUEST = "error.invalid-request"
PROVIDER_UNAVAILABLE = "error.provider-unavailable"
TIMEOUT = "error.timeout"
UNKNOWN = "error.unknown"

DEFAULT_MESSAGES: dict[str, str] = {
    RATE_LIMIT: "Superaste el límite de llamadas al modelo. Espera un momento o cambia a otro modelo.",
    INSUFFICIENT_CREDITS: "No hay créditos suficientes en el proveedor de IA. Recarga tu cuenta o usa un modelo gratuito.",
    INVALID_API_KEY: "La API key del proveedor de IA no es válida. Revísala en Ajustes.",
    FORBIDDEN: "Tu API key no tiene permiso para usar este modelo.",
    MODEL_NOT_FOUND: "El modelo configurado ya no existe o no está disponible. Elige otro en Ajustes.",
    CONTENT_BLOCKED: "El proveedor bloqueó la respuesta por sus filtros de contenido.",
    EMPTY_RESPONSE: "El proveedor de IA devolvió una respuesta vacía.",
    NOT_CONNECTED: "Esta plataforma no está conectada todavía. Vincúlala para continuar.",
    REAUTH_REQUIRED: "La sesión con la plataforma caducó. Vuelve a autorizar la cuenta.",
    NO_ACTIVE_USER: "No hay una cuenta activa para esta operación.",
    MISSING_CONFIG: "Falta configuración del servidor para esta integración.",
    CHANNEL_NOT_CONFIGURED: "Falta configurar el canal. Guarda la configuración o vuelve a vincular la cuenta.",
    NO_BROADCAST: "No hay una transmisión activa en este momento.",
    SERVICE_NOT_RUNNING: "El servicio no está en marcha.",
    ORDER_FAILED: "No se pudo aplicar la orden en el canal.",
    CATEGORY_NOT_FOUND: "Twitch no tiene ninguna categoría con ese nombre.",
    STORAGE_UNAVAILABLE: "No se pudo acceder a la base de datos. Inténtalo de nuevo en unos minutos.",
    LOCAL_PROVIDER_UNREACHABLE: (
        "No hay ninguna pestaña abierta que atienda al modelo local. Abre el "
        "panel de Sandy para que pueda responder al chat y a los eventos."
    ),
    NOT_FOUND: "No se encontró el recurso solicitado.",
    INVALID_REQUEST: "La petición no es válida.",
    PROVIDER_UNAVAILABLE: "El servicio externo no está respondiendo. Inténtalo de nuevo en unos minutos.",
    TIMEOUT: "El servicio externo tardó demasiado en responder.",
    UNKNOWN: "No se pudo completar la operación.",
}

# 401 queda reservado para la sesión de Clerk: usarlo para "plataforma sin
# vincular" haría que el cliente creyera que el usuario perdió la sesión. Esos
# estados van con 409, que es lo que son: falta un paso previo.
HTTP_STATUS: dict[str, int] = {
    RATE_LIMIT: 429,
    INSUFFICIENT_CREDITS: 402,
    INVALID_API_KEY: 401,
    FORBIDDEN: 403,
    MODEL_NOT_FOUND: 404,
    CONTENT_BLOCKED: 422,
    EMPTY_RESPONSE: 502,
    NOT_CONNECTED: 409,
    REAUTH_REQUIRED: 409,
    NO_ACTIVE_USER: 409,
    MISSING_CONFIG: 409,
    CHANNEL_NOT_CONFIGURED: 409,
    NO_BROADCAST: 409,
    SERVICE_NOT_RUNNING: 409,
    STORAGE_UNAVAILABLE: 503,
    LOCAL_PROVIDER_UNREACHABLE: 409,
    ORDER_FAILED: 409,
    CATEGORY_NOT_FOUND: 404,
    NOT_FOUND: 404,
    INVALID_REQUEST: 400,
    PROVIDER_UNAVAILABLE: 503,
    TIMEOUT: 504,
    UNKNOWN: 500,
}

# Códigos donde reintentar tiene sentido; el resto necesita que el usuario
# cambie algo.
RETRYABLE = {RATE_LIMIT, PROVIDER_UNAVAILABLE, TIMEOUT, STORAGE_UNAVAILABLE}


class AppError(Exception):
    def __init__(
        self,
        code: str,
        message: str | None = None,
        *,
        provider: str | None = None,
        model: str | None = None,
        status: int | None = None,
        detail: str | None = None,
    ):
        self.code = code
        self.message = message or DEFAULT_MESSAGES.get(code, DEFAULT_MESSAGES[UNKNOWN])
        self.provider = provider
        self.model = model
        self.status = status
        self.detail = detail
        self.retryable = code in RETRYABLE
        super().__init__(self.message)

    @property
    def http_status(self) -> int:
        return HTTP_STATUS.get(self.code, 500)

    def to_payload(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "provider": self.provider,
            "model": self.model,
            "retryable": self.retryable,
        }

    def __repr__(self) -> str:
        partes = [self.code]
        if self.provider:
            partes.append(self.provider)
        if self.status is not None:
            partes.append(f"HTTP {self.status}")
        return f"{type(self).__name__}({' | '.join(partes)}: {self.detail or self.message})"


def unwrap_error(exc: BaseException) -> BaseException:
    """Desenvuelve el RetryError con el que el SDK de Gemini tapa el error real.

    Sin `http_options.retry_options`, el SDK envuelve la llamada en un
    `tenacity.Retrying(stop=stop_after_attempt(1))`. Al no llevar `reraise`,
    cualquier excepción sale como `RetryError(<Future ... raised ClientError>)`,
    sin el código HTTP ni el mensaje de la API.
    """
    seen: set[int] = set()
    current: BaseException = exc
    while id(current) not in seen:
        seen.add(id(current))
        last_attempt = getattr(current, "last_attempt", None)
        if last_attempt is None or not hasattr(last_attempt, "exception"):
            break
        try:
            inner = last_attempt.exception()
        except Exception:
            break
        if inner is None:
            break
        current = inner
    return current


_BY_STATUS = {
    400: INVALID_REQUEST,
    401: REAUTH_REQUIRED,
    402: INSUFFICIENT_CREDITS,
    403: FORBIDDEN,
    404: NOT_FOUND,
    408: TIMEOUT,
    409: INVALID_REQUEST,
    422: INVALID_REQUEST,
    429: RATE_LIMIT,
}

# El texto de las excepciones que ya lanza el código. Se comprueban en orden,
# así que lo más específico va primero.
_BY_HINT: tuple[tuple[tuple[str, ...], str], ...] = (
    (("insufficient credit", "insufficient_quota", "not enough credit", "add credits", "payment required"), INSUFFICIENT_CREDITS),
    (("api key not valid", "invalid api key", "invalid_api_key", "incorrect api key", "no auth credentials"), INVALID_API_KEY),
    (("rate limit", "rate-limited", "too many requests", "quota exceeded", "resource_exhausted"), RATE_LIMIT),
    (("no endpoints found", "is not a valid model", "unknown model", "model not found"), MODEL_NOT_FOUND),
    (("no hay un usuario activo", "no active user"), NO_ACTIVE_USER),
    (("no existe una sesión", "no existen tokens", "usuario no autenticado",
      "no existe un canal de youtube autenticado", "no hay una sesión de twitch autenticada",
      "no hay instancia", "no se recibieron tokens"), NOT_CONNECTED),
    (("expiró y no hay refresh token", "no se pudo autenticar", "falló la autenticación",
      "no es válido o expiró", "no se pudo refrescar", "failed to refresh token",
      "no se pudo verificar", "unauthorized", "no se pudo completar el oauth",
      "failed to exchange code"), REAUTH_REQUIRED),
    (("falta twitch_channel", "no hay canal configurado", "no se pudo determinar el canal",
      "no se pudo obtener el canal"), CHANNEL_NOT_CONFIGURED),
    (("faltan ", "falta "), MISSING_CONFIG),
    (("no hay una transmisión", "no se encontró la transmisión", "no hay transmisión"), NO_BROADCAST),
    (("no está iniciado", "no hay chat activo", "no está en marcha"), SERVICE_NOT_RUNNING),
    (("supabase", "postgrest", "connection refused", "could not connect"), STORAGE_UNAVAILABLE),
    (("safety", "content filter", "blocked"), CONTENT_BLOCKED),
    (("orden desconocida",), INVALID_REQUEST),
    (("timed out", "timeout"), TIMEOUT),
)

_STATUS_IN_TEXT = re.compile(r"\b(4\d{2}|5\d{2})\b")


def _status_of(exc: BaseException) -> int | None:
    for attr in ("status_code", "code", "status"):
        value = getattr(exc, attr, None)
        if isinstance(value, int):
            return value
    response = getattr(exc, "response", None)
    status = getattr(response, "status_code", None)
    return status if isinstance(status, int) else None


def _hint_code(text: str) -> str | None:
    lowered = text.lower()
    for agujas, code in _BY_HINT:
        if any(aguja in lowered for aguja in agujas):
            return code
    return None


def classify_error(
    exc: BaseException,
    *,
    provider: str | None = None,
    model: str | None = None,
) -> AppError:
    """Traduce cualquier excepción a un AppError con código estable."""
    if isinstance(exc, AppError):
        return exc

    real = unwrap_error(exc)
    detail = f"{type(real).__name__}: {real}"
    status = _status_of(real)
    nombre = type(real).__name__

    if nombre in ("APITimeoutError", "TimeoutError") or isinstance(real, TimeoutError):
        code = TIMEOUT
    elif nombre == "APIConnectionError":
        code = PROVIDER_UNAVAILABLE
    elif status is not None and status >= 500:
        code = PROVIDER_UNAVAILABLE
    else:
        code = _BY_STATUS.get(status) if status is not None else None
        # El texto manda sobre un estado genérico, pero no sobre uno que ya es
        # específico: un 429 es límite de llamadas aunque el texto hable de
        # cuota de créditos.
        if code in (None, INVALID_REQUEST, NOT_FOUND, REAUTH_REQUIRED):
            code = _hint_code(detail) or code
        if code is None:
            # Algunos módulos incrustan el estado en el mensaje
            # ("Failed to refresh token: 401 {...}").
            encontrado = _STATUS_IN_TEXT.search(detail)
            if encontrado:
                numero = int(encontrado.group(1))
                code = (
                    PROVIDER_UNAVAILABLE
                    if numero >= 500
                    else _BY_STATUS.get(numero, UNKNOWN)
                )
        code = code or UNKNOWN

    return AppError(code, provider=provider, model=model, status=status, detail=detail)


def error_payload(
    exc: BaseException, *, provider: str | None = None, model: str | None = None
) -> tuple[int, dict[str, Any]]:
    """(estado HTTP, cuerpo) listos para devolver desde un endpoint."""
    error = classify_error(exc, provider=provider, model=model)
    if error.code == UNKNOWN:
        print(f"[ERROR] sin clasificar: {type(exc).__name__}: {exc}")
    else:
        print(f"[ERROR] {error!r}")
    return error.http_status, {"error": error.to_payload()}
