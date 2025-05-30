from fastapi import APIRouter
from fastapi.responses import JSONResponse
from app.adapters.twitch_services import TwitchService
from app.core.use_cases.auth_use_case import AuthUseCase
from app.core.use_cases.start_services_use_case import StartServicesCase
from app.core.use_cases.stop_services_use_case import StopServicesUseCase
from app.models.twitch_auth_model import TwitchAuth

router = APIRouter()
use_case_auth = AuthUseCase(TwitchService())
use_case_start = StartServicesCase(TwitchService())
use_case_stop = StopServicesUseCase(TwitchService())

@router.post("/auth")
async def authenticate_twitch_user(message: TwitchAuth):
    try:
        if message.bot:
            await use_case_auth.execute( message.token, message.refresh_token,message.bot,)
        else:
            await use_case_auth.execute(message.token, message.refresh_token,message.bot)
        return JSONResponse(status_code=200, content={"message": "Autenticación exitosa"})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@router.get("/start")
async def start_services(bot: bool = False):
    
    try:
        if bot:
            await use_case_stop.execute()
            await use_case_start.execute(bot)
        else:
            await use_case_start.execute(bot)
        return JSONResponse(status_code=200, content={"message": "Servicios iniciados"})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@router.get("/stop")
async def stop_services(bot: bool = False):
    try:
        if bot:
            await use_case_stop.execute()
            await use_case_start.execute()
        else:
            await use_case_stop.execute()
        return JSONResponse(status_code=200, content={"message": "Servicios detenidos"})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})