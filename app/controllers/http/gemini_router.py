from fastapi import APIRouter
from fastapi import Depends
from fastapi.responses import JSONResponse

from app.adapters.gemini_services import GeminiServices
from app.core.security.clerk import ClerkUser, verify_clerk_session
from app.core.use_cases.gemini_use_case import GeminiServicesUseCase
from app.domain.ai_errors import UNKNOWN, AIProviderError, classify_ai_error
from app.models.message_model import MessageModel

router = APIRouter(tags=["AI"])


@router.post("/gemini")
async def gemini_response_sandy_shandrew(
    message_payload: MessageModel, current_user: ClerkUser = Depends(verify_clerk_session)
):
    use_case = GeminiServicesUseCase(GeminiServices())
    try:
        response = await use_case.execute(message_payload.message, current_user.user_id)
        return JSONResponse(status_code=200, content={"message": response})
    except AIProviderError as exc:
        # El cuerpo lleva un código estable: el cliente elige el texto que ve el
        # usuario sin tener que leer el mensaje crudo del proveedor.
        print(f"[GEMINI ROUTER] {exc!r}")
        return JSONResponse(
            status_code=exc.http_status, content={"error": exc.to_payload()}
        )
    except Exception as exc:
        # Cualquier otro fallo se clasifica igual para que el contrato de la
        # respuesta de error sea siempre el mismo.
        error = classify_ai_error(exc)
        if error.code == UNKNOWN:
            print(f"[GEMINI ROUTER] error no clasificado: {exc!r}")
        return JSONResponse(
            status_code=error.http_status, content={"error": error.to_payload()}
        )
