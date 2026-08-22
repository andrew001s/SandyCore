from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse, JSONResponse

from app.adapters.youtube_services import YouTubeService
from app.core.security.clerk import ClerkUser, verify_clerk_session
from app.domain.errors import error_payload
from app.models.youtube_models import (
    YouTubeBroadcastUpdateModel,
    YouTubeChatMessageModel,
    YouTubeBroadcastTransitionModel,
)

router = APIRouter(prefix="/youtube", tags=["YouTube"])
use_case = YouTubeService()


def _is_missing_tokens_error(error: Exception) -> bool:
    message = str(error)
    return (
        "No existen tokens de YouTube guardados para este usuario" in message
        or "No existe un canal de YouTube autenticado para este usuario" in message
        or "No hay tokens de YouTube guardados para este usuario" in message
    )


@router.get("/auth/start")
async def start_auth(
    redirect_uri: str | None = None,
    current_user: ClerkUser = Depends(verify_clerk_session),
):
    try:
        data = await use_case.start_auth(current_user.user_id, redirect_uri)
        return JSONResponse(status_code=200, content=data)
    except Exception as e:
        status_code, body = error_payload(e, provider="youtube")
        return JSONResponse(status_code=status_code, content=body)


@router.get("/auth/callback")
async def auth_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
):
    if error:
        return JSONResponse(status_code=400, content={"error": error})
    if not code or not state:
        return JSONResponse(
            status_code=400,
            content={"error": "Faltan code o state en el callback de YouTube"},
        )
    try:
        await use_case.complete_auth(code, state)
        return HTMLResponse(
            content="""
<!doctype html>
<html>
  <head><meta charset="utf-8"><title>YouTube conectado</title></head>
  <body>
    <script>
      try {
        if (window.opener) {
          window.opener.postMessage({ type: 'youtube-auth-complete', ok: true }, '*');
        }
      } catch (e) {}
      window.close();
    </script>
    <p>YouTube conectado correctamente. Puedes cerrar esta ventana.</p>
  </body>
</html>
            """,
            status_code=200,
        )
    except Exception as e:
        status_code, body = error_payload(e, provider="youtube")
        return JSONResponse(status_code=status_code, content=body)


@router.get("/profile")
async def get_profile(
    bot: bool = False, current_user: ClerkUser = Depends(verify_clerk_session)
):
    try:
        profile = await use_case.get_profile(current_user.user_id, bot)
        return JSONResponse(status_code=200, content={"profile": profile})
    except Exception as e:
        if _is_missing_tokens_error(e):
            return JSONResponse(
                status_code=200,
                content={
                    "profile": None,
                    "authenticated": False,
                    "message": "No hay tokens de YouTube guardados para este usuario",
                },
            )
        status_code, body = error_payload(e, provider="youtube")
        return JSONResponse(status_code=status_code, content=body)


@router.get("/tokens")
async def get_tokens(
    bot: bool = False, current_user: ClerkUser = Depends(verify_clerk_session)
):
    try:
        tokens = await use_case.get_tokens(current_user.user_id, bot)
        return JSONResponse(status_code=200, content={"tokens": tokens})
    except Exception as e:
        if _is_missing_tokens_error(e):
            return JSONResponse(
                status_code=200,
                content={
                    "tokens": None,
                    "authenticated": False,
                    "message": "No hay tokens de YouTube guardados para este usuario",
                },
            )
        status_code, body = error_payload(e, provider="youtube")
        return JSONResponse(status_code=status_code, content=body)


@router.get("/service-status")
async def service_status(current_user: ClerkUser = Depends(verify_clerk_session)):
    try:
        status = await use_case.get_service_status(current_user.user_id)
        return JSONResponse(status_code=200, content={"service": status})
    except Exception as e:
        status_code, body = error_payload(e, provider="youtube")
        return JSONResponse(status_code=status_code, content=body)


