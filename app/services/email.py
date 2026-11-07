from __future__ import annotations

import re
from collections.abc import Sequence

from fastapi import HTTPException

from app.core.config import config
from app.core.http import get_http_client

RESEND_URL = "https://api.resend.com/emails"
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def sender() -> str:
    email = config.RESEND_FROM_EMAIL.strip()
    name = config.RESEND_FROM_NAME.strip()
    if not EMAIL_PATTERN.fullmatch(email) or not name:
        raise HTTPException(503, "El remitente de correo no está configurado correctamente.")
    return f"{name} <{email}>"


async def send_email(
    recipients: Sequence[str],
    subject: str,
    html: str,
    *,
    text: str | None = None,
) -> str:
    if not config.RESEND_API_KEY:
        raise HTTPException(503, "El servicio de correo no está configurado.")
    if not recipients or any(not EMAIL_PATTERN.fullmatch(value.strip()) for value in recipients):
        raise HTTPException(400, "Destinatario de correo inválido.")
    if not subject.strip() or not html.strip():
        raise HTTPException(400, "El correo necesita asunto y contenido.")
    payload: dict[str, object] = {
        "from": sender(),
        "to": [value.strip() for value in recipients],
        "subject": subject.strip(),
        "html": html,
    }
    if text is not None:
        payload["text"] = text
    try:
        response = await get_http_client().post(
            RESEND_URL,
            headers={
                "Authorization": f"Bearer {config.RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=15.0,
        )
        response.raise_for_status()
        result = response.json()
        message_id = result.get("id") if isinstance(result, dict) else None
        if not isinstance(message_id, str) or not message_id:
            raise ValueError("Missing Resend message id")
        return message_id
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(503, "No se pudo enviar el correo. Inténtalo de nuevo.") from exc
