"""Errores del proveedor de IA con códigos estables para el cliente.

El backend traduce cualquier fallo (OpenRouter, Gemini, red) a uno de estos
códigos. El frontend decide el texto que ve el usuario a partir del código, sin
tener que interpretar el mensaje crudo del proveedor, que cambia sin aviso.
"""

from __future__ import annotations

from typing import Any

# --- códigos ---------------------------------------------------------------
RATE_LIMIT = "error.rate-limit"
INSUFFICIENT_CREDITS = "error.insufficient-credits"
INVALID_API_KEY = "error.invalid-api-key"
FORBIDDEN = "error.forbidden"
MODEL_NOT_FOUND = "error.model-not-found"
INVALID_REQUEST = "error.invalid-request"
PROVIDER_UNAVAILABLE = "error.provider-unavailable"
TIMEOUT = "error.timeout"
CONTENT_BLOCKED = "error.content-blocked"
EMPTY_RESPONSE = "error.empty-response"
UNKNOWN = "error.unknown"

# Mensaje de reserva por si el cliente no conoce el código todavía.
DEFAULT_MESSAGES = {
    RATE_LIMIT: (
        "Superaste el límite de llamadas al modelo. Espera un momento o cambia "
        "a otro modelo."
    ),
    INSUFFICIENT_CREDITS: (
        "No hay créditos suficientes en el proveedor de IA. Recarga tu cuenta o "
        "usa un modelo gratuito."
    ),
    INVALID_API_KEY: (
        "La API key del proveedor de IA no es válida. Revísala en Ajustes."
    ),
    FORBIDDEN: (
        "Tu API key no tiene permiso para usar este modelo."
    ),
    MODEL_NOT_FOUND: (
        "El modelo configurado ya no existe o no está disponible. Elige otro en "
        "Ajustes."
    ),
    INVALID_REQUEST: "La petición al proveedor de IA no es válida.",
    PROVIDER_UNAVAILABLE: (
        "El proveedor de IA no está respondiendo. Inténtalo de nuevo en unos "
        "minutos."
    ),
    TIMEOUT: "El proveedor de IA tardó demasiado en responder.",
    CONTENT_BLOCKED: "El proveedor bloqueó la respuesta por sus filtros de contenido.",
    EMPTY_RESPONSE: "El proveedor de IA devolvió una respuesta vacía.",
    UNKNOWN: "No se pudo generar una respuesta con el proveedor de IA.",
}

# Estado HTTP con el que responde la API para cada código.
HTTP_STATUS = {
    RATE_LIMIT: 429,
    INSUFFICIENT_CREDITS: 402,
    INVALID_API_KEY: 401,
    FORBIDDEN: 403,
    MODEL_NOT_FOUND: 404,
    INVALID_REQUEST: 400,
    PROVIDER_UNAVAILABLE: 503,
    TIMEOUT: 504,
    CONTENT_BLOCKED: 422,
    EMPTY_RESPONSE: 502,
    UNKNOWN: 500,
}

# Códigos donde reintentar más tarde tiene sentido; el resto necesita que el
# usuario cambie algo en su configuración.
RETRYABLE = {RATE_LIMIT, PROVIDER_UNAVAILABLE, TIMEOUT}


class AIProviderError(Exception):
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
        return f"AIProviderError({' | '.join(partes)}: {self.detail or self.message})"


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
    401: INVALID_API_KEY,
    402: INSUFFICIENT_CREDITS,
    403: FORBIDDEN,
    404: MODEL_NOT_FOUND,
    408: TIMEOUT,
    422: INVALID_REQUEST,
    429: RATE_LIMIT,
}

# Algunos proveedores devuelven 400 genérico y explican la causa en el texto.
_BY_HINT = (
    (("insufficient credit", "insufficient_quota", "not enough credit", "add credits", "payment required"), INSUFFICIENT_CREDITS),
    (("api key not valid", "invalid api key", "invalid_api_key", "incorrect api key", "no auth credentials"), INVALID_API_KEY),
    (("rate limit", "rate-limited", "too many requests", "quota exceeded", "resource_exhausted"), RATE_LIMIT),
    (("model not found", "no endpoints found", "is not a valid model", "unknown model"), MODEL_NOT_FOUND),
    (("safety", "blocked", "content filter"), CONTENT_BLOCKED),
)


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


def classify_ai_error(
    exc: BaseException, *, provider: str | None = None, model: str | None = None
) -> AIProviderError:
    """Traduce la excepción de cualquier proveedor a un AIProviderError."""
    if isinstance(exc, AIProviderError):
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
        # El texto manda sobre un 400 genérico, pero no sobre un estado que ya
        # es específico: un 429 es límite de llamadas aunque el texto hable de
        # cuota de créditos.
        if code in (None, INVALID_REQUEST):
            code = _hint_code(detail) or code or UNKNOWN

    return AIProviderError(
        code, provider=provider, model=model, status=status, detail=detail
    )
