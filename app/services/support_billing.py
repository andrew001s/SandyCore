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
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

from fastapi import HTTPException

from app.core.config import config
from app.core.http import get_http_client
from app.services.email import send_email
from app.services.storage.supabase_store import _supabase_client

PRICE_CENTS = 300
CURRENCY = "USD"
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
KOFI_TEST_TRANSACTION_ID = "00000000-1111-2222-3333-444444444444"
KOFI_TEST_ITEMS = [
    {"direct_link_code": "1a2b3c4d5e", "variation_name": "Blue", "quantity": 1},
    {"direct_link_code": "a1b2c3d4e5", "variation_name": "Large", "quantity": 5},
]
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


def license_email(code: str) -> tuple[str, str]:
    safe_code = html.escape(code)
    html_body = f"""\
<!doctype html>
<html lang="es">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="color-scheme" content="dark">
    <title>Tu código de Sandy Studio Plus</title>
    <style>
      @media only screen and (max-width:520px) {{
        .email-gutter {{ padding:20px 10px !important; }}
        .email-shell {{ width:100% !important; }}
        .email-brand, .email-body-pad {{ padding-left:18px !important; padding-right:18px !important; }}
        .email-hero {{ padding-left:18px !important; padding-right:18px !important; }}
        .email-layout td {{ display:block !important; width:100% !important; box-sizing:border-box !important; text-align:left !important; }}
        .email-mascot {{ padding:0 0 8px !important; }}
        .email-mascot img {{ width:112px !important; }}
        .email-title {{ font-size:24px !important; }}
        .email-code {{ font-size:16px !important; letter-spacing:0.5px !important; }}
      }}
    </style>
  </head>
  <body style="margin:0;padding:0;background:#0E1022;color:#E9E6F5;font-family:'Atkinson Hyperlegible Next',Arial,Helvetica,sans-serif">
    <div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent">
      Tu código de un solo uso para activar Sandy Studio Plus ya está listo.
    </div>
          <table role="presentation" cellspacing="0" cellpadding="0" border="0" style="width:100%;table-layout:fixed;background:#0E1022">
      <tr>
        <td class="email-gutter" align="center" style="padding:32px 14px">
          <table class="email-shell" role="presentation" cellspacing="0" cellpadding="0" border="0" style="width:100%;max-width:600px;table-layout:fixed;background:#141733;border:1px solid #262A4D;border-radius:16px;overflow:hidden">
            <tr>
              <td class="email-brand" style="padding:22px 28px;border-bottom:1px solid #262A4D">
                <img src="cid:sandy-studio-logo" width="132" alt="Sandy Studio" style="display:block;width:132px;height:auto;border:0">
              </td>
            </tr>
            <tr>
              <td class="email-hero" style="padding:0 28px;background:#1B1E3D;border-bottom:1px solid #262A4D">
                <table class="email-layout" role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="width:100%;table-layout:fixed">
                  <tr>
                    <td style="padding:28px 0;vertical-align:middle">
                      <h1 class="email-title" style="margin:0;color:#E9E6F5;font-family:'Bricolage Grotesque','Atkinson Hyperlegible Next',Arial,sans-serif;font-size:28px;font-weight:700;line-height:1.2;letter-spacing:-0.5px">
                        Tu apoyo ya está listo
                      </h1>
                      <p style="margin:12px 0 0;color:#C5C2DF;font-size:15px;line-height:1.55">
                        Gracias por apoyar el desarrollo de Sandy Studio.
                      </p>
                    </td>
                    <td class="email-mascot" width="140" align="right" style="width:140px;padding:8px 0 0 10px;vertical-align:bottom">
                      <img src="cid:sandy-coffee-mascot" width="140" alt="Sandy te acompaña para agradecerte tu apoyo" style="display:block;width:140px;max-width:100%;height:auto;border:0">
                    </td>
                  </tr>
                </table>
              </td>
            </tr>
            <tr>
              <td class="email-body-pad" style="padding:28px">
                <p style="margin:0 0 22px;color:#C5C2DF;font-size:15px;line-height:1.6">
                  Usa este código dentro de tu cuenta para activar Sandy Studio Plus y retirar la marca de agua.
                </p>
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="width:100%;background:#0E1022;border:1px solid #51499A;border-radius:12px">
                  <tr>
                    <td align="center" style="padding:20px 12px">
                      <p style="margin:0 0 10px;color:#B9AFFf;font-size:12px;font-weight:700;letter-spacing:1px;text-transform:uppercase">
                        Código de activación
                      </p>
                      <p class="email-code" style="margin:0;color:#FFFFFF;font-family:'Courier New',Courier,monospace;font-size:19px;font-weight:700;letter-spacing:1px;line-height:1.5;overflow-wrap:anywhere;word-break:break-all">
                        {safe_code}
                      </p>
                    </td>
                  </tr>
                </table>
                <p style="margin:22px 0 18px;color:#C5C2DF;font-size:14px;line-height:1.6">
                  Inicia sesión, abre «Apoyar Sandy» y pega el código. Solo puede utilizarse una vez.
                </p>
                <table role="presentation" cellspacing="0" cellpadding="0" border="0">
                  <tr>
                    <td align="center" bgcolor="#8C7CFF" style="border-radius:8px">
                      <a href="https://sandystudio.net/home" style="display:inline-block;padding:12px 18px;color:#0E1022;font-size:14px;font-weight:700;line-height:1.2;text-decoration:none">
                        Abrir Sandy Studio
                      </a>
                    </td>
                  </tr>
                </table>
              </td>
            </tr>
            <tr>
              <td style="padding:16px 28px;border-top:1px solid #262A4D;color:#9A98B8;font-size:12px;line-height:1.55">
                Si no realizaste esta compra, responde a este correo para solicitar ayuda.
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>"""
    text_body = (
        "Sandy Studio\n\n"
        "Tu apoyo ya está listo.\n\n"
        f"Tu código de activación es: {code}\n\n"
        "Inicia sesión en Sandy Studio, abre «Apoyar Sandy» y pega el código. "
        "Solo puede utilizarse una vez.\n\n"
        "Abre Sandy Studio: https://sandystudio.net/home\n\n"
        "Si no realizaste esta compra, responde a este correo para solicitar ayuda."
    )
    return html_body, text_body


