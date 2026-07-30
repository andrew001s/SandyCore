import base64
import json
import os
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import httpx
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from fastapi import Depends, HTTPException, Request, status

from app.core.runtime import set_active_user_id


@dataclass(slots=True)
class ClerkUser:
    user_id: str
    session_id: str | None
    claims: dict[str, Any]


def _b64url_decode(data: str) -> bytes:
    padding_len = (-len(data)) % 4
    return base64.urlsafe_b64decode(data + ("=" * padding_len))


def _b64url_decode_int(data: str) -> int:
    return int.from_bytes(_b64url_decode(data), "big")


def _load_token_from_request(request: Request) -> str | None:
    authorization = request.headers.get("Authorization", "")
    if authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1].strip()
    cookie_token = request.cookies.get("__session")
    if cookie_token:
        return cookie_token
    return None


@lru_cache(maxsize=1)
def _clerk_jwks_url() -> str:
    return os.getenv("CLERK_JWKS_URL", "https://api.clerk.com/v1/jwks")


@lru_cache(maxsize=1)
def _clerk_audience() -> str | None:
    return os.getenv("CLERK_AUDIENCE")


async def _fetch_jwks() -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(_clerk_jwks_url())
        response.raise_for_status()
        return response.json()


def _jwk_to_public_key(jwk: dict[str, Any]) -> rsa.RSAPublicKey:
    n = _b64url_decode_int(jwk["n"])
    e = _b64url_decode_int(jwk["e"])
    public_numbers = rsa.RSAPublicNumbers(e=e, n=n)
    return public_numbers.public_key()


async def verify_clerk_session(request: Request) -> ClerkUser:
    token = _load_token_from_request(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Falta el token de sesión de Clerk",
        )

    parts = token.split(".")
    if len(parts) != 3:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de Clerk inválido",
        )

    try:
        header = json.loads(_b64url_decode(parts[0]))
        payload = json.loads(_b64url_decode(parts[1]))
        signature = _b64url_decode(parts[2])
        signing_input = f"{parts[0]}.{parts[1]}".encode("utf-8")

        if header.get("alg") != "RS256":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Algoritmo JWT no soportado",
            )

        jwks = await _fetch_jwks()
        keys = jwks.get("keys", [])
        kid = header.get("kid")
        key_data = next((key for key in keys if key.get("kid") == kid), None)
        if key_data is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No se encontró la clave pública de Clerk",
            )

        public_key = _jwk_to_public_key(key_data)
        public_key.verify(
            signature,
            signing_input,
            padding.PKCS1v15(),
            hashes.SHA256(),
        )

        now = int(time.time())
        if int(payload.get("exp", 0)) <= now:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="La sesión de Clerk expiró",
            )
        if int(payload.get("nbf", 0)) > now:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="La sesión de Clerk aún no es válida",
            )

        audience = _clerk_audience()
        if audience:
            token_aud = payload.get("aud")
            if isinstance(token_aud, list):
                aud_ok = audience in token_aud
            else:
                aud_ok = token_aud == audience
            if not aud_ok:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Audience de Clerk inválido",
                )

        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token de Clerk sin usuario asociado",
            )

        clerk_user = ClerkUser(
            user_id=str(user_id),
            session_id=str(payload.get("sid")) if payload.get("sid") else None,
            claims=payload,
        )
        set_active_user_id(clerk_user.user_id)
        return clerk_user
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"No se pudo verificar Clerk: {exc}",
        ) from exc


RequireClerkUser = Depends(verify_clerk_session)

