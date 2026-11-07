import asyncio
import base64
import html
import hashlib
import hmac
import re
import secrets
import time
from collections import OrderedDict, deque
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from fastapi import HTTPException

from app.core.config import config
from app.core.http import get_http_client
from app.services.email import send_email
from app.services.storage.supabase_store import _supabase_client

PRICE_CENTS = 300
CURRENCY = "USD"
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_REQUEST_WINDOWS = OrderedDict()


def limit_requests(key: str, maximum: int) -> None:
    now = time.monotonic()
    times = _REQUEST_WINDOWS.setdefault(key, deque())
    while times and times[0] <= now - 60:
        times.popleft()
    if len(times) >= maximum:
        raise HTTPException(
            429, "Demasiados intentos. Espera un minuto.", headers={"Retry-After": "60"}
        )
    times.append(now)
    _REQUEST_WINDOWS.move_to_end(key)
    if len(_REQUEST_WINDOWS) > 4096:
        _REQUEST_WINDOWS.popitem(last=False)


def configured() -> bool:
    return bool(
        getattr(config, "KOFI_WATERMARK_ENABLED", False)
        and re.fullmatch(
            r"[A-Za-z0-9_-]{6,80}", getattr(config, "KOFI_WATERMARK_PRODUCT_CODE", "")
        )
        and len(getattr(config, "KOFI_VERIFICATION_TOKEN", "")) >= 16
        and len(getattr(config, "SUPPORT_BILLING_SECRET", "")) >= 32
        and len(getattr(config, "SUPPORT_OVERLAY_SECRET", "")) >= 32
        and config.SUPPORT_OVERLAY_SECRET
        not in (
            config.SUPPORT_BILLING_SECRET,
            config.CLERK_SECRET_KEY,
            config.KOFI_VERIFICATION_TOKEN,
        )
        and config.CLERK_SECRET_KEY
        and config.SUPPORT_BILLING_SECRET
        not in (config.CLERK_SECRET_KEY, config.KOFI_VERIFICATION_TOKEN)
    )


def require_configured() -> None:
    if not configured():
        raise HTTPException(503, "La compra sin marca todavía no está disponible.")


def private_hash(email: str) -> str:
    return hmac.new(
        config.SUPPORT_BILLING_SECRET.encode(),
        b"support-email:" + email.strip().casefold().encode(),
        hashlib.sha256,
    ).hexdigest()


def license_code() -> str:
    parts = ["".join(secrets.choice(CODE_ALPHABET) for _ in range(4)) for _ in range(4)]
    return "SANDY-" + "-".join(parts)


def license_code_hash(code: str) -> str:
    return private_hash("license:" + code.strip().upper())


async def rpc(name: str, **params: Any) -> dict:
    try:
        response = await asyncio.to_thread(
            lambda: _supabase_client().rpc(name, params).execute()
        )
        if not isinstance(response.data, dict):
            raise ValueError("Unexpected payment store response")
        return response.data
    except Exception as exc:
        raise HTTPException(
            503, "No se pudo consultar el estado de la compra. Inténtalo de nuevo."
        ) from exc


async def verified_emails(user_id: str) -> list[str]:
    try:
        response = await get_http_client().get(
            f"https://api.clerk.com/v1/users/{user_id}",
            headers={"Authorization": f"Bearer {config.CLERK_SECRET_KEY}"},
            timeout=10.0,
        )
        response.raise_for_status()
        user = response.json()
        if user.get("id") != user_id:
            raise ValueError("Account mismatch")
        addresses = [
            entry
            for entry in user.get("email_addresses", [])
            if entry.get("verification", {}).get("status") == "verified"
        ]
        addresses.sort(
            key=lambda entry: entry.get("id") != user.get("primary_email_address_id")
        )
        return [
            entry["email_address"].strip().casefold()
            for entry in addresses
            if isinstance(entry.get("email_address"), str)
        ]
    except Exception as exc:
        raise HTTPException(
            503, "No se pudo verificar el correo de tu cuenta. Inténtalo de nuevo."
        ) from exc


