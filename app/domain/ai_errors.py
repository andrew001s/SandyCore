"""Errores del proveedor de IA.

Se apoya en `app.domain.errors`, que es el catálogo común de códigos: el
cliente resuelve el texto a partir del `code` sin importar de qué módulo venga
el fallo. Este módulo solo añade el tipo específico de IA y su clasificador.
"""

from __future__ import annotations

from app.domain.errors import (  # noqa: F401  (re-exportados por compatibilidad)
    NOT_FOUND,
    REAUTH_REQUIRED,
    CONTENT_BLOCKED,
    DEFAULT_MESSAGES,
    EMPTY_RESPONSE,
    FORBIDDEN,
    HTTP_STATUS,
    INSUFFICIENT_CREDITS,
    INVALID_API_KEY,
    INVALID_REQUEST,
    MODEL_NOT_FOUND,
    PROVIDER_UNAVAILABLE,
    RATE_LIMIT,
    RETRYABLE,
    TIMEOUT,
    UNKNOWN,
    AppError,
    classify_error,
    unwrap_error,
)


class AIProviderError(AppError):
    """Fallo atribuible al proveedor de IA."""


def classify_ai_error(
    exc: BaseException, *, provider: str | None = None, model: str | None = None
) -> AIProviderError:
    if isinstance(exc, AIProviderError):
        return exc

    base = classify_error(exc, provider=provider, model=model)

    # El catálogo común lee un 401 como "vuelve a autorizar la cuenta" y un 404
    # como "recurso inexistente". En un proveedor de IA significan otra cosa:
    # la API key no sirve, o el modelo configurado ya no existe.
    code = {REAUTH_REQUIRED: INVALID_API_KEY, NOT_FOUND: MODEL_NOT_FOUND}.get(
        base.code, base.code
    )

    return AIProviderError(
        code,
        provider=base.provider,
        model=base.model,
        status=base.status,
        detail=base.detail,
    )
