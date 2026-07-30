from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.core.security.clerk import ClerkUser, verify_clerk_session
from app.models.client_settings_model import ClientSettingsModel
from app.services.client_settings import load_effective_settings, save_effective_settings

router = APIRouter(tags=["Settings"])


@router.get("/settings")
async def get_settings(current_user: ClerkUser = Depends(verify_clerk_session)):
    try:
        settings = await load_effective_settings(current_user.user_id)
        return JSONResponse(status_code=200, content={"settings": settings})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.put("/settings")
async def update_settings(
    payload: ClientSettingsModel, current_user: ClerkUser = Depends(verify_clerk_session)
):
    try:
        settings = await save_effective_settings(
            payload.model_dump(exclude_none=True), current_user.user_id
        )
        return JSONResponse(status_code=200, content={"settings": settings})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
