from fastapi import APIRouter

from app.api.dependencies import HealthServiceDep
from app.schemas.common import HealthOut

router = APIRouter(tags=["Состояние"])


@router.get("/health/live", response_model=HealthOut)
async def live():
    return HealthOut()


@router.get("/health/ready", response_model=HealthOut)
async def ready(service: HealthServiceDep):
    await service.ready()
    return HealthOut()