def require_session(user) -> None:
    if not user.session_id:
        raise HTTPException(
            401, "Inicia sesión en Sandy Studio para gestionar tu compra."
        )


async def status(user, receipt_id: str | None = None) -> dict:
    require_session(user)
    limit_requests(f"status:{user.user_id}", 120)
    if receipt_id:
        limit_requests(f"restore:{user.user_id}", 6)
    base = {
        "available": configured(),
        "amount_cents": PRICE_CENTS,
        "currency": CURRENCY,
    }
    if not base["available"]:
        return {**base, "watermark_free": False, "state": "unavailable"}
    current = await rpc("support_status", p_user_id=user.user_id)
    if receipt_id or current.get("state") in ("pending", "expired"):
        addresses = await verified_emails(user.user_id)
        if not addresses:
            raise HTTPException(
                409,
                "Verifica un correo en tu cuenta de Sandy Studio antes de vincular la compra.",
            )
        current = await rpc(
            "support_status",
            p_user_id=user.user_id,
            p_email_hashes=[private_hash(email) for email in addresses],
            p_receipt_id=receipt_id,
        )
        if receipt_id and not current.get("watermark_free"):
            raise HTTPException(
                409,
                "Todavía no se pudo vincular ese recibo. Comprueba el identificador y verifica en tu cuenta el correo usado en Ko-fi. No vuelvas a pagar.",
            )
    return {**base, **current}


async def checkout(user) -> dict:
    require_configured()
    require_session(user)
    limit_requests(f"checkout:{user.user_id}", 6)
    current = await status(user)
    if current.get("watermark_free"):
        return {**current, "already_owned": True}
    addresses = await verified_emails(user.user_id)
    checkout_hash = (
        private_hash(addresses[0])
        if addresses
        else private_hash("checkout-user:" + user.user_id)
    )
    await rpc(
        "support_start_checkout",
        p_user_id=user.user_id,
        p_email_hash=checkout_hash,
    )
    return {
        "checkout_url": f"https://ko-fi.com/s/{config.KOFI_WATERMARK_PRODUCT_CODE}",
        "amount_cents": PRICE_CENTS,
        "currency": CURRENCY,
        "state": "pending",
    }


def validate_webhook(payload: dict) -> dict | None:
    require_configured()
    token = payload.get("verification_token")
    if not isinstance(token, str) or not hmac.compare_digest(
        token.encode(), config.KOFI_VERIFICATION_TOKEN.encode()
    ):
        raise HTTPException(401, "Not authorized")
    if payload.get("type") != "Shop Order":
        return None
    items = payload.get("shop_items")
    if not isinstance(items, list) or not any(
        isinstance(item, dict)
        and item.get("direct_link_code") == config.KOFI_WATERMARK_PRODUCT_CODE
        for item in items
    ):
        return None
    identifiers = [payload.get("kofi_transaction_id"), payload.get("message_id")]
    if any(
        not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{8,128}", value)
        for value in identifiers
    ):
        raise HTTPException(400, "Invalid payment identifiers")
    email = payload.get("email")
    if (
        not isinstance(email, str)
        or len(email) > 320
        or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email)
    ):
        raise HTTPException(400, "Invalid payment email")
    try:
        amount = Decimal(str(payload.get("amount")))
        if (
            not amount.is_finite()
            or amount < 0
            or amount > 10000
            or amount != amount.quantize(Decimal("0.01"))
        ):
            raise ValueError("Invalid amount")
        cents = int(amount * 100)
        paid_at = datetime.fromisoformat(
            str(payload.get("timestamp")).replace("Z", "+00:00")
        )
        if paid_at.tzinfo is None or paid_at > datetime.now(timezone.utc) + timedelta(
            minutes=5
        ):
            raise ValueError("Invalid time")
    except (ValueError, InvalidOperation, OverflowError):
        raise HTTPException(400, "Invalid payment amount or time") from None
    valid = (
        len(items) == 1
        and type(items[0].get("quantity")) is int
        and items[0]["quantity"] == 1
        and payload.get("currency") == CURRENCY
        and cents >= PRICE_CENTS
        and payload.get("is_subscription_payment", False) is False
    )
    return {
        "transaction_id": identifiers[0],
        "message_id": identifiers[1],
        "email_hash": private_hash(email),
        "amount_cents": cents,
        "currency": str(payload.get("currency", ""))[:8],
        "product_code": config.KOFI_WATERMARK_PRODUCT_CODE,
        "state": "confirmed" if valid else "review",
        "review_reason": None if valid else "unexpected_amount_currency_or_items",
        "paid_at": paid_at.isoformat(),
    }


