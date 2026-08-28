from fastapi import Depends, FastAPI, Query, WebSocket
from starlette.websockets import WebSocketState
from fastapi.responses import JSONResponse

from app.config.cors import configure_cors
from app.core.security.clerk import ClerkUser, verify_clerk_session
from app.core.rollbar import configure_rollbar
from app.controllers.http.gemini_router import router as gemini_router
from app.controllers.http.kick_router import router as kick_router
from app.controllers.http.kick_webhook_router import router as kick_webhook_router
from app.controllers.http.youtube_router import router as youtube_router
from app.controllers.http.realtime_router import router as realtime_router
from app.controllers.http.settings_router import router as settings_router
from app.controllers.http.test_router import router as test_router
from app.controllers.http.twitch_router import router as twitch_router
from app.controllers.websocket.websocket_server import handle_websocket
from app.domain.errors import error_payload

tags_metadata = [
    {"name": "Health", "description": "Verificación de estado de la API."},
    {"name": "Twitch", "description": "Autenticación, tokens y control de servicios de Twitch."},
    {"name": "Kick", "description": "Autenticación, tokens y control de servicios de Kick."},
    {"name": "YouTube", "description": "Autenticación OAuth de Google, chat y control básico de transmisiones de YouTube."},
    {"name": "Settings", "description": "Configuración por usuario guardada en SQLite."},
    {"name": "AI", "description": "Consultas a la capa de IA."},
]

app = FastAPI(
    title="Sandy Core IA API",
    description="API para autenticación con Clerk, persistencia en SQLite y control de Twitch/IA.",
    version="2.5.0",
    openapi_tags=tags_metadata,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)
configure_rollbar(app)
configure_cors(app)


app.include_router(test_router)
app.include_router(twitch_router)
app.include_router(kick_router)
app.include_router(kick_webhook_router)
app.include_router(youtube_router)
app.include_router(settings_router)
app.include_router(gemini_router)
app.include_router(realtime_router)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str | None = Query(default=None)):
    try:
        await handle_websocket(websocket, token)
    except Exception as e:
        print(f"WebSocket error: {e}")
        if websocket.client_state != WebSocketState.DISCONNECTED:
            await websocket.close()


@app.get("/get-profile", deprecated=True)
async def get_profile(
    bot: bool = False, current_user: ClerkUser = Depends(verify_clerk_session)
):
    """Obsoleto: usa /profile. Se mantiene solo por compatibilidad."""
    try:
        from app.adapters.twitch_services import TwitchService

        profile = await TwitchService().get_profile(current_user.user_id, bot)
        return JSONResponse(status_code=200, content={"profile": profile})
    except Exception as e:
        status_code, body = error_payload(e, provider="twitch")
        return JSONResponse(status_code=status_code, content=body)
