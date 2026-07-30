import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any

from fastapi import HTTPException, status

from app.core.config import config

STREAM_TOKEN_TTL_SECONDS = 300


def _get_secret() -> str:
    if not config.STREAM_TOKEN_SECRET:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Falta STREAM_TOKEN_SECRET para firmar el stream",
        )
    return config.STREAM_TOKEN_SECRET


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64decode(data: str) -> bytes:
    padding_len = (-len(data)) % 4
    return base64.urlsafe_b64decode(data + ("=" * padding_len))


def create_stream_token(user_id: str, ttl_seconds: int = STREAM_TOKEN_TTL_SECONDS) -> str:
    now = int(time.time())
    payload = {
        "sub": user_id,
        "iat": now,
        "exp": now + ttl_seconds,
        "nonce": secrets.token_urlsafe(12),
    }
    raw_payload = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode(
        "utf-8"
    )
    signature = hmac.new(
        _get_secret().encode("utf-8"),
        raw_payload,
        hashlib.sha256,
    ).digest()
    return f"{_b64encode(raw_payload)}.{_b64encode(signature)}"


def verify_stream_token(token: str) -> dict[str, Any]:
    parts = token.split(".")
    if len(parts) != 2:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de stream inválido",
        )

    try:
        raw_payload = _b64decode(parts[0])
        raw_signature = _b64decode(parts[1])
        expected_signature = hmac.new(
            _get_secret().encode("utf-8"),
            raw_payload,
            hashlib.sha256,
        ).digest()

        if not hmac.compare_digest(raw_signature, expected_signature):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Firma de stream inválida",
            )

        payload = json.loads(raw_payload)
        now = int(time.time())
        if int(payload.get("exp", 0)) <= now:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token de stream expirado",
            )

        if not payload.get("sub"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token de stream sin usuario",
            )

        return payload
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"No se pudo verificar el token de stream: {exc}",
        ) from exc
