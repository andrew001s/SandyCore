import resource
import sys
import threading
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.services.application.status_service import get_root_message

router = APIRouter(tags=["Health"])


def _get_rss_mb() -> float:
    try:
        with open("/proc/self/status", "r") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    parts = line.split()
                    return round(float(parts[1]) / 1024.0, 2)
    except Exception:
        pass
    try:
        rusage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if sys.platform == "darwin":
            return round(rusage / (1024.0 * 1024.0), 2)
        return round(rusage / 1024.0, 2)
    except Exception:
        return 0.0


@router.get("/")
def read_root():
    return JSONResponse(status_code=200, content={"message": get_root_message()})


@router.get("/health/memory")
def read_memory_stats():
    from app.services.client_settings import settings_cache_size
    from app.services.gemini import ai_client_cache_size

    return JSONResponse(
        status_code=200,
        content={
            "rss_mb": _get_rss_mb(),
            "threads_active": threading.active_count(),
            "settings_cached_users": settings_cache_size(),
            "ai_cached_clients": ai_client_cache_size(),
            "python_version": sys.version.split()[0],
        },
    )

