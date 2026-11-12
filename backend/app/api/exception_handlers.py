import logging

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

from app.core.errors import DomainError

logger = logging.getLogger(__name__)


async def domain_error(_: Request, error: DomainError):
    return JSONResponse(
        status_code=error.status,
        content={
            "error": {
                "code": error.code,
                "message": error.message,
                "context": error.context,
            }
        },
    )


async def validation_error(_: Request, error: RequestValidationError):
    fields = [
        {"field": ".".join(map(str, item["loc"])), "message": item["msg"]}
        for item in error.errors()
    ]
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "validation_error",
                "message": "Проверьте поля запроса.",
                "context": {"fields": fields},
            }
        },
    )


async def database_error(_: Request, error: OperationalError | TimeoutError | OSError):
    logger.error("Database operation failed", exc_info=error)
    return JSONResponse(
        status_code=503,
        content={
            "error": {
                "code": "database_unavailable",
                "message": "База данных временно недоступна. "
                "Перед повторной отправкой проверьте список операций.",
                "context": {},
            }
        },
    )