@router.get("/start")
async def start_services(current_user: ClerkUser = Depends(verify_clerk_session)):
    try:
        await use_case.start_services(current_user.user_id)
        return JSONResponse(status_code=200, content={"message": "Servicios iniciados"})
    except Exception as e:
        status_code, body = error_payload(e, provider="youtube")
        return JSONResponse(status_code=status_code, content=body)


@router.get("/stop")
async def stop_services(current_user: ClerkUser = Depends(verify_clerk_session)):
    try:
        await use_case.stop_services(current_user.user_id)
        return JSONResponse(status_code=200, content={"message": "Automatización pausada"})
    except Exception as e:
        status_code, body = error_payload(e, provider="youtube")
        return JSONResponse(status_code=status_code, content=body)


@router.get("/broadcasts")
async def list_broadcasts(
    broadcast_status: str = Query(default="active"),
    current_user: ClerkUser = Depends(verify_clerk_session),
):
    try:
        data = await use_case.list_broadcasts(current_user.user_id, broadcast_status)
        return JSONResponse(status_code=200, content={"broadcasts": data})
    except Exception as e:
        status_code, body = error_payload(e, provider="youtube")
        return JSONResponse(status_code=status_code, content=body)


@router.get("/live-chat")
async def live_chat(current_user: ClerkUser = Depends(verify_clerk_session)):
    try:
        service_status = await use_case.get_service_status(current_user.user_id)
        return JSONResponse(status_code=200, content={"service": service_status})
    except Exception as e:
        status_code, body = error_payload(e, provider="youtube")
        return JSONResponse(status_code=status_code, content=body)


@router.get("/stats")
async def stats(current_user: ClerkUser = Depends(verify_clerk_session)):
    try:
        data = await use_case.get_stats(current_user.user_id)
        return JSONResponse(status_code=200, content={"stats": data})
    except Exception as e:
        if _is_missing_tokens_error(e):
            return JSONResponse(
                status_code=200,
                content={
                    "stats": None,
                    "authenticated": False,
                    "message": "No hay tokens de YouTube guardados para este usuario",
                },
            )
        status_code, body = error_payload(e, provider="youtube")
        return JSONResponse(status_code=status_code, content=body)


@router.put("/broadcast")
async def update_broadcast(
    payload: YouTubeBroadcastUpdateModel,
    current_user: ClerkUser = Depends(verify_clerk_session),
):
    try:
        data = await use_case.update_broadcast(current_user.user_id, payload)
        return JSONResponse(status_code=200, content={"broadcast": data})
    except Exception as e:
        status_code, body = error_payload(e, provider="youtube")
        return JSONResponse(status_code=status_code, content=body)


@router.post("/chat")
async def send_chat_message(
    payload: YouTubeChatMessageModel,
    current_user: ClerkUser = Depends(verify_clerk_session),
):
    try:
        data = await use_case.send_chat_message(
            current_user.user_id,
            payload.live_chat_id,
            payload.message,
        )
        return JSONResponse(status_code=200, content={"message": data})
    except Exception as e:
        status_code, body = error_payload(e, provider="youtube")
        return JSONResponse(status_code=status_code, content=body)


@router.put("/transition")
async def transition_broadcast(
    payload: YouTubeBroadcastTransitionModel,
    current_user: ClerkUser = Depends(verify_clerk_session),
):
    try:
        data = await use_case.transition_broadcast(
            current_user.user_id,
            payload.broadcast_id,
            payload.status,
        )
        return JSONResponse(status_code=200, content={"broadcast": data})
    except Exception as e:
        status_code, body = error_payload(e, provider="youtube")
        return JSONResponse(status_code=status_code, content=body)


@router.delete("/auth")
async def logout_youtube(current_user: ClerkUser = Depends(verify_clerk_session)):
    try:
        await use_case.logout(current_user.user_id)
        return JSONResponse(status_code=200, content={"message": "Sesión de YouTube cerrada"})
    except Exception as e:
        status_code, body = error_payload(e, provider="youtube")
        return JSONResponse(status_code=status_code, content=body)
