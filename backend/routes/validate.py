from fastapi import APIRouter, Depends

from dependencies import get_current_user
from schemas import ProjectSchema, UserPublic, ValidationReport
from services.validator import build_validation_report


router = APIRouter()


@router.post("/", response_model=ValidationReport)
async def validate_project(
    project: ProjectSchema,
    user: UserPublic = Depends(get_current_user),
) -> ValidationReport:
    _ = user
    return build_validation_report(project)