def license_email_attachments() -> list[dict[str, str]]:
    asset_dir = Path(__file__).resolve().parents[1] / "assets" / "email"
    assets = (
        ("sandy-logo-dark.png", "sandy-studio-logo"),
        ("sandy-coffee-still.png", "sandy-coffee-mascot"),
    )
    return [
        {
            "filename": filename,
            "content": base64.b64encode((asset_dir / filename).read_bytes()).decode(
                "ascii"
            ),
            "content_type": "image/png",
            "content_id": content_id,
        }
        for filename, content_id in assets
    ]


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


def verify_kofi_token(payload: dict) -> None:
    token = payload.get("verification_token")
    if not isinstance(token, str) or not hmac.compare_digest(
        token.encode(), config.KOFI_VERIFICATION_TOKEN.encode()
    ):
        raise HTTPException(401, "Not authorized")


def validate_webhook(payload: dict) -> dict | None:
    require_configured()
    verify_kofi_token(payload)
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


async def issue_and_send_license(transaction_id: str, recipient: str) -> bool:
    code = license_code()
    issued = await rpc(
        "support_issue_license_code",
        p_transaction_id=transaction_id,
        p_code_hash=license_code_hash(code),
    )
    if not isinstance(issued, dict) or "send_required" not in issued:
        raise HTTPException(
            503,
            "La base de datos no tiene aplicada la migración de envío de códigos por correo.",
        )
    if not issued["send_required"]:
        return False
    html_body, text_body = license_email(code)
    await send_email(
        [recipient],
        "Tu acceso a Sandy Studio Plus está listo",
        html_body,
        text=text_body,
        attachments=license_email_attachments(),
    )
    await rpc("support_mark_license_email_sent", p_transaction_id=transaction_id)
    return True


async def webhook(payload: dict) -> dict:
    payment = validate_webhook(payload)
    if payment is None:
        return {"accepted": True, "eligible": False}
    await rpc("support_record_payment", p_payment=payment)
    if payment["state"] == "confirmed":
        await issue_and_send_license(
            payment["transaction_id"], payload["email"].strip().casefold()
        )
    return {"accepted": True}


