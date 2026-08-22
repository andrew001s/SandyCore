from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi.responses import JSONResponse

from app.adapters.kick_services import KickService
from app.core.use_cases.get_kick_profile import GetKickProfileUseCase
from app.core.use_cases.get_kick_tokens_use_case import GetKickTokensUseCase
from app.core.use_cases.kick_auth_use_case import KickAuthUseCase
from app.core.use_cases.logout_kick_use_case import LogoutKickUseCase
from app.core.use_cases.save_kick_tokens_use_case import SaveKickTokensUseCase
from app.core.use_cases.start_kick_services_use_case import StartKickServicesCase
from app.core.use_cases.stop_kick_services_use_case import StopKickServicesUseCase
from app.core.security.clerk import ClerkUser, verify_clerk_session
from app.models.kick_auth_model import KickAuth
from app.models.tokens_model import TokenModel
from app.services.kick.lifecycle import get_service_status
from app.domain.errors import error_payload

router = APIRouter(prefix="/kick", tags=["Kick"])
use_case_auth = KickAuthUseCase(KickService())
use_case_start = StartKickServicesCase(KickService())
use_case_stop = StopKickServicesUseCase(KickService())
use_case_logout = LogoutKickUseCase(KickService())
use_case_tokens = GetKickTokensUseCase(KickService())
use_case_save_tokens = SaveKickTokensUseCase(KickService())


def _is_missing_tokens_error(error: Exception) -> bool:
    message = str(error)
    return (
        "No existe una sesión de Kick autenticada para este usuario" in message
        or "No existe una sesión de bot autenticada para este usuario" in message
        or "No existen tokens de Kick guardados para este usuario" in message
    )


@router.post("/auth")
async def authenticate_kick_user(
    message: KickAuth, current_user: ClerkUser = Depends(verify_clerk_session)
):
    try:
        await use_case_auth.execute(
            current_user.user_id,
            message.token,
            message.refresh_token,
            message.bot,
        )
        return JSONResponse(status_code=200, content={"message": "Autenticación exitosa"})
    except HTTPException:
        raise
    except Exception as e:
        print(f"[KICK AUTH ERROR] {repr(e)}")
        status_code, body = error_payload(e, provider="kick")
        return JSONResponse(status_code=status_code, content=body)


@router.get("/start")
async def start_services(
    bot: bool = False, current_user: ClerkUser = Depends(verify_clerk_session)
):
    try:
        await use_case_start.execute(current_user.user_id, bot)
        return JSONResponse(status_code=200, content={"message": "Servicios iniciados"})
    except Exception as e:
        status_code, body = error_payload(e, provider="kick")
        return JSONResponse(status_code=status_code, content=body)


@router.get("/stop")
async def stop_services(
    bot: bool = False, current_user: ClerkUser = Depends(verify_clerk_session)
):
    try:
        await use_case_stop.execute(current_user.user_id)
        return JSONResponse(status_code=200, content={"message": "Automatización pausada"})
    except Exception as e:
        status_code, body = error_payload(e, provider="kick")
        return JSONResponse(status_code=status_code, content=body)


@router.delete("/auth")
async def logout_kick(current_user: ClerkUser = Depends(verify_clerk_session)):
    try:
        await use_case_logout.execute(current_user.user_id)
        return JSONResponse(status_code=200, content={"message": "Sesión de Kick cerrada"})
    except Exception as e:
        status_code, body = error_payload(e, provider="kick")
        return JSONResponse(status_code=status_code, content=body)


@router.get("/service-status")
async def service_status(
    bot: bool = False, current_user: ClerkUser = Depends(verify_clerk_session)
):
    try:
        status = await get_service_status(current_user.user_id)
        return JSONResponse(status_code=200, content={"service": status})
    except Exception as e:
        status_code, body = error_payload(e, provider="kick")
        return JSONResponse(status_code=status_code, content=body)


@router.get("/profile")
async def get_profile(
    bot: bool = False, current_user: ClerkUser = Depends(verify_clerk_session)
):
    try:
        use_case = GetKickProfileUseCase(KickService())
        user = await use_case.execute(current_user.user_id, bot)
        return JSONResponse(status_code=200, content={"profile": user})
    except Exception as e:
        if _is_missing_tokens_error(e):
            return JSONResponse(
                status_code=200,
                content={
                    "profile": None,
                    "authenticated": False,
                    "message": "No hay tokens de Kick guardados para este usuario",
                },
            )
        status_code, body = error_payload(e, provider="kick")
        return JSONResponse(status_code=status_code, content=body)


@router.get("/tokens")
async def get_tokens(
    bot: bool = False, current_user: ClerkUser = Depends(verify_clerk_session)
):
    try:
        tokens = await use_case_tokens.execute(current_user.user_id, bot)
        return JSONResponse(status_code=200, content={"tokens": tokens})
    except Exception as e:
        status_code, body = error_payload(e, provider="kick")
        return JSONResponse(status_code=status_code, content=body)


@router.put("/tokens")
async def save_tokens(
    tokens: TokenModel, bot: bool = False, current_user: ClerkUser = Depends(verify_clerk_session)
):
    try:
        await use_case_save_tokens.execute(
            current_user.user_id, bot, tokens.token, tokens.refresh_token
        )
        return JSONResponse(status_code=200, content={"message": "Tokens guardados exitosamente"})
    except Exception as e:
        status_code, body = error_payload(e, provider="kick")
        return JSONResponse(status_code=status_code, content=body)
