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
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import config
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
    cookie_token = request.cookies.get("__session")
    if cookie_token:
        return cookie_token
    return None


_clerk_bearer_scheme = HTTPBearer(auto_error=False)


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


async def _verify_clerk_api_key(api_key: str) -> ClerkUser:
    if not config.CLERK_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Falta CLERK_SECRET_KEY para verificar API keys de Clerk",
        )

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                "https://api.clerk.com/v1/api_keys/verify",
                headers={
                    "Authorization": f"Bearer {config.CLERK_SECRET_KEY}",
                    "Content-Type": "application/json",
                },
                json={"secret": api_key},
            )
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Clave API de Clerk inválida o expirada",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"No se pudo verificar la API key de Clerk: {exc}",
        ) from exc

    subject = payload.get("subject")
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="La API key de Clerk no tiene sujeto asociado",
        )

    clerk_user = ClerkUser(
        user_id=str(subject),
        session_id=None,
        claims=payload,
    )
    set_active_user_id(clerk_user.user_id)
    return clerk_user


def _looks_like_session_jwt(token: str) -> bool:
    return token.count(".") == 2


async def _verify_clerk_session_token(token: str) -> ClerkUser:
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


async def verify_clerk_session(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_clerk_bearer_scheme),
) -> ClerkUser:
    token = credentials.credentials if credentials else None
    if not token:
        token = _load_token_from_request(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Falta el token de sesión o la API key de Clerk",
        )

    if token.startswith("ak_") or not _looks_like_session_jwt(token):
        return await _verify_clerk_api_key(token)
    return await _verify_clerk_session_token(token)


RequireClerkUser = Depends(verify_clerk_session)