def kofi_test_endpoint_enabled() -> bool:
    return bool(
        getattr(config, "KOFI_TEST_ENDPOINT_ENABLED", False)
        and getattr(config, "SANDY_ENVIRONMENT", "production")
        in {"development", "test", "staging"}
        and configured()
        and bool(getattr(config, "RESEND_API_KEY", ""))
        and bool(getattr(config, "RESEND_FROM_NAME", "").strip())
        and re.fullmatch(
            r"[^\s@]+@[^\s@]+\.[^\s@]+",
            getattr(config, "RESEND_FROM_EMAIL", "").strip(),
        )
        and re.fullmatch(
            r"[^\s@]+@[^\s@]+\.[^\s@]+", getattr(config, "KOFI_TEST_EMAIL", "")
        )
    )


def require_kofi_test_endpoint() -> None:
    if not kofi_test_endpoint_enabled():
        raise HTTPException(404, "Not found")


def is_kofi_shop_test_fixture(payload: dict) -> bool:
    parsed_url = urlsplit(str(payload.get("url", "")))
    items = payload.get("shop_items")
    message_id = payload.get("message_id")
    timestamp = payload.get("timestamp")
    try:
        sent_at = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
    except ValueError:
        return False
    return bool(
        isinstance(message_id, str)
        and re.fullmatch(r"[A-Za-z0-9_-]{8,128}", message_id)
        and sent_at.tzinfo is not None
        and payload.get("is_public") is True
        and payload.get("type") == "Shop Order"
        and payload.get("from_name") == "Jo Example"
        and payload.get("email") == "jo.example@example.com"
        and payload.get("kofi_transaction_id") == KOFI_TEST_TRANSACTION_ID
        and parsed_url.scheme == "https"
        and parsed_url.netloc == "ko-fi.com"
        and parsed_url.path == "/Home/CoffeeShop"
        and parse_qs(parsed_url.query).get("txid") == [KOFI_TEST_TRANSACTION_ID]
        and payload.get("amount") == "27.95"
        and payload.get("currency") == CURRENCY
        and payload.get("is_subscription_payment") is False
        and payload.get("is_first_subscription_payment") is False
        and payload.get("message") is None
        and items == KOFI_TEST_ITEMS
    )


async def test_webhook(payload: dict) -> dict:
    require_kofi_test_endpoint()
    verify_kofi_token(payload)
    if not is_kofi_shop_test_fixture(payload):
        raise HTTPException(400, "Expected Ko-fi's Shop Order test fixture")
    limit_requests("kofi-shop-test", 3)

    fixture_digest = hashlib.sha256(
        f"{payload['message_id']}:{KOFI_TEST_TRANSACTION_ID}:{payload['timestamp']}".encode()
    ).hexdigest()
    transaction_id = f"test-{fixture_digest[:40]}"
    payment = {
        "transaction_id": transaction_id,
        "message_id": f"test-{fixture_digest[40:64]}",
        "email_hash": private_hash(config.KOFI_TEST_EMAIL),
        "amount_cents": PRICE_CENTS,
        "currency": CURRENCY,
        "product_code": config.KOFI_WATERMARK_PRODUCT_CODE,
        "state": "confirmed",
        "review_reason": None,
        "paid_at": datetime.now(timezone.utc).isoformat(),
        "is_test": True,
    }
    await rpc("support_record_payment", p_payment=payment)
    email_submitted = await issue_and_send_license(
        transaction_id, config.KOFI_TEST_EMAIL.strip().casefold()
    )
    return {"accepted": True, "test": True, "email_submitted": email_submitted}


def support_test_code_enabled() -> bool:
    test_code = getattr(config, "SUPPORT_TEST_REDEEM_CODE", "").strip().upper()
    return bool(
        getattr(config, "SUPPORT_TEST_REDEEM_ENABLED", False)
        and getattr(config, "SANDY_ENVIRONMENT", "production")
        in {"development", "test", "staging"}
        and re.fullmatch(r"SANDY(?:-[A-Z0-9]{4}){4}", test_code)
    )


