from fastapi import APIRouter
from fastapi.responses import JSONResponse
from app.adapters.twitch_services import TwitchService
from app.core.use_cases.auth_use_case import AuthUseCase
from app.core.use_cases.start_services_use_case import StartServicesCase
from app.core.use_cases.stop_services_use_case import StopServicesUseCase
from app.models.twitch_auth_model import TwitchAuth
from app.models.tokens_model import TokenModel
from app.core.use_cases.get_profile import GetProfileUseCase
from app.core.use_cases.get_tokens_use_case import GetTokensUseCase
from app.core.use_cases.save_tokens_use_case import SaveTokensUseCase

router = APIRouter()
use_case_auth = AuthUseCase(TwitchService())
use_case_start = StartServicesCase(TwitchService())
use_case_stop = StopServicesUseCase(TwitchService())
use_case_tokens = GetTokensUseCase(TwitchService())
use_case_save_tokens = (SaveTokensUseCase(TwitchService()))

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
    
@router.get("/profile")
async def get_profile(bot: bool = False):
    try:
        use_case = GetProfileUseCase(TwitchService())
        user = await use_case.execute(bot)
        return JSONResponse(status_code=200, content={"profile": user})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)}) 

@router.get("/tokens")
async def get_tokens(bot: bool = False):
    try:
        tokens = await use_case_tokens.execute(bot)
        return JSONResponse(status_code=200, content={"tokens": tokens})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
    
@router.put("/tokens")
async def save_tokens(tokens: TokenModel, bot: bool = False):
    try:
        await use_case_save_tokens.execute(bot, tokens.token, tokens.refresh_token)
        return JSONResponse(status_code=200, content={"message": "Tokens guardados exitosamente"})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
    
