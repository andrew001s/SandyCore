import json
from urllib.parse import parse_qs

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from app.core.security.clerk import ClerkUser, verify_clerk_session
from app.core.security.stream_token import create_stream_token
from app.services import support_billing as billing

router = APIRouter(prefix="/support", tags=["Support purchases"])


class EmptyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RestoreRequest(EmptyRequest):
    receipt_id: str = Field(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")


class LicenseCodeRequest(EmptyRequest):
    code: str = Field(min_length=11, max_length=27)


class OverlayKeyRequest(EmptyRequest):
    rotate: bool = False


class OverlayStatusRequest(EmptyRequest):
    token: str = Field(min_length=70, max_length=200)


class OverlayRealtimeRequest(OverlayStatusRequest):
    role: str = Field(pattern=r"^(publisher|viewer)$")


def private_response(payload: dict) -> JSONResponse:
    return JSONResponse(
        payload, headers={"Cache-Control": "no-store, private", "Pragma": "no-cache"}
    )


@router.get("/status")
async def get_status(user: ClerkUser = Depends(verify_clerk_session)):
    return private_response(await billing.status(user))


@router.post("/checkout")
async def start_checkout(
    payload: EmptyRequest, user: ClerkUser = Depends(verify_clerk_session)
):
    return private_response(await billing.checkout(user))


@router.post("/restore")
async def restore_purchase(
    payload: RestoreRequest, user: ClerkUser = Depends(verify_clerk_session)
):
    return private_response(await billing.status(user, payload.receipt_id))


@router.post("/redeem")
async def redeem_license(
    payload: LicenseCodeRequest, user: ClerkUser = Depends(verify_clerk_session)
):
    return private_response(await billing.redeem_license_code(user, payload.code))


@router.post("/overlay-key")
async def get_overlay_key(
    payload: OverlayKeyRequest, user: ClerkUser = Depends(verify_clerk_session)
):
    return private_response(await billing.overlay_key(user, payload.rotate))


@router.post("/overlay-status")
async def get_overlay_status(request: Request):
    body = await limited_body(request, 2048)
    try:
        payload = OverlayStatusRequest.model_validate_json(body)
    except ValueError:
        raise HTTPException(400, "Invalid overlay request") from None
    return private_response(await billing.overlay_status(payload.token))


@router.post("/overlay-stream-token")
async def get_overlay_stream_token(request: Request):
    body = await limited_body(request, 2048)
    try:
        payload = OverlayRealtimeRequest.model_validate_json(body)
    except ValueError:
        raise HTTPException(400, "Invalid overlay request") from None
    subject = await billing.overlay_stream_subject(payload.token)
    return private_response({"token": create_stream_token(subject, role=payload.role)})


async def limited_body(request: Request, maximum: int) -> bytes:
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > maximum:
            raise HTTPException(413, "Payload too large")
    return bytes(body)


@router.post(
    "/test/ko-fi-webhook",
    summary="Probar el envío de Sandy Plus desde Ko-fi",
    description=(
        "Endpoint de staging para el botón «Send shop order test» de Ko-fi. "
        "Envía el código a KOFI_TEST_EMAIL y registra una compra sintética. "
        "Requiere SANDY_ENVIRONMENT=staging, KOFI_TEST_ENDPOINT_ENABLED=true "
        "y configuración de Ko-fi, Supabase y Resend. En producción responde 404. "
        "Ko-fi envía el campo data como JSON serializado dentro de un formulario."
    ),
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/x-www-form-urlencoded": {
                    "schema": {
                        "type": "object",
                        "required": ["data"],
                        "properties": {
                            "data": {
                                "type": "string",
                                "description": "Payload JSON serializado de la prueba Shop Order de Ko-fi.",
                            }
                        },
                    }
                }
            },
        },
        "responses": {
            "200": {"description": "Código de prueba enviado por Resend."},
            "400": {"description": "El payload no coincide con el fixture de Shop Order."},
            "401": {"description": "Token de verificación de Ko-fi inválido."},
            "404": {"description": "Endpoint desactivado o entorno no apto para pruebas."},
            "413": {"description": "Payload demasiado grande."},
            "415": {"description": "Se requiere application/x-www-form-urlencoded."},
        },
    },
)
async def receive_kofi_test_webhook(request: Request):
    billing.require_kofi_test_endpoint()
    payload = await read_kofi_payload(request)
    return private_response(await billing.test_webhook(payload))


async def read_kofi_payload(request: Request) -> dict:
    body = await limited_body(request, 65536)
    if (
        request.headers.get("content-type", "").split(";")[0].strip().lower()
        != "application/x-www-form-urlencoded"
    ):
        raise HTTPException(415, "Expected a form-encoded Ko-fi notification")
    try:
        values = parse_qs(body.decode("utf-8"), strict_parsing=True, max_num_fields=4)
        if set(values) != {"data"} or len(values["data"]) != 1:
            raise ValueError("Invalid data")
        payload = json.loads(values["data"][0])
        if not isinstance(payload, dict):
            raise ValueError("Invalid data")
        return payload
    except (ValueError, UnicodeError, KeyError):
        raise HTTPException(400, "Invalid notification") from None


@router.post("/ko-fi/webhook", include_in_schema=False)
async def receive_legacy_webhook(request: Request):
    payload = await read_kofi_payload(request)
    return private_response(await billing.webhook(payload))