async def redeem_test_code(user) -> dict:
    require_session(user)
    if not support_test_code_enabled():
        raise HTTPException(404, "El canje de prueba no está disponible.")
    limit_requests(f"support-test-code:{user.user_id}", 3)
    addresses = await verified_emails(user.user_id)
    if not addresses:
        raise HTTPException(
            409,
            "Verifica un correo en tu cuenta de Sandy Studio antes de activar el código.",
        )

    current = await status(user)
    if current.get("watermark_free"):
        return current

    digest = hashlib.sha256(
        f"support-test-code:{user.user_id}".encode()
    ).hexdigest()
    transaction_id = f"test-code-{digest[:40]}"
    payment = {
        "transaction_id": transaction_id,
        "message_id": f"test-code-message-{digest[40:56]}",
        "email_hash": private_hash(addresses[0]),
        "amount_cents": PRICE_CENTS,
        "currency": CURRENCY,
        "product_code": config.KOFI_WATERMARK_PRODUCT_CODE,
        "state": "confirmed",
        "review_reason": None,
        "paid_at": datetime.now(timezone.utc).isoformat(),
        "is_test": True,
    }
    await rpc("support_record_payment", p_payment=payment)
    return await status(user, transaction_id)


async def redeem_license_code(user, code: str) -> dict:
    require_configured()
    require_session(user)
    normalized = code.strip().upper()
    if not re.fullmatch(r"SANDY(?:-[A-Z0-9]{4}){4}", normalized):
        raise HTTPException(400, "El código de Sandy Studio no es válido.")
    limit_requests(f"redeem:{user.user_id}", 6)
    expected_test_code = getattr(config, "SUPPORT_TEST_REDEEM_CODE", "").strip().upper()
    if support_test_code_enabled() and hmac.compare_digest(
        normalized.encode(), expected_test_code.encode()
    ):
        return await redeem_test_code(user)
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


def require_overlay_configured() -> None:
    secret = getattr(config, "SUPPORT_OVERLAY_SECRET", "")
    if len(secret) < 32 or secret in (
        config.SUPPORT_BILLING_SECRET,
        config.CLERK_SECRET_KEY,
        config.KOFI_VERIFICATION_TOKEN,
    ):
        raise HTTPException(503, "No se pudo preparar el enlace privado de OBS.")


async def overlay_key(user, rotate: bool = False) -> dict:
    require_overlay_configured()
    require_session(user)
    limit_requests(f"overlay-key:{user.user_id}", 12)
    key = await rpc("support_overlay_key", p_user_id=user.user_id, p_rotate=rotate)
    viewer_id, revision = key["viewer_id"], key["revision"]
    return {"token": f"{viewer_id}.{revision}.{overlay_signature(viewer_id, revision)}"}


async def overlay_status(token: str) -> dict:
    require_overlay_configured()
    match = re.fullmatch(
        r"([a-f0-9-]{36})\.([1-9][0-9]{0,8})\.([A-Za-z0-9_-]{43})", token
    )
    if not match or not hmac.compare_digest(
        match[3], overlay_signature(match[1], int(match[2]))
    ):
        raise HTTPException(401, "Invalid overlay credential")
    limit_requests(f"overlay-status:{match[1]}", 120)
    result = await rpc(
        "support_overlay_status", p_viewer_id=match[1], p_revision=int(match[2])
    )
    return {"watermark_free": configured() and result.get("watermark_free") is True}


async def overlay_stream_subject(token: str) -> str:
    """Validate a read-only OBS capability and return its isolated relay subject."""
    require_overlay_configured()
    match = re.fullmatch(
        r"([a-f0-9-]{36})\.([1-9][0-9]{0,8})\.([A-Za-z0-9_-]{43})", token
    )
    if not match or not hmac.compare_digest(
        match[3], overlay_signature(match[1], int(match[2]))
    ):
        raise HTTPException(401, "Invalid overlay credential")
    result = await rpc(
        "support_overlay_status", p_viewer_id=match[1], p_revision=int(match[2])
    )
    if result.get("valid") is False:
        raise HTTPException(401, "Revoked overlay credential")
    return match[1]
