from __future__ import annotations

from functools import lru_cache
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import config

_SECRET_PREFIX = "enc:v1:"


@lru_cache(maxsize=1)
def _fernet() -> Fernet | None:
    key = config.DATA_ENCRYPTION_KEY
    if not key:
        return None
    return Fernet(key.encode("utf-8"))


def is_encrypted_value(value: str | None) -> bool:
    return isinstance(value, str) and value.startswith(_SECRET_PREFIX)


def encrypt_secret(value: str | None) -> str | None:
    if value is None or value == "":
        return value
    if is_encrypted_value(value):
        return value

    fernet = _fernet()
    if fernet is None:
        raise RuntimeError(
            "Falta DATA_ENCRYPTION_KEY para cifrar secretos en reposo"
        )
    token = fernet.encrypt(value.encode("utf-8")).decode("utf-8")
    return f"{_SECRET_PREFIX}{token}"


def decrypt_secret(value: str | None) -> str | None:
    if value is None or value == "":
        return value
    if not is_encrypted_value(value):
        return value

    fernet = _fernet()
    if fernet is None:
        raise RuntimeError(
            "No se puede descifrar un secreto cifrado sin DATA_ENCRYPTION_KEY"
        )

    encrypted = value[len(_SECRET_PREFIX) :]
    try:
        return fernet.decrypt(encrypted.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise RuntimeError("El secreto cifrado no se pudo descifrar") from exc


def encrypt_secret_map(payload: dict[str, Any], keys: set[str]) -> dict[str, Any]:
    encrypted = dict(payload)
    for key in keys:
        if key in encrypted and isinstance(encrypted[key], str):
            encrypted[key] = encrypt_secret(encrypted[key])
    return encrypted


def decrypt_secret_map(payload: dict[str, Any], keys: set[str]) -> dict[str, Any]:
    decrypted = dict(payload)
    for key in keys:
        if key in decrypted and isinstance(decrypted[key], str):
            decrypted[key] = decrypt_secret(decrypted[key])
    return decrypted
