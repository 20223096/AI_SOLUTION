from fastapi import APIRouter, Depends, Request

from app.core.config import get_settings
from app.models.resident_notices import (
    NoticeErrorResponse,
    ResidentNoticeConfirmRequest,
    ResidentNoticeDraftCreateRequest,
    ResidentNoticeDraftResponse,
    ResidentNoticeDraftUpdateRequest,
    ResidentPublicResponse,
)
from app.services.resident_notices import JsonNoticeRepository, NoticeWorkflowError, ResidentNoticeService
from app.services.recommendation_snapshots import RecommendationSnapshotRepository

router = APIRouter(tags=["resident-notices"])
ERRORS = {
    403: {"model": NoticeErrorResponse, "description": "담당자 API 접근 제한"},
    404: {"model": NoticeErrorResponse, "description": "초안 없음"},
    409: {"model": NoticeErrorResponse, "description": "상태 또는 버전 충돌"},
    422: {"model": NoticeErrorResponse, "description": "공개 필수 필드 결측"},
}


def notice_service() -> ResidentNoticeService:
    settings = get_settings()
    return ResidentNoticeService(
        JsonNoticeRepository(settings.resident_notice_store_path),
        snapshot_repository=RecommendationSnapshotRepository(settings.recommendation_snapshot_store_path),
    )


def staff_only(request: Request) -> None:
    host = request.client.host if request.client else ""
    if host not in get_settings().staff_api_allowed_hosts:
        raise NoticeWorkflowError("forbidden", "staff API is limited to loopback or an explicitly allowed demo host", 403)


@router.post("/api/staff/resident-notices/drafts", response_model=ResidentNoticeDraftResponse, responses=ERRORS, dependencies=[Depends(staff_only)])
def create_draft(request: ResidentNoticeDraftCreateRequest):
    return notice_service().create(request)


@router.get("/api/staff/resident-notices/drafts/{project_id}", response_model=ResidentNoticeDraftResponse, responses=ERRORS, dependencies=[Depends(staff_only)])
def get_draft(project_id: str):
    return notice_service().get_draft(project_id)


@router.put("/api/staff/resident-notices/drafts/{project_id}", response_model=ResidentNoticeDraftResponse, responses=ERRORS, dependencies=[Depends(staff_only)])
def update_draft(project_id: str, request: ResidentNoticeDraftUpdateRequest):
    return notice_service().update(project_id, request)


@router.post("/api/staff/resident-notices/drafts/{project_id}/confirm", response_model=ResidentNoticeDraftResponse, responses=ERRORS, dependencies=[Depends(staff_only)])
def confirm_draft(project_id: str, request: ResidentNoticeConfirmRequest):
    return notice_service().confirm(project_id, request)


@router.get("/api/public/construction/{project_id}/resident-notice", response_model=ResidentPublicResponse)
def public_resident_notice(project_id: str):
    return notice_service().public_read(project_id)
