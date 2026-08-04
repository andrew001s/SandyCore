import logging

from fastapi import FastAPI

from app.core.config import config

logger = logging.getLogger(__name__)

try:
    import rollbar
    from rollbar.contrib.fastapi import add_to as rollbar_add_to
except ImportError:  # pragma: no cover - optional until dependencies are installed
    rollbar = None
    rollbar_add_to = None

_ROLLBAR_SCRUB_FIELDS = [
    "password",
    "secret",
    "token",
    "api_key",
    "access_token",
    "authorization",
    "cookie",
    "csrf_token",
]


def configure_rollbar(app: FastAPI) -> bool:
    if rollbar is None or rollbar_add_to is None:
        logger.warning("Rollbar is not installed; skipping error reporting integration.")
        return False

    if not config.ROLLBAR_ACCESS_TOKEN:
        logger.info("Rollbar disabled because ROLLBAR_ACCESS_TOKEN is not configured.")
        return False

    rollbar.init(
        access_token=config.ROLLBAR_ACCESS_TOKEN,
        environment=config.ROLLBAR_ENVIRONMENT,
        code_version=config.ROLLBAR_CODE_VERSION,
        scrub_fields=_ROLLBAR_SCRUB_FIELDS,
    )
    rollbar_add_to(app)
    logger.info("Rollbar enabled for environment %s.", config.ROLLBAR_ENVIRONMENT)
    return True
