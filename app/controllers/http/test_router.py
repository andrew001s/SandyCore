from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.services.application.status_service import get_root_message

router = APIRouter()


@router.get("/")
def read_root():
    return JSONResponse(status_code=200, content={"message": get_root_message()})
