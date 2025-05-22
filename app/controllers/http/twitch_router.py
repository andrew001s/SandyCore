from fastapi import APIRouter
from fastapi.responses import JSONResponse
from app.adapters.twitch_services import TwitchService
from app.core.use_cases.start_services_use_case import StartServicesUseCase

router = APIRouter()

@router.get("/start")
async def start_services(bot: bool = False):
    use_case = StartServicesUseCase(TwitchService())
    try:
        await use_case.execute(bot)
        return JSONResponse(status_code=200, content={"message": "Servicios iniciados"})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})