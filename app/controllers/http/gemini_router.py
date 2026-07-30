from fastapi import APIRouter
from fastapi import Depends
from fastapi.responses import JSONResponse

from app.adapters.gemini_services import GeminiServices
from app.core.security.clerk import ClerkUser, verify_clerk_session
from app.core.use_cases.gemini_use_case import GeminiServicesUseCase
from app.models.message_model import MessageModel

router = APIRouter(tags=["AI"])


@router.post("/gemini")
async def gemini_response_sandy_shandrew(
    message_payload: MessageModel, current_user: ClerkUser = Depends(verify_clerk_session)
):
    use_case = GeminiServicesUseCase(GeminiServices())
    try:
        response = await use_case.execute(message_payload.message)
        return JSONResponse(status_code=200, content={"message": response})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