async def webhook(payload: dict) -> dict:
    payment = validate_webhook(payload)
    if payment is None:
        return {"accepted": True, "eligible": False}
    recorded = await rpc("support_record_payment", p_payment=payment)
    if payment["state"] == "confirmed" and recorded.get("recorded"):
        email = payload["email"].strip().casefold()
        code = license_code()
        issued = await rpc(
            "support_issue_license_code",
            p_transaction_id=payment["transaction_id"],
            p_code_hash=license_code_hash(code),
        )
        if issued.get("created"):
            safe_code = html.escape(code)
            await send_email(
                [email],
                "Tu código de Sandy Studio Plus",
                f"""
                <p>Gracias por apoyar Sandy Studio.</p>
                <p>Tu código para retirar la marca de agua es:</p>
                <p style="font-size:20px;font-weight:700;letter-spacing:2px">{safe_code}</p>
                <p>Inicia sesión en Sandy Studio, pulsa «Apoyar Sandy» e introduce este código.</p>
                """,
                text=(
                    "Gracias por apoyar Sandy Studio.\n\n"
                    f"Tu código de Sandy Studio Plus es: {code}\n\n"
                    "Inicia sesión en Sandy Studio y canjea el código desde «Apoyar Sandy»."
                ),
            )
    return {"accepted": True}


async def redeem_license_code(user, code: str) -> dict:
    require_configured()
    require_session(user)
    normalized = code.strip().upper()
    if not re.fullmatch(r"SANDY(?:-[A-Z0-9]{4}){4}", normalized):
        raise HTTPException(400, "El código de Sandy Studio no es válido.")
    result = await rpc(
        "support_redeem_license_code",
        p_user_id=user.user_id,
        p_code_hash=license_code_hash(normalized),
    )
    if result.get("redeemed") is not True:
        raise HTTPException(409, "El código no existe o ya fue utilizado.")
    return await status(user)


def overlay_signature(viewer_id: str, revision: int) -> str:
    digest = hmac.new(
        config.SUPPORT_OVERLAY_SECRET.encode(),
        f"support-overlay:{viewer_id}:{revision}".encode(),
        hashlib.sha256,
    ).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


async def overlay_key(user, rotate: bool = False) -> dict:
    require_configured()
    require_session(user)
    limit_requests(f"overlay-key:{user.user_id}", 12)
    key = await rpc("support_overlay_key", p_user_id=user.user_id, p_rotate=rotate)
    viewer_id, revision = key["viewer_id"], key["revision"]
    return {"token": f"{viewer_id}.{revision}.{overlay_signature(viewer_id, revision)}"}


async def overlay_status(token: str) -> dict:
    require_configured()
    match = re.fullmatch(
        r"([a-f0-9-]{36})\.([1-9][0-9]{0,8})\.([A-Za-z0-9_-]{43})", token
    )
    if not match or not hmac.compare_digest(
        match[3], overlay_signature(match[1], int(match[2]))
    ):
        raise HTTPException(401, "Invalid overlay credential")
    limit_requests(f"overlay-status:{match[1]}", 120)
    return await rpc(
        "support_overlay_status", p_viewer_id=match[1], p_revision=int(match[2])
    )
