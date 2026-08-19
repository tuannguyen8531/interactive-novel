"""Alpha feedback endpoint."""

from fastapi import APIRouter, Depends

from src.api.container import ApplicationContainer
from src.api.dependencies import get_services
from src.api.schemas import FeedbackRequest

router = APIRouter(tags=["feedback"])
_services_dependency = Depends(get_services)


@router.post("/feedback", status_code=201)
async def submit_feedback(payload: FeedbackRequest, services: ApplicationContainer = _services_dependency):
    record = services.feedback.submit(**payload.model_dump())
    return record.as_dict()


__all__ = ["router"]
