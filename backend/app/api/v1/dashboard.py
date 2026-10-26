"""Dashboard summary and audit events."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.db.session import get_db
from app.schemas.inventory import DashboardSummary
from app.services import ipam_service

router = APIRouter()


@router.get("/dashboard/summary", response_model=DashboardSummary, summary="Dashboard metrics")
def dashboard_summary(db: Session = Depends(get_db)) -> DashboardSummary:
    return ipam_service.dashboard_summary(db)


@router.get("/audit-events", summary="List audit events (admin)")
def audit_events(
    _: object = Depends(require_admin),
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    resource_type: str | None = Query(None),
    action: str | None = Query(None),
) -> dict:
    return ipam_service.list_audit_events(
        db, page=page, page_size=page_size, resource_type=resource_type, action=action
    )
